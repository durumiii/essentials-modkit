# 윈도우 exe 굽기

WSL 안에서 `python3 build.py` 한 줄이면 `dist/modkit.exe`가 나온다. 빌드는 윈도우 쪽
파이썬으로 돌아가고, WSL은 소스를 옮기고 결과를 받아오는 심부름만 한다.

## build.py가 하는 일

1. 소스를 `C:\Users\durumii\AppData\Local\Temp\modkit-build\`로 복사한다
   (`.venv`·`.git`·`dist`·`build`·`__pycache__`·`.pytest_cache` 제외).
2. 그 폴더에서 PowerShell로 PyInstaller를 돌린다.
3. 나온 exe를 WSL 쪽 `dist/`로 가져오고 크기·sha256을 찍는다.
4. 임시 폴더를 지운다. 빌드가 실패하면 임시 폴더를 남겨 두니 로그를 그대로 볼 수 있다.

수동으로 재현하려면 위 1번처럼 복사한 뒤 그 폴더에서:

```
uv run --no-project --python 3.13 --with pyinstaller --with pywebview --with rubymarshal \
  pyinstaller --onefile --windowed --name modkit --add-data "web;web" app.py
```

## 왜 임시 폴더로 복사하나

WSL 저장소를 윈도우에서 보면 `\\wsl.localhost\...` UNC 경로가 되는데, 그 위에서 uv는
프로젝트의 리눅스용 `.venv`를 동기화하려다 깨진다. `--no-project`로 프로젝트 환경을
아예 건드리지 않게 하고, 소스도 윈도우 로컬 디스크에 두면 두 문제가 함께 사라진다.

## 콘솔 정책

`--windowed`로 묶어 GUI 실행에는 검은 콘솔 창이 뜨지 않는다. 대신 인자를 주고 실행하면
`app.py`의 `_attach_console()`이 `AttachConsole(-1)`로 부모 콘솔에 붙고 출력 코드페이지를
UTF-8로 바꿔 한글 CLI 출력이 그대로 보인다. 이 경로는 exe로 묶였을 때만(`sys.frozen`)
동작하므로 WSL에서 소스로 돌리는 테스트에는 영향이 없다.

부모 콘솔이 있어야 하므로 PowerShell에서 바로 부르지 말고 `cmd /c`로 감싼다.

## 실측 (2026-08-04)

빌드 한 번에 성공했고 걸린 시간은 31초, 산출물은 13.7 MiB짜리 `dist/modkit.exe`
(sha256 `314c4fffd338fb8aea623ef1343dae3f7651745d63e307924f3c4f8b9e49c8ba`).
매니페스트 scope 도입으로 `app.py`·`web/index.html`이 바뀌어 같은 날 다시 구웠다 —
크기는 13.7 MiB(14,389,585 바이트) 그대로고 sha256만
`2544c2287b3a2c1bee9c6d69d7b9ed28b8b595c38e7be7b54badd1cfcb198eb8`로 바뀌었다.
CLI 스모크(`shelf --store <빈 폴더>`)는 재빌드본에서도 `보관소가 비어 있어요.` ·
종료 코드 0이었다.
adopt·moddiff·얹기 전 호환 판정이 들어간 판으로 같은 날 또 구웠다(26초) —
14409136바이트, sha256
`e2eb29ee67ad7187538b0c9ca687ee96954abf2c3d6e61e0eb41eeadafcab957`.
스모크는 shelf(위와 동일)와 `adopt`(usage 출력으로 서브커맨드 탑재 확인) 둘 다 통과.
진단 중 버튼 잠금(web/index.html만 변경)으로 같은 날 한 번 더 — sha256
`47717116a58174c6c0969dfb22fea3ad44c7d94b8632a092e9db55d1bd411543`.
폴더 반입·드래그앤드롭판으로 또 한 번 — sha256
`755a1ed03eb00a3f7a44f3edadb3227f01042393429a048d00e32cf18b86070c`.
드롭 실경로 파이썬 배달·보관소 기본 ~/.modkit/mods 판 — sha256
`5242ba9512ac507b689178aacd6ef8827c5e521cbadd3a6f4152b89fe046fd13`.
게임 신원 표시·UI 문체판 — sha256
`9301a2245c73a4050b2213c6461e8791e899f0592dc408507c6ea368f0246f24`.
배너·정식 표기·에셋 설치 표시판 — sha256
`659a72c02926314d75b470b360533486d667b8849366a65152968cf29303969d`.
동봉 백업 승격 차단판 — sha256
`7120a0951d3d6e366b01720e4b681416a41116c2597894e9697d9e6bb2832cf4`.
설치 전 겹침 미리보기판 — sha256
`bfe84c5a496f2751bcf47de86be517d558c90113bc50bc59f40fdac955e428cd`.
실기 피드백 일괄판(표시명·배너·수정 UI·샌드박스) — sha256
`ecbebfeaaa07cf88533c3d2785338f095cca954e0c8c93356bd155cc96e01bdb`.
히어로 배너·불릿 줄바꿈판 — sha256
`65c314663b852b9154061c39ebfc27f79fb683e18a487197a5d241886e92bc35`.
경고 집계·순서 침묵·게임 별칭판 — sha256
`5c2d32c7871c220e433a4b90fbcdd38166c5c30bee25b42d980a2bf629e08d21`.
서랍 삭제(_trash)·폴더 열기판 — sha256
`30e96147d320ead4d6725be5cf3d617657f344db0f5df92b51f9b770b5341aa8`.
한 줄 요약·강행 선택판 — sha256
`b642a7accb8107245e854ea0d2a93bb7d81872babccddd93207b58d2ef2a9bb4`.
기준선 오염·보관소 잠금·파서 수리판 — sha256
`6a1812d32b8727a987f088ea24d49da6406ef640912987bad3515c7655eabc47`.
라벨·조사·레이아웃·반입 피드백판 — sha256
`6132b9f64876705535e5f0fc58f4beb045011d74f2e42e961ad2c7de3833c11a`.
코어 섹션 병합·부분 덮임 표시판 — sha256
`dc78f9fcf37a9d8a151a4daee1b7d0ddf846ce6a9ede0b7b7b3720b54ddb455e`.
코어 병합·게임 실행 버튼판 — sha256
`35a18aa663b51558ef5d347eeabe2c8f04fd4907c3b0ed4bc57c73d6071d811a`.
동일 파일 백업·씻김 경고 집계판 — sha256
`1f5d16ebacd04676bcbda4ee3d609398a1c1694bc658a961718811b9e19a512b`.
최근 폴더 5개·기록 지우기판 — sha256
`d417555d46ea99b5c27ef5e86090b8bbccd75fe886fafa8eb1eb4df900640080`.
최근 폴더 펼침·현재 폴더 표시판 — sha256
`4a86bc1992f0a9e5b4002d5416ff912791f2e918a792b7cc73966b1107efe412`.
기준선 콜론 이식성·복사 가능 알림판 — sha256
`d81c6ee9511dccfcc39141d32ff9553baa7ed0a62cc7081306a0a68cb1b38a60`.
부분 상태 잣대 통일판 — sha256
`7a85ea4e857f66f23484acedf8b04f9204e7b0e808955d6bb5b96a5e684ec60f`.
반쪽 상태 '마저 설치' 버튼판 — sha256
`adf08a54045527dd96404a76b8c165934cac43b8f08781ab70a386715c2f8331`.
순서 선언 겹침 층 안내판 — sha256
`f3ad8259406e17ccfe00ed4b1410aa195bedb2f1ba563bcb14158d1bc5d668bf`.
에셋 층 보관·게이트 증거판 — sha256
`b182170a272f07e7bd9ffbd5891410c0eac5806993eb8c2e6d385be88853321d`.
PyInstaller 경고는 `pycparser.lextab`·`pycparser.yacctab` 두 개인데 cffi가 런타임에
생성하는 캐시 모듈이라 실행에 지장이 없다.

스모크 두 가지를 돌렸다.

CLI 쪽은 `cmd /c "modkit.exe shelf --store <빈 폴더>"`가 `보관소가 비어 있어요.`를
찍고 종료 코드 0으로 끝났다. 한글이 깨지지 않은 것으로 콘솔 붙이기와 코드페이지 전환이
같이 확인된다.

GUI 쪽은 인자 없이 띄워 10초 뒤 살아 있었고, 창 제목이 `modkit — 모드 관리자`,
메모리 110MB, WebView2 자식 프로세스 18개였다.

주의할 점 하나. onefile 빌드는 부트로더 프로세스가 실제 앱을 자식으로 띄우기 때문에
`modkit.exe` 프로세스가 둘 보인다. 창을 가진 쪽은 자식이고, 부모는 메모리 9MB에
창 핸들이 0이다. 프로세스 하나만 보고 "창이 안 뜬다"고 판단하면 틀린다.
