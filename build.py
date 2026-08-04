"""WSL에서 실행해 윈도우 쪽 onefile exe를 굽는다 — `python build.py`.

UNC 경로(\\\\wsl.localhost\\...) 위에서는 uv가 프로젝트 .venv를 건드리다 깨지므로
소스를 윈도우 임시 폴더로 복사한 뒤 거기서 PyInstaller를 돌리고, 산출 exe만 회수한다.
"""
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
DIST = HERE / "dist"
WORK_WIN = r"C:\Users\durumii\AppData\Local\Temp\modkit-build"
WORK = Path("/mnt/c/Users/durumii/AppData/Local/Temp/modkit-build")
POWERSHELL = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
SKIP = shutil.ignore_patterns(".venv", ".git", "dist", "build", "__pycache__",
                              ".pytest_cache", "*.egg-info")

# --no-project: 프로젝트 pyproject의 리눅스용 .venv 동기화를 건너뛴다(UNC 함정과 같은 뿌리).
BUILD = (
    'uv run --no-project --python 3.13 '
    '--with pyinstaller --with pywebview --with rubymarshal '
    'pyinstaller --onefile --windowed --name modkit '
    '--add-data "web;web" --add-data "modkit/templates;modkit/templates" app.py'
)


def powershell(command: str) -> subprocess.CompletedProcess:
    return subprocess.run([POWERSHELL, "-NoProfile", "-Command", command], text=True)


def main() -> int:
    if WORK.exists():
        shutil.rmtree(WORK)
    shutil.copytree(HERE, WORK, ignore=SKIP)
    print(f"소스 복사: {WORK_WIN}")

    done = powershell(f'Set-Location "{WORK_WIN}"; {BUILD}')
    exe = WORK / "dist" / "modkit.exe"
    if done.returncode != 0 or not exe.is_file():
        print(f"빌드 실패 (returncode={done.returncode}) — 작업 폴더를 남겨둬요: {WORK_WIN}",
              file=sys.stderr)
        return 1

    DIST.mkdir(exist_ok=True)
    out = DIST / "modkit.exe"
    shutil.copy2(exe, out)
    blob = out.read_bytes()
    print(f"산출: {out} · {len(blob) / 1024 / 1024:.1f} MiB · "
          f"sha256 {hashlib.sha256(blob).hexdigest()}")

    shutil.rmtree(WORK, ignore_errors=True)
    sandbox(out)
    return 0


# 실기 테스트 샌드박스 — 릴리스마다 새 exe + 순정 게임 사본 + 빈 보관소를 한 폴더에
# 준비해 둔다(2026-08-04 사용자 요청). 실행은 동봉 bat — MODKIT_STORE를 샌드박스 안
# `mods/`로 돌려 실보관소(~/.modkit/mods)를 더럽히지 않는다.
SANDBOX = Path("/mnt/c/Users/durumii/Downloads/Modkit-Test")
GAME_ZIP = Path("/mnt/c/Users/durumii/Downloads/POKEMON Z V2.18.zip")


def sandbox(exe: Path) -> None:
    import zipfile

    if not GAME_ZIP.is_file():
        print(f"샌드박스 건너뜀 — 순정 게임 zip이 없어요: {GAME_ZIP}")
        return
    shutil.rmtree(SANDBOX, ignore_errors=True)
    SANDBOX.mkdir(parents=True)
    with zipfile.ZipFile(GAME_ZIP) as zf:
        zf.extractall(SANDBOX)  # zip 루트가 "Pokemon Z V2.18" 폴더 하나다
    shutil.copy2(exe, SANDBOX / "modkit.exe")
    (SANDBOX / "mods").mkdir()
    (SANDBOX / "modkit-test.bat").write_text(
        '@echo off\r\nset "MODKIT_STORE=%~dp0mods"\r\n'
        'start "" "%~dp0modkit.exe"\r\n', encoding="ascii")
    print(f"샌드박스 준비: {SANDBOX} (순정 사본 + 빈 mods/ + modkit-test.bat)")


if __name__ == "__main__":
    sys.exit(main())
