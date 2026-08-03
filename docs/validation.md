# 실물 검증 기록 (2026-08-03)

합성 픽스처가 아니라 진짜 게임 설치본과 진짜 보관소로 돌린 기록이다. 모든 수치는
실측이고, 명령과 출력을 그대로 붙였다. 추정에는 따로 표시를 달았다.

검증 대상 커밋은 `5d8446d`(pytest 20건 green 상태)다.

## 판 (환경)

측정 환경은 WSL2에서 `/mnt/d`(NTFS, drvfs)를 통해 읽고 쓰는 조건이다. 파일 하나하나의
입출력이 느린 판이라 걸린 시간은 이 조건에서만 유효하다.

보관소는 `/mnt/d/GameVault/mods`를 읽기 전용으로만 썼다. 검증이 끝난 뒤
`find /mnt/d/GameVault/mods -newermt "2026-08-03 23:00"`이 아무것도 내놓지 않아
보관소가 그대로임을 확인했다.

게임 사본은 `/mnt/d/GameVault/_modkit-validation/` 아래에 만들었다.

| 사본 | 원본 | 크기 | `cp -r` 소요 |
|---|---|---|---|
| `z-cli` | `/mnt/d/Game/Pokemon Z/V2.18` | 931M | 4분 18.6초 |
| `z-fanlib` | `/mnt/d/Game/Pokemon Z/V2.18` | 931M | 2분 12.8초 |
| `ws` | `/mnt/d/Game/Pokemon Wishing Star/v1.0.8` | 563M | 5분 58.7초 |

게임 설치본은 `/mnt/d/GameVault` 아래가 아니라 `/mnt/d/Game` 아래에 있다. 보관소만
GameVault에 있고 설치본은 별도 트리다.

```
$ find /mnt/d/Game -maxdepth 4 \( -name Scripts.rxdata -o -name PluginScripts.rxdata \)
/mnt/d/Game/Pokemon Wishing Star/v1.0.8/Data/PluginScripts.rxdata
/mnt/d/Game/Pokemon Wishing Star/v1.0.8/Data/Scripts.rxdata
/mnt/d/Game/Pokemon Z/V2.18/Data/Scripts.rxdata            ← 묶음 없는 옛 엔진
...
```

## 보관소 층위

`--store`는 보관소 뿌리(`/mnt/d/GameVault/mods`)와 게임 칸
(`/mnt/d/GameVault/mods/Pokemon Z Fangame`) 둘 다 받는다. `modstore._find_folder`가
`<보관소>/<모드>`와 `<보관소>/<게임>/<모드>`를 모두 훑기 때문이다. 실측:

```
$ MODKIT_STORE=/mnt/d/GameVault/mods uv run python -m modkit.cli shelf
Better Following (Pokemon: Wishing Star)
... (14줄, 두 게임 전부)

$ uv run python -m modkit.cli shelf --store "/mnt/d/GameVault/mods/Pokemon Z Fangame"
Battle Speed Z (Pokemon Z Fangame)
... (7줄, Z만)
```

둘 다 종료 코드 0. `fanlib`가 쓰는 기본값도 뿌리 쪽(`/mnt/d/GameVault/mods`)이므로
뿌리를 주는 것을 원칙으로 삼는다.

## Step 1 — 포켓몬 Z 주입 왕복

주입형(묶음 없는 옛 엔진) 경로다. 사본 `z-cli`에서 `UI Text KR`을 걷어 내고 다시 얹었다.

```
$ md5sum z-cli/Data/Scripts.rxdata
7e162212eb742142805cc45db5e027a1        # 처음

$ uv run python -m modkit.cli remove "UI Text KR" z-cli
UI Text KR: 제거됨
$ md5sum z-cli/Data/Scripts.rxdata
f127cf6f78e7c180783d4de0339a7379        # 걷어 낸 뒤

$ uv run python -m modkit.cli apply "UI Text KR" z-cli
UI Text KR: 설치됨
$ md5sum z-cli/Data/Scripts.rxdata
7e162212eb742142805cc45db5e027a1        # 처음과 같음
```

걷어 내기 0.10초, 다시 얹기 0.33초(둘 다 `uv run` 시동 포함). 파일 크기는 1,031,415바이트.
`modstore.installed`가 내놓는 목록도 왕복 전후가 같다 — `['Battle Speed Z',
'Better Movements Z', 'Controller UX Z', 'Frame Profiler', 'GC Tamer', 'UI Text KR']`.

### fanlib 심 경유 대조

같은 원본에서 뜬 두 번째 사본 `z-fanlib`에 `fanlib.modstore`로 똑같은 왕복을 걸었다.

