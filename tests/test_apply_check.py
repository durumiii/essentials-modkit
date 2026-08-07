"""얹기 전 호환 검사 — 판정기(modfit.check)가 얹기 흐름에 실제로 물려 있는가.

검사기는 완성돼 있는데 apply가 안 불러서, 유저가 깨질 모드를 그냥 얹을 수
있었다(2026-08-04 점검). 판정이 `changed`면 막고, force면 경고로 내려 얹는다.
`fits`·`unknown`은 지금까지처럼 조용히 지나간다.
"""
import json
import zlib

import pytest

from modkit import modstore
from tests.test_inject import make_core_game


def put_asset_mod(store, game, crc):
    folder = store / game / "Skin"
    folder.mkdir(parents=True)
    (folder / "look.png").write_bytes(b"new-look")
    card = {"name": "Skin", "game": game, "scripts": [],
            "assets": [{"file": "look.png", "install_to": "Graphics/look.png",
                        "replaces_crc": crc}]}
    (folder / "mod.json").write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    return folder


def test_apply_blocks_when_original_changed(tmp_path):
    game = make_core_game(tmp_path)
    (game / "Graphics").mkdir()
    (game / "Graphics" / "look.png").write_bytes(b"v2-look")   # 게임이 판 올림으로 바꾼 원본
    store = tmp_path / "store"
    put_asset_mod(store, "Old Game", crc=zlib.crc32(b"v1-look"))  # 모드가 아는 원본은 v1

    with pytest.raises(modstore.BaseChanged):
        modstore.apply(store, "Skin", game)
    assert not (game / "Graphics" / "look.png.orig").exists()   # 아무것도 안 썼다


def test_apply_force_downgrades_to_warning(tmp_path):
    game = make_core_game(tmp_path)
    (game / "Graphics").mkdir()
    (game / "Graphics" / "look.png").write_bytes(b"v2-look")
    store = tmp_path / "store"
    put_asset_mod(store, "Old Game", crc=zlib.crc32(b"v1-look"))

    done = modstore.apply(store, "Skin", game, force=True)
    assert any("강행" in w for w in done["warnings"])
    assert (game / "Graphics" / "look.png").read_bytes() == b"new-look"


def test_apply_passes_when_original_matches(tmp_path):
    game = make_core_game(tmp_path)
    (game / "Graphics").mkdir()
    (game / "Graphics" / "look.png").write_bytes(b"v1-look")
    store = tmp_path / "store"
    put_asset_mod(store, "Old Game", crc=zlib.crc32(b"v1-look"))

    done = modstore.apply(store, "Skin", game)
    assert done["did"] in ("설치됨", "덮어씀")


def put_two_overlapping_asset_mods(tmp_path):
    import json
    from tests.test_inject import make_core_game
    game = make_core_game(tmp_path)
    (game / "Graphics").mkdir()
    (game / "Graphics" / "look.png").write_bytes(b"original")
    store = tmp_path / "store"
    for name, body in (("Skin A", b"aaaa"), ("Skin B", b"bbbb")):
        folder = store / "Old Game" / name
        folder.mkdir(parents=True)
        (folder / "look.png").write_bytes(body)
        (folder / "mod.json").write_text(json.dumps(
            {"name": name, "game": "Old Game", "scripts": [],
             "assets": [{"file": "look.png", "install_to": "Graphics/look.png"}],
             "touches": {"methods": [], "files": ["Graphics/look.png"]}}),
            encoding="utf-8")
    return game, store


def test_present_counts_applied_asset_mods(tmp_path):
    game, store = put_two_overlapping_asset_mods(tmp_path)
    assert modstore.present(store, game, game="Old Game") == []
    modstore.apply(store, "Skin A", game)
    assert modstore.present(store, game, game="Old Game") == ["Skin A"]


def test_apply_warns_on_asset_overlap(tmp_path):
    """에셋 모드끼리의 겹침도 설치 전에 잡힌다 — 실기에서 GUI·한글패치가 같은 그림을
    말없이 덮어쓰던 것(2026-08-04). 묶음·주입에 이름이 안 남아 겹침 상대에서 빠져 있었다."""
    game, store = put_two_overlapping_asset_mods(tmp_path)
    modstore.apply(store, "Skin A", game)
    done = modstore.apply(store, "Skin B", game)
    assert any("Graphics/look.png" in w and "Skin A" in w for w in done["warnings"])


