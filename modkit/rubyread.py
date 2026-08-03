"""고리진 객체까지 읽는 루비 Marshal 판독기.

`rubymarshal`은 세이브 파일에서 멈춘다 — `invalid link destination`. 세이브 안에는
맵이 이벤트를 담고 그 이벤트가 다시 자기를 담은 맵을 가리키는 고리가 있는데, 라이브러리가
객체를 **다 채운 뒤에** 등록해서 고리를 만나면 아직 등록 안 된 자리를 보게 된다. 루비 본가는
반대로 등록부터 하고 채운다(`marshal.c`의 `r_entry`가 `r_ivar`보다 앞선다).

그래서 배열·해시·객체·UsrMarshal 네 갈래에서 **채우기 전에 등록**하도록 고친 판이다.
`rubymarshal.reader.Reader`를 상속하므로 라이브러리가 올라가면 나머지는 따라 올라간다.

상류에 고쳐 달라 기다리지 않는 이유는, 같은 지적이 담긴 이슈가 부분 반영으로 닫힌 채
1.2.10에서 오래 멈춰 있기 때문이다(2026-07-27 조사).

**한계**: 이 게임의 세이브 두 개로만 확인했다. 다른 팬게임 세이브에 `rubymarshal`이
아예 구현하지 않은 토큰이 들어 있으면 거기서 멈춘다. 쓰기(직렬화) 쪽은 손대지 않았다 —
세이브를 고칠 일이 생기면 따로 확인해야 한다.
"""
import io

from rubymarshal.classes import (
    Extended,
    Module,
    RubyObject,
    RubyString,
    Symbol,
    UserDef,
    UsrMarshal,
)
from rubymarshal.reader import Reader
from rubymarshal.constants import (
    TYPE_ARRAY, TYPE_BIGNUM, TYPE_CLASS, TYPE_DATA, TYPE_EXTENDED, TYPE_FALSE,
    TYPE_FIXNUM, TYPE_FLOAT, TYPE_HASH, TYPE_IVAR, TYPE_LINK, TYPE_MODULE,
    TYPE_NIL, TYPE_OBJECT, TYPE_REGEXP, TYPE_STRING, TYPE_STRUCT, TYPE_SYMBOL,
    TYPE_SYMLINK, TYPE_TRUE, TYPE_USERDEF, TYPE_USRMARSHAL,
)
import re


class CyclicReader(Reader):
    def read(self, in_ivar=False):
        result = None
        object_index = None
        re_flags = None

        token = self.fd.read(1)

        if token in (
            TYPE_CLASS, TYPE_MODULE, TYPE_FLOAT, TYPE_BIGNUM, TYPE_STRING,
            TYPE_REGEXP, TYPE_ARRAY, TYPE_HASH, TYPE_STRUCT, TYPE_OBJECT,
            TYPE_DATA, TYPE_USRMARSHAL, TYPE_USERDEF,
        ):
            object_index = len(self.objects)
            self.objects.append(None)

        if token == TYPE_NIL:
            pass
        elif token == TYPE_TRUE:
            result = True
        elif token == TYPE_FALSE:
            result = False
        elif token == TYPE_IVAR:
            result = self.read(in_ivar=True)
        elif token == TYPE_STRING:
            result = self.read_blob()
        elif token == TYPE_SYMBOL:
            result = self.read_symreal()
        elif token == TYPE_FIXNUM:
            result = self.read_long()
        elif token == TYPE_ARRAY:
            num_elements = self.read_long()
            result = []
            self.objects[object_index] = result       # PATCH: register first
            for _ in range(num_elements):
                result.append(self.read())
        elif token == TYPE_HASH:
            num_elements = self.read_long()
            result = {}
            self.objects[object_index] = result       # PATCH: register first
            for _ in range(num_elements):
                key = self.ensure_hashable(self.read())
                value = self.read()
                result[key] = value
        elif token == TYPE_FLOAT:
            floatn = self.read_blob().split(b"\0")
            result = float(floatn[0].decode("utf-8"))
        elif token == TYPE_BIGNUM:
            sign = 1 if self.fd.read(1) == b"+" else -1
            num_elements = self.read_long()
            result = 0
            factor = 1
            for _ in range(num_elements):
                result += self.read_short() * factor
                factor *= 2 ** 16
            result *= sign
        elif token == TYPE_REGEXP:
            result = self.read_blob()
            options = ord(self.fd.read(1))
            re_flags = 0
            if options & 1:
                re_flags |= re.IGNORECASE
            if options & 4:
                re_flags |= re.MULTILINE
        elif token == TYPE_USRMARSHAL:
            class_symbol = self.read()
            class_name = class_symbol.name
            python_class = self.registry.get(class_name, UsrMarshal)
            result = python_class(class_name)
            self.objects[object_index] = result       # PATCH: register first
            result.marshal_load(self.read())
        elif token == TYPE_SYMLINK:
            result = self.read_symlink()
        elif token == TYPE_LINK:
            link_id = self.read_long()
            result = self.objects[link_id]
        elif token == TYPE_USERDEF:
            class_symbol = self.read()
            private_data = self.read_blob()
            class_name = class_symbol.name
            python_class = self.registry.get(class_name, UserDef)
            result = python_class(class_name)
            result._load(private_data)
        elif token == TYPE_MODULE:
            result = Module(self.read_blob().decode(), None)
        elif token == TYPE_OBJECT:
            class_symbol = self.read()
            class_name = class_symbol.name
            python_class = self.registry.get(class_name, RubyObject)
            result = python_class(class_name, {})
            self.objects[object_index] = result       # PATCH: register first
            attributes = self.read_attributes()
            result.set_attributes(attributes)
        elif token == TYPE_EXTENDED:
            result = Extended(self.read_blob(), None)
        elif token == TYPE_CLASS:
            class_name = self.read_blob().decode()
            if class_name in self.registry:
                result = self.registry[class_name]
            else:
                result = type(class_name.rpartition(":")[2], (RubyObject,),
                              {"ruby_class_name": class_name})
        else:
            raise ValueError("token %s is not recognized at offset %d"
                             % (token, self.fd.tell()))

        if in_ivar:
            attributes = self.read_attributes()
            if token in (TYPE_STRING, TYPE_REGEXP):
                encoding = self._get_encoding(attributes)
                try:
                    result = result.decode(encoding)
                except UnicodeDecodeError:
                    result = result.decode("unicode-escape")
                if attributes and token == TYPE_STRING:
                    result = RubyString(result, attributes)
            elif attributes:
                result.set_attributes(attributes)

        if token == TYPE_REGEXP:
            result = re.compile(str(result), re_flags)

        if object_index is not None:
            self.objects[object_index] = result
        return result


def load(fd, registry=None):
    if fd.read(2) != b"\x04\x08":
        raise ValueError(r"Expected token \x04\x08")
    return CyclicReader(fd, registry=registry).read()


def loads(byte_text, registry=None):
    return load(io.BytesIO(byte_text), registry=registry)
