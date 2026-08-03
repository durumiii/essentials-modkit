# modkit

RPG Maker 기반 Essentials 팬게임(포켓몬 Z, Wishing Star 등)의 모드를 표준 카드
(`mod.json`) 한 장으로 다루는 도구다. 모드를 얹고 빼고, 설치본이 깨끗한지
진단하고, 옛 패치의 흔적을 격리한다. 자세한 계약은 [`SPEC.md`](SPEC.md)에 있다.

## 유저용 빠른 시작

`app.py`를 인자 없이 실행하면 창(GUI)이 뜬다.

```
uv run app.py
```

화면은 세 걸음이다. 게임 폴더를 고르면 → 진단이 돈다(패치가 깨끗이 깔렸는지,
남은 옛 패치 흔적이 있는지 신호등으로 보여준다) → 모드 서랍에서 보관소의 모드를
얹거나 빼거나, zip을 끌어다 보관소에 더한다. 진단에서 외래 파일이 나오면
지우지 않고 게임 폴더 안 `_quarantine/<날짜>/`로 옮겨 두므로 통째로 되돌릴 수
있다.

패치 배포판에 `manifest.json`이 동봉돼 있으면(포켓몬 Z 한글패치 v5부터) 그
파일로 진단해 "패치가 제대로 깔렸는지, 잔재가 없는지"를 스스로 확인할 수 있다.

## 제작자용 카드 규약 요약

모드는 「폴더 하나 + `mod.json` 한 장 + 사람이 읽을 수 있는 `.rb`와 에셋
원본」이다. 배포 단위는 이 폴더를 그대로 압축한 zip이다.

카드 필수 필드는 `name`과 `scripts`(에셋만 있는 모드는 빈 배열)다. `game`을
적어 두면 다른 게임에서 나온 모드가 섞여 얹히는 일을 막는다. 선택 필드로
`touches`(건드리는 메서드·파일 — harvest가 초안을 채워 준다), `order`(다른
모드 상대의 앞/뒤 제약), `requires`/`conflicts`(의존과 공존 불가)가 있어,
여러 모드를 함께 쓸 때 충돌을 미리 알려 준다. 필드 전체 사전은
[`SPEC.md`](SPEC.md) 2절에 있다.

설치 계약은 설치본의 상태로 자동 판별된다 — `PluginScripts.rxdata`가 있으면
묶음형, 없으면 `Scripts.rxdata`에 섹션을 꽂는 주입형, 스크립트가 없으면
에셋형. 얹기 전에 차단(요구/충돌 검사) → 자동 배치(순서 제약) → 경고(같은
자리를 건드리는 모드 감지) 세 겹을 거친다(SPEC.md 3절).

CLI는 GUI와 같은 진입점이다: `manifest` · `harvest` · `apply` · `remove` ·
`diagnose`. 각 명령의 인자는 `uv run python -m modkit.cli <명령> --help`로
확인한다.

## 실물 검증

합성 픽스처가 아니라 실제 게임 설치본으로 왕복·진단을 돌린 기록은
[`docs/validation.md`](docs/validation.md)에 있다.

---

## English summary

modkit is a standalone tool for managing mods in RPG Maker–based Essentials
fan games (Pokémon Z, Wishing Star, and similar). A mod is a folder plus one
`mod.json` card plus readable `.rb` scripts and asset originals; the
distribution unit is that folder zipped. modkit auto-detects the install
contract from the target install (bundled `PluginScripts.rxdata`, legacy
`Scripts.rxdata` injection, or asset-only), runs a three-layer check before
installing (blocking on unmet requirements/conflicts, auto-placement from
declared ordering, warning on undeclared overlaps), and never deletes —
foreign files found during diagnosis are quarantined under
`_quarantine/<date>/` so they can be restored in full. Run `uv run app.py`
for the GUI, or `python -m modkit.cli <command>` for the CLI (`manifest`,
`harvest`, `apply`, `remove`, `diagnose`). Full contract in `SPEC.md`.
