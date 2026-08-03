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

    done = manifest.restore(game, box)
    assert (game / "Graphics" / "old.png").read_bytes() == b"old patch trace"
    assert sorted(done["restored"]) == ["Graphics/old.png", "oldpatch.txt"]
    assert done["kept"] == []
    assert not box.exists()  # 빈 격리 폴더는 걷는다


def test_quarantine_rejects_escape(tmp_path):
    from modkit import manifest
    import pytest
    game = make_core_game(tmp_path)
    with pytest.raises(ValueError):
        manifest.quarantine(game, ["../outside.txt"])


def test_restore_keeps_conflicting(tmp_path):
    """되돌릴 자리에 파일이 이미 있으면 덮지 않고 격리함에 남긴다."""
    from modkit import manifest
    game = make_core_game(tmp_path)
    (game / "keep.txt").write_bytes(b"old")

    box = manifest.quarantine(game, ["keep.txt"], at="2026-08-03T12:00:00")
    (game / "keep.txt").write_bytes(b"new")                    # 그 자리에 새 파일이 생겼다

    done = manifest.restore(game, box)
    assert done["restored"] == [] and done["kept"] == ["keep.txt"]
    assert (game / "keep.txt").read_bytes() == b"new"          # 안 덮었다
    assert (box / "keep.txt").read_bytes() == b"old"           # 격리함에 그대로 남았다
