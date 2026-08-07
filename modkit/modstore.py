"""모드를 게임 밖에 따로 보관하고, 설치본에 얹거나 뺀다.

Essentials 팬게임의 모드는 플러그인 묶음(`Data/PluginScripts.rxdata`) 안에 눌려 들어
있다. 그 안에 두면 버전을 올릴 때마다 배포자의 묶음으로 갈리면서 사라지고, 어느 설치본에
무엇이 얹혔는지도 알기 어렵다.

그래서 **모드를 꺼내 보관소에 둔다.** 보관소에서는 사람이 읽을 수 있는 `.rb` 파일과
`mod.json` 한 장으로 눕는다. 게임에 얹는 것은 거기서 다시 묶어 넣는 일이고, 빼는 것은
묶음에서 그 항목만 덜어내는 일이다. 코어와 독립적인 모드라면 이 왕복만으로 충분하다.

**모드는 꺼내 온 게임에 매인다.** 다른 게임에도 같은 이름의 클래스가 있다는 것은 얹어도
된다는 근거가 못 된다 — 이름이 같다고 같은 물건을 가리키는 법이 없다. 그래서 보관소는
모드마다 어느 게임에서 나왔는지 적어 두고, 그 게임의 설치본에만 내놓는다.

지키는 것 넷.

  - **얹기 전에 원본을 백업한다**(`PluginScripts.rxdata.orig`). 이미 있으면 덮지 않는다 —
    두 번째 얹기가 첫 결과를 원본으로 착각하면 되돌릴 데가 없다.
  - **묶음 끝에 얹는다.** 게임이 배열 순서대로 읽어서 마지막 재정의가 이긴다.
  - **옆에 쓰고 이름을 바꿔 갈아 끼운다.** 버전 폴더끼리 하드링크로 이어져 있을 수 있어
    제자리에서 고치면 다른 버전까지 함께 바뀐다.
  - **스크립트만 넣고 끝내지 않는다.** 그림·소리를 데리고 오는 모드는 그것까지 넣어야
    온전히 돈다(`modassets`). 코드만 들어가면 오류 없이 반만 사는 채로 돈다.
"""
import io
import json
import re
import zlib
from dataclasses import dataclass
from pathlib import Path

from . import modassets, rubyread

BUNDLE = "Data/PluginScripts.rxdata"
BACKUP = "Data/PluginScripts.rxdata.orig"
# 묶음이 없는 옛 엔진(포켓몬 Z 팬게임)의 스크립트 모드는 코어 배열에 섹션으로 들어간다.
# 규약은 poke-essentials의 주입기와 한 벌이다 — 섹션 제목 `MOD:<모드명>/<파일명>`,
# `Main` 앞에 꽂기(RGSS는 배열 순서대로 실행하고 Main 뒤는 영영 안 돈다).
SCRIPTS = "Data/Scripts.rxdata"
SCRIPTS_BACKUP = "Data/Scripts.rxdata.orig"
MOD_MARK = "MOD:"
CARD = "mod.json"
import os
# 실행 위치에 따라 서랍이 떠돌면 안 된다 — exe를 다운로드 폴더에서 더블클릭했더니
# 보관소가 Downloads/mods(야생 zip 무더기)에 겹쳐 만들어진 실물 사고(2026-08-04).
DEFAULT_STORE = Path(os.environ.get("MODKIT_STORE") or Path.home() / ".modkit" / "mods")
_UNSAFE = re.compile(r'[/\\:*?"<>|]')


class NoBundle(Exception):
    """플러그인 파일이 없다."""


class ModMissing(Exception):
    """그런 모드가 없다."""


class BaseChanged(Exception):
    """모드가 기대하는 원문과 게임의 지금 원문이 다르다 — 훅이 조용히 어긋날 수 있다."""


@dataclass(frozen=True)
class Mod:
    name: str
    folder: Path
    scripts: tuple  # (스크립트 이름, 소스)
    meta: dict
    game: str = ""  # 이 모드가 매인 게임
    from_version: str = ""  # 꺼내 온 설치본의 버전 지문
    from_build: str = ""  # 그 설치본의 폴더 이름
    harvested_at: str = ""  # 꺼낸 시각
    updated_at: str = ""  # 스크립트가 마지막으로 바뀐 시각
    baseline_taken: bool = False  # 원본 코드를 저장해 봤는가 (빈 것과 안 해 본 것은 다르다)
    description: str = ""  # 이 모드가 무엇을 하는지 — mod.json에서 사람이 고쳐 쓴다
    summary: str = ""  # 서랍 목록에 뜨는 한 줄 요약 — 긴 얘기는 description의 몫
    assets: tuple = ()  # 함께 들어가야 하는 그림·소리 (`modassets` 참고)

    @property
    def line_count(self) -> int:
        return sum(source.count("\n") + 1 for _, source in self.scripts)


# ── 설치본 쪽 ────────────────────────────────────────────────

def present(store: Path | str, game_dir: Path | str, game: str | None = None) -> list:
    """설치본에 실제로 들어가 있는 모드 이름 — 겹침 판정의 상대 목록.

    `installed`는 묶음·주입 섹션에 이름이 남는 모드만 안다. 에셋 전용 모드는 이름이
    안 남아 겹침 상대에서 빠졌고, 그래서 같은 그림을 덮는 두 모드가 경고 없이
    서로를 덮었다(2026-08-04 실기). 파일 대조(`modassets.applied`)로 보탠다.
    """
    try:
        found = installed(game_dir)
    except NoBundle:
        found = []
    for mod in shelf(store, game=game):
        if mod.name not in found and not mod.scripts and mod.assets:
            matched, total = modassets.applied_ratio(mod, game_dir)
            if matched:  # 일부가 다른 모드에 덮였어도 이 모드는 게임에 있다
                found.append(mod.name)
    return found


