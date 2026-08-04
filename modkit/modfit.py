"""모드가 이 설치본에 맞는지 따진다.

플러그인으로 코어 메서드를 다시 정의하는 방식의 위험은 하나다 — 게임이 업데이트로 그
메서드를 고쳤는데 우리 재정의가 낡은 코드를 되살리는 것. 조용히 어긋나므로 눈으로는
알아채기 어렵다.

그래서 모드를 꺼낼 때 **그 모드가 덮어쓰는 메서드의 원문을 함께 떠 둔다**(기준선).
얹을 때는 대상 설치본에서 같은 메서드를 다시 읽어 기준선과 대조한다. 같으면 맞는 것이고,
다르면 무엇이 달라졌는지 보여 주고 멈춘다.

이름이 같은지만 보지 않는 이유는 앞서 정한 것과 같다 — 이름이 같다고 같은 물건을 가리키는
법이 없다. 여기서는 **원문 자체**를 견준다.

기준선을 모드 안에 두므로 꺼내 온 설치본이 사라져도 대조할 수 있다.
"""
import re
from dataclasses import dataclass
from pathlib import Path

from . import scripts
from .modstore import MOD_MARK

BASELINE = "baseline"
# `class X`·`module X`, 그리고 이름 없는 `class << self`. 셋 다 def를 담는 그릇이다.
BLOCK_LINE = re.compile(
    r"^(?P<indent>[ \t]*)(?:(?:class|module)\s+(?P<name>[A-Z][\w:]*)|class\s*<<\s*self\b)",
    re.MULTILINE,
)
DEF_LINE = re.compile(
    r"^(?P<indent>[ \t]*)def\s+(?P<singleton>self\.)?(?P<name>[\w?!=\[\]<>+\-*/]+)",
    re.MULTILINE,
)
PLACE = re.compile(r"([#.])")

FITS, CHANGED, UNKNOWN = "fits", "changed", "unknown"


@dataclass(frozen=True)
class Fit:
    verdict: str
    findings: tuple  # 사람이 읽는 줄
    checked: int  # 대조한 메서드 수


def overrides(mod_scripts) -> set:
    """이 모드가 다시 정의하는 자리들.

    자리 표기는 두 가지다 — 인스턴스 메서드는 `Klass#method`, 싱글턴(`class << self`
    안이나 `def self.` 꼴)은 `Klass.method`. 루비에서 둘은 이름이 같아도 서로 다른
    메서드라서, 한 표기로 뭉개면 겹침 판정과 기준선이 엉뚱한 짝을 맞춘다.
    """
    found = set()
    for _, source in mod_scripts:
        for block in _class_blocks(source):
            for match in DEF_LINE.finditer(block.body):
                found.add(f"{block.name}{_sep(block, match)}{match.group('name')}")
    return found


def take_baseline(game_dir: Path | str, mod_scripts, skip: str = "") -> dict:
    """모드가 덮어쓰는 메서드의 **게임 쪽 원문**을 뜬다.

    `skip`은 무시할 플러그인 이름이다 — 이미 얹혀 있는 그 모드 자신을 기준선으로 뜨면
    자기 코드를 원본으로 착각한다.
    """
    wanted = overrides(mod_scripts)
    if not wanted:
        return {}

    sources = [one for one in scripts.sources(game_dir) if not _is_mine(one[0], skip)]
    return find_methods(sources, wanted)


def check(game_dir: Path | str, mod, skip_self: bool = True, sources=None) -> Fit:
    """모드의 기준선과 이 설치본의 지금 원문을 대조한다.

    `sources`를 주면 그것을 쓴다. 한 게임에 모드가 여럿이면 같은 스크립트를 모드 수만큼
    다시 풀게 되므로, 부르는 쪽이 한 번 읽어 돌려쓸 수 있게 열어 둔다.
    """
    if not getattr(mod, "scripts", ()) and getattr(mod, "assets", ()):
        return _asset_fit(Path(game_dir), mod)

    if not getattr(mod, "baseline_taken", False):
        return Fit(
            verdict=UNKNOWN,
            findings=("원본 코드를 저장하기 전에 가져온 모드예요. 다시 가져오면 확인할 수 있어요.",),
            checked=0,
        )

    baseline = read_baseline(mod)
    if not baseline:
        # 떠 봤는데 빈 것은 "게임 코드를 안 건드린다"는 뜻이다. 새 클래스만 더하는 모드가 그렇다.
        return Fit(verdict=FITS, findings=("게임 코드를 수정하지 않는 모드예요.",), checked=0)

    read = scripts.sources(game_dir) if sources is None else sources
    sources = [one for one in read if not (skip_self and _is_mine(one[0], mod.name))]

    now_by_place = find_methods(sources, list(baseline))

    findings = []
    for place, was in sorted(baseline.items()):
        now = now_by_place.get(place)
        if now is None:
            findings.append(f"{place}가 이 버전에는 없어요 — 모드가 수정할 대상이 사라졌어요")
        elif _tidy(now) != _tidy(was):
            findings.append(f"{place}가 이 버전에서 바뀌었어요 — 모드가 예전 코드로 되돌려요")

    verdict = CHANGED if findings else FITS
    return Fit(verdict=verdict, findings=tuple(findings), checked=len(baseline))


