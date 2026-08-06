"""harvest가 touches 초안을 공짜로 채운다 — 사람 손 선언은 안 덮는다."""
import json
import zlib

from tests.test_import_standalone import make_game


def test_harvest_fills_touches_draft(tmp_path):
    from modkit import modstore, rubywrite
    game = make_game(tmp_path)
    # 코어(Scripts.rxdata)에 원본 메서드, 모드가 같은 메서드를 재정의하는 상황
    core = [[1, b"Foo", zlib.compress(b"class Foo\r\n  def bar\r\n  end\r\nend\r\n")],
            [2, b"Main", zlib.compress(b"# main\r\n")]]
    (game / "Data" / "Scripts.rxdata").write_bytes(rubywrite.dumps(core))
    store = tmp_path / "store"
    modstore.harvest(game, ["Base Mod"], store=store)

    card = json.loads((store / "Test Game" / "Base Mod" / "mod.json")
                      .read_text(encoding="utf-8"))
    assert "Foo#bar" in card["touches"]["methods"]


def test_harvest_keeps_manual_touches(tmp_path):
    from modkit import modstore
    game = make_game(tmp_path)
    store = tmp_path / "store"
    modstore.harvest(game, ["Base Mod"], store=store)
    card_path = store / "Test Game" / "Base Mod" / "mod.json"
    card = json.loads(card_path.read_text(encoding="utf-8"))
    card["touches"] = {"methods": ["Hand#written"], "files": []}
    card_path.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")

    modstore.harvest(game, ["Base Mod"], store=store)  # 다시 꺼내도
    card = json.loads(card_path.read_text(encoding="utf-8"))
    assert card["touches"]["methods"] == ["Hand#written"]  # 손 선언 보존


def test_harvest_keeps_declarations(tmp_path):
    """선언 필드는 게임에 없고 카드에만 산다 — 다시 꺼낼 때 지워지면 검사가 조용히 꺼진다."""
    from modkit import modstore
    game = make_game(tmp_path)
    store = tmp_path / "store"
    modstore.harvest(game, ["Base Mod"], store=store)
    card_path = store / "Test Game" / "Base Mod" / "mod.json"
    card = json.loads(card_path.read_text(encoding="utf-8"))
    card.update({"requires": ["hangul-font"], "provides": ["ui-kr"],
                 "conflicts": {"Other": "같은 씬"}, "order": {"after": ["Base KR"]}})
    card_path.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")

    modstore.harvest(game, ["Base Mod"], store=store)
    card = json.loads(card_path.read_text(encoding="utf-8"))
    assert card["requires"] == ["hangul-font"]
    assert card["provides"] == ["ui-kr"]
    assert card["conflicts"] == {"Other": "같은 씬"}
    assert card["order"] == {"after": ["Base KR"]}