def wholesale_effects(mod, game_dir: Path | str) -> list:
    """코어·묶음을 통째로 덮는 에셋 모드의 부수 효과 — 사람이 읽을 경고 목록.

    주입 모드는 Scripts.rxdata **안에** 살아서, 그 파일을 통째로 갈아 끼우면 함께
    씻겨 나간다. 반대로 교체본 안에 담긴 다른 모드의 주입은 함께 실려 들어온다.
    말없이 일어나면 유저는 모드가 사라진 이유를 알 길이 없다(2026-08-04 실기).
    """
    game_dir = Path(game_dir)
    notes = []
    for one in getattr(mod, "assets", ()) or ():
        install_to = one.get("install_to", "").replace("\\", "/")
        if install_to not in (SCRIPTS, BUNDLE):
            continue
        try:
            current = installed(game_dir)
        except NoBundle:
            current = []
        embedded = []
        try:
            for entry in rubyread.loads((Path(mod.folder) / one["file"]).read_bytes()):
                title = bytes(entry[1]).decode("utf-8", "replace") \
                    if isinstance(entry[1], (bytes, bytearray)) else str(entry[1])
                if title.startswith(MOD_MARK):
                    name = title[len(MOD_MARK):].split("/", 1)[0]
                    if name not in embedded:
                        embedded.append(name)
        except Exception:
            pass  # 판독 불가면 담긴 모드는 모름 — 씻김 경고만이라도 낸다
        if install_to == SCRIPTS:
            # 코어는 섹션 병합으로 들어간다 — 살아 있는 주입은 보존되고, 실려 온
            # 남의 주입은 뺀다. 유저에게는 후자만 알리면 된다.
            for name in embedded:
                if name != mod.name:
                    notes.append(f"교체본에 담긴 `{name}`의 주입은 빼고 설치해요 — "
                                 f"`{name}`이 필요하면 서랍에서 따로 설치해 주세요.")
            continue
        wiped = [n for n in current if n != mod.name and n not in embedded]
        if wiped:
            notes.append(_wipe_note(install_to, wiped))
        for name in embedded:
            if name != mod.name:
                notes.append(f"이 모드의 {install_to} 안에 `{name}`의 주입이 담겨 있어요 — 함께 설치돼요.")
    return notes


def _wipe_note(install_to: str, wiped: list) -> str:
    """씻김 경고 한 줄 — 이름 4개까지, 넘치면 '외 N개'로 집계한다.

    Añil처럼 게임이 플러그인 수십 개를 동봉한 설치본에서 전부 나열하면
    경고문이 화면을 삼킨다(2026-08-04 실기, 52개).
    """
    heads = ", ".join(f"`{n}`" for n in wiped[:4])
    more = f" 외 {len(wiped) - 4}개" if len(wiped) > 4 else ""
    return (f"{install_to}를 통째로 갈아 끼워요 — 들어 있는 {heads}{more}도 "
            "함께 제거돼요. 이 모드를 설치한 뒤 다시 설치하면 돌아와요.")


def installed(game_dir: Path | str) -> list:
    """이 설치본에 얹혀 있는 모드 이름을 순서대로.

    묶음이 있으면 묶음에서, 없으면(옛 엔진) 코어의 주입 섹션에서 읽는다.
    """
    game_dir = Path(game_dir)
    if (game_dir / BUNDLE).is_file():
        return [str(entry[0]) for entry in _read(game_dir / BUNDLE)]
    if (game_dir / SCRIPTS).is_file():
        return _injected(game_dir)
    raise NoBundle(f"플러그인 파일이 없어요: {game_dir / BUNDLE}")


_injected_memo: dict = {}


def _injected(game_dir: Path) -> list:
    """코어에 주입된 모드 이름들. 화면이 폴링으로 묻는 자리라 파일 도장으로 기억해 둔다."""
    scripts = game_dir / SCRIPTS
    told = scripts.stat()
    key = str(scripts)
    stamp = (told.st_size, told.st_mtime_ns)
    kept = _injected_memo.get(key)
    if kept and kept[0] == stamp:
        return list(kept[1])
    names = []
    for entry in rubyread.loads(scripts.read_bytes()):
        title = bytes(entry[1]).decode("utf-8", "replace")
        if title.startswith(MOD_MARK):
            name = title[len(MOD_MARK):].split("/", 1)[0]
            if name not in names:
                names.append(name)
    _injected_memo[key] = (stamp, tuple(names))
    return names


class WrongGame(Exception):
    """다른 게임의 모드다."""


class NameTaken(Exception):
    """그 이름을 쓰는 모드가 이미 있다."""


