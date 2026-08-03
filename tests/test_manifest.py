"""매니페스트 캡처와 4종 판정."""
import json
from pathlib import Path

import pytest

from tests.test_inject import make_core_game, put_mod


def test_capture_and_roundtrip(tmp_path):
    from modkit import manifest
    game = make_core_game(tmp_path)
    (game / "Graphics").mkdir(); (game / "Graphics" / "a.png").write_bytes(b"png")
    (game / "Saves").mkdir(); (game / "Saves" / "s1.rxdata").write_bytes(b"save")

    m = manifest.capture(game, game="Old Game", version="v1")
    assert m["modkit_manifest"] == 1
    assert "Graphics/a.png" in m["files"]
    assert "Data/Scripts.rxdata" in m["files"]
    assert not any(p.startswith("Saves/") for p in m["files"])  # 유저 데이터 제외

    manifest.save(m, tmp_path / "manifest.json")
    assert manifest.load(tmp_path / "manifest.json") == m


def test_diagnose_four_verdicts(tmp_path):
    from modkit import manifest, modstore
    game = make_core_game(tmp_path)
    (game / "Graphics").mkdir(); (game / "Graphics" / "a.png").write_bytes(b"png")
    m = manifest.capture(game, game="Old Game")

    store = tmp_path / "store"
    put_mod(store, "My Mod")
    modstore.apply(store, "My Mod", game)                      # 아는 변경 + .orig 백업
    (game / "Graphics" / "a.png").write_bytes(b"tampered")     # 외래 (변경)
    (game / "oldpatch.txt").write_bytes(b"trace")              # 외래 (추가)
    (game / "Game.ini").unlink()                               # 누락

    d = manifest.diagnose(game, m, store=store)
    assert ("Data/Scripts.rxdata", "My Mod") in d.known
    assert "Graphics/a.png" in d.foreign and "oldpatch.txt" in d.foreign
    assert "Game.ini" in d.missing
    assert "Data/Scripts.rxdata.orig" in d.backups
    assert "Data/Scripts.rxdata" not in d.foreign              # 아는 변경은 외래가 아니다


def test_diagnose_known_via_asset(tmp_path):
    """에셋 install_to도 known으로 잡힌다 — 스크립트 소유 경로만이 아니다."""
    from modkit import manifest, modstore
    game = make_core_game(tmp_path)
    m = manifest.capture(game, game="Old Game")

    store = tmp_path / "store"
    put_mod(store, "UI Mod", extra={"assets": [
        {"file": "ui.png", "install_to": "Graphics/ui.png"},
    ]})
    (store / "Old Game" / "UI Mod" / "ui.png").write_bytes(b"asset")
    (game / "Graphics").mkdir()
    (game / "Graphics" / "ui.png").write_bytes(b"asset-installed")  # 매니페스트엔 없음

    d = manifest.diagnose(game, m, store=store)
    assert ("Graphics/ui.png", "UI Mod") in d.known
    assert "Graphics/ui.png" not in d.foreign


def test_diagnose_clean(tmp_path):
    from modkit import manifest
    game = make_core_game(tmp_path)
    m = manifest.capture(game, game="Old Game")
    d = manifest.diagnose(game, m)
    assert d.foreign == () and d.missing == ()
    assert set(d.intact) == set(m["files"])


def test_capture_fills_game_from_title(tmp_path):
    """game을 안 주면 Game.ini 제목으로 채운다 — 빈 값이면 known 판정이 죽는다."""
    from modkit import manifest, modstore
    game = make_core_game(tmp_path)
    m = manifest.capture(game)                                 # --game 없이
    assert m["game"] == "Old Game"

    store = tmp_path / "store"
    put_mod(store, "My Mod")
    modstore.apply(store, "My Mod", game)

    d = manifest.diagnose(game, m, store=store)
    assert ("Data/Scripts.rxdata", "My Mod") in d.known


def test_bundled_manifest_not_foreign(tmp_path):
    """동봉 manifest.json은 foreign이 아니어야 한다."""
    from modkit import manifest
    game = make_core_game(tmp_path)
    m = manifest.capture(game, game="Old Game")

    # 매니페스트를 게임 폴더에 저장
    manifest.save(m, game / "manifest.json")

    # 재진단하면 foreign이 비어 있어야 한다
    d = manifest.diagnose(game, m)
    assert "manifest.json" not in d.foreign


def test_partial_scope_untracked_not_foreign(tmp_path):
    """부분 매니페스트: 목록 밖 파일은 untracked — 격리 대상(foreign)이 아니다."""
    from modkit import manifest
    game = make_core_game(tmp_path)
    (game / "Graphics").mkdir(); (game / "Graphics" / "patched.png").write_bytes(b"png")

    stage = tmp_path / "stage" / "Graphics"
    stage.mkdir(parents=True)
    (stage / "patched.png").write_bytes(b"png")
    m = manifest.capture(stage.parent, game="Old Game", scope="partial")
    assert m["scope"] == "partial"

    d = manifest.diagnose(game, m)
    assert d.foreign == ()
    assert "Data/Scripts.rxdata" in d.untracked
    assert "Graphics/patched.png" in d.intact


def test_partial_scope_still_catches_tampered_listed_file(tmp_path):
    """목록에 있는 파일이 어긋나면 부분 매니페스트에서도 여전히 외래다."""
    from modkit import manifest
    game = make_core_game(tmp_path)
    (game / "Graphics").mkdir(); (game / "Graphics" / "patched.png").write_bytes(b"png")

    stage = tmp_path / "stage" / "Graphics"
    stage.mkdir(parents=True)
    (stage / "patched.png").write_bytes(b"png")
    m = manifest.capture(stage.parent, game="Old Game", scope="partial")

    (game / "Graphics" / "patched.png").write_bytes(b"OLD PATCH")
    d = manifest.diagnose(game, m)
    assert d.foreign == ("Graphics/patched.png",)


def test_scope_defaults_to_full(tmp_path):
    """scope 키가 없는 옛 매니페스트는 full로 읽는다 — 목록 밖은 외래 그대로."""
    from modkit import manifest
    game = make_core_game(tmp_path)
    m = manifest.capture(game, game="Old Game")
    assert m["scope"] == "full"
    del m["scope"]
    (game / "oldpatch.txt").write_bytes(b"trace")
    d = manifest.diagnose(game, m)
    assert d.foreign == ("oldpatch.txt",) and d.untracked == ()
