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
