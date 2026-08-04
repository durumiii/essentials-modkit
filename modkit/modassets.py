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

  - **이미 있던 자리에는 백업을 남긴다**(`.orig`) — 내용이 모드 것과 같아도. 새로 놓은
    자리는 그냥 지우면 되고, 있던 자리는 되돌릴 것이 있다. 둘을 가르는 표시가 백업의
    유무라서, 같다고 백업을 거르면 제거가 손패치 실물을 지운다(2026-08-04 Nova).
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
    matched, total = applied_ratio(mod, game_dir)
    return total > 0 and matched == total


def applied_ratio(mod, game_dir: Path | str) -> tuple:
    """(일치한 에셋 수, 전체 수) — 다른 모드가 일부를 덮으면 '부분 설치'로 보인다.

    전량 일치만 설치로 치던 첫 판은, 그림 몇 장을 덮는 모드 하나에 한글패치가
    "사일런트 제거"된 것처럼 보였다(2026-08-04 실기 — 실제로는 다 살아 있었다).
    """
    game_dir = Path(game_dir).resolve()
    pairs = declared(mod)
    matched = sum(
        1 for source, where in pairs
        if matches(source, (target := _inside(game_dir, where))) or _shelved(source, target))
    return matched, len(pairs)


def _shelved(source: Path, target: Path) -> bool:
    """내 판이 층 보관본(.pre-*)에 온전히 있는가 — 위 모드에 덮여도 설치는 산 것이다.

    KR 위에 GUI를 얹자 KR이 '부분 설치'로 표시돼 깨진 걸로 읽혔다(2026-08-04,
    pokemon-z 물음 1). order 선언 추측이 아니라 보관 실물을 대조한다.
    """
    head = target.name + ".pre-"   # glob은 이름의 `[`를 문자 클래스로 읽는다(AGENTS 함정)
    try:
        return any(kept.name.startswith(head) and matches(source, kept)
                   for kept in target.parent.iterdir())
    except OSError:
        return False


def unbacked_mismatches(mod, game_dir: Path | str) -> list:
    """어긋난 자리 중 백업이 없어 되돌릴 길이 없는 곳 — 제거 가능 판정의 재료.

    백업 없는 손패치 반쪽은 소유를 몰라 못 빼지만, modkit이 설치해 백업을 남긴
    모드는 다른 모드가 일부를 덮었어도 뺄 수 있다(2026-08-04 실기 — KR 위에 GUI를
    얹었더니 KR 제거가 '반쪽'으로 거부됐다).
    """
    game_dir = Path(game_dir).resolve()
    stuck = []
    for source, where in declared(mod):
        target = _inside(game_dir, where)
        if matches(source, target):
            continue
        if not target.exists():
            continue  # 자리 자체가 비었으면 되돌릴 것도 없다
        if not target.with_name(target.name + BACKUP_SUFFIX).is_file():
            stuck.append(where)
    return stuck


def any_backups(mod, game_dir: Path | str) -> bool:
    """이 모드의 자리 어딘가에 백업이 있는가 — modkit이 설치했던 흔적."""
    game_dir = Path(game_dir).resolve()
    return any(
        _inside(game_dir, where).with_name(
            _inside(game_dir, where).name + BACKUP_SUFFIX).is_file()
        for _, where in declared(mod))


def _sample(path: Path, size: int = 4096) -> bytes:
    """파일의 머리·꼬리 표본 — 같은 크기의 다른 내용을 싸게 가른다."""
    with open(path, "rb") as handle:
        head = handle.read(size)
        handle.seek(max(0, path.stat().st_size - size))
        return head + handle.read(size)


def matches(source: Path, target: Path) -> bool:
    """게임의 파일이 보관소의 것과 같은가.

    # ponytail: 크기 + 머리·꼬리 4KB 표본만 견준다 — 전체를 읽으면 화면이 폴링할
    # 때마다 수백 MB를 읽는다. 크기만 보던 첫 판은 같은 크기의 다른 그림에 속아
    # 겹침 판정이 틀렸다(2026-08-04). 표본까지 같은 다른 내용에 속으면 그때 CRC로 올린다.
    예외가 하나 있다: 코어(`Scripts.rxdata`)는 주입 모드가 섹션을 덧붙이므로 크기가
    달라도 **주입 섹션을 걷어낸 나머지**가 같으면 같은 것이다 — 주입이 붙었다고
    한글패치가 빠진 게 아니다.
    """
    try:
        if target.stat().st_size == source.stat().st_size:
            return _sample(target) == _sample(source)
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

        backup = target.with_name(target.name + BACKUP_SUFFIX)
        if target.is_file() and not backup.exists():
            shutil.copy2(target, backup)  # 게임이 원래 들고 있던 것
            backed_up.append(where)

        if target.is_file() and target.read_bytes() == source.read_bytes():
            # 내용이 같아도 백업은 남긴다 — 백업 없는 자리를 제거가 "내가 새로 놓은
            # 것"으로 읽어, 손패치로 있던 실물을 지웠다(2026-08-04 Nova 실기).
            skipped.append(where)
            continue

        if target.is_file() and backup.is_file():
            now = target.read_bytes()
            self_again = matches(source, target)  # 코어는 same_core — 뜻-왕복 재직렬화가
            # 자기 재설치를 남의 층으로 보이게 한다(2026-08-04 실기: 제거가 순정 대신
            # 자기 판을 "복원"해 코어가 영영 패치판에 머물렀다).
            if now != backup.read_bytes() and not self_again:
                # 백업(첫 원본)과도 다르면 지금 내용은 다른 모드의 층이다 — 밀어내기
                # 전에 보관해야 이 모드 제거가 그 층을 되살린다(2026-08-04 실기:
                # KR 위 GUI를 빼자 겹친 그림이 순정으로 떨어졌다).
                _put(target.with_name(target.name + f".pre-{mod.name}"), now)

        if target.name == "Scripts.rxdata":
            # 코어 통째 교체는 섹션 병합으로 — 살아 있는 주입 모드는 보존하고,
            # 교체본에 실려 온 남의 주입은 뺀다(modstore.merge_core 참고).
            from . import modstore

            merged = modstore.merge_core(
                source.read_bytes(), target.read_bytes() if target.is_file() else None)
            _put(target, merged)
            written.append(where)
            continue

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
        shelved = target.with_name(target.name + f".pre-{mod.name}")
        if shelved.is_file():
            # 이 모드가 밀어냈던 아래층을 되살린다. 백업(.orig)은 아래층 모드의
            # 몫이라 그대로 둔다. # ponytail: 역순 제거(아래층 먼저)는 층 표식이
            # 위층 이름에 매여 있어 못 살린다 — 순서대로 빼는 경우만 정확.
            _put(target, shelved.read_bytes())
            shelved.unlink()
            reverted.append(where)
        elif backup.is_file():
            blob = backup.read_bytes()
            if target.name == "Scripts.rxdata" and target.is_file():
                # 원본을 돌려놓되, 이 위에 살던 주입 모드는 도로 꽂아 살린다.
                from . import modstore

                blob = modstore.merge_core(blob, target.read_bytes())
            _put(target, blob)
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
