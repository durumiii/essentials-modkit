"""격리는 이동이지 삭제가 아니다 — 통째로 되돌릴 수 있어야 한다."""
from pathlib import Path

from tests.test_inject import make_core_game


def test_quarantine_and_restore(tmp_path):
    from modkit import manifest
    game = make_core_game(tmp_path)
    (game / "Graphics").mkdir()
    (game / "Graphics" / "old.png").write_bytes(b"old patch trace")
    (game / "oldpatch.txt").write_bytes(b"trace")

    box = manifest.quarantine(game, ["Graphics/old.png", "oldpatch.txt"],
                              at="2026-08-03T12:00:00")
    assert not (game / "oldpatch.txt").exists()
    assert (box / "Graphics" / "old.png").read_bytes() == b"old patch trace"
    assert box.parent == game / "_quarantine"

    back = manifest.restore(game, box)
    assert (game / "Graphics" / "old.png").read_bytes() == b"old patch trace"
    assert sorted(back) == ["Graphics/old.png", "oldpatch.txt"]
    assert not box.exists()  # 빈 격리 폴더는 걷는다


def test_quarantine_rejects_escape(tmp_path):
    from modkit import manifest
    import pytest
    game = make_core_game(tmp_path)
    with pytest.raises(ValueError):
        manifest.quarantine(game, ["../outside.txt"])
