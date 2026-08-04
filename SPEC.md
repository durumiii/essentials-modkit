# modkit SPEC v1

이 문서는 modkit이 지금 코드로 지키는 계약을 적는다. 설계 의도가 아니라 구현이
실제로 하는 일의 기록이므로, 코드가 바뀌면 이 문서도 함께 바뀌어야 한다. 각
절 끝에는 그 절의 문장을 실제로 검사하는 테스트 파일을 적어 둔다.

## 1. 모드의 정의

모드는 「폴더 하나 + `mod.json` 한 장 + 사람이 읽을 수 있는 `.rb` 파일과 에셋
원본」이다. 배포 단위는 이 폴더를 그대로 압축한 zip이다. 보관소(store)는 이
폴더들을 게임별 하위 폴더로 모아 둔 곳이고(`<보관소>/<게임>/<모드>/mod.json`),
평면 배치(`<보관소>/<모드>/mod.json`)도 옛 배치로 함께 읽힌다.

모드는 꺼내 온 게임에 매인다. 보관소는 어느 게임에서 나온 모드인지 카드에
적어 두고(`game` 필드), 얹을 때 그 값과 설치본의 제목을 대조한다. 클래스 이름이
같다는 것은 얹어도 된다는 근거가 못 된다는 판단이다.

검증: `tests/test_import_standalone.py`, `tests/test_inject.py`

보관소 폴더 이름은 카드의 `name`을 그대로 쓰지 않는다. `_safe`가 파일 시스템이
못 받는 문자(`/\:*?"<>|`)를 밑줄로 바꾸고, 게임 폴더 이름은 콜론을 아예
떼어낸다(NTFS가 못 받는다). `modstore.shelf(store, game=...)`는 그 게임에 매인
모드만 돌려준다 — 다른 게임 것을 이름만 보고 섞어 내놓지 않는다.

모드 이름을 바꾸는 `modstore.rename`은 보관소 폴더 이름·카드의 `name`·묶음
안에서 게임이 읽는 이름만 고치고, 루비 코드는 건드리지 않는다. 설치돼 있는
버전이 있으면 옛 이름으로 먼저 걷어내고 새 이름으로 다시 얹어, 게임에 옛
이름이 남아 두 개로 보이는 일을 막는다. 이 문단은 코드 읽기로만 확인했다 —
`rename`과 `shelf`의 게임별 거르기를 직접 거치는 테스트는 아직 없다.

## 2. 카드 형식 v1

카드는 `mod.json` 하나다. `modstore.read_mod`가 이 필드들을 읽고, `_lay_down`
(harvest)이 이 필드들을 쓴다.

| 필드 | 성격 | 의미 |
|---|---|---|
| `name` | 필수 | 모드 이름. 보관소 폴더 이름·묶음/주입 섹션의 식별자로 그대로 쓰인다. |
| `scripts` | 필수(키 자체는 항상 있어야 함) | `[{file, script_name}, ...]`. 에셋만 있는 모드는 빈 배열로 둔다 — 키가 아예 없으면 읽기 단계에서 오류가 난다. |
| `game` | 선택, 강력 권장 | 이 모드가 매인 게임 제목. 비어 있으면 게임 귀속 검사(3절)를 건너뛴다. |
| `assets` | 선택 | `[{file, install_to, replaces_crc?}, ...]`. `scripts`가 비어 있으면 이 필드가 실질적으로 필수다 — 스크립트도 에셋도 없는 모드는 아무것도 설치하지 않는다. |
| `description` | 선택 | 사람이 고쳐 쓰는 설명. harvest를 다시 돌려도 지워지지 않는다. |
| `meta` | 선택 | 플러그인 묶음 항목의 두 번째 자리(루비 값, 대개 심볼 딕셔너리). harvest가 그대로 옮겨 적고, 얹을 때 다시 루비 값으로 되돌린다(`_plain`/`_ruby`). |
| `expects` | 선택 | `{섹션 제목: 원문 md5}`. **주입형에서만** 검사된다(3절). |
| `touches` | 선택(제작자 선언) | `{"methods": [...], "files": [...]}`. harvest가 초안을 자동으로 채운다(아래). |
| `order` | 선택(제작자 선언) | `{"after": [...], "before": [...]}`. 이름 붙은 다른 모드 상대의 앞/뒤 제약. |
| `requires` | 선택(제작자 선언) | 먼저 얹혀 있어야 하는 모드 이름 목록. |
| `conflicts` | 선택(제작자 선언) | `{모드 이름: 사유}`. 공존 불가 목록. |
| `from_version`·`from_build`·`harvested_at`·`updated_at`·`baseline_taken` | harvest가 채우는 출처 기록 | 손으로 적는 필드가 아니다. 어느 설치본·언제 꺼냈는지, 원본 기준선을 떴는지를 남긴다. |

