"""선언 검사 3겹 — 차단(requires·conflicts), 배치(order), 경고(touches)."""
import pytest

from tests.test_import_standalone import make_game
from tests.test_inject import make_core_game, put_mod


def test_requires_blocks(tmp_path):
    from modkit import modstore, declare
    game = make_core_game(tmp_path)
    store = tmp_path / "store"
    put_mod(store, "Addon", extra={"requires": ["Base KR"]})
    with pytest.raises(declare.Blocked, match="Base KR"):
        modstore.apply(store, "Addon", game)


def test_conflicts_blocks_with_reason(tmp_path):
    from modkit import modstore, declare
    game = make_core_game(tmp_path)
    store = tmp_path / "store"
    put_mod(store, "Menu A")
    put_mod(store, "Menu B", extra={"conflicts": {"Menu A": "같은 씬을 통째로 갈아 끼움"}})
    modstore.apply(store, "Menu A", game)
    with pytest.raises(declare.Blocked, match="같은 씬"):
        modstore.apply(store, "Menu B", game)
    r = modstore.apply(store, "Menu B", game, force=True)  # 강행은 경고로
    assert any("Menu A" in w for w in r["warnings"])


def test_order_after_places_later(tmp_path):
    from modkit import modstore
    game = make_core_game(tmp_path)
    store = tmp_path / "store"
    put_mod(store, "Base KR")
    put_mod(store, "Labels", extra={"order": {"after": ["Base KR"]}})
    modstore.apply(store, "Labels", game)      # Base KR가 아직 없어도 얹힌다 (제약은 상대)
    modstore.apply(store, "Base KR", game)
    modstore.apply(store, "Labels", game)      # 다시 얹으면 after 제약이 실현된다
    names = modstore.installed(game)
    assert names.index("Base KR") < names.index("Labels")


def test_order_before_inserts_ahead_in_bundle(tmp_path):
    """묶음형은 자리를 골라 꽂는다 — before 제약이면 그 모드 앞에."""
    from modkit import modstore
    game = make_game(tmp_path)                 # 묶음에 "Base Mod"가 이미 있다
    store = tmp_path / "store"
    put_mod(store, "Early", game="Test Game", extra={"order": {"before": ["Base Mod"]}})
    modstore.apply(store, "Early", game)
    assert modstore.installed(game) == ["Early", "Base Mod"]


def test_touches_overlap_warns(tmp_path):
    from modkit import modstore
    game = make_core_game(tmp_path)
    store = tmp_path / "store"
    put_mod(store, "Mod A", extra={"touches": {"methods": ["Scene_Map#update"]}})
    put_mod(store, "Mod B", extra={"touches": {"methods": ["Scene_Map#update"]}})
    modstore.apply(store, "Mod A", game)
    r = modstore.apply(store, "Mod B", game)
    assert any("Scene_Map#update" in w and "Mod A" in w for w in r["warnings"])


def test_overlap_warning_is_one_line_per_counterpart(tmp_path):
    """겹침 경고는 상대 모드당 한 줄 — 자리마다 같은 부연이 되풀이되면 못 읽는다(실기)."""
    from modkit import modstore
    game = make_core_game(tmp_path)
    store = tmp_path / "store"
    both = {"touches": {"methods": ["Scene_Map#update", "Scene_Map#main", "Input.update"]}}
    put_mod(store, "Mod A", extra=both)
    put_mod(store, "Mod B", extra=both)
    modstore.apply(store, "Mod A", game)
    r = modstore.apply(store, "Mod B", game)
    overlap = [w for w in r["warnings"] if "Mod A" in w]
    assert len(overlap) == 1
    assert "Scene_Map#update" in overlap[0] and "Input.update" in overlap[0]


def test_declared_order_silences_overlap(tmp_path):
    """상대와의 순서를 선언한 겹침은 의도된 층이다 — 경고하지 않는다."""
    from modkit import modstore
    game = make_core_game(tmp_path)
    store = tmp_path / "store"
    put_mod(store, "Mod A", extra={"touches": {"methods": ["Scene_Map#update"]}})
    put_mod(store, "Mod B", extra={"touches": {"methods": ["Scene_Map#update"]},
                                   "order": {"after": ["Mod A"]}})
    modstore.apply(store, "Mod A", game)
    r = modstore.apply(store, "Mod B", game)
    assert not [w for w in r["warnings"] if "Mod A" in w and "건드려" in w]
