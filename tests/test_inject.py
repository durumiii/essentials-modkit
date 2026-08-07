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


HOOKED = b"class Talk\n  def say\n    1\n  end\nend\n\nSALUDO = 'hola'\n"
PATCHED = b"class Talk\n  def say\n    1\n  end\nend\n\nSALUDO = '\xec\x95\x88\xeb\x85\x95'\n"
OVERRIDE = b"class Talk\n  def say\n    2\n  end\nend\n"


def _mod_with_baseline(store, game, name="Hooker"):
    """덮어쓰는 메서드의 원문을 기준선으로 들고 있는 모드."""
    import hashlib
    folder = put_mod(store, name, source=OVERRIDE,
                     extra={"expects": {"Talk": hashlib.md5(HOOKED).hexdigest()},
                            "baseline_taken": True})
    base = folder / "baseline"
    base.mkdir()
    (base / "Talk__say.rb").write_bytes(b"  def say\n    1\n  end\n")
    return folder


def test_expects_drift_passes_when_the_hooked_method_is_intact(tmp_path):
    """섹션의 딴 문구만 바뀐 자리는 막지 않고 알린다.

    한글패치가 같은 섹션의 문자열만 옮겨 놓으면 섹션 md5는 어긋나지만 모드가
    손대는 메서드는 그대로다. 그때 막으면 멀쩡한 조합을 막는 것이다
    (2026-08-07 실측: Controller UX의 TextEntry · Better Movements의 Following).
    """
    from modkit import modstore
    game = make_core_game(tmp_path, sections=(("Talk", PATCHED), ("Main", b"# main\n")))
    store = tmp_path / "store"
    _mod_with_baseline(store, game)

    r = modstore.apply(store, "Hooker", game)
    assert r["did"] == "설치됨"
    assert any("Talk" in w and "그대로라" in w for w in r["warnings"]), r["warnings"]


def test_expects_drift_still_blocks_when_the_hooked_method_moved(tmp_path):
    """훅 거는 메서드까지 바뀌었으면 예전대로 막는다."""
    from modkit import modstore
    moved = b"class Talk\n  def say\n    99\n  end\nend\n\nSALUDO = 'hola'\n"
    game = make_core_game(tmp_path, sections=(("Talk", moved), ("Main", b"# main\n")))
    store = tmp_path / "store"
    _mod_with_baseline(store, game)

    with pytest.raises(modstore.BaseChanged):
        modstore.apply(store, "Hooker", game)
    r = modstore.apply(store, "Hooker", game, force=True)   # 강행은 경고로
    assert r["did"] == "설치됨"
