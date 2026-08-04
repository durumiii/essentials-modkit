"""재정의 추출 — `module`·`class << self`·`def self.`까지 본다.

2026-08-04 실측: `module Input` 안의 `class << self`에서 `update`를 감싸는 모드
(Pokémon Z Fangame의 Controller UX Z)가 추출에 하나도 안 걸렸다. 기준선이 안 떠지면
호환 검사가 조용히 통과한다.
"""
from modkit import modfit


def test_plain_class_method():
    found = modfit.overrides([("x", "class Baz\n  def qux\n  end\nend\n")])
    assert found == {"Baz#qux"}


def test_module_singleton_block():
    source = (
        "module Input\n"
        "  class << self\n"
        "    def update\n"
        "    end\n"
        "  end\n"
        "end\n"
    )
    assert modfit.overrides([("x", source)]) == {"Input.update"}


def test_def_self_is_singleton():
    found = modfit.overrides([("x", "class Baz\n  def self.qux\n  end\nend\n")])
    assert found == {"Baz.qux"}


def test_singleton_and_instance_are_different_places():
    source = (
        "class X\n"
        "  def a\n"
        "  end\n"
        "  class << self\n"
        "    def a\n"
        "    end\n"
        "  end\n"
        "end\n"
    )
    assert modfit.overrides([("x", source)]) == {"X#a", "X.a"}


def test_method_belongs_to_nearest_block():
    """중첩된 안쪽 클래스의 메서드가 바깥 이름으로도 잡히면 안 된다."""
    source = (
        "module Foo\n"
        "  class Bar\n"
        "    def baz\n"
        "    end\n"
        "  end\n"
        "end\n"
    )
    assert modfit.overrides([("x", source)]) == {"Bar#baz"}


def test_module_own_method():
    source = "module Foo\n  def bar\n  end\nend\n"
    assert modfit.overrides([("x", source)]) == {"Foo#bar"}


def test_find_method_reads_singleton_source():
    source = (
        "module Input\n"
        "  class << self\n"
        "    def update\n"
        "      poll\n"
        "    end\n"
        "  end\n"
        "end\n"
    )
    got = modfit.find_method([("x", source)], "Input.update")
    assert got == "    def update\n      poll\n    end"  # 블록 몸통은 마지막 end 앞에서 끊긴다


def test_baseline_roundtrip_keeps_singleton_place(tmp_path):
    """기준선 파일로 눕혔다가 다시 읽어도 싱글턴 표기가 살아 있다."""
    modfit.write_baseline(tmp_path, {"Input.update": "def update\nend\n",
                                     "Scene_Map#main": "def main\nend\n"})
    assert set(modfit.read_baseline(_Mod(tmp_path))) == {"Input.update", "Scene_Map#main"}


def test_baseline_filename_has_no_colon(tmp_path):
    """`::`는 NTFS 파일명에 못 들어간다 — 이름은 안전한 치환으로 눕히고 왕복은 유지.

    2026-08-04 실기: WSL이 쓴 `Battle::Scene__x.rb`가 NTFS에 사설 영역 문자
    (U+F03A)로 저장돼, Windows exe의 검사가 그 자리를 영영 못 찾았다(전부 '없어요').
    """
    modfit.write_baseline(tmp_path, {"Battle::Scene#pbShow": "def pbShow\nend\n"})
    names = [p.name for p in (tmp_path / "baseline").glob("*.rb")]
    assert names and all(":" not in n for n in names)
    assert set(modfit.read_baseline(_Mod(tmp_path))) == {"Battle::Scene#pbShow"}


def test_read_baseline_heals_ntfs_mangled_colons(tmp_path):
    """WSL이 이미 눕혀 둔 `::` 파일명(NTFS에선 U+F03A로 치환)도 읽을 때 복원한다."""
    room = tmp_path / "baseline"
    room.mkdir()
    (room / "BattleScene__pbShow.rb").write_text("def pbShow\nend\n")
    assert set(modfit.read_baseline(_Mod(tmp_path))) == {"Battle::Scene#pbShow"}


class _Mod:
    def __init__(self, folder):
        self.folder = folder


def test_skip_self_sees_injected_section_names(tmp_path):
    """주입형으로 얹힌 자기 코드를 원본으로 착각하면 안 된다.

    2026-08-04 실측: 주입기가 꽂는 섹션 제목은 `MOD:<모드명>/<파일>`인데 걸러 내는
    쪽은 `<모드명>/`으로만 견줘, 이미 얹힌 모드의 기준선이 제 코드로 떠졌다
    (Pokémon Z Fangame에 설치된 Controller UX Z 등 주입형 6개 전부).
    """
    from tests.test_inject import make_core_game

    mine = b"module Input\r\n  class << self\r\n    def update\r\n      mine\r\n    end\r\n  end\r\nend\r\n"
    core = b"module Input\r\n  class << self\r\n    def update\r\n      core\r\n    end\r\n  end\r\nend\r\n"
    game = make_core_game(tmp_path, sections=(
        ("Input_Core", core),
        ("MOD:Controller UX Z/001_Cursor.rb", mine),  # 이미 얹혀 있는 자기 코드
    ))

    got = modfit.take_baseline(game, [("001_Cursor.rb", mine.decode())], skip="Controller UX Z")
    assert "mine" not in got["Input.update"]
    assert "core" in got["Input.update"]


