# essentials-modkit

RPG Maker 기반 Essentials 팬게임(포켓몬 Z, Wishing Star 등)의 모드·패치 관리자.

예전 패치 위에 새 패치를 덮었다가 게임이 깨지고, 폴더에 뭐가 깔렸는지 아무도
모르게 되는 문제를 풀기 위해 만들었다. 모드를 **mod.json 카드가 붙은 폴더**
하나로 정의하고, 그 단위로 얹고 빼고 진단한다. 규약 전문은 [SPEC.md](SPEC.md).

## 유저용 — 패치·모드 설치와 진단

1. [릴리스](https://github.com/durumiii/essentials-modkit/releases)에서
   `modkit.exe`를 받는다. 설치 과정 없이 더블클릭하면 바로 뜬다.
2. 게임 폴더를 고르면 **진단**이 돈다. 패치가 온전한지, 옛 패치 흔적이
   남았는지 보여준다.
3. 흔적이 있으면 **격리** 버튼 하나로 게임 폴더 안 `_quarantine`에 옮긴다.
   지우지 않으므로 언제든 되돌릴 수 있다.
4. **모드 서랍**에서 모드를 얹고 뺀다. 받아 둔 모드 zip은 끌어다 넣으면 된다.
   충돌하는 모드는 이유와 함께 막아 주고, 순서가 중요한 모드는 알아서 맞는
   자리에 놓는다.

알아 둘 것:

- 진단은 패치 배포판에 `manifest.json`이 들어 있어야 돈다.
  (포켓몬 Z 한글패치는 v5부터 들어 있다.)
- 파일이 많은 게임은 진단에 몇 분 걸린다.
- 창이 안 뜨면 Edge WebView2 런타임이 없는 구형 윈도우 10이다.
  마이크로소프트 공식 페이지에서 받으면 해결된다. (윈도우 11은 기본 내장.)

## 제작자용 — 모드 만들기

```
modkit new "내 모드" --game "게임 제목"   # 1. 뼈대 생성
                                          # 2. 스크립트를 쓰고 mod.json을 채운다
modkit lint "내 모드"                     # 3. 규약 검사 — 오류 0이 될 때까지
                                          # 4. 폴더째 zip으로 묶으면 그게 배포본
```

설치 안내문은 쓸 필요 없다. 유저 쪽 설치는 modkit이 알아서 한다.

mod.json 필드는 이렇다:

| 필드 | 뜻 |
|---|---|
| `name`, `scripts` | 필수. 에셋만 있는 모드는 scripts를 빈 배열로 |
| `game` | 강력 권장. 다른 게임에 잘못 얹히는 사고를 막는다 |
| `description` | 유저의 모드 서랍에 그대로 뜨는 설명 |
| `touches` `order` `requires` `conflicts` | 여러 모드가 공존할 때의 선언. [SPEC.md](SPEC.md) 2절 참고 |

`lint`의 잔소리는 두 단계다. **오류**(규약 위반, 고치기 전엔 배포 불가)와
**권장**(비워 두면 유저가 손해 보는 것 — 이를테면 설명이 비면 "유저 서랍에
설명이 안 떠요" 하고 알려 준다).

### AI 에이전트에게 시킨다면

에이전트에게 이 저장소 주소를 주고 "이 규약대로"라고 하면 된다.

- [llms.txt](llms.txt) — 에이전트용 안내문 (저장소 루트)
- `modkit new`가 모드 폴더에 심어 주는 `AGENTS.md` — 작업 폴더 안에서 같은 역할
- 종료 조건은 사람과 같다: `modkit lint` 오류 0

## CLI

GUI와 CLI는 같은 파일이다. `modkit.exe`에 인자를 주면(개발 중엔
`uv run app.py`) 명령줄 도구가 된다.

```
modkit new · lint · manifest · diagnose · harvest · apply · remove · shelf
```

각 명령에 `--help`가 달려 있다.

## 검증

실제 게임 설치본 두 개(포켓몬 Z, Wishing Star)로 설치·제거를 왕복시키고
바이트 단위로 대조한 기록이 [docs/validation.md](docs/validation.md)에 있다.
SPEC.md의 각 절에는 그 절을 검증하는 테스트 파일 이름이 달려 있다.