def apply(store: Path | str, name: str, game_dir: Path | str, force: bool = False) -> dict:
    """보관소의 모드를 설치본에 얹는다. 같은 이름이 있으면 갈아 끼운다.

    얹기 전에 제작자 선언을 본다(`declare`) — requires·conflicts는 막고, order는 삽입
    자리를 정하고, touches 겹침은 경고로 돌려준다. `force=True`면 막을 일도 경고로 내린다.
    """
    from . import declare, gameinfo

    game_dir = Path(game_dir)
    here = gameinfo.read_title(game_dir)
    mod = read_mod(store, name, game=here)   # 이름이 겹치면 이 게임 것을 고른다

    warnings = []
    if mod.game and gameinfo.canon(mod.game) != gameinfo.canon(here):
        # 귀속 불일치도 강행 가능하다 — 매니저의 일은 제한이 아니라 정보와
        # 가드레일이고, 백업(.orig)이 되돌릴 길을 지킨다.
        why = (f"{gameinfo.josa(f'`{mod.name}`', '은/는')} `{mod.game}` 전용 모드예요. "
               f"이 게임은 {gameinfo.josa(f'`{here}`', '이에요/예요')} — "
               "클래스 이름이 같아도 다른 게임에서는 다른 것을 가리킬 수 있어요.")
        if not force:
            raise WrongGame(why)
        warnings.append(f"강행: {why}")

    card = json.loads((mod.folder / CARD).read_text(encoding="utf-8"))
    already = present(store, game_dir, game=mod.game or here)
    others = [one for one in already if one != mod.name]
    try:
        warnings += declare.gate(card, others, store)
    except declare.Blocked as no:
        if not force:
            raise
        warnings += [f"강행: {why}" for why in no.reasons]

    # 얹기 전 호환 판정 — 게임이 판 올림으로 원본을 고쳤는데 모드가 낡은 것을
    # 되살리는 사고를 여기서 막는다. fits·unknown은 조용히 지나간다(unknown은
    # 기준선 없는 옛 카드가 많아 경고로 올리면 소음이 된다).
    from . import modfit

    fit = modfit.check(game_dir, mod)
    if fit.verdict == modfit.CHANGED:
        if not force:
            raise BaseChanged(
                "이 게임 판과 안 맞아요 — 설치하면 낡은 코드가 되살아나요:\n"
                + "\n".join(fit.findings))
        warnings += [f"강행: {why}" for why in fit.findings]

    if not mod.scripts:
        # 스크립트 없이 파일만 갈아 끼우는 모드 — 플러그인 묶음이 없는 게임(포켓몬 Z처럼
        # 옛 엔진)에도 얹을 수 있어야 하므로 묶음은 아예 건드리지 않는다.
        warnings += wholesale_effects(mod, game_dir)
        did = "덮어씀" if modassets.applied(mod, game_dir) else "설치됨"
        brought = modassets.install(mod, game_dir)
        return {
            "mod": mod.name,
            "did": did,
            "total": 0,
            "backup": "",
            "assets": len(brought["written"]) + len(brought["skipped"]),
            "warnings": warnings,
        }

    if not (game_dir / BUNDLE).is_file():
        # 플러그인 묶음이 없는 옛 엔진(포켓몬 Z처럼)의 스크립트 모드는 주입형이다 —
        # Scripts.rxdata에 섹션으로 덧붙인다. 규약은 poke-essentials 주입기와 한 벌.
        # 주입은 늘 Main 앞에 일괄로 들어가므로 자리를 골라 꽂지 않는다. 모드 사이의
        # 상대 순서는 걷어내고 다시 꽂는 재적용으로 실현되니, 상대가 아직 없으면 알린다.
        for need in (card.get("order") or {}).get("after") or []:
            if need not in others:
                warnings.append(
                    f"`{need}`가 아직 없어서 `{mod.name}`이 앞에 놓여요 — "
                    f"`{need}`를 설치한 뒤 `{mod.name}`을 다시 설치하면 순서가 잡혀요")
        done = _inject(mod, game_dir)
        done["warnings"] = warnings
        return done
    entries = _read(game_dir / BUNDLE)

    packed = _pack_mod(mod)
    at = next((i for i, entry in enumerate(entries) if str(entry[0]) == mod.name), None)
    if at is None:
        # 묶음의 항목과 모드가 1:1이라 이름 리스트의 인덱스를 그대로 배열 자리로 쓴다.
        try:
            spot = declare.place(card, [str(entry[0]) for entry in entries])
        except declare.Blocked as no:
            if not force:
                raise
            warnings += [f"강행: {why}" for why in no.reasons]
            spot = len(entries)
        entries = entries[:spot] + [packed] + entries[spot:]
        did = "설치됨"
    else:
        entries = list(entries)
        entries[at] = packed
        did = "덮어씀"

    backup = _back_up(game_dir)
    _write(game_dir / BUNDLE, entries)
    # 에셋을 먼저 넣지 않는 이유: 스크립트 쓰기가 실패하면 게임 폴더에 남길 것이 없다.
    brought = modassets.install(mod, game_dir)
    return {
        "mod": mod.name,
        "did": did,
        "total": len(entries),
        "backup": str(backup),
        "assets": len(brought["written"]) + len(brought["skipped"]),
        "warnings": warnings,
    }


