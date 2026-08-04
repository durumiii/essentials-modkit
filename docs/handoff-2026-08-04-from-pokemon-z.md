# 핸드오프: pokemon-z 세션 → modkit (2026-08-04)

modkit이 8/4 밤에 넘긴 핸드오프 둘(한글패치 슬림화 · Z GUI 경계)을 pokemon-z에서
처리했다. 카드 내용이 바뀌었고, modkit 쪽에 물음이 셋 생겼다.

## 1. 두 카드가 바뀌었다 — 샌드박스 기대값을 갱신할 것

`D:\GameVault\mods\Pokemon Z Fangame\` 아래 두 카드의 `mod.json`·`mod.json.draft`를
함께 고쳤다(스키마는 그대로, assets·touches·description·order만).

| 카드 | 전 | 후 |
|---|---|---|
| 한글패치 통합 | 에셋 182 | **179** |
| Z GUI 260804 | 에셋 8 | 8 (겹침 3장의 소유자가 됨) |

겹치던 그림 3장(`battleCommandButtons.png` · `pokedexTypes.png` · `types.png`)은
**Z GUI 소유로 확정**됐다(사용자 판정). 한글패치에서 뺐다. 두 카드의 파일 겹침은
이제 0이고, Z GUI의 `order.after`는 지웠다 — 죽은 참조 `'한글패치 v5.1'`도 함께.

**따라서 「한글패치가 179/182로 내려간다」는 샌드박스 관측은 원인째 사라졌다.**
그 수치를 기대값으로 쓰는 검사가 있으면 갱신하라.

판단 근거(재현 가능): 순정 V2.18의 3장과 두 모드의 3장을 나란히 열면, Z GUI 것이
순정의 그림체(입체 베벨·굵은 외곽선)를 지킨 한글화이고 한글패치 것이 그림체가
뭉개진 판이다. Z GUI 카드 description의 「이 모드 그림에도 한글이 들어 있다」는
주장은 **사실로 확인됐다**(3장 모두 한국어, 용어도 한글패치판과 동일).

## 2. 물음 하나 — 선언된 덮어쓰기가 「부분 설치」로 읽힌다

이번엔 소유를 갈라 겹침을 없앴지만, 일반적으로는 **나중 모드가 앞 모드의 파일을
정당하게 덮는 배치**가 있다. 지금 modkit은 그때 앞 모드를 `179/182` 같은 부분
설치로 표시한다 — 사용자가 「한글패치가 깨졌나」로 읽는다.

`order.after`가 선언돼 있으면 그 겹침을 「의도된 층」으로 세고 설치 표시에서
빼는 계약이 있으면 좋겠다. 이번 건은 소유 분리로 우회했으니 급하진 않다.

## 3. 물음 둘 — 통째 재정의에는 `expects`가 안 통한다

한글패치 슬림화를 검토하며 나온 것이다. `mod.json`의 `expects`(섹션 제목 → 원문
md5)는 **원문을 고치는 모드**에는 훌륭한 안전판이다 — 게임 판이 올라 원문이 바뀌면
주입기가 멈춘다.

그런데 주입형 모드가 메서드를 **통째로 다시 정의**하면 원문이 바뀌어도 조용히 옛
본문으로 덮는다. 어긋남이 오류가 아니라 되감기로 나타난다. 지금 계약에 이걸 잡는
수단이 없다 — 재정의 대상 메서드의 원문 md5를 `expects`에 적을 수 있으면
(섹션이 아니라 메서드 단위) 같은 안전판이 걸린다.

Z 쪽 결정: 그래서 한글패치는 재정의로 옮기지 않고 코어 수정으로 남기기로 했다.
분류 정본은 pokemon-z의 `docs/design/z-kr-core-section-triage.md`.

## 4. 관측 — 한글패치 카드에 목록 밖 파일 셋이 있다

`한글패치 통합` 폴더에 카드의 `assets`에 없는 파일이 디스크에 있다:
`Data/Scripts.rxdata.pre-intl.bak` · `Data/korean.dat.orig` · `읽어주세요.txt`.

의도된 것인지(백업·안내문은 설치 대상이 아니다) harvest가 흘린 것인지 모르겠다.
설치엔 지장이 없다. 판단은 modkit 몫.

## 5. moddiff는 잘 돌았다

한글패치 코어 분류(30섹션)의 전 과정이 `moddiff.sections` + `diff` 하나로 끝났다.
base 255 · mine 256 · changed 30 · added 1 · removed 0, 실변경은 다 합쳐 100여 줄.
같은 제목 반복 섹션에 `@2`를 붙이는 처리 덕분에 짝이 안 어긋났다.

재현:

```
uv run python -c "
import pathlib; from modkit import moddiff
b=moddiff.sections(pathlib.Path(r'/mnt/c/Users/durumii/Downloads/Modkit-Test/Pokemon Z V2.18/Data/Scripts.rxdata').read_bytes())
m=moddiff.sections(pathlib.Path(r'/mnt/d/GameVault/mods/Pokemon Z Fangame/한글패치 통합/Data/Scripts.rxdata').read_bytes())
d=moddiff.diff(b,m); print(len(d.changed), d.added)"
```

## 6. 앞으로 올 변경 예고

한글패치 통합의 코어 수정 자리를 **30섹션 → 6섹션**으로 줄일 계획이다(22섹션 68줄을
`UI Text KR` 치환표로 이관). 한글패치가 혼자서도 작동해야 하므로 `Data/Scripts.rxdata`
자체는 계속 실린다 — 언어 등록·기본 언어 값·조사 시스템이 자립 조건이다.

이관이 끝나면 `UI Text KR` 카드에 `requires: ["한글패치 통합"]`이 붙는다.
