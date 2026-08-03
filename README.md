# essentials-modkit

RPG Maker 기반 Essentials 팬게임(포켓몬 Z, Wishing Star 등)의 모드를 표준 카드
(`mod.json`) 한 장으로 다루는 도구다. 모드를 얹고 빼고, 설치본이 깨끗한지
진단하고, 옛 패치의 흔적은 지우는 대신 격리한다. 규약 전문은
[`SPEC.md`](SPEC.md)에 있다.

## 유저 — 패치와 모드를 관리하고 싶다면

[릴리스](https://github.com/durumiii/essentials-modkit/releases)에서
`modkit.exe`를 받아 더블클릭하면 끝이다. 설치 과정은 없다. 창을 그리는 데
Windows 10/11의 Edge WebView2 런타임이 필요한데, 윈도우 11에는 기본으로 들어
있다(없으면 마이크로소프트 공식 페이지에서 받는다).

화면은 세 걸음으로 흐른다. 게임 폴더를 고르면 진단이 돈다. 패치가 온전히
깔렸는지, 옛 패치의 흔적이 남았는지를 신호등으로 보여준다. 그다음 모드
서랍에서 보관소의 모드를 얹거나 빼거나, 모드 zip을 끌어다 보관소에 더한다.

진단에서 정체불명 파일이 나와도 지우지 않는다. 게임 폴더 안
`_quarantine/<날짜>/`로 옮겨 둘 뿐이라 언제든 통째로 되돌릴 수 있다. 진단은
패치 배포판에 동봉된 `manifest.json`이 있어야 돌고(포켓몬 Z 한글패치 v5부터),
파일이 많은 게임에서는 몇 분 걸린다.

## 제작자 — 모드를 만들고 싶다면

만드는 순서는 이렇다.

```
modkit new "내 모드" --game "게임 제목"   # 뼈대 생성
(스크립트를 쓰고 mod.json을 채운다)
modkit lint "내 모드"                     # 규약 검사 — 오류 0이 목표
(폴더째 zip으로 묶으면 그게 배포본)
```

`new`가 만드는 폴더에는 카드 뼈대와 함께 작업 지침(`AGENTS.md`)이 들어
있다. 카드의 필수 필드는 `name`과 `scripts`(에셋만 있는 모드는 빈 배열)이고,
`game`을 적어 두면 다른 게임에 잘못 얹히는 사고를 도구가 막아 준다. 선택
필드 `touches` · `order` · `requires` · `conflicts`는 여러 모드가 공존할 때의
선언이다. 충돌하면 사유와 함께 막고, 순서는 알아서 배치한다. 겹치는 자리는
유저에게 경고로 알린다. 필드 사전은 [`SPEC.md`](SPEC.md) 2절.

`lint`는 두 층으로 알려 준다. 오류(규약 위반 — 이대로는 배포 불가)와 권장
(비워 두면 유저가 손해 보는 것들 — 설명 없음, touches 선언 없음 따위).

설치 방식은 유저 쪽 도구가 설치본을 보고 알아서 고른다 — 묶음형
(`PluginScripts.rxdata`), 주입형(`Scripts.rxdata` 섹션), 에셋형 셋 중
하나다(SPEC.md 3절).

### AI 에이전트로 만든다면

에이전트에게 이 저장소 주소를 주고 "이 규약대로"라고 하면 된다. 저장소 루트의
[`llms.txt`](llms.txt)가 에이전트용 진입로이고, `new`가 심어 주는 `AGENTS.md`는
작업 폴더 안에서 같은 역할을 한다. 에이전트의 종료 조건은 사람과 같다 —
`modkit lint` 오류 0.

## CLI

GUI와 같은 exe(또는 `uv run app.py`)가 인자를 받으면 CLI가 된다:
`new` · `lint` · `manifest` · `diagnose` · `harvest` · `apply` · `remove` ·
`shelf`. 각 명령의 인자는 `--help`로 본다.

## 검증

합성 픽스처만이 아니라 실제 게임 설치본으로 왕복·진단을 돌린 기록이
[`docs/validation.md`](docs/validation.md)에 있다. 규약 문서(SPEC.md)의 각 절에는
그 절을 검증하는 테스트 파일명이 각주로 달려 있다.

---

## English summary

essentials-modkit is a standalone mod manager and packaging standard for RPG
Maker–based Essentials fan games (Pokémon Z, Wishing Star, and similar). A mod
is one folder with a `mod.json` card, readable `.rb` scripts, and asset
originals; the distribution unit is that folder zipped. The tool auto-detects
the install contract (bundled `PluginScripts.rxdata`, legacy `Scripts.rxdata`
injection, or asset-only), runs a three-layer pre-install check (block on
unmet requirements/conflicts, auto-place from declared ordering, warn on
undeclared overlaps), and never deletes — foreign files found during diagnosis
are quarantined under `_quarantine/<date>/`, fully restorable. End users grab
`modkit.exe` from Releases (double-click GUI, WebView2 required); authors
scaffold with `modkit new`, validate with `modkit lint`, and ship the folder
as a zip. Agent-facing entry point: `llms.txt`. Full contract: `SPEC.md`.
