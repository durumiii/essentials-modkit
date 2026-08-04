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


# 아는 게임의 한국어 표시명 — Game.ini Title이 열쇠다. 실측으로 판별해 본 게임만
# 올린다(2026-08-04 아홉 게임). 모르는 게임은 Title 그대로 보여 주면 된다.
KNOWN_GAMES = {
    "Pokemon Z Fangame": "포켓몬 Z 팬게임",
    "Pokemon: Wishing Star": "포켓몬 소원의 별",
    "Pokemon: Another Red": "포켓몬 어나더레드",
    "Pokemon Anil": "포켓몬 아닐",
    "Nova": "포켓몬 노바",
    "Pokemon Opalo": "포켓몬 오팔로",
    "Realidea System": "포켓몬 레알리데아 시스템",
    "Reminiscencia": "포켓몬 레미니센시아",
    "Pokemon Tectonic": "포켓몬 텍토닉",
    "Pokemon Decay": "포켓몬 디케이",
}


def identify(game_dir: Path | str) -> dict:
    """이 폴더의 신원 — 제목과, 아는 게임이면 한국어 표시명."""
    title = read_title(game_dir)
    label = KNOWN_GAMES.get(title)
    return {"title": title, "known": label is not None, "label": label or title}


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
