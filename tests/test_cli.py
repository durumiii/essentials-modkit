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