def test_remove_partial_state_guides_instead_of_lying(tmp_path):
    """반쪽 상태(손패치 41/89류)의 제거는 사유+출구를 말한다 — '설치돼 있지 않다'는 거짓말 금지.

    2026-08-04 아닐 실기: 화면은 부분 일치를 '설치됨'으로 보여 주고, 제거는 전량
    일치를 요구해 '설치돼 있지 않아요'로 거부 — 같은 상태에 두 잣대였다. 백업이
    없어 소유를 모르니 안전하게 못 빼는 건 맞고, 출구(설치→정식화→제거)를 안내한다.
    """
    import json
    from tests.test_inject import make_core_game
    game = make_core_game(tmp_path)
    (game / "Graphics").mkdir()
    (game / "Graphics" / "a.png").write_bytes(b"kr")   # 손으로 넣은 절반
    store = tmp_path / "store"
    folder = store / "Old Game" / "KR"
    folder.mkdir(parents=True)
    (folder / "a.png").write_bytes(b"kr")
    (folder / "b.png").write_bytes(b"kr2")             # 이건 게임에 없음 → 1/2 부분
    (folder / "mod.json").write_text(json.dumps(
        {"name": "KR", "game": "Old Game", "scripts": [],
         "assets": [{"file": "a.png", "install_to": "Graphics/a.png"},
                    {"file": "b.png", "install_to": "Graphics/b.png"}]}), encoding="utf-8")

    with pytest.raises(modstore.ModMissing) as no:
        modstore.remove("KR", game, store=store)
    said = str(no.value)
    assert "1/2" in said and "설치" in said            # 비율과 출구 안내가 문장에 있다
    assert "설치돼 있지 않아요" not in said            # 거짓말은 하지 않는다


def test_remove_partial_with_backups_proceeds(tmp_path):
    """modkit이 설치한(백업 있는) 모드는 다른 모드가 일부를 덮었어도 제거된다.

    2026-08-04 실기: KR 설치(백업 완비) → GUI가 3장 덮음 → KR 제거가 '반쪽'
    거부. 반쪽 게이트는 백업 없는 손패치를 위한 것 — 백업이 어긋난 자리를
    전부 덮으면 되돌릴 길이 있으니 막을 이유가 없다.
    """
    game, store = put_two_overlapping_asset_mods(tmp_path)
    modstore.apply(store, "Skin A", game)          # 백업(.orig) 생성
    modstore.apply(store, "Skin B", game, force=True)  # A의 자리를 덮음 → A는 0/1
    done = modstore.remove("Skin A", game, store=store)
    assert done["did"] == "제거됨"


def test_layered_under_counts_as_applied(tmp_path):
    """층 아래로 밀려난 모드는 '부분'이 아니라 설치됨이다 — 판이 보관돼 있으니까.

    2026-08-04 실기: KR 위에 GUI를 얹자 KR이 179/182 부분으로 표시돼 "한글패치가
    깨졌나"로 읽혔다(pokemon-z 물음 1). 어긋난 자리의 내 판이 층 보관본(.pre)에
    온전하면 설치로 센다 — 선언 추측이 아니라 보관 실물 대조.
    """
    from modkit import modassets
    game, store = put_two_overlapping_asset_mods(tmp_path)
    a = modstore.read_mod(store, "Skin A")
    modstore.apply(store, "Skin A", game)
    modstore.apply(store, "Skin B", game, force=True)   # A판이 .pre-Skin B로 보관됨
    assert modassets.applied_ratio(a, game) == (1, 1)
    assert modassets.applied(a, game) is True


