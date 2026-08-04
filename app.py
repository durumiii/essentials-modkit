"""GUI 진입점 — pywebview 창 + Api(js_api).

Api는 순수 파이썬이라 창 없이도 테스트할 수 있다. 모든 메서드는 JSON 직렬화 가능한
dict를 반환하고 예외를 밖으로 던지지 않는다(`{"ok": False, "error": 사유}`).
"""
import json
import os
import sys
import zipfile
from pathlib import Path, PurePosixPath

from modkit import declare, gameinfo, manifest, modassets, modstore

MANIFEST_NAME = "manifest.json"
LOG_NAME = "modkit-log.jsonl"


def _banner_uri(path: str) -> str:
    """배너 이미지를 data URI로 — file:// 은 WebView 보안 정책에 걸릴 수 있어 인라인이 안전하다."""
    if not path:
        return ""
    try:
        p = Path(path)
        raw = p.read_bytes()
        if len(raw) > 2 << 20:  # 2MB 넘는 그림을 매번 base64로 나르진 않는다
            return ""
        kind = {"jpg": "jpeg"}.get(p.suffix.lower().lstrip("."), p.suffix.lower().lstrip("."))
        import base64
        return f"data:image/{kind};base64,{base64.b64encode(raw).decode()}"
    except OSError:
        return ""


