"""깨끗한 원본의 지문을 뜨고, 설치본을 대조해 넷으로 가른다.

판정: 원본 일치(intact) / 아는 변경(known — 보관소 카드가 설명) /
외래(foreign — 옛 패치 흔적) / 누락(missing). 도구 자신의 백업(.orig)은
backups로 따로 선다. 지문은 CRC32 — modassets의 replaces_crc와 한 벌이다.
"""
import fnmatch
import json
import zlib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_EXCLUDE = (
    "Saves/*", "*.sav", "LastSave.dat", "*.ini.bak", "screenshot*",
    "_quarantine/*", "modkit-log.jsonl", "manifest.json",
)
BACKUP_SUFFIXES = (".orig",)


@dataclass(frozen=True)
class Diagnosis:
    intact: tuple
    known: tuple    # (상대경로, 모드명)
    foreign: tuple
    missing: tuple
    backups: tuple


def _crc(path: Path) -> int:
    crc = 0
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            crc = zlib.crc32(chunk, crc)
    return crc


def _excluded(rel: str, patterns) -> bool:
    return any(fnmatch.fnmatch(rel, p) for p in patterns)


def capture(game_dir, game="", version="", exclude=None) -> dict:
    """`game`을 안 주면 설치본 제목으로 채운다 — 빈 값이면 진단의 모드 소유 판정이
    죽는다(shelf(game="")가 전부 걸러진다)."""
    from . import gameinfo
    game_dir = Path(game_dir)
    game = game or gameinfo.read_title(game_dir)
    patterns = tuple(exclude or DEFAULT_EXCLUDE)
    files = {}
    for p in sorted(game_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(game_dir).as_posix()
        if _excluded(rel, patterns) or rel.endswith(BACKUP_SUFFIXES):
            continue
        files[rel] = [p.stat().st_size, _crc(p)]
    return {"modkit_manifest": 1, "game": game, "version": version,
            "exclude": list(patterns), "files": files}


def save(manifest: dict, path) -> None:
    Path(path).write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")


def load(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _owned_paths(store, manifest: dict, game_dir: Path) -> dict:
    """모드가 소유한 경로 → 모드 이름. 카드 assets의 install_to 전부, 그리고
    스크립트 있는 모드의 코어 경로(그 모드가 이 설치본에 실제로 설치돼 있을 때만)."""
    from . import modstore

    try:
        installed_names = set(modstore.installed(game_dir))
    except modstore.NoBundle:
        installed_names = set()

    owned = {}
    for mod in modstore.shelf(store, game=manifest.get("game")):
        for asset in mod.assets or ():
            owned[asset["install_to"]] = mod.name
        if mod.scripts and mod.name in installed_names:
            owned[modstore.SCRIPTS] = mod.name
            owned[modstore.BUNDLE] = mod.name
    return owned


def diagnose(game_dir, manifest: dict, store=None) -> Diagnosis:
    game_dir = Path(game_dir)
    patterns = tuple(manifest.get("exclude") or DEFAULT_EXCLUDE)

    current = {}
    backups = []
    for p in sorted(game_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(game_dir).as_posix()
        if _excluded(rel, patterns):
            continue
        if rel.endswith(BACKUP_SUFFIXES):
            backups.append(rel)
            continue
        current[rel] = [p.stat().st_size, _crc(p)]

    owned = _owned_paths(store, manifest, game_dir) if store is not None else {}

    files = manifest["files"]
    intact, known, foreign, missing = [], [], [], []
    for rel in sorted(set(files) | set(current)):
        if rel not in current:
            missing.append(rel)
        elif rel in files and files[rel] == current[rel]:
            intact.append(rel)
        elif rel in owned:
            known.append((rel, owned[rel]))
        else:
            foreign.append(rel)

    return Diagnosis(
        intact=tuple(intact),
        known=tuple(known),
        foreign=tuple(foreign),
        missing=tuple(missing),
        backups=tuple(sorted(backups)),
    )


def quarantine(game_dir, rel_paths, at: str | None = None) -> Path:
    """외래 파일을 게임 폴더 안 격리함으로 옮긴다. 지우는 일은 하지 않는다."""
    from . import gameinfo
    game_dir = Path(game_dir)
    stamp = (at or gameinfo.now()).replace(":", "-")
    box = game_dir / "_quarantine" / stamp
    moved = []
    for rel in rel_paths:
        src = (game_dir / rel).resolve()
        if not src.is_relative_to(game_dir.resolve()):
            raise ValueError(f"게임 폴더 밖이에요: {rel}")
        dst = box / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        moved.append(rel)
    return box


def restore(game_dir, box: Path) -> dict:
    """격리함 하나를 원위치한다.

    되돌릴 자리에 파일이 이미 있으면 덮지 않고 격리함에 남긴다 — 되돌리기가 새 파일을
    조용히 잡아먹으면 격리가 파괴 동사가 된다. 남긴 것이 있으면 그 가지도 남는다.
    """
    game_dir, box = Path(game_dir), Path(box)
    restored, kept = [], []
    for p in sorted(box.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(box).as_posix()
        dst = game_dir / rel
        if dst.exists():
            kept.append(rel)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        p.rename(dst)
        restored.append(rel)
    for d in sorted(box.rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    if not any(box.iterdir()):
        box.rmdir()
    return {"restored": restored, "kept": kept}