def remove(name: str, game_dir: Path | str, store: Path | str | None = None) -> dict:
    """설치본에서 그 플러그인과, 그 모드가 데리고 온 파일을 함께 뺀다.

    `store`를 주면 그 모드가 무엇을 데리고 왔는지 읽어 되돌린다. 보관소에서 이미 사라진
    모드라도 스크립트는 뺄 수 있어야 하므로, 못 읽으면 스크립트만 뺀다.
    """
    game_dir = Path(game_dir)

    from . import gameinfo

    here = gameinfo.read_title(game_dir)
    told = None
    try:
        told = read_mod(store or DEFAULT_STORE, name, game=here)
    except ModMissing:
        pass
    if told is not None and told.scripts and not (game_dir / BUNDLE).is_file():
        # 주입형 — 코어에서 이 모드의 섹션만 걷어 낸다. 다른 모드의 섹션은 그대로 선다.
        return _uninject(told, game_dir)

    if told is not None and not told.scripts:
        # 파일만 갈아 끼우는 모드 — 묶음에 이름이 없으니 에셋으로 설치 여부를 가른다.
        matched, total = modassets.applied_ratio(told, game_dir)
        stuck = modassets.unbacked_mismatches(told, game_dir)
        marked = modassets.any_backups(told, game_dir)
        if matched == 0 and not marked:
            raise ModMissing(f"설치돼 있지 않아요: {name}")
        if stuck or (matched < total and not marked):
            # 손패치 반쪽 상태 — 백업이 없어 무엇이 이 모드 것인지 모른다. 내용이
            # 같다고 지우면 순정까지 지운다(2026-08-04 Nova 교훈의 일반형). 출구를 안내.
            # 어긋난 자리가 전부 백업으로 덮이면 통과 — modkit이 설치한 모드는
            # 다른 모드가 일부를 덮었어도 뺄 수 있다(2026-08-04 KR 위 GUI 실기).
            raise ModMissing(
                f"`{name}`이 반쪽만 들어 있어요(파일 {matched}/{total} 일치) — 무엇이 "
                "이 모드 것인지 백업이 없어 안전하게 못 빼요. 먼저 한 번 '설치'해서 "
                "정식 상태로 만들면, 그다음 제거는 깨끗하게 돼요.")
        taken = modassets.remove(told, game_dir)
        return {
            "mod": name,
            "did": "제거됨",
            "total": 0,
            "assets": len(taken["removed"]) + len(taken["reverted"]),
            "warnings": _kept_note(taken),
        }

    entries = _read(game_dir / BUNDLE)
    kept = [entry for entry in entries if str(entry[0]) != name]
    if len(kept) == len(entries):
        raise ModMissing(f"설치돼 있지 않아요: {name}")

    _back_up(game_dir)
    _write(game_dir / BUNDLE, kept)

    taken = {"removed": [], "reverted": []}
    try:
        taken = modassets.remove(read_mod(store or DEFAULT_STORE, name, game=here), game_dir)
    except ModMissing:
        pass  # 보관소에 없는 모드 — 무엇을 데리고 왔는지 알 길이 없다
    return {
        "mod": name,
        "did": "제거됨",
        "total": len(kept),
        "assets": len(taken["removed"]) + len(taken["reverted"]),
    }


def discard(store: Path | str, name: str) -> Path:
    """모드를 서랍에서 치운다 — 지우지 않고 보관소 안 `_trash/<시각>/`으로 옮긴다.

    삭제 대신 격리라는 도구 전체 규율의 서랍판이다. 잘못 치웠으면 폴더를 도로
    옮기면 된다. `shelf`·`read_mod`는 게임 폴더 두 단계까지만 훑으므로 _trash
    아래는 서랍에 안 보인다.
    """
    from . import gameinfo

    store = Path(store)
    mod = read_mod(store, name)
    stamp = gameinfo.now().replace(":", "-")
    dest = store / "_trash" / stamp / mod.folder.parent.name / mod.folder.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    mod.folder.rename(dest)
    return dest