design.md가 언급한 `engine`·`install` 필드는 지금 코드 어디에서도 읽지 않는다
(`grep -n '"engine"\|"install"' modkit/*.py`가 빈 결과를 낸다). 설치 계약이
묶음형·주입형·에셋형 중 무엇인지는 카드의 값이 아니라 **설치본의 상태**로
자동 판별된다(3절) — 그러니 이 두 필드는 지금은 사람이 읽는 참고 정보일 뿐,
동작에 관여하지 않는다.

`touches`는 harvest 시점에 도구가 초안을 채운다. `modfit.overrides`로 모드
스크립트가 재정의하는 자리를 뽑고, 에셋의 `install_to`를 모아
`{"methods": [...], "files": [...]}`를 만든다. 카드에 이미 `touches`가 있으면
(사람이 손으로 채웠거나 앞서 자동으로 채워졌으면) 덮어쓰지 않는다 — 손 선언이
공짜 초안보다 우선한다.

자리 표기는 두 가지다. 인스턴스 메서드는 `Scene_Map#update`, 싱글턴 메서드는
`Input.update`. 싱글턴은 `class << self` 안의 `def`와 `def self.` 꼴 둘 다를
말한다. 루비에서 이름이 같은 인스턴스·싱글턴 메서드는 서로 다른 메서드라
한 표기로 뭉개면 겹침 경고와 기준선이 엉뚱한 짝을 맞춘다. 그릇은 `class`뿐
아니라 `module`도 센다 — `module Input`의 `class << self`에서 코어를 감싸는
모드가 실물에 있다(2026-08-04, Pokémon Z Fangame의 Controller UX Z).

검증: `tests/test_modfit_overrides.py`(자리 추출 규칙),
`tests/test_touches_draft.py`, `tests/test_import_standalone.py`

## 3. 설치 계약 3종과 검사 3겹

설치 계약은 모드가 무엇을 들고 있는지와 설치본이 무엇을 갖췄는지로 갈린다.
카드에 계약 종류를 적는 필드는 없다 — `modstore.apply`가 그때그때 판별한다.

- **묶음형** — 모드에 `scripts`가 있고 설치본에 `Data/PluginScripts.rxdata`가
  있으면 이 경로다. 그 파일을 읽어(`[이름, 메타, [[스크립트명, 압축 소스], ...]]`
  형태의 목록) 이름이 같은 항목을 갈아 끼우거나, 없으면 새 자리에 끼워 넣는다.
  묶음을 다시 쓴 파일은 게임 원본의 직렬화와 바이트까지 같지는 않다 — 항목의 뜻이
  왕복하고, 도구 자신의 출력이 재현된다(`docs/validation.md` Step 3).
- **주입형** — 모드에 `scripts`가 있는데 설치본에 `PluginScripts.rxdata`가 없는
  옛 엔진이면 이 경로다. `Data/Scripts.rxdata`의 코어 배열에 `MOD:<모드명>/<파일명>`
  제목의 섹션으로 얹는다. 자리는 늘 `Main` 항목 바로 앞이다(RGSS가 배열 순서대로
  실행하고 `Main` 뒤는 돌지 않는다). 같은 모드를 다시 얹으면 자기 섹션을 먼저
  걷어 내고 새로 꽂아 쌓이지 않는다.
- **에셋형** — 모드에 `scripts`가 비어 있으면 스크립트 묶음·코어를 아예 건드리지
  않고 `assets`만 게임 폴더에 놓거나 덮는다. 묶음이 없는 설치본에도 얹을 수 있다.

세 계약 모두 적용 전에 `declare.gate`를 거친다. 검사는 세 겹이다.

