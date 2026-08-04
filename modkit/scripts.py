"""게임이 들고 있는 루비 코드에서 **무엇이 정의돼 있는지** 읽는다.

팬게임은 엔진(`Data/Scripts.rxdata`)을 그대로 두고 플러그인 묶음
(`Data/PluginScripts.rxdata`)만 갈아 끼우는 형태가 흔하다. 그래서 엔진만 봐서는
두 판이 정말 같은지 알 수 없고, 세이브가 열릴지도 알 수 없다 — 세이브에 담긴 객체의
클래스가 플러그인 쪽에 정의돼 있을 수 있기 때문이다.

두 파일 모두 `[이름, zlib으로 눌린 소스]` 꼴의 목록이다. 플러그인 묶음은 한 겹 더 싸여
있어서 `[플러그인명, 메타, [[스크립트명, 눌린 소스], ...]]`으로 들어 있다.
"""
import re
import zlib
from pathlib import Path

from . import rubyread

CORE = "Data/Scripts.rxdata"
PLUGINS = "Data/PluginScripts.rxdata"
CLASS_LINE = re.compile(r"^\s*class\s+([A-Z]\w*(?:::\w+)*)", re.MULTILINE)


def defined_classes(game_dir: Path | str) -> set:
    """이 게임에서 정의하는 클래스 이름 전부 — 엔진과 플러그인을 합쳐서."""
    found = set()
    for name, source in sources(game_dir):
        found.update(CLASS_LINE.findall(source))
    return found


def plugin_names(game_dir: Path | str) -> set:
    """얹혀 있는 플러그인 이름들."""
    bundle = Path(game_dir) / PLUGINS
    if not bundle.is_file():
        return set()
    return {str(entry[0]) for entry in _unpack(bundle) if entry}


def sources(game_dir: Path | str):
    """(이름, 소스)를 하나씩 내놓는다. 엔진 먼저, 그다음 플러그인."""
    game_dir = Path(game_dir)

    # 한쪽이 안 읽혀도 다른 쪽은 내놓는다 — 코어가 깨졌다고 플러그인까지 못 볼 이유가 없다.
    for entry in _unpack(game_dir / CORE):
        yield _name(entry[1]), _unzip(entry[2])

    for entry in _unpack(game_dir / PLUGINS):
        plugin = _name(entry[0])
        for script in entry[2] or []:
            yield f"{plugin}/{script[0]}", _unzip(script[1])


def _name(value) -> str:
    """섹션 제목 — 루비가 쓴 실물은 생 바이트다.

    `str()`로 감싸면 `b'MOD:...'` 꼴 repr이 나온다. 그 상태로는 이름에 견주는 쪽이
    전부 헛돈다(2026-08-04 실측 — 이미 얹힌 모드를 걸러 내는 검사가 안 먹었다).
    """
    return value.decode("utf-8", "replace") if isinstance(value, (bytes, bytearray)) else str(value)


def _unpack(path: Path) -> list:
    """묶음 하나를 푼다. 없거나 못 읽으면 빈 목록."""
    if not path.is_file():
        return []
    try:
        packed = rubyread.loads(path.read_bytes())
    except Exception:
        return []
    return packed if isinstance(packed, list) else []


def _unzip(blob) -> str:
    try:
        return zlib.decompress(bytes(blob)).decode("utf-8", "replace")
    except (zlib.error, TypeError):
        return ""
