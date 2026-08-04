"""GUI 백엔드 Api — 헤드리스 계약 검증."""
import json
import zipfile

import pytest

from tests.test_inject import make_core_game, put_mod


def make_api(tmp_path):
    from app import Api
    store = tmp_path / "store"
    state = tmp_path / "state.json"
    return Api(store, state), store, state


def test_recent_round_trip(tmp_path):
    api, store, state = make_api(tmp_path)
    assert api.recent() == {"ok": True, "paths": []}

    r = api.remember(str(tmp_path / "gameA"))
    assert r["ok"] and r["paths"] == [str(tmp_path / "gameA")]

    api.remember(str(tmp_path / "gameB"))
    got = api.recent()
    assert got["paths"] == [str(tmp_path / "gameB"), str(tmp_path / "gameA")]

    # 다시 기억하면 맨 앞으로, 중복 없음
    api.remember(str(tmp_path / "gameA"))
    assert api.recent()["paths"] == [str(tmp_path / "gameA"), str(tmp_path / "gameB")]


def test_pick_folder_no_window(tmp_path):
    api, _, _ = make_api(tmp_path)
    assert api.pick_folder() == {"ok": False, "error": "no-window"}


def test_pick_zip_no_window(tmp_path):
    api, _, _ = make_api(tmp_path)
    assert api.pick_zip() == {"ok": False, "error": "no-window"}


def test_game_status(tmp_path):
    api, store, state = make_api(tmp_path)
    game = make_core_game(tmp_path)

    status = api.game_status(game)
    assert status["ok"] is True
    assert status["title"] == "Old Game"
    assert status["installed"] == []  # 묶음도 주입도 없는 첫 상태 (NoBundle → [])
    assert status["has_manifest"] is False


def test_diagnose_requires_manifest(tmp_path):
    api, store, state = make_api(tmp_path)
    game = make_core_game(tmp_path)

    r = api.diagnose(game)
    assert r == {"ok": False, "error": r["error"]}
    assert "매니페스트가 없어요" in r["error"]


def test_diagnose_clean_and_foreign(tmp_path):
    from modkit import manifest as manifest_mod
    api, store, state = make_api(tmp_path)
    game = make_core_game(tmp_path)
    made = manifest_mod.capture(game, game="Old Game")
    manifest_mod.save(made, game / "manifest.json")

    r = api.diagnose(game)
    assert r["ok"] is True
    assert r["foreign"] == [] and r["missing"] == [] and r["known"] == []
    assert r["backups"] == 0
    assert r["intact"] >= 1

    (game / "oldpatch.txt").write_bytes(b"trace")
    r = api.diagnose(game)
    assert r["ok"] is True
    assert r["foreign"] == ["oldpatch.txt"]


def test_quarantine_foreign_then_clean(tmp_path):
    from modkit import manifest as manifest_mod
    api, store, state = make_api(tmp_path)
    game = make_core_game(tmp_path)
    made = manifest_mod.capture(game, game="Old Game")
    manifest_mod.save(made, game / "manifest.json")
    (game / "oldpatch.txt").write_bytes(b"trace")

    r = api.quarantine_foreign(game)
    assert r["ok"] is True
    assert r["moved"] == 1
    assert not (game / "oldpatch.txt").exists()

    again = api.diagnose(game)
    assert again["foreign"] == []

    # 로그가 남는다
    log = (game / "modkit-log.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(log) == 1
    entry = json.loads(log[0])
    assert entry["action"] == "quarantine_foreign"


def test_apply_and_remove_mod_round_trip(tmp_path):
    api, store, state = make_api(tmp_path)
    game = make_core_game(tmp_path)
    put_mod(store, "My Mod")

    got = api.mods(game)
    assert got["ok"] is True
    assert got["installed"] == []
    assert got["available"] == [{"name": "My Mod", "description": "", "summary": "", "installed": False, "partial": False}]

    applied = api.apply_mod(game, "My Mod")
    assert applied == {"ok": True, "did": "설치됨", "warnings": []}

    got = api.mods(game)
    assert got["available"][0]["installed"] is True

    removed = api.remove_mod(game, "My Mod")
    assert removed["ok"] is True
    assert removed["did"] == "제거됨"

    log = (game / "modkit-log.jsonl").read_text(encoding="utf-8").strip().splitlines()
    actions = [json.loads(line)["action"] for line in log]
    assert actions == ["apply_mod", "remove_mod"]


def test_apply_mod_blocked(tmp_path):
    api, store, state = make_api(tmp_path)
    game = make_core_game(tmp_path)
    put_mod(store, "Needs Other", extra={"requires": ["Other"]})

    r = api.apply_mod(game, "Needs Other")
    assert r["ok"] is False
    assert "blocked" in r
    assert any("Other" in why for why in r["blocked"])


def test_import_zip_installs_mod(tmp_path):
    api, store, state = make_api(tmp_path)
    zpath = tmp_path / "mod.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("Zipped Mod/mod.json", json.dumps(
            {"name": "Zipped Mod", "game": "Old Game", "scripts": []}))
        zf.writestr("Zipped Mod/001_Zipped.rb", "def zipped\nend\n")

    r = api.import_zip(zpath)
    assert r == {"ok": True, "name": "Zipped Mod"}

    from modkit import modstore
    mod = modstore.read_mod(store, "Zipped Mod")
    assert mod.game == "Old Game"
    assert (mod.folder / "001_Zipped.rb").is_file()