def reassign(store: Path | str, name: str, game: str) -> dict:
    """모드를 다른 게임 소속으로 옮긴다 — 보관소 폴더 자리와 카드의 `game`을 함께.

    소속은 얹기 검사(`WrongGame`)와 서랍 표시의 기준이라, 잘못 지어진 소속은
    사람이 바로잡을 수 있어야 한다(입양이 게임 제목을 자동으로 추정하므로).
    """
    store = Path(store)
    mod = read_mod(store, name)
    dest = store / _game_folder(game) / mod.folder.name
    if dest.exists() and dest != mod.folder:
        raise NameTaken(f"그 게임 서랍에 같은 이름이 이미 있어요: {name}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest != mod.folder:
        mod.folder.rename(dest)
    card = dest / CARD
    told = json.loads(card.read_text(encoding="utf-8"))
    told["game"] = game
    card.write_text(json.dumps(told, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"name": name, "game": game}


def rename(store: Path | str, old: str, new: str, builds=()) -> dict:
    """모드의 이름표를 바꾼다. 설치돼 있는 버전에서는 옛 이름을 걷고 새 이름으로 다시 넣는다.

    **이름만 바꾸고 설치본을 두면 게임에 옛 이름이 남아 둘이 된다.** 그래서 `builds`에 그
    모드를 든 버전들을 함께 준다.

    루비 코드는 건드리지 않는다 — 같은 모드를 든 다른 자리(원본을 두는 프로젝트 같은 곳)와
    어긋나기 때문이다. 바뀌는 것은 보관소 폴더 이름, `mod.json`의 이름, 그리고 게임이 읽는
    묶음 속 이름뿐이다.
    """
    store = Path(store)
    mod = read_mod(store, old)
    fresh = mod.folder.with_name(_safe(new))  # 같은 게임 폴더 안에서만 옮긴다
    if fresh.exists():
        raise NameTaken(f"이미 그 이름을 쓰는 모드가 있어요: {new}")

    was_on = [Path(where) for where in builds if old in installed(where)]
    for where in was_on:
        remove(old, where, store)

    mod.folder.rename(fresh)
    card = fresh / CARD
    told = json.loads(card.read_text(encoding="utf-8"))
    told["name"] = new
    if isinstance(told.get("meta"), dict) and ":name" in told["meta"]:
        told["meta"][":name"] = new  # Essentials가 플러그인을 부르는 이름
    card.write_text(json.dumps(told, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for where in was_on:
        apply(store, new, where)
    return {"from": old, "to": new, "moved": len(was_on)}


# ── 보관소 쪽 ────────────────────────────────────────────────

def harvest(
    game_dir: Path | str,
    names: list,
    store: Path | str = DEFAULT_STORE,
    game: str | None = None,
    at: str | None = None,
    version: str | None = None,
) -> list:
    """설치본에 얹힌 모드를 꺼내 보관소에 눕힌다.

    `game`은 이 모드가 매일 게임의 이름이다. 안 주면 설치본의 제목을 쓴다.
    """
    game_dir, store = Path(game_dir), Path(store)
    found = {str(entry[0]): entry for entry in _read(game_dir / BUNDLE)}

    missing = [name for name in names if name not in found]
    if missing:
        raise ModMissing(f"이 게임에 설치돼 있지 않아요: {', '.join(missing)}")

    from . import gameinfo

    belongs_to = game or gameinfo.read_title(game_dir)
    when = at or gameinfo.now()
    version = version or ""   # 버전 지문은 부르는 쪽이 알면 준다 (예: 상위 라이브러리)

    kept = []
    for name in names:
        kept.append(
            _lay_down(
                found[name],
                store,
                came_from=game_dir,
                game=belongs_to,
                version=version,
                when=when,
            )
        )
    return kept


def _find_folder(store: Path, name: str, game: str | None = None):
    """모드 폴더를 찾는다. 보관소는 게임별 하위 폴더로 나뉘어 있다
    (`<보관소>/<게임>/<모드>/mod.json`). 평면에 남은 옛 배치도 함께 본다.

    `game`을 주면 그 게임 것을 먼저 고른다. 이름이 같은 모드가 게임마다 있을 수 있는데
    (`Better Movements`), 첫 매치만 돌려주던 판은 게임 폴더 이름 사전순으로 남의 것을
    집어 귀속 검사에 막혔다 — 그 게임의 제 모드는 이름으로 설치할 길이 없었다.
    """
    import glob as _glob

    safe = _safe(name)
    flat = store / safe
    # 이름의 대괄호가 glob 문자 클래스로 읽히지 않게 이스케이프한다
    found = ([flat] if (flat / CARD).is_file() else []) + [
        card.parent for card in sorted(store.glob(f"*/{_glob.escape(safe)}/{CARD}"))]
    if not found:
        # 폴더 이름과 카드 이름이 어긋난 모드도 찾아진다 — 폴더 하나 때문에 그 모드가
        # (그리고 shelf를 타는 모든 흐름이) 유령이 되면 안 된다(2026-08-04 실기).
        found = [card.parent
                 for card in sorted(store.glob(f"*/{CARD}")) + sorted(store.glob(f"*/*/{CARD}"))
                 if _card(card).get("name") == name]
    if game and len(found) > 1:
        from . import gameinfo

        want = gameinfo.canon(game)
        found = [f for f in found
                 if gameinfo.canon(_card(f / CARD).get("game") or "") == want] or found
    return found[0] if found else None


def _card(card: Path) -> dict:
    """카드를 읽되 깨진 것은 빈 것으로 — 하나 때문에 보관소가 멎지 않게."""
    try:
        return json.loads(card.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def read_mod(store: Path | str, name: str, game: str | None = None) -> Mod:
    """보관소에 누워 있는 모드 하나를 읽는다. `game`을 주면 그 게임 것을 먼저 고른다."""
    folder = _find_folder(Path(store), name, game)
    if folder is None:
        raise ModMissing(f"저장된 모드가 아니에요: {name}")
    return _mod_at(folder)


def _mod_at(folder: Path, told: dict | None = None) -> Mod:
    """폴더 하나에서 모드를 읽는다 — 이름 해석과 분리해 shelf가 직접 쓴다."""
    card = folder / CARD
    if told is None:
        told = json.loads(card.read_text(encoding="utf-8"))
    scripts = tuple(
        (one["script_name"], _read_keeping_line_ends(folder / one["file"]))
        for one in told["scripts"]
    )
    return Mod(
        name=told["name"],
        folder=folder,
        scripts=scripts,
        meta=told.get("meta") or {},
        game=told.get("game", ""),
        from_version=told.get("from_version", ""),
        from_build=told.get("from_build", ""),
        harvested_at=told.get("harvested_at", ""),
        updated_at=told.get("updated_at", ""),
        baseline_taken=bool(told.get("baseline_taken")),
        description=told.get("description", ""),
        summary=told.get("summary", ""),
        assets=tuple(told.get("assets") or ()),
    )


def shelf(store: Path | str = DEFAULT_STORE, game: str | None = None) -> list:
    """보관소에 있는 모드. `game`을 주면 그 게임에 매인 것만.

    다른 게임 것을 섞어 내놓지 않는다 — 얹을 수 있는지 이름으로 짐작하지 않기로 했다.
    """
    store = Path(store)
    if not store.is_dir():
        return []
    from . import gameinfo as _who

    found = []
    for card in sorted(store.glob(f"*/{CARD}")) + sorted(store.glob(f"*/*/{CARD}")):
        if "_trash" in card.parts:
            continue
        try:
            told = json.loads(card.read_text(encoding="utf-8"))
            mod = _mod_at(card.parent, told)
        except Exception:
            continue  # 깨진 카드 하나가 서랍 전체를 잠그면 안 된다(2026-08-04 실기)
        if game is None or _who.canon(mod.game) == _who.canon(game):
            found.append(mod)
    return found


# ── 안쪽 ─────────────────────────────────────────────────────

def _kept(card: Path, key: str, empty):
    """다시 가져와도 사람이 손으로 적어 둔 것은 지우지 않는다 — 설명과 에셋 목록."""
    if not card.is_file():
        return empty
    try:
        return json.loads(card.read_text(encoding="utf-8")).get(key) or empty
    except json.JSONDecodeError:
        return empty


def describe(store: Path | str, name: str, description: str) -> Mod:
    """모드 설명을 고쳐 쓴다."""
    mod = read_mod(store, name)
    card = mod.folder / CARD
    told = json.loads(card.read_text(encoding="utf-8"))
    told["description"] = description
    card.write_text(json.dumps(told, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return read_mod(store, name)


def _read_keeping_line_ends(path: Path) -> str:
    """줄바꿈을 건드리지 않고 읽는다.

    원본 스크립트는 CRLF다. 그냥 읽으면 파이썬이 LF로 바꿔 주고, 되묶을 때 원본과 다른
    바이트가 나온다. (`Path.read_text(newline=…)`는 3.13부터라 직접 연다.)
    """
    with open(path, encoding="utf-8", newline="") as handle:
        return handle.read()


def _game_folder(game: str) -> str:
    """게임 이름을 하위 폴더 이름으로. 콜론은 NTFS가 못 받아 떼어 낸다."""
    return _safe((game or "기타").replace(":", "")).strip() or "기타"


def _lay_down(entry, store: Path, came_from: Path, game: str, version: str, when: str) -> Mod:
    name = str(entry[0])
    folder = _find_folder(store, name, game) or store / _game_folder(game) / _safe(name)
    folder.mkdir(parents=True, exist_ok=True)
    kept_description = _kept(folder / CARD, "description", "")
    kept_assets = _kept(folder / CARD, "assets", [])
    kept_touches = _kept(folder / CARD, "touches", None)
    # 선언 필드는 게임에서 다시 읽어 낼 수 없다 — 카드에만 산다. 덮어쓰면 조용히
    # 사라져서, 다시 꺼낸 뒤로는 의존도 충돌도 검사되지 않는다.
    kept_declared = {key: _kept(folder / CARD, key, None)
                     for key in ("requires", "provides", "conflicts", "order", "expects")}
    kept_declared = {k: v for k, v in kept_declared.items() if v}

    for stale in folder.glob("*.rb"):
        stale.unlink()  # 다시 꺼낼 때 옛 이름의 파일이 남지 않게

    scripts, written = [], []
    for order, script in enumerate(entry[2] or []):
        script_name = str(script[0])
        source = zlib.decompress(bytes(script[1])).decode("utf-8", "replace")
        # 원본 스크립트는 줄바꿈이 CRLF다. newline=""로 써서 그대로 오간다.
        filename = _safe(script_name if script_name.endswith(".rb") else f"{script_name}.rb")
        if not filename[:1].isdigit():
            filename = f"{order:03d}_{filename}"  # 이름에 순서가 없으면 붙여 준다
        (folder / filename).write_text(source, encoding="utf-8", newline="")
        scripts.append((script_name, source))
        written.append({"file": filename, "script_name": script_name})

    (folder / CARD).write_text(
        json.dumps(
            {
                "name": name,
                "game": game,
                "description": kept_description,
                "from_version": version,
                "from_build": came_from.name,
                "harvested_at": when,
                "updated_at": when,
                "baseline_taken": True,
                "meta": _plain(entry[1]),
                **kept_declared,
                "assets": kept_assets,
                "touches": kept_touches or _draft_touches(scripts, kept_assets),
                "scripts": written,
                "harvested_from": str(came_from),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    mod = Mod(
        name=name,
        folder=folder,
        scripts=tuple(scripts),
        meta=_plain(entry[1]),
        game=game,
        description=kept_description,
        assets=tuple(kept_assets),
        from_version=version,
        from_build=came_from.name,
        harvested_at=when,
        updated_at=when,
        baseline_taken=True,
    )
    _take_baseline(mod, came_from)
    return mod


def _draft_touches(scripts, assets) -> dict:
    """제작자 선언의 초안 — 모드 소스에서 재정의 메서드를, 에셋에서 파일을 뽑는다.

    `modfit.overrides`를 그대로 쓴다(계산 규칙이 두 벌이 되면 어긋난다) — 그게 이미
    모드 스크립트에서 재정의된 자리를 뽑는 유일한 곳이다.
    """
    from . import modfit

    methods = sorted(modfit.overrides(scripts))
    files = sorted(a.get("install_to", "") for a in assets if a.get("install_to"))
    return {"methods": methods, "files": files}


def _take_baseline(mod: "Mod", game_dir: Path) -> None:
    """모드가 덮어쓰는 메서드의 게임 쪽 원문을 함께 떠 둔다.

    이걸 떠 두면 꺼내 온 설치본이 사라져도 "이 판에서 그 메서드가 바뀌었는지"를 따질 수
    있다. 모드 자신은 빼고 읽는다 — 자기 코드를 원본으로 착각하면 대조가 무의미해진다.
    """
    from . import modfit

    try:
        baseline = modfit.take_baseline(game_dir, mod.scripts, skip=mod.name)
    except Exception as unreadable:
        # 꺼내기 자체는 성공이지만, 못 떴다는 사실은 남긴다 — 나중에 "맞음"으로 오해하면 안 된다.
        _note_baseline(mod.folder, taken=False, why=str(unreadable))
        return
    if baseline:
        modfit.write_baseline(mod.folder, baseline)


def _note_baseline(folder: Path, taken: bool, why: str = "") -> None:
    card = folder / CARD
    told = json.loads(card.read_text(encoding="utf-8"))
    told["baseline_taken"] = taken
    if why:
        told["baseline_failed"] = why
    card.write_text(json.dumps(told, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _pack_mod(mod: Mod) -> list:
    return [
        mod.name,
        _ruby(mod.meta),
        [[name, zlib.compress(source.encode("utf-8"))] for name, source in mod.scripts],
    ]


def _inject(mod: Mod, game_dir: Path) -> dict:
    """모드 스크립트를 코어 배열의 `Main` 앞에 섹션으로 꽂는다.

    - 자기 섹션(`MOD:<이름>/`)이 이미 있으면 걷어 내고 새로 꽂는다 — 두 번 눌러도 안 쌓인다.
    - `mod.json`의 `expects`(섹션 제목 → 원문 md5)가 있으면 지금 코어와 대조하고, 다르면
      멈춘다 — 게임 판이 올라 원문이 바뀌었는데 낡은 훅을 꽂으면 조용히 어긋난다.
    - 첫 주입 전의 코어를 `.orig`로 남긴다. 쓰기 전에 되읽어 왕복을 확인한다.
    """
    import hashlib

    scripts_path = game_dir / SCRIPTS
    if not scripts_path.is_file():
        raise NoBundle(f"코어 스크립트가 없어요: {scripts_path}")
    entries = rubyread.loads(scripts_path.read_bytes())

    expects = _kept(mod.folder / CARD, "expects", {})
    if expects:
        md5_by_title = {}
        for entry in entries:
            source = zlib.decompress(bytes(entry[2]))
            md5_by_title.setdefault(
                bytes(entry[1]).decode("utf-8", "replace"), hashlib.md5(source).hexdigest()
            )
        for title, want in expects.items():
            got = md5_by_title.get(title)
            if got != want:
                raise BaseChanged(
                    f"`{mod.name}`이 기대하는 원문과 게임이 달라요 — 섹션 {title} "
                    f"md5 {got} (기대 {want}). 게임 판이 바뀌었으면 훅부터 다시 확인해요."
                )

    prefix = f"{MOD_MARK}{mod.name}/".encode("utf-8")
    kept = [e for e in entries if not bytes(e[1]).startswith(prefix)]
    did = "덮어씀" if len(kept) != len(entries) else "설치됨"

    fresh = []
    for script_name, source in mod.scripts:
        title = f"{MOD_MARK}{mod.name}/{script_name}".encode("utf-8")
        sid = int(hashlib.md5(title).hexdigest()[:7], 16)  # 결정적이고 안 겹치는 id
        fresh.append([sid, title, zlib.compress(source.encode("utf-8"))])

    main_at = max(
        (i for i, e in enumerate(kept) if bytes(e[1]) == b"Main"), default=len(kept)
    )
    result = kept[:main_at] + fresh + kept[main_at:]

    from . import rubywrite

    payload = rubywrite.dumps(result)
    again = rubyread.loads(payload)  # 쓰기 전에 왕복 확인 — 코어를 깨뜨리면 게임이 안 뜬다
    if len(again) != len(result) or any(
        bytes(a[1]) != bytes(b[1]) for a, b in zip(again, result)
    ):
        raise NoBundle("왕복 확인이 어긋났어요 — 코어를 건드리지 않았어요")

    backup = game_dir / SCRIPTS_BACKUP
    if not backup.exists():
        _put(backup, scripts_path.read_bytes())
    _put(scripts_path, payload)

    brought = modassets.install(mod, game_dir)
    return {
        "mod": mod.name,
        "did": did,
        "total": len(result),
        "backup": str(backup),
        "assets": len(brought["written"]) + len(brought["skipped"]),
    }


def _uninject(mod: Mod, game_dir: Path) -> dict:
    """코어에서 이 모드의 섹션만 걷어 낸다."""
    from . import rubywrite

    scripts_path = game_dir / SCRIPTS
    if not scripts_path.is_file():
        raise ModMissing(f"설치돼 있지 않아요: {mod.name}")
    entries = rubyread.loads(scripts_path.read_bytes())
    prefix = f"{MOD_MARK}{mod.name}/".encode("utf-8")
    kept = [e for e in entries if not bytes(e[1]).startswith(prefix)]
    if len(kept) == len(entries):
        raise ModMissing(f"설치돼 있지 않아요: {mod.name}")
    _put(scripts_path, rubywrite.dumps(kept))

    taken = modassets.remove(mod, game_dir)
    return {
        "mod": mod.name,
        "did": "제거됨",
        "total": len(kept),
        "assets": len(taken["removed"]) + len(taken["reverted"]),
        "warnings": _kept_note(taken),
    }


def _kept_note(taken: dict) -> list:
    """못 지운 자리 안내 — 순정이 있던 자리인데 되돌릴 백업이 없어 그대로 뒀다."""
    left = taken.get("kept") or []
    if not left:
        return []
    heads = ", ".join(left[:3]) + (f" 외 {len(left) - 3}개" if len(left) > 3 else "")
    return [f"파일 {len(left)}개({heads})는 그대로 뒀어요 — 원래 게임에 있던 자리인데 "
            "되돌릴 백업이 없어요(같은 자리를 쓰는 다른 모드가 먼저 빠지며 가져갔을 수 "
            "있어요). 원본 배포물에서 그 파일만 덮어 주세요."]


_core_memo: dict = {}


def merge_core(payload: bytes, current: bytes | None) -> bytes:
    """코어 통째 교체본을 섹션 병합으로 바꾼다.

    통째 교체는 야생 배포의 기본값이지만, 그대로 쓰면 코어 안에 사는 주입 모드가
    전멸한다(2026-08-04 실기 — 한글패치 설치가 말없이 모드 전부를 걷어냈다).
    규칙 둘: 게임에 살아 있는 주입(MOD:) 섹션은 Main 앞에 도로 꽂아 보존하고,
    교체본에 실려 온 남의 주입 섹션은 뺀다(조립 흔적이 유저 모르게 설치되는 것 방지).
    """
    from . import rubywrite

    def title(entry) -> str:
        return bytes(entry[1]).decode("utf-8", "replace") \
            if isinstance(entry[1], (bytes, bytearray)) else str(entry[1])

    base = [e for e in rubyread.loads(payload) if not title(e).startswith(MOD_MARK)]
    riders = []
    if current is not None:
        try:
            riders = [e for e in rubyread.loads(current) if title(e).startswith(MOD_MARK)]
        except Exception:
            riders = []  # 지금 코어가 못 읽히면 보존할 주입도 읽을 수 없다
    if riders:
        main_at = next((i for i, e in enumerate(base) if title(e) == "Main"), len(base))
        base = base[:main_at] + riders + base[main_at:]
    return rubywrite.dumps(base)


def same_core(source: Path, target: Path) -> bool:
    """두 코어가 주입 섹션을 빼고 같은가. 파일 도장으로 기억해 폴링에도 싸다."""
    try:
        key = (str(source), str(target))
        stamp = tuple((p.stat().st_size, p.stat().st_mtime_ns) for p in (source, target))
    except OSError:
        return False
    kept = _core_memo.get(key)
    if kept and kept[0] == stamp:
        return kept[1]

    def bones(path: Path):
        return [
            (bytes(e[1]), zlib.decompress(bytes(e[2])))
            for e in rubyread.loads(path.read_bytes())
            if not bytes(e[1]).decode("utf-8", "replace").startswith(MOD_MARK)
        ]

    try:
        told = bones(source) == bones(target)
    except Exception:
        told = False  # 어느 쪽이든 Marshal이 아니면 같다고 말할 근거가 없다
    _core_memo[key] = (stamp, told)
    return told


def _read(bundle: Path) -> list:
    if not bundle.is_file():
        raise NoBundle(f"플러그인 파일이 없어요: {bundle}")
    packed = rubyread.loads(bundle.read_bytes())
    if not isinstance(packed, list):
        raise NoBundle(f"플러그인 파일 형식이 달라요: {bundle}")
    return packed


def _back_up(game_dir: Path) -> Path:
    backup = game_dir / BACKUP
    if not backup.exists():
        _put(backup, (game_dir / BUNDLE).read_bytes())
    return backup


def _write(bundle: Path, entries: list) -> None:
    """묶음을 다시 적는다.

    상류 기록기가 아니라 `rubywrite`를 쓴다 — 상류는 문자열에 번호를 안 매겨 가리킴이
    어긋나고, 그러면 다른 플러그인의 이름 자리가 엉뚱한 값으로 바뀐다(`rubywrite` 참고).
    쓰기 전에 되읽어 항목 수와 이름을 대조한다 — 주입형과 같은 방어다.
    """
    from . import rubywrite

    payload = rubywrite.dumps(entries)
    again = rubyread.loads(payload)
    if not isinstance(again, list) or len(again) != len(entries) or any(
        str(a[0]) != str(b[0]) for a, b in zip(again, entries)
    ):
        raise NoBundle("왕복 확인이 어긋났어요 — 묶음을 건드리지 않았어요")
    _put(bundle, payload)


def _put(target: Path, blob: bytes) -> None:
    spare = target.with_name(target.name + ".writing")
    spare.write_bytes(blob)
    import os

    os.replace(spare, target)


def _safe(name: str) -> str:
    return _UNSAFE.sub("_", name).strip() or "mod"


def _plain(value):
    """루비 심볼이 섞인 메타를 JSON으로 담을 수 있는 모양으로."""
    from rubymarshal.classes import RubyString, Symbol

    if isinstance(value, Symbol):
        return {"$sym": str(value).lstrip(":")}
    if isinstance(value, RubyString):
        return str(value)
    if isinstance(value, dict):
        return {_key(key): _plain(one) for key, one in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(one) for one in value]
    return value


def _key(value) -> str:
    from rubymarshal.classes import Symbol

    return ":" + str(value).lstrip(":") if isinstance(value, Symbol) else str(value)


def _ruby(value):
    from rubymarshal.classes import Symbol

    if isinstance(value, dict):
        if set(value) == {"$sym"}:
            return Symbol(value["$sym"])
        return {(Symbol(k[1:]) if k.startswith(":") else k): _ruby(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_ruby(one) for one in value]
    return value
