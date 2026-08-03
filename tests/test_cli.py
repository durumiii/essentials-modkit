"""CLI — 매니페스트·진단·격리 한 바퀴."""
import json
import subprocess
import sys

from tests.test_inject import make_core_game


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "modkit.cli", *map(str, args)],
                          capture_output=True, text=True)


def test_manifest_diagnose_quarantine_flow(tmp_path):
    game = make_core_game(tmp_path)
    out = tmp_path / "m.json"
    r = run_cli("manifest", game, "-o", out, "--game", "Old Game")
    assert r.returncode == 0 and out.is_file()

    (game / "oldpatch.txt").write_bytes(b"trace")
    r = run_cli("diagnose", game, "-m", out)
    assert r.returncode == 2 and "oldpatch.txt" in r.stdout

    r = run_cli("diagnose", game, "-m", out, "--quarantine")
    assert r.returncode == 0
    assert not (game / "oldpatch.txt").exists()
    assert list((game / "_quarantine").iterdir())  # 격리함에 들어갔다

    r = run_cli("diagnose", game, "-m", out)
    assert r.returncode == 0 and "깨끗" in r.stdout


def test_apply_without_bundle_reports(tmp_path):
    """Data 폴더가 없는 경로에 apply — 트레이스백 없이 사유만 남기고 1로 끝난다."""
    from tests.test_inject import put_mod
    store = tmp_path / "store"
    put_mod(store, "My Mod")
    bare = tmp_path / "Old Game"  # Game.ini 없으면 폴더 이름이 제목 — 귀속은 통과
    bare.mkdir()

    r = run_cli("apply", "My Mod", bare, "--store", store)
    assert r.returncode == 1
    assert "Traceback" not in r.stderr
    assert "Scripts.rxdata" in r.stderr
