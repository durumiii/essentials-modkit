# /// script
# requires-python = ">=3.12"
# ///
"""Pokemon Z 모드 배포 zip을 보관소에서 뜬다 (릴리스 `mods-z-v*`의 자산).

    uv run build-mods.py [--store <보관소>] [--out <폴더>]

담는 것은 카드가 아는 파일과 스크립트뿐이다 — 작업 부스러기(`.draft`·`.bak`·`.orig`)와
modkit이 남긴 장부는 뺀다. zip 안은 **모드 폴더 한 겹**이라 받는 쪽이 보관소에 그대로
풀면 된다(게임 폴더에 덮는 패치 zip과 구조가 다르다).

자산 이름이 영문인 이유: GitHub 업로드가 한글 파일명을 404로 거부한다(2026-08-05 실측).
"""
import argparse
import hashlib
import zipfile
from pathlib import Path

STORE = Path("/mnt/d/GameVault/mods/Pokemon Z Fangame")
OUT = Path(__file__).resolve().parent / "dist" / "mods-z"

# 보관소 이름 → 자산 파일 이름. 실험·진단용(GC Tamer·Frame Profiler)은 안 낸다.
MODS = {
    "Battle Speed": "Battle-Speed",
    "Better Movements": "Better-Movements",
    "Controller UX": "Controller-UX",
    "DPPT Font": "DPPT-Font",
    "UI Text KR": "UI-Text-KR",
    "Z-GUI": "Z-GUI",
    "디버그 모드": "Debug-Mode",
    "한글패치 통합-Runa": "KR-Patch-Runa",
}
JUNK_TAIL = (".draft", ".orig", ".pyc")
JUNK_NAME = {"modkit-owners.json", "AGENTS.md", "CLAUDE.md"}


def wanted(path: Path) -> bool:
    if path.name in JUNK_NAME or path.name.endswith(JUNK_TAIL):
        return False
    return not (".bak" in path.name or ".pre-" in path.name)


def main() -> None:
    ap = argparse.ArgumentParser(description="모드 배포 zip을 뜬다")
    ap.add_argument("--store", type=Path, default=STORE)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    lines = []
    for mod, asset in MODS.items():
        src = args.store / mod
        if not (src / "mod.json").is_file():
            raise SystemExit(f"카드가 없어요: {src / 'mod.json'}")
        picked = sorted(p for p in src.rglob("*") if p.is_file() and wanted(p))
        out = args.out / f"{asset}.zip"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for p in picked:
                z.write(p, (Path(mod) / p.relative_to(src)).as_posix())
        digest = hashlib.sha256(out.read_bytes()).hexdigest()
        lines.append(f"{digest}  {out.name}")
        print(f"{out.name} — 파일 {len(picked)}개 · {out.stat().st_size / 1e3:,.0f}KB")

    sums = args.out / "zz-SHA256SUMS.txt"
    sums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{sums.name} — {len(lines)}줄")


if __name__ == "__main__":
    main()
