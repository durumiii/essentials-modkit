"""판정 코드의 판을 한 값으로 말한다.

**왜 있나**: fanlib이 모드 판정 결과를 디스크에 남겨 두려 한다(fanlib의 요청, 2026-08-06 —
게임 열아홉을 찬 프로세스에서 따지는 데 11.1초, 두 번째부터 0.69초라 껐다 켤 때마다 값을
다시 치르고 있었다). 그 캐시의 열쇠는 게임 폴더와 모드 보관소만 본다. 우리가 판정 규칙을
고쳐도 게임 파일과 보관소는 그대로라 **열쇠 값이 안 바뀌고, 디스크에 남은 옛 판정이 새 규칙을
이긴다.** `fit_stamp()`를 열쇠에 함께 넣으면 우리가 규칙을 고치는 순간 저쪽 캐시가 저절로
버려진다.

**손으로 올리는 번호(`__version__`)를 안 쓴 까닭**: 올리는 것을 한 번 잊으면 바로 그 사고가
난다. 파일 내용에서 뽑으면 사람이 기억할 것이 없다.

**값이 무엇을 뜻하는지는 약속하지 않는다** — 같으면 같은 판, 다르면 다른 판, 그뿐이다.
자릿수나 만드는 법에 기대지 마라.
"""
from hashlib import blake2b
from pathlib import Path

# 모드가 이 설치본에 맞는지 따지는 데 실제로 끼는 파일들. 여기 없는 파일을 고쳐도 값은
# 안 바뀐다 — 판정에 끼는 파일을 새로 만들면 이 목록에 함께 올려라.
JUDGES = ("modfit.py", "modassets.py", "modstore.py", "scripts.py")

_remembered: str | None = None


def fit_stamp(home: Path | str | None = None) -> str:
    """판정에 끼는 파일들의 내용에서 뽑은 짧은 값.

    `home`은 시험이 다른 자리를 가리켜 볼 때만 준다. 안 주면 우리 자신을 보고, 한 번 뽑은
    값을 프로세스가 사는 동안 그대로 쓴다 — 이미 임포트한 코드가 도중에 바뀌지는 않는다.
    """
    global _remembered
    if home is None and _remembered is not None:
        return _remembered

    where = Path(home) if home is not None else Path(__file__).parent
    digest = blake2b(digest_size=8)
    for name in JUDGES:
        digest.update(name.encode("utf-8"))
        try:
            digest.update((where / name).read_bytes())
        except OSError:
            # 못 읽어도 값은 나와야 한다. 여기서 터지면 부르는 쪽은 캐시를 아예 못 세운다.
            digest.update("<없음>".encode("utf-8"))
    told = digest.hexdigest()
    if home is None:
        _remembered = told
    return told
