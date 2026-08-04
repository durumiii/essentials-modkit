"""맨 zip 입양 — mod.json 없는 야생 배포물을 기계 규칙으로 카드화한다.

규칙은 2026-08-04 야생 표본 5개에서 나왔다: 겉포장 폴더 벗기기(ANIL KR 꼴),
게임 상대경로 그대로(NOVA·이로치 꼴), 조각 경로 꼬리 대조(Z GUI의 Pictures/ →
Graphics/Pictures/), 게임 트리에 맞는 파일 0개면 비모드(공략 txt 묶음 꼴).
"""
import json
import zipfile
import zlib

import pytest

from modkit import adopt, rubywrite


def make_game(tmp_path):
    game = tmp_path / "game"
    (game / "Data").mkdir(parents=True)
    (game / "Graphics" / "Pictures").mkdir(parents=True)
    (game / "Game.ini").write_text("[Game]\nTitle=Test Game\n", encoding="utf-8")
    (game / "Data" / "Scripts.rxdata").write_bytes(
        rubywrite.dumps([[1, b"A", zlib.compress(b"a = 1\r\n")],
                         [2, b"B", zlib.compress(b"b = 2\r\n")]]))
    (game / "Graphics" / "Pictures" / "types.png").write_bytes(b"PNG-original")
    return game


def make_zip(tmp_path, entries, name="wild.zip"):
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as zf:
        for arcname, data in entries:
            zf.writestr(arcname, data)
    return path


def read_card(store, game, name):
    return json.loads((store / game / name / "mod.json").read_text(encoding="utf-8"))


def test_game_relative_overlay(tmp_path):
    game, store = make_game(tmp_path), tmp_path / "store"
    z = make_zip(tmp_path, [("Graphics/Pictures/types.png", b"PNG-new"),
                            ("README.txt", b"hi")])
    got = adopt.adopt(z, game, store)
    card = read_card(store, "Test Game", "wild")
    assert card["name"] == "wild"                      # zip 파일명이 기본 이름
    assert card["game"] == "Test Game"
    [asset] = card["assets"]
    assert asset["install_to"] == "Graphics/Pictures/types.png"
    assert asset["replaces_crc"] == zlib.crc32(b"PNG-original")
    # 지도 밖 파일은 폴더에 보관만 하고 설치 목록엔 없다
    assert (store / "Test Game" / "wild" / "README.txt").is_file()
    assert "Graphics/Pictures/types.png" in card["touches"]["files"]


def test_wrapper_folder_unwrapped(tmp_path):
    game, store = make_game(tmp_path), tmp_path / "store"
    z = make_zip(tmp_path, [("My Mod/Graphics/Pictures/types.png", b"PNG-new")])
    adopt.adopt(z, game, store)
    [asset] = read_card(store, "Test Game", "wild")["assets"]
    assert asset["install_to"] == "Graphics/Pictures/types.png"


def test_fragment_maps_by_tree_tail(tmp_path):
    """Pictures/x.png가 게임의 Graphics/Pictures/x.png에 유일하게 맞으면 거기로."""
    game, store = make_game(tmp_path), tmp_path / "store"
    z = make_zip(tmp_path, [("Pictures/types.png", b"PNG-new")])
    adopt.adopt(z, game, store)
    [asset] = read_card(store, "Test Game", "wild")["assets"]
    assert asset["install_to"] == "Graphics/Pictures/types.png"


def test_docs_only_zip_is_not_a_mod(tmp_path):
    game, store = make_game(tmp_path), tmp_path / "store"
    z = make_zip(tmp_path, [("공략1.txt", b"x"), ("공략2.txt", b"y")])
    with pytest.raises(adopt.NotAMod):
        adopt.adopt(z, game, store)


def test_identical_files_warn_once_aggregated(tmp_path):
    """실물에서 43줄씩 쏟아졌다(ANIL KR) — 동일 파일 경고는 한 줄로 묶는다."""
    game, store = make_game(tmp_path), tmp_path / "store"
    (game / "Data" / "extra.dat").write_bytes(b"same-too")
    z = make_zip(tmp_path, [("Graphics/Pictures/types.png", b"PNG-original"),
                            ("Data/extra.dat", b"same-too")])
    got = adopt.adopt(z, game, store)
    [warning] = got.warnings
    assert "2개" in warning and "이미 적용" in warning


def test_orig_backup_is_the_original(tmp_path):
    """설치본이 이미 덮인 자리는 .orig가 원본이다 — _asset_fit과 같은 눈."""
    game, store = make_game(tmp_path), tmp_path / "store"
    (game / "Graphics" / "Pictures" / "types.png.orig").write_bytes(b"PNG-pristine")
    z = make_zip(tmp_path, [("Graphics/Pictures/types.png", b"PNG-new")])
    adopt.adopt(z, game, store)
    [asset] = read_card(store, "Test Game", "wild")["assets"]
    assert asset["replaces_crc"] == zlib.crc32(b"PNG-pristine")


def test_wholesale_rxdata_finds_base_mod(tmp_path):
    """통짜 Scripts.rxdata — 보관소 모드 산출물과의 차이가 원본보다 작으면 그게 기반."""
    game, store = make_game(tmp_path), tmp_path / "store"
    patched = rubywrite.dumps([[1, b"A", zlib.compress(b"a = 100\r\n")],
                               [2, b"B", zlib.compress(b"b = 200\r\n")]])
    base_mod = store / "Test Game" / "한글패치"
    base_mod.mkdir(parents=True)
    (base_mod / "Data").mkdir()
    (base_mod / "Data" / "Scripts.rxdata").write_bytes(patched)
    (base_mod / "mod.json").write_text(json.dumps(
        {"name": "한글패치", "game": "Test Game", "scripts": [],
         "assets": [{"file": "Data/Scripts.rxdata", "install_to": "Data/Scripts.rxdata"}]},
        ensure_ascii=False), encoding="utf-8")

    bundle_patched = rubywrite.dumps([["P", {}, [["001.rb", zlib.compress(b"p1\r\n")]]]])
    (game / "Data" / "PluginScripts.rxdata").write_bytes(
        rubywrite.dumps([["P", {}, [["001.rb", zlib.compress(b"p0\r\n")]]]]))
    (base_mod / "Data" / "PluginScripts.rxdata").write_bytes(bundle_patched)

    mine = rubywrite.dumps([[1, b"A", zlib.compress(b"a = 100\r\n")],
                            [2, b"B", zlib.compress(b"b = 999\r\n")]])
    z = make_zip(tmp_path, [("Data/Scripts.rxdata", mine),
                            ("Data/PluginScripts.rxdata", bundle_patched)], name="addon.zip")
    got = adopt.adopt(z, game, store)

    card = read_card(store, "Test Game", "addon")
    assert card["requires"] == ["한글패치"]           # 두 파일이 같은 기반이라도 한 번만
    assert card["order"] == {"after": ["한글패치"]}
    assert any("B" in note for note in got.notes)      # 바뀐 섹션 이름이 보고에 담긴다


def test_wholesale_rxdata_on_original_base_declares_nothing(tmp_path):
    game, store = make_game(tmp_path), tmp_path / "store"
    mine = rubywrite.dumps([[1, b"A", zlib.compress(b"a = 1\r\n")],
                            [2, b"B", zlib.compress(b"changed\r\n")]])
    z = make_zip(tmp_path, [("Data/Scripts.rxdata", mine)], name="tweak.zip")
    adopt.adopt(z, game, store)
    card = read_card(store, "Test Game", "tweak")
    assert "requires" not in card
