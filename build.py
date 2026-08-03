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
    return 0


if __name__ == "__main__":
    sys.exit(main())