def test_import_zip_rejects_path_escape(tmp_path):
    api, store, state = make_api(tmp_path)
    zpath = tmp_path / "evil.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("mod.json", json.dumps({"name": "Evil", "game": "Old Game", "scripts": []}))
        zf.writestr("../escape.rb", "haha\n")

    r = api.import_zip(zpath)
    assert r["ok"] is False


def test_diagnose_reports_untracked_count(tmp_path):
    """부분 매니페스트에서 목록 밖 파일은 개수만 보고되고 격리 대상에서 빠진다."""
    from modkit import manifest as manifest_mod
    api, store, state = make_api(tmp_path)
    game = make_core_game(tmp_path)
    stage = tmp_path / "stage"
    (stage / "Data").mkdir(parents=True)
    (stage / "Data" / "Scripts.rxdata").write_bytes(
        (game / "Data" / "Scripts.rxdata").read_bytes())
    made = manifest_mod.capture(stage, game="Old Game", scope="partial")
    manifest_mod.save(made, game / "manifest.json")

    r = api.diagnose(game)
    assert r["ok"] is True
    assert r["foreign"] == []
    assert r["untracked"] >= 1

    moved = api.quarantine_foreign(game)
    assert moved == {"ok": True, "moved": 0, "box": ""}


def test_game_status_flags_non_game_folder(tmp_path):
    from app import Api
    api = Api(tmp_path / "store", tmp_path / "state.json")
    (tmp_path / "notgame").mkdir()
    s = api.game_status(str(tmp_path / "notgame"))
    assert s["ok"] and s["looks_like_game"] is False


def test_import_zip_without_card_adopts(tmp_path):
    """카드 없는 zip(야생 표준형)은 게임 폴더 기준으로 입양된다."""
    api, store, state = make_api(tmp_path)
    game = make_core_game(tmp_path)
    (game / "Graphics").mkdir()
    (game / "Graphics" / "look.png").write_bytes(b"old")
    zpath = tmp_path / "wildskin.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("Graphics/look.png", b"new")

    r = api.import_zip(zpath, str(game))
    assert r["ok"] and r["adopted"] and r["name"] == "wildskin"

    from modkit import modstore
    assert modstore.read_mod(store, "wildskin").game == "Old Game"


def test_import_zip_without_card_and_game_says_why(tmp_path):
    api, store, state = make_api(tmp_path)
    zpath = tmp_path / "wild.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("Graphics/look.png", b"new")
    r = api.import_zip(zpath)
    assert r["ok"] is False and "게임 폴더" in r["error"]


def test_import_folder_with_card_copies(tmp_path):
    api, store, state = make_api(tmp_path)
    src = tmp_path / "Ready Mod"
    src.mkdir()
    (src / "mod.json").write_text(json.dumps(
        {"name": "Ready Mod", "game": "Old Game", "scripts": []}), encoding="utf-8")
    (src / "001_Ready.rb").write_text("def ready\nend\n", encoding="utf-8")

    r = api.import_folder(str(src))
    assert r == {"ok": True, "name": "Ready Mod"}
    from modkit import modstore
    assert (modstore.read_mod(store, "Ready Mod").folder / "001_Ready.rb").is_file()


def test_import_folder_without_card_adopts(tmp_path):
    api, store, state = make_api(tmp_path)
    game = make_core_game(tmp_path)
    (game / "Graphics").mkdir()
    (game / "Graphics" / "look.png").write_bytes(b"old")
    src = tmp_path / "wildfolder"
    (src / "Graphics").mkdir(parents=True)
    (src / "Graphics" / "look.png").write_bytes(b"new")

    r = api.import_folder(str(src), str(game))
    assert r["ok"] and r["adopted"] and r["name"] == "wildfolder"


def test_game_status_carries_identity(tmp_path):
    api, store, state = make_api(tmp_path)
    game = make_core_game(tmp_path)      # 제목 "Old Game" — 아는 게임이 아니다
    r = api.game_status(str(game))
    assert r["ok"] and r["label"] == "Old Game" and r["known"] is False


