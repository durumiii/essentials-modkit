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

BASELINE = "baseline"
CLASS_LINE = re.compile(r"^(?P<indent>[ \t]*)class\s+(?P<name>[A-Z][\w:]*)", re.MULTILINE)
DEF_LINE = re.compile(r"^(?P<indent>[ \t]*)def\s+(?P<name>[\w?!=\[\]<>+\-*/]+)", re.MULTILINE)

FITS, CHANGED, UNKNOWN = "fits", "changed", "unknown"


@dataclass(frozen=True)
class Fit:
    verdict: str
    findings: tuple  # 사람이 읽는 줄
    checked: int  # 대조한 메서드 수


def overrides(mod_scripts) -> set:
    """이 모드가 다시 정의하는 (클래스, 메서드)들."""
    found = set()
    for _, source in mod_scripts:
        for block in _class_blocks(source):
            for method in _methods_in(block.body):
                found.add((block.name, method))
    return found


def take_baseline(game_dir: Path | str, mod_scripts, skip: str = "") -> dict:
    """모드가 덮어쓰는 메서드의 **게임 쪽 원문**을 뜬다.

    `skip`은 무시할 플러그인 이름이다 — 이미 얹혀 있는 그 모드 자신을 기준선으로 뜨면
    자기 코드를 원본으로 착각한다.
    """
    wanted = overrides(mod_scripts)
    if not wanted:
        return {}

    sources = [
        (name, text)
        for name, text in scripts.sources(game_dir)
        if not (skip and name.startswith(f"{skip}/"))
    ]
    found = find_methods(sources, wanted)
    return {f"{class_name}#{method}": source for (class_name, method), source in found.items()}


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
    sources = [
        (name, text)
        for name, text in read
        if not (skip_self and name.startswith(f"{mod.name}/"))
    ]

    wanted = [tuple(place.partition("#")[::2]) for place in baseline]
    now_by_place = find_methods(sources, wanted)

    findings = []
    for place, was in sorted(baseline.items()):
        class_name, _, method = place.partition("#")
        now = now_by_place.get((class_name, method))
        if now is None:
            findings.append(f"{place}가 이 버전에는 없어요 — 모드가 수정할 대상이 사라졌어요")
        elif _tidy(now) != _tidy(was):
            findings.append(f"{place}가 이 버전에서 바뀌었어요 — 모드가 예전 코드로 되돌립니다")

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


def find_method(sources, class_name: str, method: str) -> str | None:
    """여러 스크립트에서 `class X`의 `def m` 원문을 찾는다."""
    return find_methods(sources, [(class_name, method)]).get((class_name, method))


def find_methods(sources, wanted) -> dict:
    """찾을 것들을 한 번에 찾는다 — `(클래스, 메서드)` → 원문.

    메서드마다 따로 찾으면 게임의 스크립트 전부를 그 횟수만큼 다시 훑는다. 게임 하나의
    스크립트가 수천 개라 그 되풀이가 화면을 4초씩 붙잡고 있었다(2026-07-29).

    같은 메서드가 여러 번 정의돼 있으면 **마지막 것**이 이긴다 — 게임이 배열 순서대로
    읽어서 나중 정의가 앞의 것을 덮기 때문이다.
    """
    by_tail = {}
    for class_name, method in wanted:
        by_tail.setdefault(class_name.split("::")[-1], set()).add((class_name, method))

    found = {}
    for _, text in sources:
        for block in _class_blocks(text):
            for pair in by_tail.get(block.name.split("::")[-1], ()):
                source = _method_source(block.body, pair[1])
                if source is not None:
                    found[pair] = source
    return found


@dataclass(frozen=True)
class _Block:
    name: str
    body: str


def _class_blocks(text: str):
    """`class X` … 짝이 맞는 `end`까지."""
    for match in CLASS_LINE.finditer(text):
        indent = match.group("indent")
        rest = text[match.end():]
        closing = f"\n{indent}end"
        at = rest.find(closing)
        yield _Block(name=match.group("name"), body=rest[: at if at >= 0 else len(rest)])


def _methods_in(body: str) -> set:
    return {match.group("name") for match in DEF_LINE.finditer(body)}


def _method_source(body: str, method: str) -> str | None:
    """`def <method>`부터 같은 들여쓰기의 `end`까지."""
    pattern = re.compile(
        r"^(?P<indent>[ \t]*)def " + re.escape(method) + r"(?![\w?!=])", re.MULTILINE
    )
    match = pattern.search(body)
    if not match:
        return None
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
            findings.append(f"{one['install_to']} — 덮을 원본이 게임에 없어요.")
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
