"""루비가 세는 것과 같은 번호를 매기는 Marshal 기록기.

루비 Marshal은 nil·true·false·Fixnum·심볼을 뺀 **모든** 객체에 나온 순서대로 번호를 붙이고,
같은 객체가 다시 나오면 내용을 또 적는 대신 그 번호를 적는다. 문자열도, 바이트열도, 실수도
번호를 받는다.

`rubymarshal`의 기록기는 배열·해시·객체만 번호를 매기고 문자열과 바이트열은 그냥 적는다.
읽는 쪽은 루비 규칙대로 문자열에도 번호를 주므로, 문자열이 하나 지날 때마다 두 셈이 한 칸씩
벌어진다. 그래서 뒤에 나오는 가리킴이 전부 엉뚱한 것을 집는다.

**이 어긋남은 조용하다.** 파일은 멀쩡히 읽히고 길이도 맞는다. 다만 어떤 플러그인의 이름
자리에 다른 플러그인의 압축된 소스가 들어앉는다. 실제로 그렇게 되어 게임이
`plugin name must be a non-empty string`으로 멈췄다(2026-07-28, Wishing Star v1.0.6).

고침은 한 가지다 — 상류가 번호를 안 매기는 갈래를 적기 전에 번호부터 매긴다.
"""
import io

from rubymarshal.classes import Module, RubyObject, RubyString, Symbol
from rubymarshal.writer import Writer as PlainWriter

FIXNUM_BITS = 5 * 8  # 이보다 크면 Bignum이고, Bignum은 번호를 받는다
_REGEXP = type(__import__("re").compile(""))


class CountingWriter(PlainWriter):
    """상류가 빠뜨린 갈래에도 번호를 매기는 기록기."""

    def __init__(self, fd):
        super().__init__(fd)
        self._alive = []  # id로 세는 동안 객체가 사라져 번호가 겹치지 않게 붙잡아 둔다

    def write(self, obj):
        if _numbered_but_unregistered(obj):
            self._alive.append(obj)
            if not self.must_write(obj):
                return  # 이미 적은 것이다 — 가리킴만 남기고 끝낸다
        super().write(obj)


def _numbered_but_unregistered(obj) -> bool:
    """루비는 번호를 주는데 상류 기록기는 안 주는 것인가."""
    if obj is None or obj is True or obj is False:
        return False
    if isinstance(obj, (Symbol, RubyString)):
        return False  # 심볼은 따로 세고, RubyString은 상류가 이미 센다
    if isinstance(obj, bool):
        return False
    if isinstance(obj, int):
        return obj.bit_length() > FIXNUM_BITS
    if isinstance(obj, type):
        return issubclass(obj, RubyObject)
    return isinstance(obj, (str, bytes, float, Module, _REGEXP))


def dump(fd, obj) -> None:
    fd.write(b"\x04\x08")
    CountingWriter(fd).write(obj)


def dumps(obj) -> bytes:
    buffer = io.BytesIO()
    dump(buffer, obj)
    return buffer.getvalue()