class Api:
    def __init__(self, store_dir, state_path):
        self.store_dir = Path(store_dir)
        self.state_path = Path(state_path)
        self._window = None

    def set_window(self, window) -> None:
        self._window = window

    def pick_folder(self) -> dict:
        if self._window is None:
            return {"ok": False, "error": "no-window"}
        import webview  # 지연 임포트 — 창 없는 환경(테스트)에서는 안 닿는다

        picked = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        path = picked[0] if picked else None
        return {"ok": bool(path), "path": path or ""}

    def pick_zip(self) -> dict:
        """드래그앤드롭이 실경로를 못 주는 pywebview 한계의 폴백 — 파일 선택 대화상자."""
        if self._window is None:
            return {"ok": False, "error": "no-window"}
        import webview  # 지연 임포트 — 창 없는 환경(테스트)에서는 안 닿는다

        picked = self._window.create_file_dialog(
            webview.OPEN_DIALOG, file_types=("Zip 파일 (*.zip)",))
        path = picked[0] if picked else None
        return {"ok": bool(path), "path": path or ""}

    def recent(self) -> dict:
        try:
            if not self.state_path.is_file():
                return {"ok": True, "paths": []}
            told = json.loads(self.state_path.read_text(encoding="utf-8"))
            return {"ok": True, "paths": told.get("recent", [])}
        except Exception as err:
            return {"ok": False, "error": str(err)}

    def remember(self, path) -> dict:
        try:
            path = str(path)
            paths = self.recent().get("paths", [])
            paths = [path] + [p for p in paths if p != path]
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(
                json.dumps({"recent": paths}, ensure_ascii=False), encoding="utf-8")
            return {"ok": True, "paths": paths}
        except Exception as err:
            return {"ok": False, "error": str(err)}

    def game_status(self, path) -> dict:
        try:
            game_dir = Path(path)
            try:
                installed = modstore.installed(game_dir)
            except modstore.NoBundle:
                installed = []
            who = gameinfo.identify(game_dir)
            return {
                "ok": True,
                "title": who["title"],
                "label": who["label"],
                "known": who["known"],
                "banner": _banner_uri(who["banner"]),
                "installed": installed,
                "has_manifest": (game_dir / MANIFEST_NAME).is_file(),
                # 게임 폴더인지 어림 판정 — 엉뚱한 폴더를 골랐을 때 화면이 알려 준다
                "looks_like_game": (game_dir / "Data").is_dir()
                or (game_dir / "Game.ini").is_file(),
            }
        except Exception as err:
            return {"ok": False, "error": str(err)}

    def diagnose(self, path) -> dict:
        game_dir = Path(path)
        manifest_path = game_dir / MANIFEST_NAME
        if not manifest_path.is_file():
            return {"ok": False, "error": "매니페스트가 없어요 — 패치에 manifest.json이 동봉돼 있는지 확인해요."}
        try:
            told = manifest.load(manifest_path)
            diag = manifest.diagnose(game_dir, told, store=self.store_dir)
            return {
                "ok": True,
                "intact": len(diag.intact),
                "known": [list(pair) for pair in diag.known],
                "foreign": list(diag.foreign),
                "missing": list(diag.missing),
                "backups": len(diag.backups),
                "untracked": len(diag.untracked),
            }
        except Exception as err:
            return {"ok": False, "error": str(err)}

    def quarantine_foreign(self, path) -> dict:
        game_dir = Path(path)
        diag = self.diagnose(path)
        if not diag["ok"]:
            return diag
        foreign = diag["foreign"]
        if not foreign:
            return {"ok": True, "moved": 0, "box": ""}
        try:
            box = manifest.quarantine(game_dir, foreign)
            self._log(game_dir, "quarantine_foreign", str(box))
            return {"ok": True, "moved": len(foreign), "box": str(box)}
        except Exception as err:
            return {"ok": False, "error": str(err)}

    def mods(self, path) -> dict:
        try:
            game_dir = Path(path)
            title = gameinfo.read_title(game_dir)
            try:
                installed = modstore.installed(game_dir)
            except modstore.NoBundle:
                installed = []
            available = []
            for mod in modstore.shelf(self.store_dir, game=title):
                on = mod.name in installed
                if not on and not mod.scripts and mod.assets:
                    # 에셋 전용 모드는 묶음·주입 섹션에 이름이 안 남는다 — 파일로 답한다.
                    on = modassets.applied(mod, game_dir)
                available.append(
                    {"name": mod.name, "description": mod.description, "installed": on})
            return {"ok": True, "installed": installed, "available": available}
        except Exception as err:
            return {"ok": False, "error": str(err)}

    def edit_mod(self, name, new_name="", new_game="", game_path="") -> dict:
        """모드의 이름표와 게임 소속을 사람이 다듬는다 — 입양 기본값은 추정일 뿐이다."""
        try:
            final = name
            if new_name and new_name != name:
                builds = [game_path] if game_path else []
                modstore.rename(self.store_dir, name, new_name, builds=builds)
                final = new_name
            mod = modstore.read_mod(self.store_dir, final)
            game = mod.game
            if new_game and new_game != mod.game:
                modstore.reassign(self.store_dir, final, new_game)
                game = new_game
            return {"ok": True, "name": final, "game": game}
        except Exception as err:
            return {"ok": False, "error": str(err)}

    def delete_mod(self, name, game_path="") -> dict:
        """모드를 서랍에서 치운다 — 설치돼 있으면 먼저 걷어내고, 실물은 _trash로 옮긴다."""
        try:
            if game_path:
                try:
                    if name in modstore.present(self.store_dir, Path(game_path)):
                        modstore.remove(name, Path(game_path), store=self.store_dir)
                except Exception:
                    pass  # 게임 쪽 걷어내기가 안 돼도 서랍 치우기는 진행한다
            box = modstore.discard(self.store_dir, name)
            return {"ok": True, "trash": str(box)}
        except Exception as err:
            return {"ok": False, "error": str(err)}

    def preview_apply(self, path, name) -> dict:
        """설치 전 미리보기 — 아무것도 쓰지 않고 차단 사유·겹침 경고만 계산한다.

        touches는 기계로 아는 정보다. 설치 후 통보가 아니라 설치 전에 보여 주고
        유저가 계속할지 고르게 한다.
        """
        try:
            game_dir = Path(path)
            mod = modstore.read_mod(self.store_dir, name)
            card = json.loads((Path(mod.folder) / "mod.json").read_text(encoding="utf-8"))
            already = modstore.present(self.store_dir, game_dir, game=mod.game or None)
            others = [one for one in already if one != mod.name]
            try:
                warnings = declare.gate(card, others, self.store_dir)
            except declare.Blocked as no:
                return {"ok": True, "blocked": no.reasons, "warnings": []}
            return {"ok": True, "blocked": [], "warnings": warnings}
        except Exception as err:
            return {"ok": False, "error": str(err)}

    def apply_mod(self, path, name, force=False) -> dict:
        game_dir = Path(path)
        try:
            done = modstore.apply(self.store_dir, name, game_dir, force=force)
        except declare.Blocked as no:
            return {"ok": False, "blocked": no.reasons}
        except Exception as err:
            return {"ok": False, "error": str(err)}
        self._log(game_dir, "apply_mod", name)
        return {"ok": True, "did": done["did"], "warnings": done.get("warnings") or []}

    def remove_mod(self, path, name) -> dict:
        game_dir = Path(path)
        try:
            done = modstore.remove(name, game_dir, store=self.store_dir)
        except Exception as err:
            return {"ok": False, "error": str(err)}
        self._log(game_dir, "remove_mod", name)
        return {"ok": True, "did": done["did"], "warnings": []}

    def import_folder(self, folder_path, game_path="") -> dict:
        """풀린 폴더 반입 — 카드가 있으면 그대로 복사, 없으면 zip과 같은 입양 규칙."""
        import shutil

        try:
            src = Path(folder_path)
            if not src.is_dir():
                return {"ok": False, "error": "폴더가 아니에요 — zip은 zip 반입으로, 낱개 파일은 폴더에 담아 주세요."}
            card_path = next(
                (p for p in [src / "mod.json", *sorted(src.glob("*/mod.json"))] if p.is_file()),
                None)
            if card_path is None:
                return self._adopt_zip(src, game_path)
            card = json.loads(card_path.read_text(encoding="utf-8"))
            dest = self.store_dir / modstore._game_folder(card.get("game") or "기타") \
                / modstore._safe(card["name"])
            shutil.copytree(card_path.parent, dest, dirs_exist_ok=True)
            return {"ok": True, "name": card["name"]}
        except Exception as err:
            return {"ok": False, "error": str(err)}

    def _adopt_zip(self, zip_path, game_path) -> dict:
        from modkit import adopt

        if not game_path:
            return {"ok": False,
                    "error": "mod.json이 없는 zip이에요 — 게임 폴더를 먼저 연 뒤 반입하면 "
                             "모드로 만들 수 있어요."}
        try:
            got = adopt.adopt(zip_path, game_path, self.store_dir)
        except adopt.NotAMod as no:
            return {"ok": False, "error": str(no)}
        except Exception as err:
            return {"ok": False, "error": str(err)}
        return {"ok": True, "name": got.name, "adopted": True,
                "notes": list(got.notes) + list(got.warnings)}

    def import_zip(self, zip_path, game_path="") -> dict:
        try:
            with zipfile.ZipFile(zip_path) as zf:
                names = [n for n in zf.namelist() if not n.endswith("/")]
                for name in names:
                    if _escapes(name):
                        return {"ok": False, "error": f"경로 탈출 항목이에요: {name}"}

                card_name = next(
                    (n for n in names
                     if PurePosixPath(n).name == "mod.json" and len(PurePosixPath(n).parts) <= 2),
                    None)
                if card_name is None:
                    # 야생 배포물의 표준형이다 — 카드 없는 zip은 입양 규칙으로 받는다.
                    return self._adopt_zip(zip_path, game_path)

                card = json.loads(zf.read(card_name))
                mod_name = card["name"]
                game = card.get("game") or "기타"
                prefix = PurePosixPath(card_name).parent

                dest = self.store_dir / modstore._game_folder(game) / modstore._safe(mod_name)
                dest.mkdir(parents=True, exist_ok=True)
                for name in names:
                    rel = PurePosixPath(name).relative_to(prefix) if str(prefix) != "." \
                        else PurePosixPath(name)
                    target = dest / Path(*rel.parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(zf.read(name))
            return {"ok": True, "name": mod_name}
        except Exception as err:
            return {"ok": False, "error": str(err)}

    def _log(self, game_dir, action, target) -> None:
        entry = {"at": gameinfo.now(), "action": action, "target": target}
        with open(Path(game_dir) / LOG_NAME, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _escapes(name: str) -> bool:
    p = PurePosixPath(name)
    return p.is_absolute() or ".." in p.parts


def _attach_console() -> None:
    """--windowed로 묶은 exe는 stdout이 없다 — 부모 콘솔에 붙여 CLI 출력이 보이게 한다."""
    import ctypes

    kernel32 = ctypes.windll.kernel32
    if not kernel32.AttachConsole(-1):  # -1 = ATTACH_PARENT_PROCESS
        return
    kernel32.SetConsoleOutputCP(65001)  # 한글 출력이 cp949에서 깨지지 않게
    sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
    sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        if sys.platform == "win32" and getattr(sys, "frozen", False):
            _attach_console()
        from modkit.cli import main as cli_main
        return cli_main(argv)

    import webview  # 지연 임포트 — CLI 경로에서는 pywebview가 없어도 된다

    # onefile exe에서는 소스가 아니라 풀린 임시 폴더(_MEIPASS)에 web/이 놓인다.
    index = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "web" / "index.html"
    store_dir = Path(os.environ.get("MODKIT_STORE", modstore.DEFAULT_STORE))
    state_path = Path.home() / ".modkit" / "state.json"
    api = Api(store_dir, state_path)
    window = webview.create_window(
        "modkit — Essentials 팬게임 모드 관리자", str(index), js_api=api,
        width=780, height=680, min_size=(560, 480))
    api.set_window(window)
    webview.start(_wire_drop, window)
    return 0


def _wire_drop(window) -> None:
    """드롭된 파일의 실경로 배달.

    브라우저 보안상 JS의 File 객체에는 실경로가 없다 — pywebview는 **파이썬 쪽**
    DOM 이벤트의 직렬화에만 `pywebviewFullPath`를 실어 준다. 그래서 여기서 받아
    JS(`handleDroppedPaths`)로 넘긴다. 폴더 여부도 파이썬만 알 수 있어 함께 실어 준다.
    """
    from webview.dom import DOMEventHandler

    def on_drop(e):
        files = (e.get("dataTransfer") or {}).get("files") or []
        dropped = [
            {"path": p, "isDir": Path(p).is_dir()}
            for f in files if (p := f.get("pywebviewFullPath"))
        ]
        if dropped:
            window.evaluate_js(f"window.handleDroppedPaths({json.dumps(dropped)})")

    # prevent_default까지 파이썬 쪽에서 걸어야 브라우저가 파일을 열어 버리지 않는다.
    window.dom.document.events.dragover += DOMEventHandler(lambda e: None, True, True)
    window.dom.document.events.drop += DOMEventHandler(on_drop, True, True)


if __name__ == "__main__":
    sys.exit(main())
