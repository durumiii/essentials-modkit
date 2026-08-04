"""명령줄 진입점 — new/lint/manifest/diagnose/harvest/apply/remove/shelf.

각 핸들러는 코어 함수(manifest·modstore)를 부르고 사람이 읽을 몇 줄을 찍는다.
종료 코드: 성공 0, 차단·오류 1, 진단에서 외래 발견 2.
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path, PurePosixPath

from . import adopt, declare, manifest, modstore

# onefile exe에서는 소스가 아니라 풀린 임시 폴더(_MEIPASS)에 놓인다.
# --add-data "modkit/templates;modkit/templates"로 구우므로 얼린 상태에서는
# _MEIPASS 바로 아래 modkit/templates, 안 얼렸으면 이 파일 옆 templates.
def _templates_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass) / "modkit" / "templates"
    return Path(__file__).parent / "templates"


def _escapes(rel: str) -> bool:
    """폴더 밖을 가리키는지 — modassets.py의 _inside()와 같은 계열 판정.
    백슬래시 표기(윈도우 exe에서 실경로로 풀림)도 구분자로 본다."""
    if os.path.isabs(rel) or (len(rel) > 1 and rel[1] == ":"):
        return True
    return ".." in PurePosixPath(rel.replace("\\", "/")).parts


def _cmd_new(args) -> int:
    target = args.dir / args.name
    if target.exists():
        print(f"이미 있어요: {target}", file=sys.stderr)
        return 1
    target.mkdir(parents=True)

    card = {
        "name": args.name,
        "game": args.game or "",
        "description": "",
        "scripts": [{"file": "001_Main.rb", "script_name": "001_Main.rb"}],
    }
    (target / "mod.json").write_text(
        json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")

    with open(target / "001_Main.rb", "w", encoding="utf-8", newline="") as f:
        f.write(f"# {args.name} — 여기서부터 쓴다\r\n")

    templates = _templates_dir()
    for fname in ("AGENTS.md", "CLAUDE.md"):
        shutil.copy2(templates / fname, target / fname)

    print(f"모드 뼈대: {target}")
    print("다음: 스크립트를 쓰고 mod.json을 채운 뒤 `modkit lint <폴더>`")
    return 0


def _cmd_lint(args) -> int:
    folder = args.mod_dir
    card_path = folder / "mod.json"
    if not card_path.is_file():
        print("오류 · mod.json — 파일이 없어요 — modkit new로 뼈대를 만들거나 mod.json을 추가해요")
        print("오류 1 · 권장 0")
        return 1
    try:
        card = json.loads(card_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"오류 · mod.json — JSON을 읽을 수 없어요 ({e}) — 문법을 고쳐요")
        print("오류 1 · 권장 0")
        return 1

    errors = []
    warnings = []

    name = card.get("name")
    if not name:
        errors.append("오류 · mod.json:name — 값이 비어 있어요 — 모드 이름을 적어요")

    if not card.get("game"):
        warnings.append("권장 · mod.json:game — 비어 있어요 — 다른 게임 오설치를 못 막아요")
    if not card.get("description"):
        warnings.append("권장 · mod.json:description — 비어 있어요 — 유저 서랍에 설명이 안 떠요")

    scripts = card.get("scripts")
    if scripts is None:
        errors.append("오류 · mod.json:scripts — 키가 없어요 — scripts를 배열로 추가해요(빈 배열도 가능)")
        scripts = []
    elif scripts and not card.get("touches"):
        warnings.append("권장 · mod.json:touches — 없어요 — 겹침 경고를 못 받아요")

    seen_names = set()
    for i, s in enumerate(scripts):
        file = s.get("file")
        if file:
            if _escapes(file):
                errors.append(f"오류 · mod.json:scripts[{i}].file — 폴더를 벗어나요 — 모드 폴더 안 상대경로만 써요")
            elif not (folder / file).is_file():
                errors.append(f"오류 · mod.json:scripts[{i}].file — {folder / file}에 없어요 — 파일을 폴더 안에 두거나 경로를 고쳐요")
        sname = s.get("script_name")
        if sname:
            if sname in seen_names:
                errors.append(f"오류 · mod.json:scripts[{i}].script_name — '{sname}' 중복이에요 — 이름을 다르게 해요")
            seen_names.add(sname)

    for i, a in enumerate(card.get("assets") or []):
        file = a.get("file")
        if file:
            if _escapes(file):
                errors.append(f"오류 · mod.json:assets[{i}].file — 폴더를 벗어나요 — 모드 폴더 안 상대경로만 써요")
            elif not (folder / file).is_file():
                errors.append(f"오류 · mod.json:assets[{i}].file — {folder / file}에 없어요 — 파일을 폴더 안에 두거나 경로를 고쳐요")
        install_to = a.get("install_to")
        if install_to and _escapes(install_to):
            errors.append(f"오류 · mod.json:assets[{i}].install_to — 절대경로거나 상위로 나가요 — 게임 폴더 기준 상대경로만 써요")

    order = card.get("order") or {}
    if name and name in (card.get("requires") or []):
        warnings.append("권장 · mod.json:requires — 자기 이름이 들어 있어요 — 스스로를 가리킬 필요 없어요")
    if name and name in (order.get("after") or []):
        warnings.append("권장 · mod.json:order.after — 자기 이름이 들어 있어요 — 스스로를 가리킬 필요 없어요")
    if name and name in (order.get("before") or []):
        warnings.append("권장 · mod.json:order.before — 자기 이름이 들어 있어요 — 스스로를 가리킬 필요 없어요")

    for line in errors + warnings:
        print(line)
    if errors:
        print(f"오류 {len(errors)} · 권장 {len(warnings)}")
        return 1
    print(f"괜찮아요 — 오류 0 · 권장 {len(warnings)}")
    return 0


def _cmd_manifest(args) -> int:
    made = manifest.capture(args.game_dir, game=args.game or "", version=args.version or "")
    manifest.save(made, args.out)
    print(f"매니페스트 저장: {args.out} ({len(made['files'])}개 파일)")
    return 0


def _cmd_diagnose(args) -> int:
    told = manifest.load(args.manifest)
    diag = manifest.diagnose(args.game_dir, told, store=args.store)

    if args.quarantine and diag.foreign:
        box = manifest.quarantine(args.game_dir, diag.foreign)
        print(f"격리함: {box} ({len(diag.foreign)}개)")
        return 0

    known_by = sorted({name for _, name in diag.known})
    known_desc = f"아는 변경 {len(diag.known)} ({', '.join(known_by)})" if diag.known \
        else "아는 변경 0"
    untracked_desc = f" · 추적 밖 {len(diag.untracked)}" if diag.untracked else ""
    print(f"원본 일치 {len(diag.intact)} · {known_desc} · "
          f"외래 {len(diag.foreign)} · 누락 {len(diag.missing)}{untracked_desc}")
    if diag.foreign:
        print("외래: " + ", ".join(diag.foreign))
        print("→ --quarantine로 격리하거나, 그대로 두려면 아무것도 안 해도 돼요.")
        return 2
    print("깨끗해요 — 외래 파일이 없어요.")
    return 0


def _cmd_harvest(args) -> int:
    kept = modstore.harvest(args.game_dir, args.names, store=args.store)
    for mod in kept:
        print(f"꺼냄: {mod.name} → {mod.folder}")
    return 0


def _cmd_adopt(args) -> int:
    try:
        got = adopt.adopt(args.zip, args.game_dir, args.store, name=args.name or "")
    except adopt.NotAMod as no:
        print(str(no), file=sys.stderr)
        return 1
    print(f"입양: {got.name} → {got.folder}")
    for note in got.notes:
        print(f"판독: {note}")
    for warning in got.warnings:
        print(f"경고: {warning}")
    if got.kept:
        print(f"보관만: {', '.join(got.kept)} (게임 자리를 못 찾아 설치 목록엔 없어요)")
    print("이름과 설명은 mod.json에서 다듬어 주세요.")
    return 0


def _cmd_apply(args) -> int:
    try:
        done = modstore.apply(args.store, args.name, args.game_dir, force=args.force)
    except declare.Blocked as no:
        for why in no.reasons:
            print(why, file=sys.stderr)
        return 1
    except (modstore.ModMissing, modstore.WrongGame, modstore.BaseChanged,
            modstore.NoBundle) as err:
        print(str(err), file=sys.stderr)
        return 1
    print(f"{done['mod']}: {done['did']}")
    for warning in done.get("warnings") or []:
        print(f"경고: {warning}")
    return 0


def _cmd_remove(args) -> int:
    try:
        done = modstore.remove(args.name, args.game_dir, store=args.store)
    except (modstore.ModMissing, modstore.NoBundle) as err:
        print(str(err), file=sys.stderr)
        return 1
    print(f"{done['mod']}: {done['did']}")
    return 0


def _cmd_shelf(args) -> int:
    found = modstore.shelf(args.store)
    if not found:
        print("보관소가 비어 있어요.")
        return 0
    for mod in found:
        print(f"{mod.name} ({mod.game})")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="modkit")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("new", help="모드 뼈대 생성")
    p.add_argument("name")
    p.add_argument("--game", help="대상 게임 제목")
    p.add_argument("--dir", type=Path, default=Path("."))
    p.set_defaults(func=_cmd_new)

    p = sub.add_parser("lint", help="mod.json·스크립트·에셋 검사")
    p.add_argument("mod_dir", type=Path)
    p.set_defaults(func=_cmd_lint)

    p = sub.add_parser("manifest")
    p.add_argument("game_dir", type=Path)
    p.add_argument("-o", "--out", type=Path, required=True)
    p.add_argument("--game")
    p.add_argument("--version")
    p.set_defaults(func=_cmd_manifest)

    p = sub.add_parser("diagnose")
    p.add_argument("game_dir", type=Path)
    p.add_argument("-m", "--manifest", type=Path, required=True)
    p.add_argument("--store", type=Path, default=modstore.DEFAULT_STORE)
    p.add_argument("--quarantine", action="store_true")
    p.set_defaults(func=_cmd_diagnose)

    p = sub.add_parser("harvest")
    p.add_argument("game_dir", type=Path)
    p.add_argument("names", nargs="+")
    p.add_argument("--store", type=Path, default=modstore.DEFAULT_STORE)
    p.set_defaults(func=_cmd_harvest)

    p = sub.add_parser("adopt", help="mod.json 없는 zip·폴더를 모드로 입양")
    p.add_argument("zip", metavar="zip_or_folder", type=Path)
    p.add_argument("game_dir", type=Path)
    p.add_argument("--store", type=Path, default=modstore.DEFAULT_STORE)
    p.add_argument("--name", default="")
    p.set_defaults(func=_cmd_adopt)

    p = sub.add_parser("apply")
    p.add_argument("name")
    p.add_argument("game_dir", type=Path)
    p.add_argument("--store", type=Path, default=modstore.DEFAULT_STORE)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=_cmd_apply)

    p = sub.add_parser("remove")
    p.add_argument("name")
    p.add_argument("game_dir", type=Path)
    p.add_argument("--store", type=Path, default=modstore.DEFAULT_STORE)
    p.set_defaults(func=_cmd_remove)

    p = sub.add_parser("shelf")
    p.add_argument("--store", type=Path, default=modstore.DEFAULT_STORE)
    p.set_defaults(func=_cmd_shelf)

    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
