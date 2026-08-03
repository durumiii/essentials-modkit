"""설치본의 신원 — 게임 제목과 시각.

원본 라이브러리 entry.read_title의 이식본이다. 옛 RGSS 엔진은 Game.ini를 ANSI
(한국어 Windows에선 CP949)로 읽으므로 UTF-8이 먼저, 안 읽히면 CP949로 다시.
"""
import configparser
from datetime import datetime
from pathlib import Path


def read_title(game_dir: Path | str) -> str:
    """`Game.ini`의 Title을 읽고, 없거나 깨졌으면 폴더 이름을 쓴다."""
    game_dir = Path(game_dir)
    ini = game_dir / "Game.ini"
    if ini.is_file():
        for encoding in ("utf-8", "cp949"):
            parser = configparser.ConfigParser()
            try:
                parser.read(ini, encoding=encoding)
                title = parser.get("Game", "Title", fallback="").strip()
            except (configparser.Error, UnicodeDecodeError):
                continue
            if title:
                return title
    return game_dir.name


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
