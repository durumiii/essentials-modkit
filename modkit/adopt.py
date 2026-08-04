"""맨 zip 입양 — mod.json 없는 야생 배포물을 기계 규칙으로 카드화한다.

야생 배포물에는 카드가 없다(2026-08-04 표본 5개 전부). 배치는 세 꼴로 갈렸다:
게임 상대경로 그대로, 겉포장 폴더 하나 아래, 게임 상대경로가 아닌 조각(Pictures/
→ Graphics/Pictures/). 셋 다 대상 게임의 실제 트리를 기준으로 기계 판별이 된다 —
그래서 입양은 게임 폴더를 함께 받는다.

판단이 필요한 자리는 기본값으로 후퇴한다: 이름은 zip 파일명, 설명은 출처 한 줄,
기반 선언은 통짜 rxdata의 최소 차이 추정(moddiff)이 채운다.
"""
import json
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from . import gameinfo, moddiff
from .modstore import CARD, _draft_touches, _game_folder, _safe

GAME_ROOTS = {"Data", "Graphics", "Audio", "Fonts", "PBS", "Plugins"}
GAME_FILES = {"mkxp.json"}
WHOLESALE = ("Data/Scripts.rxdata", "Data/PluginScripts.rxdata")


class NotAMod(Exception):
    """게임 트리에 맞는 파일이 하나도 없다 — 공략 문서 묶음 같은 것."""


@dataclass(frozen=True)
class Adopted:
    name: str
    folder: Path
    assets: tuple
    kept: tuple       # 지도 밖 파일 — 폴더에 보관만, 설치 목록엔 없다
    warnings: tuple
    notes: tuple      # 통짜 rxdata 판독 결과 등 사람이 읽을 관찰


def adopt(zip_path: Path | str, game_dir: Path | str, store: Path | str,
          name: str = "") -> Adopted:
    zip_path, game_dir, store = Path(zip_path), Path(game_dir), Path(store)
    name = name or zip_path.stem

    with zipfile.ZipFile(zip_path) as zf:
        members = [n for n in zf.namelist() if not n.endswith("/")]
        for member in members:
            if _escapes(member):
                raise NotAMod(f"경로 탈출 항목이에요: {member}")
        files = {_unwrap(members)(m): zf.read(m) for m in members}

    placed, kept = _place(files, game_dir)
    if not placed:
        raise NotAMod("게임에 설치할 파일이 하나도 없어요 — 모드가 아닌 것 같아요.")

    game = gameinfo.read_title(game_dir)
    folder = store / _game_folder(game) / _safe(name)
    folder.mkdir(parents=True, exist_ok=True)

    assets, warnings, same = [], [], []
    for install_to, body in sorted(placed.items()):
        target = folder / install_to
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        one = {"file": install_to, "install_to": install_to}
        original = _original(game_dir, install_to)
        if original is not None:
            was = original.read_bytes()
            one["replaces_crc"] = zlib.crc32(was)
            if was == body:
                same.append(install_to)
        assets.append(one)
    if same:
        heads = ", ".join(same[:3]) + (" 등" if len(same) > 3 else "")
        warnings.append(
            f"설치본과 바이트가 같은 파일 {len(same)}개 ({heads}) — 원본 그대로 동봉했거나 "
            "이미 적용된 판이에요.")
    for rel, body in sorted(kept.items()):
        target = folder / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)

    card = {
        "name": name, "game": game,
        "description": f"{zip_path.name}에서 입양한 모드예요. 설명은 아직 사람이 안 적었어요.",
        "harvested_at": gameinfo.now(),
        "scripts": [], "assets": assets,
        "touches": _draft_touches([], assets),
    }
    notes = _wholesale_notes(placed, game_dir, store, _game_folder(game), name, card)
    (folder / CARD).write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
    return Adopted(name=name, folder=folder, assets=tuple(assets),
                   kept=tuple(sorted(kept)), warnings=tuple(warnings), notes=tuple(notes))


def _unwrap(members):
    """겉포장 폴더 하나가 전부를 감싸면 벗긴다 — 그 폴더가 게임 뿌리 이름이 아닐 때만."""
    heads = {PurePosixPath(m).parts[0] for m in members}
    if len(heads) == 1 and (wrap := next(iter(heads))) not in GAME_ROOTS | GAME_FILES \
            and all(len(PurePosixPath(m).parts) > 1 for m in members):
        return lambda m: str(PurePosixPath(*PurePosixPath(m).parts[1:]))
    return lambda m: m


def _place(files: dict, game_dir: Path):
    """각 파일의 설치 자리 — 게임 상대경로면 그대로, 조각이면 게임 트리 꼬리 대조."""
    placed, kept, tree = {}, {}, None
    for rel, body in files.items():
        parts = PurePosixPath(rel).parts
        if parts[0] in GAME_ROOTS or rel in GAME_FILES:
            placed[rel] = body
            continue
        if tree is None:  # 조각이 있을 때만 게임 트리를 훑는다 — 수만 파일이라 공짜가 아니다
            tree = [p.relative_to(game_dir).parts for p in game_dir.rglob("*") if p.is_file()]
        matches = [t for t in tree if t[-len(parts):] == parts]
        if len(matches) == 1:
            placed[str(PurePosixPath(*matches[0]))] = body
        else:
            kept[rel] = body
    return placed, kept


def _original(game_dir: Path, install_to: str) -> Path | None:
    """이 자리의 원본 — 이미 덮인 자리는 `.orig`가 원본이다(modfit._asset_fit과 같은 눈)."""
    target = game_dir / install_to
    backup = target.with_name(target.name + ".orig")
    if backup.is_file():
        return backup
    return target if target.is_file() else None


def _wholesale_notes(placed, game_dir, store, game_folder, my_name, card) -> list:
    """통짜 rxdata의 실제 발자국 — 기반을 추정해 카드의 requires·order를 채운다."""
    notes = []
    for install_to in WHOLESALE:
        if install_to not in placed:
            continue
        candidates, original = [], _original(game_dir, install_to)
        if original is not None:
            candidates.append(("(원본)", original.read_bytes()))
        for other_card in sorted((store / game_folder).glob(f"*/{CARD}")):
            other = json.loads(other_card.read_text(encoding="utf-8"))
            shipped = other_card.parent / install_to
            if other.get("name") != my_name and shipped.is_file():
                candidates.append((other["name"], shipped.read_bytes()))
        if not candidates:
            continue
        [(base, delta), *rest] = moddiff.find_base(placed[install_to], candidates)
        spots = ", ".join((delta.changed + delta.added + delta.removed)[:10]) or "차이 없음"
        notes.append(f"{install_to}: 기반은 {base} — 다른 섹션 {delta.count}개 ({spots})")
        if base != "(원본)" and base not in card.get("requires", ()):  # 파일 둘이 같은 기반이면 한 번만
            card.setdefault("requires", []).append(base)
            card.setdefault("order", {"after": []})["after"].append(base)
    return notes


def _escapes(member: str) -> bool:
    p = PurePosixPath(member)
    return p.is_absolute() or ".." in p.parts or (len(p.parts) > 0 and ":" in p.parts[0])