1. **차단** — `requires`에 든 이름이 아직 설치돼 있지 않거나, 이미 설치된 다른
   모드가 나를 `conflicts`로 지목하거나, 내가 설치된 것을 `conflicts`로 지목하면
   `declare.Blocked`를 던지고 멈춘다. `apply(..., force=True)`면 막는 대신
   "강행: …" 문구로 경고에 담아 통과시킨다.
2. **자동 배치** — 묶음형에서만 실제 순서를 만든다. `order.after`/`order.before`가
   가리키는 이름들의 현재 인덱스로 삽입 구간 `[lo, hi]`를 구하고, `lo > hi`면
   순환(모순)으로 보아 `Blocked`. 주입형은 늘 `Main` 앞 일괄 삽입이라 자리를
   고르지 않는다 — 대신 `order.after`가 아직 설치되지 않았으면 "먼저 얹은 뒤
   다시 얹으면 순서가 잡혀요"라는 경고만 남긴다.
3. **경고** — 차단·배치를 통과한 뒤, 내 `touches`(자동 초안 포함)와 이미 설치된
   다른 모드의 `touches`가 겹치면 "`A`와 `B`가 모두 `X`를 건드려요 — 순서 선언이
   없으면 나중 것이 이겨요"를 warnings 목록에 담아 돌려준다. 설치를 막지 않는다.

선언이 하나도 없는 옛 모드도 지금처럼 얹히고, 3번(기계 감지) 경고만 받을 수
있다.

검증: `tests/test_declare.py`, `tests/test_inject.py`

## 4. 안전 규약

- **첫 쓰기 전 백업**. 묶음형·주입형은 `PluginScripts.rxdata.orig` /
  `Scripts.rxdata.orig`를 얹기 직전에 뜬다. 이미 있으면 다시 뜨지 않는다 — 두
  번째 얹기가 첫 결과를 원본으로 착각하면 되돌릴 데가 없어진다. 에셋형은 자리마다
  `<파일명>.orig`를 남기되, **덮는 자리에만** 남긴다(새로 놓는 자리는 백업할
  원본이 없다).
- **왕복 확인**. 묶음형·주입형 모두 새 배열을 직렬화한 뒤 곧바로 다시 읽어
  (`rubyread.loads`) 항목 수와 이름이 원래 계획과 같은지 대조하고, 다르면 `NoBundle`을 던지며
  **파일을 건드리지 않는다**. 확인이 쓰기보다 먼저다.
- **원자적 교체**. 파일을 고칠 때는 항상 `<대상>.writing`에 먼저 쓰고
  `os.replace`로 이름을 바꿔 끼운다. 제자리에서 고치지 않는 이유는 버전 폴더끼리
  하드링크로 이어져 있을 수 있어서다 — 제자리 수정은 다른 버전까지 함께 바꾼다.
- **CRLF 보존**. 스크립트를 읽고 쓸 때 `newline=""`을 지정해 파이썬이 줄바꿈을
  LF로 바꾸지 못하게 막는다. 원본이 CRLF이므로 왕복 후에도 CRLF여야 한다.
- **게임 귀속 거부**. 카드의 `game`이 있고 설치본 제목과 다르면 `WrongGame`.
- **파괴 동사 없음**. 삭제 대신 격리(5절)를 쓴다. `remove`도 스크립트/에셋을
  걷어낼 뿐이고, 덮었던 에셋은 `.orig`에서 원본을 되살린다.

검증: `tests/test_inject.py`, `tests/test_import_standalone.py`

## 5. 매니페스트와 진단

매니페스트는 깨끗한 원본에서 `manifest.capture(game_dir)`로 뽑는 JSON 한 장이다.
`{modkit_manifest: 1, game, version, exclude, files: {상대경로: [크기, CRC32]}}`
꼴이며, `exclude`에 든 glob 패턴에 걸리는 파일과 `.orig`·`.bak`으로 끝나는
파일은 애초에 목록에 들어가지 않는다. 기본값 `manifest.DEFAULT_EXCLUDE`는
세 게임(Essentials v21·v21.1·v16) 대조 실측으로 고른 것이다 — 게임 폴더 뿌리에
떨어지는 세이브(`Game*.rxdata`), v16의 `LastSave.dat`, 윈도·맥 탐색기가 남기는
`desktop.ini`·`Thumbs.db`·`.DS_Store`, 두 세대의 스크린샷(v21은
`[2026-08-04] 03_12_45.123.png` 꼴, v16은 `capture*.bmp`), 그리고 도구 자신의
산물. 패턴은 상대경로 전체에 `fnmatch`로 걸리고 `*`가 `/`를 넘으므로, 하위
폴더까지 잡으려면 `*/desktop.ini`처럼 따로 적어야 한다.

