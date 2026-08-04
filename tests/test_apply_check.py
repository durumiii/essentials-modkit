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