def test_layered_remove_restores_middle_layer(tmp_path):
    """위층을 빼면 아래층으로 돌아온다 — 순정으로 건너뛰지 않는다.

    2026-08-04 실기: KR(층1) 위에 GUI(층2)를 얹었다 빼면, 백업(.orig=순정)만
    있어서 겹친 그림이 KR판이 아니라 순정으로 떨어졌다. 얹을 때 밀려나는 판을
    보관해 두면 위층 제거가 아래층을 되살린다.
    """
    game, store = put_two_overlapping_asset_mods(tmp_path)
    target = game / "Graphics" / "look.png"

    modstore.apply(store, "Skin A", game)                # 층1 — .orig(원본) 생성
    modstore.apply(store, "Skin B", game, force=True)    # 층2 — A판이 밀려남
    assert target.read_bytes() == b"bbbb"

    modstore.remove("Skin B", game, store=store)
    assert target.read_bytes() == b"aaaa", "위층 제거가 아래층(A판)을 되살려야 한다"

    modstore.remove("Skin A", game, store=store)
    assert target.read_bytes() == b"original"            # 층1 제거 → 원본 복귀
    leftovers = [p.name for p in (game / "Graphics").iterdir() if p.name != "look.png"]
    assert leftovers == [], f"층 보관 파일이 남았다: {leftovers}"


def test_core_reinstall_is_not_a_layer(tmp_path):
    """코어 재설치를 남의 층으로 오인하면 제거가 순정 대신 자기 판을 복원한다.

    2026-08-04 실기: merge_core 산출은 뜻-왕복이라 카드 원본과 바이트가 다르다.
    바이트 비교 층 감지가 그걸 층으로 셸빙(.pre)했고, 제거가 순정(.orig) 대신
    그 셸빙본을 되살려 코어가 영영 패치판에 머물렀다. 코어는 same_core로 가른다.
    """
    import json
    import zlib
    from modkit import rubywrite
    from tests.test_inject import make_core_game

    game = make_core_game(tmp_path)
    pure = (game / "Data" / "Scripts.rxdata").read_bytes()
    store = tmp_path / "store"
    folder = store / "Old Game" / "KR Core"
    folder.mkdir(parents=True)
    # 실물 카드 파일은 루비가 쓴 것이라 modkit 재직렬화와 바이트가 다르다 —
    # 압축 레벨을 달리해 그 어긋남을 재현한다(뜻은 동일).
    payload = rubywrite.dumps([
        [1, b"Patched", zlib.compress(b"# kr\r\n", 9)],
        [2, b"Main", zlib.compress(b"# main\r\n", 9)],
    ])
    (folder / "Scripts.rxdata").write_bytes(payload)
    (folder / "mod.json").write_text(json.dumps(
        {"name": "KR Core", "game": "Old Game", "scripts": [],
         "assets": [{"file": "Scripts.rxdata", "install_to": "Data/Scripts.rxdata"}]}),
        encoding="utf-8")

    modstore.apply(store, "KR Core", game, force=True)
    # 주입 모드가 들어왔다 나가면 코어는 재직렬화된다(뜻-왕복) — 그 상태를 흉내낸다.
    core = game / "Data" / "Scripts.rxdata"
    entries = [[n, t, zlib.compress(zlib.decompress(bytes(s)), 0)]
               for n, t, s in __import__("modkit.rubyread", fromlist=["loads"]).loads(core.read_bytes())]
    core.write_bytes(rubywrite.dumps(entries))
    told = core.read_bytes()
    assert told != payload and len(told) != len(payload)  # 크기까지 다르되 뜻은 같다

    modstore.apply(store, "KR Core", game, force=True)   # 재설치
    pre_files = list((game / "Data").glob("*.pre-*"))
    assert pre_files == [], f"재설치가 자기 자신을 층으로 셸빙했다: {pre_files}"

    modstore.remove("KR Core", game, store=store)
    assert (game / "Data" / "Scripts.rxdata").read_bytes() == pure
    assert not (game / "Data" / "Scripts.rxdata.orig").exists()


def test_remove_keeps_preexisting_identical_file(tmp_path):
    """이미 손패치로 놓여 있던 파일(모드 것과 동일)은 제거해도 살아남아야 한다.

    2026-08-04 Nova 실기: 설치가 동일 파일을 '건너뜀'(백업 없음) 하고, 제거가
    백업 없음을 '내가 놓은 것'으로 오인해 실물 999_Main.rb·폰트를 지웠다.
    """
    game, store = put_two_overlapping_asset_mods(tmp_path)
    target = game / "Graphics" / "look.png"
    target.write_bytes(b"aaaa")  # Skin A와 동일한 내용이 이미 손으로 들어가 있다

    modstore.apply(store, "Skin A", game)
    modstore.remove("Skin A", game, store=store)
    assert target.is_file(), "손패치로 있던 파일이 제거 때 사라졌다"
    assert target.read_bytes() == b"aaaa"


