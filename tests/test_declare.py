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


def test_requires_accepts_capability(tmp_path):
    """requires는 이름 또는 능력 — 「한글 폰트 아무거나」를 이름으로는 못 적는다."""
    from modkit import modstore
    game = make_core_game(tmp_path)
    store = tmp_path / "store"
    put_mod(store, "DPPT Font", extra={"provides": ["hangul-font"]})
    put_mod(store, "한글패치", extra={"requires": ["hangul-font"]})
    modstore.apply(store, "DPPT Font", game)
    modstore.apply(store, "한글패치", game)                    # 이름이 달라도 능력으로 통과
    assert "한글패치" in modstore.installed(game)


def test_requires_capability_blocks_when_nobody_provides(tmp_path):
    from modkit import modstore, declare
    game = make_core_game(tmp_path)
    store = tmp_path / "store"
    put_mod(store, "Some Font", extra={"provides": ["latin-font"]})
    put_mod(store, "한글패치", extra={"requires": ["hangul-font"]})
    modstore.apply(store, "Some Font", game)
    with pytest.raises(declare.Blocked, match="hangul-font"):
        modstore.apply(store, "한글패치", game)


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


def test_declared_order_softens_overlap_to_layer_note(tmp_path):
    """상대와의 순서를 선언한 겹침은 의도된 층 — 경고 대신 층 안내 한 줄을 준다.

    첫 판은 완전 침묵이었는데, 이로치 설치가 한글패치를 부분 상태로 내리는 걸
    유저가 알 길이 없었다(2026-08-04 아닐 실기). 순서를 아는 것과 결과를 알리는
    것은 다르다 — 톤만 경고에서 안내로 내린다.
    """
    from modkit import modstore
    game = make_core_game(tmp_path)
    store = tmp_path / "store"
    put_mod(store, "Mod A", extra={"touches": {"methods": ["Scene_Map#update"]}})
    put_mod(store, "Mod B", extra={"touches": {"methods": ["Scene_Map#update"]},
                                   "order": {"after": ["Mod A"]}})
    modstore.apply(store, "Mod A", game)
    r = modstore.apply(store, "Mod B", game)
    assert not [w for w in r["warnings"] if "건드리는 자리예요" in w]   # 경고 톤은 여전히 금지
    layer = [w for w in r["warnings"] if "Mod A" in w and "위에" in w]
    assert len(layer) == 1                                            # 층 안내 한 줄
    assert "겹치는 자리 1곳" in layer[0]
