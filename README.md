# essentials-modkit

RPG Maker 기반 Essentials 팬게임(포켓몬 Z, Wishing Star 등)의 모드·패치
관리자예요. 모드를 **mod.json 카드가 붙은 폴더** 하나로 정의하고, 그 단위로
얹고 빼고 진단해요. 규약 전문은 [SPEC.md](SPEC.md).

## 유저용 — 패치·모드 설치와 진단

1. [릴리스](https://github.com/durumiii/essentials-modkit/releases)에서
   `modkit.exe` 받기
2. 실행해서 게임 폴더 고르기 — 패치가 온전한지, 옛 패치 흔적이 남았는지
   진단이 보여줘요
3. 흔적이 있으면 격리 — 게임 폴더 안 `_quarantine`으로 옮겨 두는 거라
   언제든 되돌릴 수 있어요
4. 모드 서랍에서 모드 얹고 빼기 — 받아 둔 모드 zip은 끌어다 넣기

알아 둘 것:

- 진단에는 패치 배포판에 동봉된 `manifest.json`이 필요해요.
  (포켓몬 Z 한글패치는 v5부터 동봉.)
- 파일이 많은 게임은 진단에 몇 분 걸려요.
- 창이 안 뜨면 Edge WebView2 런타임을 설치하세요. (윈도우 11은 기본 내장.)

## 제작자용 — 모드 만들기

```
modkit new "내 모드" --game "게임 제목"   # 1. 뼈대 생성
                                          # 2. 스크립트를 쓰고 mod.json 채우기
modkit lint "내 모드"                     # 3. 규약 검사 — 오류 0이 될 때까지
                                          # 4. 폴더째 zip으로 묶으면 배포본
```

설치 안내문은 따로 쓸 필요 없어요. 설치는 유저 쪽 modkit이 해요.

mod.json 필드:

| 필드 | 뜻 |
|---|---|
| `name`, `scripts` | 필수. 에셋만 있는 모드는 scripts를 빈 배열로 |
| `game` | 강력 권장. 다른 게임에 잘못 얹히는 사고를 막아요 |
| `description` | 유저의 모드 서랍에 그대로 뜨는 설명 |
| `touches` `order` `requires` `conflicts` | 여러 모드가 공존할 때의 선언. [SPEC.md](SPEC.md) 2절 |

`lint`는 두 단계로 알려줘요. **오류**는 규약 위반이라 고쳐야 배포할 수 있고,
**권장**은 경고만 해요(예: 설명이 비면 "유저 서랍에 설명이 안 떠요").

### AI 에이전트에게 시킨다면

에이전트에게 이 저장소 주소를 주고 "이 규약대로"라고 하면 돼요.

- [llms.txt](llms.txt) — 에이전트용 안내문
- `modkit new`가 모드 폴더에 심는 `AGENTS.md` — 작업 폴더 안에서 같은 역할
- 종료 조건: `modkit lint` 오류 0

## CLI

`modkit.exe`에 인자를 주면(개발 중엔 `uv run app.py`) 명령줄 도구가 돼요.

```
modkit new · lint · manifest · diagnose · harvest · apply · remove · shelf
```

## 검증

실제 게임 설치본 두 개(포켓몬 Z, Wishing Star)로 설치·제거 왕복을 바이트
단위로 대조한 기록이 [docs/validation.md](docs/validation.md)에 있어요.
SPEC.md 각 절에는 그 절을 검증하는 테스트 파일 이름이 달려 있어요.