def test_baseline_excludes_all_injected_sections(tmp_path):
    """기준선은 게임 원문이다 — 남의 주입 섹션(MOD:*)이 원본으로 잡히면 형제 모드의
    코드를 게임 코드로 착각한다(2026-08-04 실기: 모드 4종이 서로를 기준선으로 떠서
    순정에서 전부 차단, 순환 의존까지 생겼다)."""
    from tests.test_inject import make_core_game

    core = b"class Scene_Map\r\n  def update\r\n    vanilla\r\n  end\r\nend\r\n"
    other = b"class Scene_Map\r\n  def update\r\n    fpz_update\r\n  end\r\nend\r\n"
    game = make_core_game(tmp_path, sections=(
        ("Scene_Map", core),
        ("MOD:Frame Profiler/001_Profiler.rb", other),   # 이미 설치된 다른 모드
    ))
    mine = "class Scene_Map\n  def update\n  end\nend\n"
    got = modfit.take_baseline(game, [("001_My.rb", mine)], skip="My Mod")
    assert "vanilla" in got["Scene_Map#update"]
    assert "fpz_update" not in got["Scene_Map#update"]


def test_check_ignores_foreign_injected_sections(tmp_path):
    """대조도 마찬가지 — 옆 모드가 설치돼 있다고 '게임이 바뀌었다'고 하면 안 된다."""
    import json
    from tests.test_inject import make_core_game

    core = b"class Scene_Map\r\n  def update\r\n    vanilla\r\n  end\r\nend\r\n"
    other = b"class Scene_Map\r\n  def update\r\n    fpz_update\r\n  end\r\nend\r\n"
    game = make_core_game(tmp_path, sections=(
        ("Scene_Map", core),
        ("MOD:Frame Profiler/001_Profiler.rb", other),
    ))
    folder = tmp_path / "mymod"
    folder.mkdir()
    modfit.write_baseline(folder, {"Scene_Map#update": "  def update\r\n    vanilla\r\n  end"})
    mod = type("M", (), {"folder": folder, "name": "My Mod", "baseline_taken": True,
                         "scripts": (("001_My.rb", "x"),), "assets": ()})
    fit = modfit.check(game, mod)
    assert fit.verdict == modfit.FITS, fit.findings


def test_asset_fit_skips_places_the_mod_adds(tmp_path):
    """대응 파일이 게임에 없는 자리는 '판이 바뀜'이 아니라 모드가 새로 놓는 자리다
    (2026-08-04 실기: 하비스트 때 잘못 새겨진 지문 하나가 설치 전체를 막았다)."""
    game = tmp_path / "game"
    game.mkdir()
    folder = tmp_path / "mod"
    folder.mkdir()
    mod = type("M", (), {"folder": folder, "name": "Adder", "scripts": (),
                         "assets": ({"file": "new.txt", "install_to": "new.txt",
                                     "replaces_crc": 12345},)})
    fit = modfit.check(game, mod)
    assert fit.verdict != modfit.CHANGED


def test_block_survives_flush_left_if(tmp_path):
    """실물 코어에는 클래스 안에 들여쓰기 0의 if…end가 박혀 있다(Z의
    PokeBattle_Battle, $entrenador 분기 실측) — 그 end를 클래스 닫힘으로 오인하면
    뒤쪽 메서드가 전부 유령이 된다."""
    source = (
        "class Foo\n"
        "  def early\n"
        "  end\n"
        "if $flag\n"
        "  x = 1\n"
        "else\n"
        "  x = 2\n"
        "end\n"
        "  def late\n"
        "  end\n"
        "end\n"
    )
    assert modfit.overrides([("x", source)]) == {"Foo#early", "Foo#late"}
    got = modfit.find_methods([("x", source)], ["Foo#late"])
    assert "def late" in got.get("Foo#late", "")


def test_one_line_class_does_not_swallow_siblings(tmp_path):
    """`class X < Exception; end` 한 줄짜리가 제 end를 못 찾고 뒤 17만 자를 삼키던
    실물 사례(Z의 PokeBattle_Battle 안 BattleAbortedException)."""
    source = (
        "class Foo\n"
        "  class Oops < Exception; end\n"
        "  def target\n"
        "  end\n"
        "end\n"
    )
    assert modfit.overrides([("x", source)]) == {"Foo#target"}
    assert "def target" in modfit.find_methods([("x", source)], ["Foo#target"])["Foo#target"]