def test_mods_marks_asset_mod_installed(tmp_path):
    """에셋 전용 모드는 묶음·주입 섹션에 이름이 안 남는다 — 설치 표시가 파일로 잡혀야
    설치 버튼이 '제거'로 바뀐다(2026-08-04 실기 제보)."""
    api, store, state = make_api(tmp_path)
    game = make_core_game(tmp_path)
    (game / "Graphics").mkdir()
    (game / "Graphics" / "look.png").write_bytes(b"old")
    folder = store / "Old Game" / "Skin"
    folder.mkdir(parents=True)
    (folder / "look.png").write_bytes(b"new-look")
    (folder / "mod.json").write_text(json.dumps(
        {"name": "Skin", "game": "Old Game", "scripts": [],
         "assets": [{"file": "look.png", "install_to": "Graphics/look.png"}]}),
        encoding="utf-8")

    before = api.mods(str(game))
    assert before["ok"] and before["available"][0]["installed"] is False

    assert api.apply_mod(str(game), "Skin")["ok"]
    after = api.mods(str(game))
    assert after["available"][0]["installed"] is True


def test_preview_apply_reports_overlap_before_install(tmp_path):
    from tests.test_apply_check import put_two_overlapping_asset_mods
    api, store, state = make_api(tmp_path)
    game, store2 = put_two_overlapping_asset_mods(tmp_path)
    api.store_dir = store2
    from modkit import modstore
    modstore.apply(store2, "Skin A", game)

    p = api.preview_apply(str(game), "Skin B")
    assert p["ok"] and any("Skin A" in w for w in p["warnings"])
    # 미리보기는 아무것도 설치하지 않는다
    assert (game / "Graphics" / "look.png").read_bytes() == b"aaaa"


def test_edit_mod_renames_and_reassigns(tmp_path):
    api, store, state = make_api(tmp_path)
    folder = store / "Old Game" / "Draft"
    folder.mkdir(parents=True)
    (folder / "mod.json").write_text(json.dumps(
        {"name": "Draft", "game": "Old Game", "scripts": [],
         "assets": [{"file": "a.png", "install_to": "Graphics/a.png"}]}), encoding="utf-8")
    (folder / "a.png").write_bytes(b"x")

    r = api.edit_mod("Draft", new_name="한글패치 v5.1", new_game="New Game")
    assert r["ok"] and r["name"] == "한글패치 v5.1" and r["game"] == "New Game"

    from modkit import modstore
    mod = modstore.read_mod(store, "한글패치 v5.1")
    assert mod.game == "New Game"
    assert mod.folder.parent.name == "New Game"


def test_delete_mod_moves_to_trash_and_uninstalls(tmp_path):
    """삭제는 파괴가 아니다 — 게임에서 걷어낸 뒤 보관소 안 _trash로 옮긴다."""
    api, store, state = make_api(tmp_path)
    game = make_core_game(tmp_path)
    put_mod(store, "Doomed")
    from modkit import modstore
    modstore.apply(store, "Doomed", game)
    assert modstore.installed(game) == ["Doomed"]

    r = api.delete_mod("Doomed", str(game))
    assert r["ok"]
    assert modstore.installed(game) == []                      # 게임에서 걷힘
    with pytest.raises(modstore.ModMissing):
        modstore.read_mod(store, "Doomed")                     # 서랍에서 사라짐
    assert list((store / "_trash").rglob("mod.json"))          # 실물은 _trash에 남는다


def test_summary_flows_to_shelf_list(tmp_path):
    """긴 설명이 목록을 난잡하게 만든다(실기) — 한 줄 요약 자리가 따로 있다."""
    api, store, state = make_api(tmp_path)
    game = make_core_game(tmp_path)
    put_mod(store, "Wordy", extra={"summary": "한 줄 요약이에요",
                                   "description": "아주 " * 100 + "긴 설명"})
    r = api.mods(str(game))
    assert r["available"][0]["summary"] == "한 줄 요약이에요"

    r = api.edit_mod("Wordy", new_summary="더 짧게")
    assert r["ok"]
    assert api.mods(str(game))["available"][0]["summary"] == "더 짧게"


def test_apply_mod_reports_mismatch_for_force_choice(tmp_path):
    """판 불일치·귀속 불일치는 죽은 끝이 아니라 강행 선택지로 돌아온다."""
    import zlib
    from tests.test_apply_check import put_asset_mod
    api, store, state = make_api(tmp_path)
    game = make_core_game(tmp_path)
    (game / "Graphics").mkdir()
    (game / "Graphics" / "look.png").write_bytes(b"v2-look")
    put_asset_mod(store, "Old Game", crc=zlib.crc32(b"v1-look"))

    r = api.apply_mod(str(game), "Skin")
    assert r["ok"] is False and r.get("mismatch")

    r = api.apply_mod(str(game), "Skin", force=True)
    assert r["ok"] is True


def test_find_game_exe(tmp_path):
    from app import _find_game_exe
    game = tmp_path / "g"
    game.mkdir()
    assert _find_game_exe(game) is None
    (game / "Reminiscencia.exe").write_bytes(b"x")
    assert _find_game_exe(game).name == "Reminiscencia.exe"   # Game.exe 없으면 유일한 exe
    (game / "Game.exe").write_bytes(b"x")
    assert _find_game_exe(game).name == "Game.exe"            # 있으면 관례가 우선