```
$ cd fangame-library && uv run python -c "from fanlib import modstore; ..."
DEFAULT_STORE: /mnt/d/GameVault/mods
module file: /home/durumii/workspace/claude-native/sketches/modkit/modkit/modstore.py
remove: {'mod': 'UI Text KR', 'did': '제거됨', 'total': 268, 'assets': 0}
apply : {'mod': 'UI Text KR', 'did': '설치됨', 'total': 269, ...}

$ md5sum z-fanlib/Data/Scripts.rxdata
7e162212eb742142805cc45db5e027a1        # CLI 쪽과 같은 해시
```

두 경로의 결과 바이트가 같다. 다만 이 대조가 무엇을 말하는지는 정확히 적어 둬야 한다.
`fangame-library` HEAD `5d52eb6`에서 모드 코어가 이미 modkit으로 이사했고, `fanlib/modstore.py`는
`sys.modules[__name__] = modkit.modstore`로 modkit 모듈을 그대로 내미는 심이다. 위
출력의 `module file`이 modkit 경로를 가리키는 것이 그 증거다. 그러므로 이 결과는 **서로
다른 두 구현이 같은 답을 냈다는 뜻이 아니라, 심이 modkit으로 제대로 이어지고 기본 보관소
경로가 뿌리로 잡힌다는 뜻**이다. 독립 구현 대조는 이 시점에 성립하지 않는다.

## Step 2 — 매니페스트 실측

깨끗한 V2.18 원본이 남아 있지 않아(`/mnt/d/Game/Pokemon Z/`에는 `V2.18`과
`V2.18 한글패치 v3`뿐이고 둘 다 패치본이다) 브리프의 대체안을 따랐다. 지금 설치본
(v5 패치 적용판)을 기준으로 삼아 매니페스트를 뜨고, 그 매니페스트로 사본을 진단했다.

```
$ time uv run python -m modkit.cli manifest "/mnt/d/Game/Pokemon Z/V2.18" \
    -o z-v218-v5.json --game "Pokemon Z Fangame" --version "V2.18+v5"
매니페스트 저장: z-v218-v5.json (19109개 파일)
1:47.82 total
```

파일 19,109개에 1분 47.8초, 매니페스트 JSON은 1,236,211바이트. 브리프가 예상한
"수천 파일 수초 이내"와 어긋난다 — 파일 수가 한 자릿수 배 많고, 시간은 두 자릿수 배
느리다. CPU는 14%만 쓰고 나머지는 대기라 병목은 CRC 계산이 아니라 drvfs 입출력으로
보인다(추정).

자기 자신 진단은 전부 원본 일치로 떨어졌다.

```
$ time uv run python -m modkit.cli diagnose z-cli -m z-v218-v5.json
원본 일치 19109 · 아는 변경 0 · 외래 0 · 누락 0
깨끗해요 — 외래 파일이 없어요.
1:48.81 total   (종료 코드 0)
```

이 결과는 Step 1의 왕복이 `Scripts.rxdata` 한 파일만이 아니라 설치본 전체에서
바이트 동일하게 끝났다는 증거이기도 하다.

이어서 사본을 두 군데 건드리고 다시 진단했다. `GC Tamer`를 걷어 내
`Data/Scripts.rxdata`를 바꾸고, `Data/_tamper_probe.txt`를 새로 심었다.

```
$ uv run python -m modkit.cli remove "GC Tamer" z-cli
GC Tamer: 제거됨
$ printf 'tamper probe\n' > z-cli/Data/_tamper_probe.txt

$ uv run python -m modkit.cli diagnose z-cli -m z-v218-v5.json --store /nonexistent-store
원본 일치 19108 · 아는 변경 0 · 외래 2 · 누락 0
외래: Data/Scripts.rxdata, Data/_tamper_probe.txt        (종료 코드 2)

$ uv run python -m modkit.cli diagnose z-cli -m z-v218-v5.json --store /mnt/d/GameVault/mods
원본 일치 19108 · 아는 변경 1 (한글패치 통합) · 외래 1 · 누락 0
외래: Data/_tamper_probe.txt                             (종료 코드 2)
```

보관소를 물리면 `Data/Scripts.rxdata`가 외래에서 아는 변경으로 넘어간다. 주인으로
찍히는 것은 `한글패치 통합`인데, 그 카드가 `Data/Scripts.rxdata`를 에셋으로 들고 있기
때문이다(`/mnt/d/GameVault/mods/Pokemon Z Fangame/한글패치 통합/Data/Scripts.rxdata`가
실재한다). 같은 경로를 주장하는 모드가 여럿일 때 이름 하나만 찍히는 구조라는 점은
알아 둘 만하다.

에셋 대부분이 known으로 넘어가는지는 이번 조건에서 확인하지 못했다. 매니페스트를
패치본에서 떴으므로 패치가 덮은 파일이 애초에 원본 일치로 잡히기 때문이다. 깨끗한
V2.18을 구하면 그때 다시 재야 한다.

## Step 3 — 묶음형(Wishing Star) 왕복