def read_baseline(mod) -> dict:
    """모드에 떠 둔 기준선."""
    room = Path(mod.folder) / BASELINE
    if not room.is_dir():
        return {}
    found = {}
    for path in sorted(room.glob("*.rb")):
        found[path.stem.replace("__", "#")] = path.read_text(encoding="utf-8")
    return found


def write_baseline(folder: Path | str, baseline: dict) -> Path:
    """기준선을 모드 옆에 눕힌다."""
    room = Path(folder) / BASELINE
    room.mkdir(parents=True, exist_ok=True)
    for stale in room.glob("*.rb"):
        stale.unlink()
    for place, source in baseline.items():
        (room / f"{place.replace('#', '__')}.rb").write_text(source, encoding="utf-8")
    return room


def find_method(sources, place: str) -> str | None:
    """여러 스크립트에서 한 자리(`Klass#method` 또는 `Klass.method`)의 원문을 찾는다."""
    return find_methods(sources, [place]).get(place)


def find_methods(sources, wanted) -> dict:
    """찾을 것들을 한 번에 찾는다 — 자리 → 원문.

    메서드마다 따로 찾으면 게임의 스크립트 전부를 그 횟수만큼 다시 훑는다. 게임 하나의
    스크립트가 수천 개라 그 되풀이가 화면을 4초씩 붙잡고 있었다(2026-07-29).

    클래스 이름은 꼬리로 견준다 — 모드가 `Foo::Bar`로 적고 게임이 `Bar`로 열어 두는
    일이 흔하다. 돌려주는 키는 부르는 쪽이 물어본 자리 그대로다.

    같은 메서드가 여러 번 정의돼 있으면 **마지막 것**이 이긴다 — 게임이 배열 순서대로
    읽어서 나중 정의가 앞의 것을 덮기 때문이다.
    """
    by_tail = {}
    for place in wanted:
        name, sep, method = _split(place)
        by_tail.setdefault(name.split("::")[-1], {})[sep + method] = place

    found = {}
    for _, text in sources:
        for block in _class_blocks(text):
            here = by_tail.get(block.name.split("::")[-1])
            if not here:
                continue
            for match in DEF_LINE.finditer(block.body):
                place = here.get(_sep(block, match) + match.group("name"))
                if place is None:
                    continue
                source = _method_source(block.body, match)
                if source is not None:
                    found[place] = source
    return found


@dataclass(frozen=True)
class _Block:
    name: str
    body: str
    singleton: bool = False


def _class_blocks(text: str, name: str = "", singleton: bool = False):
    """`class X`·`module X`·`class << self` … 짝이 맞는 `end`까지.

    몸통에는 **직계 `def`만** 남긴다 — 안쪽 블록 구간은 도려내고 그 블록을 따로 내놓는다.
    그러지 않으면 `class << self` 안의 싱글턴 메서드가 바깥 이름으로도 잡히고, 중첩
    클래스의 메서드가 바깥 클래스의 것으로도 잡힌다.

    `class << self`는 자기 이름이 없어 감싼 블록의 이름을 물려받는다.
    """
    mine, at = [], 0
    for match in BLOCK_LINE.finditer(text):
        if match.start() < at:  # 이미 안쪽 블록으로 넘긴 구간
            continue
        indent = match.group("indent")
        line_end = text.find("\n", match.end())
        line_rest = text[match.end():line_end if line_end >= 0 else len(text)]
        if re.search(r";\s*end\b", line_rest):
            # `class X < Exception; end` 한 줄짜리 — 제 end를 못 찾으면 뒤 전체를
            # 삼킨다(실물: Z의 PokeBattle_Battle 안 17만 자가 유령이 됐다).
            mine.append(text[at:match.start()])
            at = line_end if line_end >= 0 else len(text)
            continue
        stop = _closing(text, match.end(), indent)
        mine.append(text[at:match.start()])
        at = stop
        inner = match.group("name")
        yield from _class_blocks(
            text[match.end():stop],
            name=name if inner is None else inner,
            singleton=inner is None,
        )
    mine.append(text[at:])
    if name:
        yield _Block(name=name, body="".join(mine), singleton=singleton)


