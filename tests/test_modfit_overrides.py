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


class _Mod:
    def __init__(self, folder):
        self.folder = folder
