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


# 아는 게임의 표시명과 배너(설치본 안 상대경로) — Game.ini Title이 열쇠다.
# 표시명은 게임 라이브러리 프로젝트를 따른다(2026-08-04 조사): 한국어 정식 표기가
# 있는 것은 둘뿐(eventday.py PROPER — 소원의 별·어나더 레드)이고, 나머지는 거기서도
# 원어에 Pokémon 악센트 접두만 붙인다(shownname.py). 임의 음차를 만들지 않는다.
# 배너는 각 설치본의 실물 그림(2026-08-04 실측 — 경로·크기·픽셀 확인).
KNOWN_GAMES = {
    # 순정 배포판의 Title은 "Pokemon Z"고, "Pokemon Z Fangame"은 한글패치가 덮은
    # 제목이다(2026-08-04 실측 — 원본 아카이브 Game.ini 대조). 둘 다 받는다.
    "Pokemon Z": {"label": "포켓몬 Z", "banner": "Graphics/Titles/pokelogo.png"},
    "Pokemon Z Fangame": {"label": "포켓몬 Z", "banner": "Graphics/Titles/pokelogo.png"},
    "Pokemon: Wishing Star": {"label": "소원의 별", "banner": "Graphics/Titles/title.png"},
    "Pokemon: Another Red": {"label": "어나더 레드", "banner": "Graphics/Titles/title.png"},
    "Pokemon Anil": {"label": "Pokémon Anil", "banner": "Graphics/Titles/title.png"},
    "Nova": {"label": "Pokémon Nova", "banner": "Graphics/Titles/title.png"},
    "Pokemon Opalo": {"label": "Pokémon Ópalo", "banner": "Graphics/Titles/pokelogo.png"},
    "Realidea System": {"label": "Pokémon Realidea System", "banner": "Graphics/Pictures/logo.png"},
    "Reminiscencia": {"label": "Pokémon Reminiscencia", "banner": "Graphics/Titles/luciustitle.png"},
    "Pokemon Tectonic": {"label": "Pokémon Tectonic", "banner": "Graphics/Titles/title.png"},
    "Pokemon Decay": {"label": "Pokémon Decay", "banner": "Graphics/Titles/title1.png"},
}

# 아는 게임이 아니어도 시도해 볼 만한 타이틀 화면 자리 — Essentials 관례.
BANNER_FALLBACKS = ("Graphics/Titles/title.png", "Graphics/Pictures/title.png",
                    "Graphics/Pictures/splash.png")


def identify(game_dir: Path | str) -> dict:
    """이 폴더의 신원 — 제목, 아는 게임이면 한국어 표시명, 배너 이미지 경로."""
    game_dir = Path(game_dir)
    title = read_title(game_dir)
    known = KNOWN_GAMES.get(title)
    tries = ([known["banner"]] if known and known["banner"] else []) + list(BANNER_FALLBACKS)
    banner = next((game_dir / rel for rel in tries if (game_dir / rel).is_file()), None)
    return {
        "title": title,
        "known": known is not None,
        "label": known["label"] if known else title,
        "banner": str(banner) if banner else "",
    }


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
