"""판정 코드의 판 — fanlib의 디스크 캐시가 열쇠에 넣는 값."""
from modkit import stamp


def _judges(room, **files):
    for name in stamp.JUDGES:
        (room / name).write_text(files.get(name, "처음"), encoding="utf-8")
    return room


def test_the_same_code_gives_the_same_stamp(tmp_path):
    room = _judges(tmp_path)

    assert stamp.fit_stamp(room) == stamp.fit_stamp(room)


def test_changing_a_judging_file_changes_the_stamp(tmp_path):
    """이것이 안 되면 fanlib의 캐시가 옛 판정을 계속 내놓는다."""
    room = _judges(tmp_path)
    before = stamp.fit_stamp(room)

    (room / "modfit.py").write_text("규칙을 고쳤다", encoding="utf-8")

    assert stamp.fit_stamp(room) != before


def test_a_file_that_is_not_a_judge_does_not_change_the_stamp(tmp_path):
    room = _judges(tmp_path)
    before = stamp.fit_stamp(room)

    (room / "cli.py").write_text("여기는 판정을 안 한다", encoding="utf-8")

    assert stamp.fit_stamp(room) == before


def test_a_missing_file_still_gives_a_stamp(tmp_path):
    """여기서 터지면 부르는 쪽은 캐시를 아예 못 세운다."""
    assert stamp.fit_stamp(tmp_path / "없는 자리")


def test_our_own_stamp_is_a_short_string():
    told = stamp.fit_stamp()

    assert isinstance(told, str) and told
    assert told == stamp.fit_stamp()  # 프로세스가 사는 동안 안 바뀐다