def test_force_overrides_wrong_game(tmp_path):
    """게임 귀속도 강행 가능해야 한다 — 매니저는 제한이 아니라 정보와 가드레일이다."""
    game = make_core_game(tmp_path)
    store = tmp_path / "store"
    from tests.test_inject import put_mod
    put_mod(store, "Foreign", game="Another Game")

    with pytest.raises(modstore.WrongGame):
        modstore.apply(store, "Foreign", game)
    done = modstore.apply(store, "Foreign", game, force=True)
    assert any("강행" in w for w in done["warnings"])


def test_wholesale_wipe_warning_stays_readable(tmp_path):
    """씻김 경고는 이름 몇 개 + '외 N개'로 집계한다 — Añil 실기(2026-08-04)에서
    게임 동봉 플러그인 52개가 전부 나열돼 경고문이 화면을 삼켰다."""
    names = [f"Plugin {i:02d}" for i in range(52)]
    note = modstore._wipe_note("Data/PluginScripts.rxdata", names)
    assert note.count("`") == 8          # 이름 4개까지만 (백틱 4쌍)
    assert "외 48개" in note
    short = modstore._wipe_note("Data/PluginScripts.rxdata", names[:3])
    assert "외" not in short             # 넘치지 않으면 집계 없이 그대로


def test_wholesale_asset_warns_about_wiped_mods(tmp_path):
    """코어를 통째로 덮는 에셋 모드는 그 안에 살던 주입 모드들을 씻어 낸다 —
    설치 전에 무엇이 지워지고 무엇이 담겨 오는지 말해야 한다(2026-08-04 실기:
    한글패치 설치가 말없이 모드 전부를 제거하고 UI Text KR만 심었다)."""
    import json
    import zlib
    from modkit import rubywrite
    from tests.test_inject import make_core_game, put_mod

    game = make_core_game(tmp_path)
    store = tmp_path / "store"
    put_mod(store, "Speed Up")
    modstore.apply(store, "Speed Up", game)
    assert modstore.installed(game) == ["Speed Up"]

    # 통째 교체본 — 안에 다른 모드(Embedded)의 주입 섹션이 담겨 있다
    payload = rubywrite.dumps([
        [1, b"Main", zlib.compress(b"# main\r\n")],
        [2, b"MOD:Embedded/001_E.rb", zlib.compress(b"# embedded\r\n")],
    ])
    folder = store / "Old Game" / "Big Patch"
    folder.mkdir(parents=True)
    (folder / "Scripts.rxdata").write_bytes(payload)
    (folder / "mod.json").write_text(json.dumps(
        {"name": "Big Patch", "game": "Old Game", "scripts": [],
         "assets": [{"file": "Scripts.rxdata", "install_to": "Data/Scripts.rxdata"}]}),
        encoding="utf-8")

    done = modstore.apply(store, "Big Patch", game)
    # 코어는 병합이라 Speed Up이 살아남고, 실려 온 Embedded는 빠진다는 안내가 온다
    assert "Speed Up" in modstore.installed(game)
    ride = [w for w in done["warnings"] if "Embedded" in w]
    assert ride and "빼고 설치" in ride[0]


