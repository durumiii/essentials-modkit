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


# 표시명 규칙은 게임 라이브러리(fangame-library)의 shownname 방식이다 — 임의 번역
# 없이 원제에 Pokémon 악센트만 살리고, 접두가 필요한 변칙만 표로 받는다(2026-08-04
# 사용자 교정: "포켓몬 Z" 같은 음차·번역이 아니라 "Pokémon Z Fangame"이 떠야 한다).
# 배너는 각 설치본의 실물 그림(2026-08-04 실측 — 경로·크기·픽셀 확인).
KNOWN_GAMES = {
    # 순정 배포판의 Title은 "Pokemon Z"고, "Pokemon Z Fangame"은 한글패치가 덮은
    # 제목이다(원본 아카이브 Game.ini 대조). 둘 다 같은 게임으로 받는다.
    "Pokemon Z": {"label": "Pokémon Z Fangame", "banner": "Graphics/Titles/pokelogo.png"},
    "Pokemon Z Fangame": {"label": "Pokémon Z Fangame", "banner": "Graphics/Titles/pokelogo.png"},
    "Pokemon: Wishing Star": {"label": None, "banner": "Graphics/Titles/title.png"},
    "Pokemon: Another Red": {"label": None, "banner": "Graphics/Titles/title.png"},
    "Pokemon Anil": {"label": None, "banner": "Graphics/Titles/title.png"},
    "Nova": {"label": "Pokémon Nova", "banner": "Graphics/Titles/title.png"},
    "Pokemon Opalo": {"label": None, "banner": "Graphics/Titles/pokelogo.png"},
    "Realidea System": {"label": "Pokémon Realidea System", "banner": "Graphics/Pictures/logo.png"},
    "Reminiscencia": {"label": "Pokémon Reminiscencia", "banner": "Graphics/Titles/luciustitle.png"},
    "Pokemon Tectonic": {"label": None, "banner": "Graphics/Titles/title.png"},
    "Pokemon Decay": {"label": None, "banner": "Graphics/Titles/title1.png"},
}

# 아는 게임이 아니어도 시도해 볼 만한 타이틀 화면 자리 — Essentials 관례.
BANNER_FALLBACKS = ("Graphics/Titles/title.png", "Graphics/Pictures/title.png",
                    "Graphics/Pictures/splash.png")


def shown_name(title: str) -> str:
    """유저에게 보여 주는 게임 이름 — 원제에 Pokémon 악센트만 살린다."""
    import re

    return re.sub(r"\bPokemon\b", "Pokémon", title)


def canon(title: str) -> str:
    """게임 신원 비교용 정규형 — 별칭(순정 제목 vs 패치가 덮은 제목)을 한 게임으로 본다.

    표시명(label)이 같으면 같은 게임이다. 카드의 `game`과 설치본 제목이 다른 표기로
    적혀 있어도 서랍·귀속 검사가 갈라놓지 않는다(2026-08-04 실기 — 순정 사본
    "Pokemon Z"에서 "Pokemon Z Fangame"에 매인 모드가 안 보였다).
    """
    known = KNOWN_GAMES.get(title)
    return (known and known["label"]) or shown_name(title)


def identify(game_dir: Path | str) -> dict:
    """이 폴더의 신원 — 제목, 표시명(악센트 보정), 배너 이미지 경로."""
    game_dir = Path(game_dir)
    title = read_title(game_dir)
    known = KNOWN_GAMES.get(title)
    tries = ([known["banner"]] if known and known["banner"] else []) + list(BANNER_FALLBACKS)
    banner = next((game_dir / rel for rel in tries if (game_dir / rel).is_file()), None)
    label = (known and known["label"]) or shown_name(title)
    return {
        "title": title,
        "known": known is not None,
        "label": label,
        "banner": str(banner) if banner else "",
    }


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
