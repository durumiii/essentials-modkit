"""주입형 계약 — Scripts.rxdata의 MOD: 섹션 왕복."""
import json
import zlib
from pathlib import Path

import pytest


def make_core_game(tmp_path, sections=(("Main", b"# main\r\n"),)):
    """묶음 없는 옛 엔진 설치본 — Scripts.rxdata 코어 배열만 있다."""
    from modkit import rubywrite
    game = tmp_path / "oldgame"
    (game / "Data").mkdir(parents=True)
    (game / "Game.ini").write_text("[Game]\nTitle=Old Game\n", encoding="utf-8")
    entries = [[i + 1, title.encode("utf-8"), zlib.compress(body)]
               for i, (title, body) in enumerate(sections)]
    (game / "Data" / "Scripts.rxdata").write_bytes(rubywrite.dumps(entries))
    return game


def put_mod(store, name, source=b"def patched\r\nend\r\n", game="Old Game", extra=None):
    """보관소에 주입형 모드 카드를 손으로 눕힌다."""
    folder = store / game / name
    folder.mkdir(parents=True)
    (folder / "001_Mod.rb").write_bytes(source)
    card = {"name": name, "game": game, "scripts":
            [{"file": "001_Mod.rb", "script_name": "001_Mod.rb"}]}
    card.update(extra or {})
    (folder / "mod.json").write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    return folder


def test_inject_before_main_and_uninject(tmp_path):
    from modkit import modstore
    game = make_core_game(tmp_path)
    store = tmp_path / "store"
    put_mod(store, "My Mod")

    original = (game / "Data" / "Scripts.rxdata").read_bytes()
    r = modstore.apply(store, "My Mod", game)
    assert r["did"] == "설치됨"
    assert modstore.installed(game) == ["My Mod"]
    assert (game / "Data" / "Scripts.rxdata.orig").read_bytes() == original

    modstore.apply(store, "My Mod", game)          # 두 번 눌러도 안 쌓인다
    assert modstore.installed(game) == ["My Mod"]

    modstore.remove("My Mod", game, store=store)
    assert modstore.installed(game) == []


def test_expects_mismatch_blocks(tmp_path):
    from modkit import modstore
    game = make_core_game(tmp_path)
    store = tmp_path / "store"
    put_mod(store, "Picky Mod", extra={"expects": {"Main": "0" * 32}})
    with pytest.raises(modstore.BaseChanged):
        modstore.apply(store, "Picky Mod", game)


def test_wrong_game_blocks(tmp_path):
    from modkit import modstore
    game = make_core_game(tmp_path)
    store = tmp_path / "store"
    put_mod(store, "Alien Mod", game="Other Game")
    (store / "Other Game").rename(store / "OtherDir")  # 폴더명은 무관, 카드의 game이 기준
    with pytest.raises(modstore.WrongGame):
        modstore.apply(store, "Alien Mod", game)


def test_same_name_in_two_games_picks_this_game(tmp_path):
    """게임마다 같은 이름의 모드가 있으면 이 게임 것이 잡힌다 — 사전순 첫 매치가 아니라."""
    from modkit import modstore, rubyread

    game = make_core_game(tmp_path)                        # Title=Old Game
    other = make_core_game(tmp_path / "b")
    (other / "Game.ini").write_text("[Game]\nTitle=Aaa Game\n", encoding="utf-8")
    store = tmp_path / "store"
    put_mod(store, "Better Movements", source=b"# for old\r\n", game="Old Game")
    put_mod(store, "Better Movements", source=b"# for aaa\r\n", game="Aaa Game")

    def injected(where):
        return [zlib.decompress(bytes(e[2]))
                for e in rubyread.loads((where / "Data/Scripts.rxdata").read_bytes())
                if bytes(e[1]).startswith(b"MOD:Better Movements/")]

    modstore.apply(store, "Better Movements", game)        # 사전순으로는 Aaa가 앞
    assert injected(game) == [b"# for old\r\n"]
    modstore.apply(store, "Better Movements", other)
    assert injected(other) == [b"# for aaa\r\n"]

    modstore.remove("Better Movements", game, store=store)  # 제거도 제 것을 본다
    assert injected(game) == []
    assert injected(other) == [b"# for aaa\r\n"]
