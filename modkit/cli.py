"""명령줄 진입점 — manifest/diagnose/harvest/apply/remove/shelf.

각 핸들러는 코어 함수(manifest·modstore)를 부르고 사람이 읽을 몇 줄을 찍는다.
종료 코드: 성공 0, 차단·오류 1, 진단에서 외래 발견 2.
"""
import argparse
import sys
from pathlib import Path

from . import declare, manifest, modstore


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
    print(f"원본 일치 {len(diag.intact)} · {known_desc} · "
          f"외래 {len(diag.foreign)} · 누락 {len(diag.missing)}")
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
