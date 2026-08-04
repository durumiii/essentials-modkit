"""CLI new/lint — 뼈대 생성과 검사."""
import json
from pathlib import Path

from tests.test_cli import run_cli


def test_new_creates_skeleton_with_crlf_and_templates(tmp_path):
    r = run_cli("new", "MyMod", "--game", "Pokemon Test", "--dir", tmp_path)
    assert r.returncode == 0
    mod = tmp_path / "MyMod"
    assert (mod / "mod.json").is_file()
    assert (mod / "001_Main.rb").is_file()
    assert (mod / "AGENTS.md").is_file()
    assert (mod / "CLAUDE.md").is_file()

    templates = Path(__file__).parent.parent / "modkit" / "templates"
    assert (mod / "AGENTS.md").read_text(encoding="utf-8") == \
        (templates / "AGENTS.md").read_text(encoding="utf-8")
    assert (mod / "CLAUDE.md").read_text(encoding="utf-8") == \
        (templates / "CLAUDE.md").read_text(encoding="utf-8")

    rb_bytes = (mod / "001_Main.rb").read_bytes()
    assert b"\r\n" in rb_bytes
    assert b"\n" not in rb_bytes.replace(b"\r\n", b"")

    card = json.loads((mod / "mod.json").read_text(encoding="utf-8"))
    assert card["name"] == "MyMod"
    assert card["game"] == "Pokemon Test"
    assert card["scripts"] == [{"file": "001_Main.rb", "script_name": "001_Main.rb"}]
    assert "touches" not in card
    assert "order" not in card


def test_new_then_lint_clean(tmp_path):
    run_cli("new", "MyMod", "--game", "Pokemon Test", "--dir", tmp_path)
    r = run_cli("lint", tmp_path / "MyMod")
    assert r.returncode == 0
    assert "오류 0" in r.stdout
    assert "game" not in r.stdout  # game 채웠으니 경고 없음


def test_new_without_game_warns(tmp_path):
    run_cli("new", "MyMod", "--dir", tmp_path)
    r = run_cli("lint", tmp_path / "MyMod")
    assert r.returncode == 0
    assert "game" in r.stdout


def test_new_existing_folder_fails(tmp_path):
    (tmp_path / "MyMod").mkdir()
    r = run_cli("new", "MyMod", "--dir", tmp_path)
    assert r.returncode == 1
    assert r.stderr.strip()


def test_lint_catches_missing_name_and_missing_file(tmp_path):
    mod = tmp_path / "Broken"
    mod.mkdir()
    (mod / "mod.json").write_text(json.dumps({
        "name": "",
        "scripts": [{"file": "ghost.rb", "script_name": "ghost.rb"}],
    }), encoding="utf-8")
    r = run_cli("lint", mod)
    assert r.returncode == 1
    assert r.stdout.count("오류") >= 2


def test_lint_catches_install_to_escape(tmp_path):
    mod = tmp_path / "Escapey"
    mod.mkdir()
    (mod / "mod.json").write_text(json.dumps({
        "name": "Escapey",
        "scripts": [],
        "assets": [{"file": "a.png", "install_to": "../x"}],
    }), encoding="utf-8")
    (mod / "a.png").write_bytes(b"x")
    r = run_cli("lint", mod)
    assert r.returncode == 1
    assert "install_to" in r.stdout


def test_lint_catches_backslash_path_escape_in_script_file(tmp_path):
    mod = tmp_path / "Backslashy"
    mod.mkdir()
    (mod / "mod.json").write_text(json.dumps({
        "name": "Backslashy",
        "scripts": [{"file": "..\\evil.rb", "script_name": "evil.rb"}],
    }), encoding="utf-8")
    r = run_cli("lint", mod)
    assert r.returncode == 1
    assert "scripts[0].file" in r.stdout


def test_lint_catches_windows_drive_path_in_install_to(tmp_path):
    mod = tmp_path / "Drivey"
    mod.mkdir()
    (mod / "mod.json").write_text(json.dumps({
        "name": "Drivey",
        "scripts": [],
        "assets": [{"file": "a.png", "install_to": "C:\\Windows\\x"}],
    }), encoding="utf-8")
    (mod / "a.png").write_bytes(b"x")
    r = run_cli("lint", mod)
    assert r.returncode == 1
    assert "install_to" in r.stdout


def test_lint_missing_mod_json(tmp_path):
    mod = tmp_path / "Empty"
    mod.mkdir()
    r = run_cli("lint", mod)
    assert r.returncode == 1
    assert "mod.json" in r.stdout


def test_lint_rejects_backup_suffix_install(tmp_path, capsys):
    """install_to가 .orig/.bak로 끝나는 카드는 오류 — 설치가 백업 자리를 덮는다."""
    import json
    from modkit.cli import main
    folder = tmp_path / "Bad Mod"
    folder.mkdir()
    (folder / "Scripts.rxdata.orig").write_bytes(b"x")
    (folder / "mod.json").write_text(json.dumps(
        {"name": "Bad Mod", "game": "G", "scripts": [],
         "assets": [{"file": "Scripts.rxdata.orig", "install_to": "Data/Scripts.rxdata.orig"}]},
        ensure_ascii=False), encoding="utf-8")
    assert main(["lint", str(folder)]) == 1
    assert "백업" in capsys.readouterr().out