def test_wholesale_core_merge_preserves_injected_mods(tmp_path):
    """코어 통째 교체 에셋은 섹션 병합으로 들어간다 — 살아 있는 주입 모드는 보존하고,
    교체본에 실려 온 남의 주입은 뺀다. 통째 교체가 야생의 기본값이라도, 충돌 없이
    설치·제거하자고 만든 도구가 모드 전멸을 기본 동작으로 둘 수는 없다(2026-08-04)."""
    import json
    import zlib
    from modkit import rubywrite
    from tests.test_inject import make_core_game, put_mod

    game = make_core_game(tmp_path)
    store = tmp_path / "store"
    put_mod(store, "Speed Up")
    modstore.apply(store, "Speed Up", game)

    payload = rubywrite.dumps([
        [1, b"Translated", zlib.compress(b"# kr\r\n")],
        [2, b"Main", zlib.compress(b"# main\r\n")],
        [3, b"MOD:Rider/001_R.rb", zlib.compress(b"# rider\r\n")],
    ])
    folder = store / "Old Game" / "KR Patch"
    folder.mkdir(parents=True)
    (folder / "Scripts.rxdata").write_bytes(payload)
    (folder / "mod.json").write_text(json.dumps(
        {"name": "KR Patch", "game": "Old Game", "scripts": [],
         "assets": [{"file": "Scripts.rxdata", "install_to": "Data/Scripts.rxdata"}]}),
        encoding="utf-8")

    modstore.apply(store, "KR Patch", game, force=True)
    now = modstore.installed(game)
    assert "Speed Up" in now                 # 살아 있는 주입은 보존된다
    assert "Rider" not in now                # 실려 온 남의 주입은 안 들어온다
    # 병합돼도 '설치됨' 판정은 유지된다 (주입 걷어낸 뼈대 비교)
    from modkit import modassets
    assert modassets.applied(modstore.read_mod(store, "KR Patch"), game)


def test_wholesale_core_remove_preserves_injected_mods(tmp_path):
    """통째 교체 에셋을 제거할 때도 그 뒤에 설치된 주입 모드는 살아남는다."""
    import json
    import zlib
    from modkit import rubywrite
    from tests.test_inject import make_core_game, put_mod

    game = make_core_game(tmp_path)
    store = tmp_path / "store"
    payload = rubywrite.dumps([[1, b"Main", zlib.compress(b"# kr main\r\n")]])
    folder = store / "Old Game" / "KR Patch"
    folder.mkdir(parents=True)
    (folder / "Scripts.rxdata").write_bytes(payload)
    (folder / "mod.json").write_text(json.dumps(
        {"name": "KR Patch", "game": "Old Game", "scripts": [],
         "assets": [{"file": "Scripts.rxdata", "install_to": "Data/Scripts.rxdata"}]}),
        encoding="utf-8")
    modstore.apply(store, "KR Patch", game, force=True)
    put_mod(store, "Speed Up")
    modstore.apply(store, "Speed Up", game)   # 패치 위에 주입 모드
    assert modstore.installed(game) == ["Speed Up"]

    modstore.remove("KR Patch", game, store=store)
    assert "Speed Up" in modstore.installed(game)   # 원본 복원 후에도 주입은 남는다


def test_remove_keeps_vanilla_slot_when_backup_is_gone(tmp_path):
    """백업이 없어도 순정이 있던 자리(`replaces_crc`)는 안 지운다 — 안내만 낸다.

    백업은 자리마다 하나뿐이라 그 자리를 함께 쓰는 다른 모드가 먼저 빠지면서
    가져갈 수 있다. 그때 「백업이 없으니 내가 새로 놓은 것」으로 읽으면 순정이
    사라진다(2026-08-07 실기 — helpCkey.png 등 다섯 장).
    """
    game = make_core_game(tmp_path)
    (game / "Graphics").mkdir()
    (game / "Graphics" / "look.png").write_bytes(b"vanilla")
    store = tmp_path / "store"
    put_asset_mod(store, "Old Game", crc=zlib.crc32(b"vanilla"))

    modstore.apply(store, "Skin", game)
    (game / "Graphics" / "look.png.orig").unlink()             # 남이 백업을 가져간 상태
    r = modstore.remove("Skin", game, store=store)

    assert (game / "Graphics" / "look.png").is_file()          # 순정 자리가 살아 있다
    assert r["warnings"] and "Graphics/look.png" in r["warnings"][0]


def test_remove_still_deletes_its_own_new_file(tmp_path):
    """반대편 — 순정에 없던 자리(지문 없음)는 지금까지처럼 지운다."""
    game = make_core_game(tmp_path)
    store = tmp_path / "store"
    folder = put_asset_mod(store, "Old Game", crc=0)
    card = json.loads((folder / "mod.json").read_text(encoding="utf-8"))
    del card["assets"][0]["replaces_crc"]                      # 새로 놓는 자리
    (folder / "mod.json").write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")

    modstore.apply(store, "Skin", game)
    assert (game / "Graphics" / "look.png").is_file()
    r = modstore.remove("Skin", game, store=store)
    assert not (game / "Graphics" / "look.png").exists()
    assert not r["warnings"]
