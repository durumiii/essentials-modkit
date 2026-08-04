"""통짜 rxdata 교체의 실제 발자국 — 섹션 대조와 기반 추정.

2026-08-04 실측에서 나왔다: 야생 배포물은 rxdata를 통째로 덮는데(이로치패치 2.3MB),
실변경은 섹션 셋뿐이었다. 기반도 게임 원본이 아니라 다른 모드(한글패치)였다 —
원본 대비 220섹션, 한글패치 대비 3섹션. 차이가 최소인 후보가 기반이다.
"""
import zlib

from modkit import moddiff, rubywrite


def core(*sections):
    """코어 꼴 rxdata — [id, 제목(생 바이트), zlib 본문]."""
    return rubywrite.dumps(
        [[i + 1, title.encode(), zlib.compress(body)] for i, (title, body) in enumerate(sections)]
    )


def bundle(*plugins):
    """플러그인 묶음 꼴 — [이름, 메타, [[스크립트명, zlib 본문], ...]]."""
    return rubywrite.dumps(
        [[name, {}, [[fname, zlib.compress(body)] for fname, body in scripts]]
         for name, scripts in plugins]
    )


def test_sections_core():
    got = moddiff.sections(core(("Settings", b"A = 1\r\n"), ("Main", b"main\r\n")))
    assert got == {"Settings": b"A = 1\r\n", "Main": b"main\r\n"}


def test_sections_bundle():
    got = moddiff.sections(bundle(("Mod A", [("001.rb", b"a\r\n"), ("002.rb", b"b\r\n")])))
    assert got == {"Mod A/001.rb": b"a\r\n", "Mod A/002.rb": b"b\r\n"}


def test_sections_duplicate_titles_pair_by_order():
    """실물 코어에는 같은 제목(구분선 섹션)이 되풀이된다 — 순서로 짝을 맞춘다."""
    got = moddiff.sections(core(("====", b"1"), ("Main", b"m"), ("====", b"2")))
    assert got == {"====": b"1", "Main": b"m", "====@2": b"2"}


def test_diff_added_removed_changed():
    base = moddiff.sections(core(("A", b"old"), ("B", b"same"), ("C", b"bye")))
    mine = moddiff.sections(core(("A", b"new"), ("B", b"same"), ("D", b"hi")))
    got = moddiff.diff(base, mine)
    assert got.changed == ("A",)
    assert got.removed == ("C",)
    assert got.added == ("D",)
    assert got.count == 3


def test_find_base_picks_minimal_diff(tmp_path):
    original = core(("A", b"1"), ("B", b"2"), ("C", b"3"))
    patched = core(("A", b"x"), ("B", b"y"), ("C", b"3"))       # 어떤 모드의 산출물
    mine = core(("A", b"x"), ("B", b"y"), ("C", b"z"))          # 그 위에 하나 더 고친 것
    scores = moddiff.find_base(mine, [("원본", original), ("한글패치", patched)])
    assert scores[0][0] == "한글패치"
    assert scores[0][1].count == 1
    assert scores[1] == ("원본", scores[1][1])
    assert scores[1][1].count == 3
