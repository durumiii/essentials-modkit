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
    """상대가 나중에 들어와도 그 자리에서 순서가 잡힌다 — 사람이 다시 누르지 않는다."""
    from modkit import modstore
    game = make_core_game(tmp_path)
    store = tmp_path / "store"
    put_mod(store, "Base KR")
    put_mod(store, "Labels", extra={"order": {"after": ["Base KR"]}})
    modstore.apply(store, "Labels", game)      # Base KR가 아직 없어도 얹힌다 (제약은 상대)
    assert modstore.installed(game) == ["Labels"]
    modstore.apply(store, "Base KR", game)     # 상대가 들어오는 순간 재배치된다
    assert modstore.installed(game) == ["Base KR", "Labels"]


def test_reorder_keeps_undeclared_mods_in_place(tmp_path):
    """선언 없는 모드끼리는 지금 순서 그대로 — 옛 모드의 동작이 바뀌면 안 된다."""
    from modkit import modstore
    game = make_core_game(tmp_path)
    store = tmp_path / "store"
    for name in ("Mod A", "Mod B", "Mod C"):
        put_mod(store, name)
    put_mod(store, "Labels", extra={"order": {"after": ["Mod C"]}})
    modstore.apply(store, "Labels", game)
    for name in ("Mod A", "Mod B", "Mod C"):
        modstore.apply(store, name, game)
    assert modstore.installed(game) == ["Mod A", "Mod B", "Mod C", "Labels"]


def test_reorder_in_bundle_when_counterpart_arrives_later(tmp_path):
    """묶음형도 같은 규칙 — 나중에 들어온 상대에 맞춰 다시 늘어선다."""
    from modkit import modstore
    game = make_game(tmp_path)                 # 묶음에 "Base Mod"가 이미 있다
    store = tmp_path / "store"
    put_mod(store, "Late", game="Test Game", extra={"order": {"after": ["Extra"]}})
    put_mod(store, "Extra", game="Test Game")
    modstore.apply(store, "Late", game)
    modstore.apply(store, "Extra", game)
    names = modstore.installed(game)
    assert names.index("Extra") < names.index("Late")
    assert names.index("Base Mod") == 0        # 선언 없는 옛 항목은 자리를 지킨다


def test_reorder_cycle_warns_and_keeps_current_order(tmp_path):
    """제약이 순환이면 설치는 되돌리지 않고 지금 순서를 둔 채 알린다."""
    from modkit import modstore
    game = make_core_game(tmp_path)
    store = tmp_path / "store"
    put_mod(store, "Ping", extra={"order": {"after": ["Pong"]}})
    put_mod(store, "Pong", extra={"order": {"after": ["Ping"]}})
    modstore.apply(store, "Ping", game)
    r = modstore.apply(store, "Pong", game, force=True)
    assert modstore.installed(game) == ["Ping", "Pong"]
    assert any("순환" in w for w in r["warnings"])


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


def test_core_swap_removal_keeps_later_injections(tmp_path):
    """코어를 통째로 덮는 모드를 뺄 때, 그 뒤에 얹힌 주입 모드는 살아남아야 한다."""
    import io
    import json
    import zlib

    from modkit import modstore, rubyread, rubywrite

    game = make_core_game(tmp_path)
    store = tmp_path / "store"
    swap = store / "Core Swap"
    (swap / "Data").mkdir(parents=True)
    core = rubyread.load(io.BytesIO((game / "Data/Scripts.rxdata").read_bytes()))
    core.insert(0, [99, b"Extra", zlib.compress(b"# translated\r\n")])
    (swap / "Data/Scripts.rxdata").write_bytes(rubywrite.dumps(core))
    (swap / "mod.json").write_text(json.dumps(
        {"name": "Core Swap", "game": "Old Game", "scripts": [],
         "assets": [{"file": "Data/Scripts.rxdata", "install_to": "Data/Scripts.rxdata"}]},
        ensure_ascii=False), encoding="utf-8")
    put_mod(store, "Inject A", game="Old Game")
    put_mod(store, "Inject B", game="Old Game")

    modstore.apply(store, "Inject A", game)
    modstore.apply(store, "Core Swap", game)
    modstore.apply(store, "Inject B", game)      # 코어 교체 뒤에 얹은 주입
    modstore.remove("Core Swap", game, store=store)

    titles = [bytes(e[1]).decode("utf-8", "replace")
              for e in rubyread.load(io.BytesIO((game / "Data/Scripts.rxdata").read_bytes()))]
    living = {t.split("/")[0][4:] for t in titles if t.startswith("MOD:")}
    assert living == {"Inject A", "Inject B"}
    assert "Extra" not in titles          # 자기 것은 남김없이 빠졌다
    assert len(titles) == len(set(titles))  # 남의 층을 두 번 꽂지 않았다