매니페스트는 자기 목록이 설치본 전체인지 일부인지를 `scope`로 밝힌다. 깨끗한
원본을 통째로 뜬 것은 `"full"`(기본값)이고, 패치 zip에 동봉하는 것처럼 스테이징
폴더만 뜬 것은 `capture(..., scope="partial")`로 `"partial"`이 된다. 이 값이 진단의
닫힌 세계 가정을 가른다 — full은 목록이 곧 설치본의 전부라고 보고 목록 밖 파일을
외래로 몰지만, partial은 목록 밖을 판정 대상에서 빼고 `untracked`로 센다. `scope`
키가 없는 옛 매니페스트는 `"full"`로 읽는다.

`manifest.diagnose(game_dir, manifest, store=...)`가 설치본을 대조해 파일마다
넷 중 하나를 매긴다.

1. **원본 일치(intact)** — 지금 크기·CRC32가 매니페스트와 같다.
2. **아는 변경(known)** — 매니페스트와 다르지만, `store`에 있는 모드 중 하나가
   그 경로를 소유하고 있다고 볼 수 있다. 소유 판정은 두 갈래다 — 카드
   `assets`의 `install_to` 전부, 그리고 스크립트를 가진 모드가 **지금 이
   설치본에 실제로 설치돼 있으면** `Data/Scripts.rxdata`와
   `Data/PluginScripts.rxdata` 전체.
3. **외래(foreign)** — 매니페스트와 다른데 아는 변경도 아니다. 옛 패치 흔적처럼
   어떤 카드도 설명하지 못하는 변경·추가.
4. **누락(missing)** — 매니페스트엔 있는데 지금 설치본엔 없다.

부분 매니페스트에서만 서는 다섯째 자리가 **추적 밖(untracked)**이다 — 목록에도
없고 모드 소유도 아닌 파일. 게임 원본이나 유저 데이터가 여기 들어오며 격리
대상이 아니다. 목록에 있는 파일이 크기·CRC32에서 어긋나면 부분 매니페스트에서도
그대로 외래다 — 옛 패치가 패치 파일을 덮은 자리를 놓치지 않는다.

`.orig`·`.bak`으로 끝나는 백업은 이 네 판정과 별도로 `backups`에 선다. 도구가
남긴 `.orig`뿐 아니라 엔진이 남긴 세이브 백업(`Game.rxdata.bak`)도 여기 온다 —
조용히 제외하지 않고 눈에 보이게 세우는 편이 진단에 정직하다. `store`를
안 주면(매니페스트만 있고 보관소가 없는 상황) 아는 변경 판정이 나오지 않는다 —
카드가 없으니 무엇이 아는 변경인지 알 길이 없다.

외래 파일은 지우지 않고 게임 폴더 안 `_quarantine/<타임스탬프>/`로 상대경로를
보존한 채 옮긴다(`manifest.quarantine`). 게임 폴더 밖을 가리키는 경로는
`ValueError`로 거절한다. `manifest.restore`는 격리함 하나를 통째로 원래
자리에 되돌리고 빈 격리 폴더를 걷어낸다.

CLI(`modkit diagnose`)는 외래가 있으면 종료 코드 2, 없으면 0, `--quarantine`
플래그를 주면 격리까지 하고 0을 돌려준다. 추적 밖 파일은 요약에 「추적 밖 N」으로
만 적히고 종료 코드를 바꾸지 않는다.

검증: `tests/test_manifest.py`, `tests/test_quarantine.py`, `tests/test_cli.py`

## 6. 호환성 검증

호환성 검증은 두 층으로 나뉘고, 실제로 얹기 흐름에 물려 있는 층은 하나뿐이다.