def _is_mine(section: str, mod_name: str) -> bool:
    """이 섹션이 기준선·대조에서 빠져야 하는가.

    **주입 섹션(MOD:*)은 이름을 불문하고 전부 뺀다** — 자기 것만 빼면 옆 모드의
    재정의를 게임 원문으로 떠 간다(2026-08-04 실기: 모드 4종이 서로의 코드를
    기준선으로 굳혀 순정에서 전부 차단되고 순환 의존까지 생겼다). 묶음형은 섹션
    제목이 `<모드명>/<파일>`이라 자기 이름으로 거른다.
    """
    if section.startswith(MOD_MARK):
        return True  # 어떤 모드의 주입이든 게임 원문이 아니다
    return bool(mod_name) and section.startswith(f"{mod_name}/")


_OPENER = None  # 지연 컴파일 — 아래 _closing 참고


def _closing(text: str, start: int, indent: str) -> int:
    """블록의 닫는 `end` 위치 — 같은 들여쓰기의 `end`를 처음 만난 곳이 아니다.

    실물 코어에는 클래스 안에 들여쓰기 0의 `if…end`가 박혀 있다(Z의
    PokeBattle_Battle 실측 — 그 end에서 끊으면 뒤쪽 메서드 16만 자가 유령이 된다).
    같은 들여쓰기에서 여는 키워드를 만나면 하나 세고, `end`를 만나면 세어 둔 것부터
    닫는다. do 블록·heredoc까지는 안 본다 — 같은 들여쓰기 줄만 보는 어림이다.
    """
    global _OPENER
    if _OPENER is None:
        _OPENER = re.compile(
            r"^(if|unless|while|until|for|begin|case|def|class|module)\b")
    depth = 0
    at = start
    probe = re.compile(rf"^{re.escape(indent)}(\S.*)$", re.MULTILINE)
    for line in probe.finditer(text, start):
        body = line.group(1)
        if body == "end" or body.startswith(("end ", "end\r")):
            if depth == 0:
                return max(start, line.start() - 1)  # 닫는 줄 앞 개행까지가 몸통
            depth -= 1
        elif _OPENER.match(body):
            depth += 1
    return len(text)


def _sep(block: _Block, def_match) -> str:
    """이 `def`가 앉은 자리의 구분자 — 싱글턴이면 `.`, 아니면 `#`."""
    return "." if block.singleton or def_match.group("singleton") else "#"


def _split(place: str):
    """`Klass#method` / `Klass.method` → (클래스, 구분자, 메서드)."""
    name, sep, method = PLACE.split(place, maxsplit=1)
    return name, sep, method


def _method_source(body: str, match) -> str | None:
    """`def …`부터 같은 들여쓰기의 `end`까지."""
    indent = match.group("indent")
    lines = body[match.start():].splitlines(keepends=True)
    closing = indent + "end"
    for index, line in enumerate(lines[1:], start=1):
        if line.rstrip("\r\n") == closing:
            return "".join(lines[: index + 1])
    return None


def _tidy(source: str) -> str:
    """줄바꿈과 뒤 공백 차이는 다름으로 보지 않는다."""
    return "\n".join(line.rstrip() for line in source.replace("\r\n", "\n").split("\n")).strip()


def _asset_fit(game_dir: Path, mod) -> Fit:
    """파일만 갈아 끼우는 모드의 대조 — 덮을 자리의 **원본**이 모드가 아는 원본인가.

    코드 대조와 같은 물음이다: 게임이 업데이트로 그 파일을 고쳤는데 우리 판이 낡은 것을
    되살리면 조용히 어긋난다. 모드가 `replaces_crc`(꺼내 올 때의 원본 지문)를 들고 있으면
    지금 설치본의 그 자리와 견준다. 이미 설치돼 있으면 원본은 `.orig`에 있다.
    새로 놓는 파일(원본이 없던 자리)은 대조할 것이 없어 건너뛴다.
    """
    import zlib

    checked, findings = 0, []
    for one in mod.assets:
        expect = one.get("replaces_crc")
        if expect is None:
            continue
        target = game_dir / one["install_to"]
        backup = target.with_name(target.name + ".orig")
        original = backup if backup.is_file() else target
        if not original.is_file():
            # 대응 파일이 없는 자리는 모드가 새로 놓는 자리다 — 판이 바뀐 게 아니다
            # (하비스트 때 남의 파일 위에서 지문이 새겨진 사고의 방어이기도 하다).
            continue
        running = 0
        with open(original, "rb") as handle:
            while chunk := handle.read(1 << 20):
                running = zlib.crc32(chunk, running)
        checked += 1
        if running != expect:
            findings.append(f"{one['install_to']} — 원본이 이 모드가 아는 판과 달라요.")

    if findings:
        return Fit(verdict=CHANGED, findings=tuple(findings), checked=checked)
    if not checked:
        return Fit(verdict=UNKNOWN, findings=("대조할 원본 지문이 없는 모드예요.",), checked=0)
    return Fit(verdict=FITS, findings=(f"덮는 자리의 원본 {checked}개가 그대로예요.",), checked=checked)
