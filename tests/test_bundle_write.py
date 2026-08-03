"""묶음형도 쓰기 전에 되읽어 확인한다 — 어긋나면 파일을 건드리지 않는다."""
import pytest

from tests.test_import_standalone import make_game
from tests.test_inject import put_mod


def test_write_roundtrip_guard(tmp_path, monkeypatch):
    from modkit import modstore, rubywrite
    game = make_game(tmp_path)
    store = tmp_path / "store"
    put_mod(store, "New Mod", game="Test Game")

    bundle = game / "Data" / "PluginScripts.rxdata"
    before = bundle.read_bytes()
    # 되읽으면 빈 목록이 나오는 오염된 기록기 — 항목 수가 어긋난다
    monkeypatch.setattr(rubywrite, "dumps", lambda entries: b"\x04\x08[\x00")

    with pytest.raises(modstore.NoBundle):
        modstore.apply(store, "New Mod", game)
    assert bundle.read_bytes() == before