- **`expects`(md5) — 주입형에서만, 얹기 흐름에 실제로 물려 있다.** 카드의
  `expects`는 `{섹션 제목: 원문 md5}`다. 주입 직전에 지금 코어의 각 섹션을
  md5로 뜨고 대조해, 하나라도 다르면 `BaseChanged`를 던지고 **아무것도 쓰지
  않는다**. 게임 판이 올라 원문이 바뀌었는데 낡은 훅을 그대로 꽂으면 조용히
  어긋나는 것을 막는 장치다. 묶음형·에셋형 `apply` 경로에는 이 검사가 없다.
- **베이스라인(기준선) — 도구는 있으나 얹기 흐름에는 물려 있지 않다.**
  harvest가 끝나면 `modfit.take_baseline`이 그 모드가 재정의하는 메서드의
  게임 쪽 원문을 읽어 모드 폴더 옆 `baseline/`에 저장한다(성공하면
  `baseline_taken: true`, 못 뜨면 `false`와 실패 사유를 카드에 남긴다 — 침묵을
  성공으로 오해하지 않도록). `modfit.check(game_dir, mod)`가 이 기준선과 대상
  설치본의 지금 원문을 대조해 `fits`(같다) / `changed`(달라졌다, 무엇이
  바뀌었는지 사람이 읽을 문장과 함께) / `unknown`(기준선이 없거나 아직 못 떴다)
  중 하나를 돌려준다. 에셋만 있는 모드는 `replaces_crc`로 같은 판단을 CRC32로
  한다. **다만 `modstore.apply`도 `cli.py`도 지금 `modfit.check`를 부르지
  않는다** — 이 판정은 harvest 시점에 기준선을 떠 두는 데까지만 자동이고, 얹기
  전 호환성 확인은 아직 별도 호출이 필요하다.
- **판 올림 절차**는 현재 사람이 하는 일로 남아 있다. `harvest`가 `version`
  인자를 받아 카드의 `from_version`에 적어 두므로, 게임 판이 올라 다시
  harvest하면 새 카드의 `from_version`이 갈린다 — 이전 판과 지금 판의 카드를
  나란히 두고 `touches`·`baseline` 차이를 사람이 비교하는 것이 지금 절차다.
  이를 자동으로 비교·병합하는 명령은 아직 없다.

검증: `tests/test_inject.py`(`expects` 불일치 차단), `tests/test_touches_draft.py`
(touches 초안), `tests/test_modfit_overrides.py`(어떤 자리를 기준선으로 뜨는지).
베이스라인 판정(`fits`/`changed`/`unknown`) 자체를 거치는 회귀 테스트는 아직
없다 — 그 경로는 코드 읽기로만 확인했다.

---

## Step 2 대조 검토 기록

SPEC 본문이 백틱으로 적은 필드명을 코드가 실제로 쓰는지 grep으로 훑었다.
SPEC이 `"필드"` 인용부호가 아니라 `` `필드` `` 코드 표기를 쓰므로, 브리프가
제시한 명령을 그 표기에 맞게 바꿔 돌렸다.

```
$ grep -o '`[a-z_]*`' SPEC.md | tr -d '`' | sort -u
```

이 목록에서 카드 필드 후보만 추려(`name`·`game`·`scripts`·`assets`·
`description`·`meta`·`expects`·`touches`·`order`·`requires`·`conflicts`·
`from_version`·`from_build`·`harvested_at`·`updated_at`·`baseline_taken`·
`file`·`script_name`·`install_to`·`replaces_crc`·`modkit_manifest`·`version`·
`exclude`·`after`·`before`·`methods`·`files`) 각각을 `modkit/*.py` 안에서
`"필드"` 리터럴로 실제로 참조하는지 셌다.

```
$ for f in name game scripts assets description meta expects touches order \
    requires conflicts from_version from_build harvested_at updated_at \
    baseline_taken file script_name install_to replaces_crc modkit_manifest \
    version exclude after before methods files engine install; do
    n=$(grep -rc "\"$f\"" modkit/*.py | awk -F: '{s+=$2} END{print s+0}')
    echo "$f: $n"
  done
```

`engine`과 `install`을 뺀 전부가 1회 이상 걸렸다(`name: 9`, `assets: 11`,
`touches: 5`, `expects: 1`, `requires: 1` 등). `engine: 0`·`install: 0`은
SPEC 2절에서 이미 "코드가 읽지 않는다"라고 명시한 것과 정확히 일치한다 —
어긋남이 아니라 그 문장의 근거다.