`Data/PluginScripts.rxdata`를 쓰는 묶음형 경로다. 사본 `ws`(v1.0.8)에는 보관소의
Wishing Star 모드가 하나도 설치돼 있지 않아, 게임에 이미 들어 있는 플러그인 하나
(`Namebox`)를 꺼내 보관소로 만들고 왕복시켰다. 실보관소를 건드리지 않으려고 임시
보관소 `_modkit-validation/scratch-store`를 따로 썼다.

```
$ uv run python -m modkit.cli harvest ws "Namebox" --store scratch-store
꺼냄: Namebox → scratch-store/Pokemon Wishing Star/Namebox     (0.22초)

$ md5sum ws/Data/PluginScripts.rxdata
fac4c174af40f2d29b214f3e1a4d53c2        # 처음 (779,093바이트)

$ uv run python -m modkit.cli remove "Namebox" ws --store scratch-store
Namebox: 제거됨
ef46aaee6882fe9ca04c6cebea1569d1

$ uv run python -m modkit.cli apply "Namebox" ws --store scratch-store
Namebox: 설치됨
901db20eadeae0b65066925cc6f00eaf        ← 처음과 다르다
```

바이트가 돌아오지 않았다. 원인을 둘로 갈라 확인했고, 둘 다 실측이다.

첫째는 자리다. `Namebox`는 26개 중 12번 자리에 있었는데 다시 얹은 뒤에는 25번(끝)에
있다. 카드에 `order` 선언이 없으면 `declare.place`가 끝에 붙이기 때문이다.

둘째는 직렬화 배치다. 자리를 원래대로 되돌려 다시 써도 처음 바이트가 나오지 않는다.

```python
a = modstore._read(원본);  b = modstore._read(왕복본)
len(a) == len(b) == 26
set(이름) 같음: True
이름별 항목 값이 전부 같음: True
a를 그대로 다시 쓰기      → fac4c174af40f2d29b214f3e1a4d53c2  (처음과 같음, 779,093)
b를 a의 순서로 재배열해 쓰기 → ca0678c5eac4beb1ab58a4a559dda917  (779,103)
```

즉 26개 항목의 **값은 전부 같은데** 바이트가 10바이트 어긋난다. 읽고 그대로 다시 쓰는
것 자체는 바이트 동일(`fac4…` → `fac4…`)이므로 쓰기 자체는 충실하다. 남는 설명은 Ruby
Marshal의 객체 링크 테이블이다 — 같은 객체가 두 번 나오면 뒷쪽은 backreference로
나가는데, 항목 하나를 새로 만들어 끼우면 그 공유 관계가 달라진다(추정, 링크 바이트를
직접 뜯어보지는 않았다).

도구 자신의 반복 재현성은 확인했다. 같은 왕복을 한 번 더 돌리면 중간 해시와 끝 해시가
1차와 정확히 같다.

```
2차 제거 → ef46aaee6882fe9ca04c6cebea1569d1   (1차와 같음)
2차 설치 → 901db20eadeae0b65066925cc6f00eaf   (1차와 같음)
```

왕복 뒤에도 묶음은 정상적으로 읽힌다 — 플러그인 26개, 정의된 클래스 1,197개가 잡힌다.

정리하면 묶음형은 **뜻은 왕복하지만 바이트는 왕복하지 않는다.** 그리고 어긋남은 게임
원본 바이트에서 처음 벗어나는 한 번에만 생기고, 그 뒤로는 도구가 자기 출력을 그대로
재현한다.

## 어긋난 관측 (고치지 않고 기록만)

1. 게임 설치본이 `/mnt/d/GameVault` 아래가 아니라 `/mnt/d/Game` 아래에 있다. 브리프의
   전제와 다르다.
2. 매니페스트 캡처가 파일 19,109개에 1분 47.8초다. 브리프가 예상한 "수천 파일 수초
   이내"와 어긋난다.
3. 묶음형 왕복이 바이트 동일하지 않다. 자리(선언 없으면 끝으로)와 Marshal 링크 배치
   두 갈래다.
4. 같은 경로를 주장하는 모드가 여럿일 때 `diagnose`의 아는 변경은 이름 하나만 찍는다.
5. 보관소 카드의 `game`(`Pokemon: Wishing Star`)과 폴더 이름(`Pokemon Wishing Star`)이
   다르다. `harvest`도 같은 규칙으로 콜론을 떼고 폴더를 만들어 실보관소와 어긋나지
   않지만, 두 이름이 다르다는 사실 자체는 적어 둔다.
6. 보관소의 Wishing Star 모드는 `from_build`가 `v1.0.7`인데 설치본은 v1.0.8이다.
   이번 검증에서는 게임 자신의 플러그인을 꺼내 썼으므로 이 어긋남은 시험하지 않았다.

## 검증 뒤 정리

`/mnt/d/GameVault/_modkit-validation/`(사본 3개와 임시 보관소)은 기록을 뜬 뒤 지웠다.
실보관소와 게임 원본은 이 검증에서 한 번도 쓰기 대상이 아니었다.
