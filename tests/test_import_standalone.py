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
                   "label": "포켓몬 Z", "banner": ""}
