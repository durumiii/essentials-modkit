"""통짜 rxdata 교체 모드의 실제 발자국을 잰다.

야생 배포물은 Scripts.rxdata를 통째로 덮는 형태가 주류다 — 게임 자체가 통짜
rxdata라 모더도 그 모국어를 쓴다. 통째 파일만 봐서는 무엇을 고친 모드인지 알 수
없으므로, 섹션 단위로 기준판과 대조해 바뀐 자리만 추린다(2026-08-04 실측:
2.3MB 교체본의 실변경이 섹션 셋이었다).

기반이 게임 원본이 아닐 수도 있다 — 한글패치 위에 얹는 패치는 원본과 견주면
수백 섹션이 다르지만 한글패치와 견주면 몇 개만 다르다. **차이가 최소인 후보가
기반이다.**
"""
import zlib
from dataclasses import dataclass

from . import rubyread


@dataclass(frozen=True)
class Diff:
    added: tuple
    removed: tuple
    changed: tuple

    @property
    def count(self) -> int:
        return len(self.added) + len(self.removed) + len(self.changed)


def sections(blob: bytes) -> dict:
    """rxdata 묶음을 {섹션 이름: 원문 바이트}로 편다. 코어·플러그인 묶음 모두.

    실물 코어에는 같은 제목(구분선 섹션)이 되풀이된다 — 두 번째부터 `@2`, `@3`을
    붙여 순서로 짝을 맞춘다.
    """
    entries = rubyread.loads(blob)
    if not isinstance(entries, list):
        return {}
    found = {}
    for entry in entries:
        if not isinstance(entry, list) or len(entry) < 3:
            continue
        if isinstance(entry[2], list):  # 플러그인 묶음 — [이름, 메타, [[스크립트, 본문]]]
            for script in entry[2]:
                _put(found, f"{_text(entry[0])}/{_text(script[0])}", _unzip(script[1]))
        else:  # 코어 — [id, 제목, 본문]
            _put(found, _text(entry[1]), _unzip(entry[2]))
    return found


def diff(base: dict, mine: dict) -> Diff:
    """기준판 대비 이쪽 판 — 더해진 것, 사라진 것, 본문이 다른 것."""
    return Diff(
        added=tuple(sorted(k for k in mine if k not in base)),
        removed=tuple(sorted(k for k in base if k not in mine)),
        changed=tuple(sorted(k for k in mine if k in base and mine[k] != base[k])),
    )


def find_base(mine_blob: bytes, candidates) -> list:
    """이 통짜 판의 기반 추정 — `(이름, rxdata 바이트)` 후보들과 각각 대조한다.

    차이가 작은 순으로 `(이름, Diff)`를 돌려준다. 첫째가 가장 그럴듯한 기반이다.
    """
    mine = sections(mine_blob)
    scored = [(name, diff(sections(blob), mine)) for name, blob in candidates]
    return sorted(scored, key=lambda pair: pair[1].count)


def _put(found: dict, name: str, body) -> None:
    key, n = name, 1
    while key in found:
        n += 1
        key = f"{name}@{n}"
    found[key] = body


def _text(value) -> str:
    return bytes(value).decode("utf-8", "replace") if isinstance(value, (bytes, bytearray)) else str(value)


def _unzip(blob):
    try:
        return zlib.decompress(bytes(blob))
    except (zlib.error, TypeError, ValueError):
        return None
