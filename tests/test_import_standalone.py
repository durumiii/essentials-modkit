"""modkit이 fanlib 없이 홀로 서는지 — 임포트와 왕복."""
import sys
import zlib
from pathlib import Path

import pytest


def test_no_fanlib_import():
    for name in ("modstore", "modassets", "modfit", "scripts",
                 "rubyread", "rubywrite", "gameinfo"):
        mod = __import__(f"modkit.{name}", fromlist=[name])
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "fanlib" not in src, f"{name}이 아직 fanlib을 물고 있다"


def make_game(tmp_path, title="Test Game"):
    """묶음(PluginScripts.rxdata) 있는 합성 설치본."""
    from modkit import rubywrite
    game = tmp_path / "game"
    (game / "Data").mkdir(parents=True)
    (game / "Game.ini").write_text(f"[Game]\nTitle={title}\n", encoding="utf-8")
    entries = [["Base Mod", {}, [["001_Base.rb",
                zlib.compress(b"class Foo\r\n  def bar\r\n  end\r\nend\r\n")]]]]
    (game / "Data" / "PluginScripts.rxdata").write_bytes(rubywrite.dumps(entries))
    return game


def test_roundtrip_harvest_apply_remove(tmp_path):
    from modkit import modstore
    game = make_game(tmp_path)
    store = tmp_path / "store"

    got = modstore.harvest(game, ["Base Mod"], store=store)
    assert got[0].name == "Base Mod"
    assert got[0].game == "Test Game"          # gameinfo.read_title 경유
    assert (store / "Test Game" / "Base Mod" / "mod.json").is_file()

    before = (game / "Data" / "PluginScripts.rxdata").read_bytes()
    modstore.remove("Base Mod", game, store=store)
    assert modstore.installed(game) == []
    modstore.apply(store, "Base Mod", game)
    assert modstore.installed(game) == ["Base Mod"]
    after = (game / "Data" / "PluginScripts.rxdata").read_bytes()
    assert before == after                      # 빼기→얹기 왕복 바이트 동일


def test_gameinfo_title_fallback(tmp_path):
    from modkit import gameinfo
    assert gameinfo.read_title(tmp_path) == tmp_path.name  # Game.ini 없으면 폴더 이름


def test_identify_known_game(tmp_path):
    from modkit import gameinfo
    game = tmp_path / "z"
    game.mkdir()
    (game / "Game.ini").write_text("[Game]\nTitle=Pokemon Z Fangame\n", encoding="utf-8")
    who = gameinfo.identify(game)
    assert who == {"title": "Pokemon Z Fangame", "known": True,
                   "label": "Pokémon Z Fangame", "banner": ""}


def test_shelf_matches_game_aliases(tmp_path):
    """순정 제목("Pokemon Z")과 패치 제목("Pokemon Z Fangame")은 같은 게임이다 —
    카드가 어느 쪽에 매였든 서랍에 보여야 한다(2026-08-04 실기: 순정 사본에서 서랍이 비었다)."""
    import json
    from modkit import modstore
    store = tmp_path / "store"
    folder = store / "Pokemon Z Fangame" / "Some Mod"
    folder.mkdir(parents=True)
    (folder / "mod.json").write_text(json.dumps(
        {"name": "Some Mod", "game": "Pokemon Z Fangame", "scripts": []}), encoding="utf-8")
    assert [m.name for m in modstore.shelf(store, game="Pokemon Z")] == ["Some Mod"]


def test_shelf_survives_broken_card(tmp_path):
    """카드 하나가 이상해도 보관소 전체가 죽으면 안 된다(2026-08-04 실기 — 폴더
    이름과 카드 이름이 어긋난 모드 하나가 서랍·설치 전부를 잠갔다)."""
    import json
    from modkit import modstore
    store = tmp_path / "store"
    good = store / "G" / "Good Mod"
    good.mkdir(parents=True)
    (good / "mod.json").write_text(json.dumps(
        {"name": "Good Mod", "game": "G", "scripts": []}), encoding="utf-8")
    # 폴더 이름 ≠ 카드 이름 — 어긋난 카드
    odd = store / "G" / "Odd Folder"
    odd.mkdir()
    (odd / "mod.json").write_text(json.dumps(
        {"name": "전혀 다른 이름", "game": "G", "scripts": []}), encoding="utf-8")
    # 아예 깨진 카드
    broken = store / "G" / "Broken"
    broken.mkdir()
    (broken / "mod.json").write_text("{잘못된 json", encoding="utf-8")

    names = [m.name for m in modstore.shelf(store, game="G")]
    assert "Good Mod" in names
    assert "전혀 다른 이름" in names          # 폴더 이름이 달라도 카드로 읽힌다
    # 이름으로도 찾아진다 — 폴더 탐색이 실패하면 카드 이름을 훑는다
    assert modstore.read_mod(store, "전혀 다른 이름").folder == odd


def test_josa_picks_particle():
    from modkit import gameinfo
    j = gameinfo.josa
    assert j("모드", "은/는") == "모드는"
    assert j("한글패치 통합", "은/는") == "한글패치 통합은"
    assert j("`Battle Speed Z`", "은/는") == "`Battle Speed Z`는"      # Z=지
    assert j("`UI Text KR`", "은/는") == "`UI Text KR`은"              # KR=케이알
    assert j("`Frame Profiler`", "은/는") == "`Frame Profiler`는"      # 프로파일러
    assert j("`Pokemon Z`", "이에요/예요") == "`Pokemon Z`예요"
    assert j("v1.0.8", "이에요/예요") == "v1.0.8이에요"                # 팔
