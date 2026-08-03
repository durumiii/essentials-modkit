"""모드가 데리고 오는 그림·소리를 게임 폴더에 넣고, 뺄 때 되돌린다.

플러그인 중에는 루비 코드만으로는 못 도는 것이 있다. 새 그래픽이나 소리를 읽는 모드다.
스크립트만 넣으면 **조용히 반만 산다** — Essentials의 `pbResolveBitmap`은 그림을 못 찾으면
nil을 돌려주고, 잘 짠 플러그인은 거기서 그 표시만 건너뛴다. 오류도 경고도 없이 기능 일부가
빠진 채로 돌아서, 사람은 "모드가 안 먹네"라고만 본다(2026-07-28 `Type Helper`).

그래서 모드는 `mod.json`의 `assets`에 데리고 오는 파일을 적는다.

    {"file": "Graphics/Plugins/Type Helper/types.png",
     "install_to": "Graphics/Plugins/Type Helper/types.png"}

`file`은 보관소의 모드 폴더 기준, `install_to`는 게임 폴더 기준이다.

지키는 것 넷.

  - **덮은 자리에만 백업을 남긴다**(`.orig`). 새로 놓은 자리는 그냥 지우면 되고, 덮은 자리는
    되돌릴 것이 있다. 둘을 가르는 표시가 백업의 유무다.
  - **두 번 설치해도 백업은 처음 것 그대로.** 두 번째가 첫 결과를 원본으로 뜨면 되돌릴 데가
    사라진다.
  - **제자리에서 고치지 않는다.** 버전끼리 하드링크로 이어져 있어 함께 바뀐다. 옆에 쓰고
    이름을 바꿔 갈아 끼운다.
  - **게임 폴더 밖은 못 가리킨다.** `install_to`는 사람이 손으로 적는 값이라, 밖을 향하면
    거절한다.
"""
import os
import shutil
from pathlib import Path

BACKUP_SUFFIX = ".orig"


class UnsafeTarget(Exception):
    """게임 폴더 밖을 가리킨다."""


class AssetMissing(Exception):
    """보관소에 그 파일이 없다."""


def declared(mod) -> tuple:
    """(보관소의 원본, 게임 폴더 기준 자리) 짝들."""
    return tuple(
        (mod.folder / one["file"], one["install_to"])
        for one in (getattr(mod, "assets", None) or [])
    )


def applied(mod, game_dir: Path | str) -> bool:
    """이 모드의 에셋이 지금 게임에 들어가 있는가.

    스크립트 없는 모드는 플러그인 묶음에 이름이 안 남아, 설치 여부를 파일로 답해야 한다.
    # ponytail: 크기만 견준다 — 내용까지 읽으면 화면이 폴링할 때마다 수백 MB를 읽는다.
    # 크기가 같은 다른 내용에 속으면 그때 CRC 대조로 올린다.
    """
    game_dir = Path(game_dir).resolve()
    pairs = declared(mod)
    if not pairs:
        return False
    return all(matches(source, _inside(game_dir, where)) for source, where in pairs)


def matches(source: Path, target: Path) -> bool:
    """게임의 파일이 보관소의 것과 같은가.

    # ponytail: 크기만 견준다 — 내용까지 읽으면 화면이 폴링할 때마다 수백 MB를 읽는다.
    예외가 하나 있다: 코어(`Scripts.rxdata`)는 주입 모드가 섹션을 덧붙이므로 크기가
    달라도 **주입 섹션을 걷어낸 나머지**가 같으면 같은 것이다 — 주입이 붙었다고
    한글패치가 빠진 게 아니다.
    """
    try:
        if target.stat().st_size == source.stat().st_size:
            return True
    except OSError:
        return False
    if target.name == "Scripts.rxdata":
        from . import modstore

        return modstore.same_core(source, target)
    return False


def install(mod, game_dir: Path | str) -> dict:
    """모드의 에셋을 게임 폴더에 넣는다."""
    game_dir = Path(game_dir).resolve()
    written, skipped, backed_up = [], [], []

    for source, where in declared(mod):
        target = _inside(game_dir, where)
        if not source.is_file():
            raise AssetMissing(f"`{mod.name}`이 가져올 파일이 보관소에 없어요: {source}")

        if target.is_file() and target.read_bytes() == source.read_bytes():
            skipped.append(where)
            continue

        backup = target.with_name(target.name + BACKUP_SUFFIX)
        if target.is_file() and not backup.exists():
            shutil.copy2(target, backup)  # 게임이 원래 들고 있던 것
            backed_up.append(where)

        target.parent.mkdir(parents=True, exist_ok=True)
        _put(target, source.read_bytes())
        written.append(where)

    return {"written": written, "skipped": skipped, "backed_up": backed_up}


def remove(mod, game_dir: Path | str) -> dict:
    """넣었던 에셋을 걷어낸다. 덮었던 자리는 원본을 돌려놓는다."""
    game_dir = Path(game_dir).resolve()
    removed, reverted = [], []

    for _, where in declared(mod):
        target = _inside(game_dir, where)
        backup = target.with_name(target.name + BACKUP_SUFFIX)
        if backup.is_file():
            _put(target, backup.read_bytes())
            backup.unlink()
            reverted.append(where)
        elif target.is_file():
            target.unlink()
            removed.append(where)
            _sweep_empty(game_dir, target.parent)

    return {"removed": removed, "reverted": reverted}


def _inside(game_dir: Path, where: str) -> Path:
    """게임 폴더 안의 자리로 풀어 준다. 밖을 가리키면 거절한다."""
    if os.path.isabs(where) or (len(where) > 1 and where[1] == ":"):
        raise UnsafeTarget(f"게임 폴더 안의 자리를 적어 주세요: {where}")
    target = (game_dir / where).resolve()
    if target == game_dir or game_dir not in target.parents:
        raise UnsafeTarget(f"게임 폴더 밖을 가리켜요: {where}")
    return target


def _put(target: Path, blob: bytes) -> None:
    """옆에 쓰고 이름을 바꿔 갈아 끼운다 — 하드링크로 이어진 옆 버전을 건드리지 않으려고."""
    spare = target.with_name(target.name + ".writing")
    spare.write_bytes(blob)
    os.replace(spare, target)


def _sweep_empty(game_dir: Path, folder: Path) -> None:
    """우리 파일을 빼고 빈 채로 남은 폴더만 걷어낸다. 남의 것이 있으면 둔다."""
    while folder != game_dir and game_dir in folder.parents:
        if any(folder.iterdir()):
            return
        folder.rmdir()
        folder = folder.parent
