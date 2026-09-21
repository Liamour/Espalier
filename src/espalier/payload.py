"""载荷与内容存储(DESIGN.md v2.2)+ 规范形 c1(D-X1-1 / D-X14-1)。

三件事:

1. **内容与账本分离**:``ContentRef(hash, size)`` 是取回键 + 预算键;``ContentStore``
   是跨账本去重的居所。``size`` 存在的理由:未取回也能做预算/截断决策。
2. **``Payload = Text | Blob``**。``Text`` 自带 ``canon`` 声明,``Blob`` 自带 ``mime``。
   全库零 ``type`` 字段(v2.13 禁令)。
3. **规范形**:``c1`` = CRLF→LF + 纯空白行归空行;``raw`` = 恒等。

canon 的适用范围(F-2-D1 / D-X14-1,V0-PLAN §3.1 已裁):**运行期摄入默认 ``raw``**,
``c1`` 只在编写面 / ``parse()`` 路径用。X14 实测 c1 全域默认会静默改 12.5% 的
tool_result 字节——那是 L1 丢失,不是规范化。

**c1 的定义边界(V0-CHOICE;D-X14-3 待签核)**:

* 行尾只处理 ``CRLF → LF``。**孤立 CR 不动**——把孤立 CR 当行尾会改变行数,是改写不是
  归一(D-X14-3 原话)。X1 当年的原型脚本连孤立 CR 一起归了,本实现按 V0 任务书给的
  字面定义(CRLF→LF)收窄。若 owner 裁定要归孤立 CR,那是 **c2**,发新 ``CanonId``,
  不重铸旧身份(D-X1-4)。
* "纯空白行"用 Python ``str.strip()`` 的字符类判定(含 U+00A0 等 Unicode 空白)——
  与 X1 原型一致。这一条同样待 D-X14-3 钉死。

**canon 与 CAS 键的关系(V0-CHOICE)**:``ContentStore.put`` 只看见字节,它算的
``ContentRef.hash`` 恒为 ``bytes_hash(data, canon="raw")``,即**存储字节的 CAS 键**;
而载荷的身份哈希 :func:`payload_bytes_hash` 用载荷**自己声明的** canon。canon="raw"
时两者相等,这是常态;canon="c1" 的外置文本两者不等——这是诚实的:去重键与身份键本来
就是两个问题(v2.1 纪律②的同构推论)。
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable, Final, Mapping, Protocol, runtime_checkable

from .hashes import BytesHash, bytes_hash
from .ids import CANON_C1, CANON_RAW, CanonId
from .origin import ExternalAddress, FileAddress

__all__ = [
    "ContentRef",
    "ContentStore",
    "MemoryContentStore",
    "Text",
    "Blob",
    "Payload",
    "c1",
    "raw",
    "CANONS",
    "canonicalize",
    "is_canonical",
    "payload_bytes",
    "payload_canon",
    "payload_bytes_hash",
    "payload_size",
]


# --------------------------------------------------------------------------- 规范形


def raw(text: str) -> str:
    """``raw`` 规范形:恒等。运行期摄入的默认(F-2-D1)。"""
    return text


def c1(text: str) -> str:
    """``c1`` 规范形:CRLF→LF,只含空白的行归为空行。幂等。

    见模块 docstring 的 "c1 的定义边界" —— 孤立 CR 不动。
    """
    lines = text.replace("\r\n", "\n").split("\n")
    return "\n".join("" if line.strip() == "" else line for line in lines)


#: 规范形注册表。加一个规范形 = 加一个 ``CanonId`` + 一个纯函数,旧身份不重铸(D-X1-4)。
CANONS: Final[Mapping[CanonId, Callable[[str], str]]] = MappingProxyType(
    {CANON_RAW: raw, CANON_C1: c1}
)


def canonicalize(text: str, canon: CanonId) -> str:
    """按 ``canon`` 规范化。未知规范形抛 ``KeyError``——库不猜。"""
    try:
        fn = CANONS[canon]
    except KeyError:
        raise KeyError(f"unknown canon: {canon!r}; known: {sorted(CANONS)}") from None
    return fn(text)


def is_canonical(text: str, canon: CanonId) -> bool:
    """纯查询:``text`` 是否已是 ``canon`` 的不动点。"""
    return canonicalize(text, canon) == text


# --------------------------------------------------------------------------- 内容存储


@dataclass(frozen=True)
class ContentRef:
    """CAS 取回键 + 大小。

    ``hash`` 恒为 ``bytes_hash(data, canon="raw")``(存储字节的 CAS 键),这是
    :class:`ContentStore` 的契约的一部分。
    """

    hash: BytesHash
    size: int


@runtime_checkable
class ContentStore(Protocol):
    """内容与账本分离;跨账本去重的居所(v2.2)。"""

    def put(self, data: bytes) -> ContentRef: ...

    def get(self, ref: ContentRef) -> bytes: ...

    def has(self, hash: BytesHash) -> bool: ...


class MemoryContentStore:
    """进程内 CAS。dev 模式(零流水)与测试用。

    A0:除 Protocol 的三件外还露出 ``__len__`` / ``__contains__`` / ``hashes()``
    这几个纯查询。**没有 delete**——CAS 是 append-only,熟删归账本的 ``prune``。
    """

    __slots__ = ("_data",)

    def __init__(self) -> None:
        self._data: dict[BytesHash, bytes] = {}

    def put(self, data: bytes) -> ContentRef:
        key = bytes_hash(data, canon=CANON_RAW)
        self._data.setdefault(key, data)
        return ContentRef(hash=key, size=len(data))

    def get(self, ref: ContentRef) -> bytes:
        try:
            return self._data[ref.hash]
        except KeyError:
            raise KeyError(f"content not in store: {ref.hash}") from None

    def has(self, hash: BytesHash) -> bool:
        return hash in self._data

    def hashes(self) -> frozenset[BytesHash]:
        return frozenset(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, hash: object) -> bool:
        return hash in self._data


# --------------------------------------------------------------------------- 载荷


@dataclass(frozen=True)
class Text:
    """文本载荷。``body`` 小叶内联 / 大叶外置;外置必自带取回键,禁裸 ``None``。

    构造器**不做**规范化(A0:默认动作不能有)。要规范化请显式走
    :meth:`Text.canonical`;``Text.of`` 原样存下并只做声明。
    """

    canon: CanonId
    body: str | ContentRef

    @classmethod
    def of(cls, body: str | ContentRef, canon: CanonId = CANON_RAW) -> "Text":
        """原样存下,声明 ``canon``(默认 ``raw`` = 运行期默认,F-2-D1)。不改字节。"""
        return cls(canon=canon, body=body)

    @classmethod
    def canonical(cls, text: str, canon: CanonId = CANON_C1) -> "Text":
        """**先规范化再存**。编写面 / ``parse()`` 路径用。"""
        return cls(canon=canon, body=canonicalize(text, canon))

    @property
    def inline(self) -> bool:
        return isinstance(self.body, str)

    def is_canonical(self) -> bool | None:
        """纯查询:内联正文是否已是自己声明的规范形的不动点。

        外置正文(``ContentRef``)不取回即无法判定,如实返回 ``None``——不拿 ``False``
        冒充"不是"(A9:不丢信息,也不造信息)。
        """
        if isinstance(self.body, ContentRef):
            return None
        return is_canonical(self.body, self.canon)


@dataclass(frozen=True)
class Blob:
    """二进制载荷。全库零 ``type`` 字段;媒体类型一律 ``mime``(v2.13)。

    C-6(2026-09-06 签):``data`` 可以是 ``ContentRef``(字节在 CAS)**或**
    ``ExternalAddress``(字节只在外部,如溢出内容的取回定位符 / 只存路径的附件)。
    后者是诚实的"字节不在手":``payload_bytes`` / ``payload_bytes_hash`` 抛 ``KeyError``,
    ``payload_size`` 只在 ``FileAddress.total`` 给了时答得出,``Block.bytes_hash`` 返回
    ``None``(不编造),叶 TreeHash 第四槽落 ``{"external": 地址记录}``。这样保住了
    ``ContentRef.hash`` 恒为 CAS 键的契约——地址不冒充哈希。
    """

    mime: str
    data: ContentRef | ExternalAddress

    @property
    def external(self) -> bool:
        """[派] 字节不在 CAS、只有外部地址。"""
        return not isinstance(self.data, ContentRef)


Payload = Text | Blob


def payload_canon(payload: Payload) -> CanonId:
    """载荷入哈希时用的 ``canon``。

    V0-CHOICE:``Blob`` 没有 canon 字段(二进制不谈行尾),入哈希时按 ``raw`` 计。
    v2.2 的 CanonId 取值域只有 ``raw`` / ``c1``,不为 Blob 另发一个值。
    """
    if isinstance(payload, Text):
        return payload.canon
    return CANON_RAW


def payload_bytes(payload: Payload, *, store: ContentStore | None = None) -> bytes:
    """取载荷的**存储字节**。内联文本按 UTF-8 编码;外置载荷经 ``store`` 取回。

    需要 store 而没给时抛 ``ValueError``——不静默返回半个答案。
    """
    if isinstance(payload, Text):
        if isinstance(payload.body, str):
            return payload.body.encode("utf-8")
        ref = payload.body
    else:
        if not isinstance(payload.data, ContentRef):
            raise KeyError(
                f"blob bytes are not in hand: only an external address {payload.data!r} (C-6)"
            )
        ref = payload.data
    if store is None:
        raise ValueError("payload is external; a ContentStore is required to resolve it")
    return store.get(ref)


def payload_size(payload: Payload, *, store: ContentStore | None = None) -> int:
    """载荷的存储字节数。外置载荷用 ``ContentRef.size``,**不取回**(预算决策要的就是这个)。"""
    if isinstance(payload, Text):
        if isinstance(payload.body, str):
            return len(payload.body.encode("utf-8"))
        return payload.body.size
    data = payload.data
    if isinstance(data, ContentRef):
        return data.size
    if isinstance(data, FileAddress) and data.total is not None:
        return int(data.total)
    raise KeyError(f"blob size is not in hand: external address {data!r} carries no total (C-6)")


def payload_bytes_hash(payload: Payload, *, store: ContentStore | None = None) -> BytesHash:
    """载荷的 ``BytesHash`` = h(声明的 canon ‖ 存储字节)(D-X14-2 / D-X1-4)。

    ``kind`` **不**入(v2.1 纪律②);``annotations`` 构造性排除(纪律③)。

    捷径:外置载荷且声明 canon 就是 ``raw`` 时,CAS 键本身即答案,不必取回内容。
    """
    canon = payload_canon(payload)
    if canon == CANON_RAW:
        if isinstance(payload, Blob):
            if not isinstance(payload.data, ContentRef):
                raise KeyError(
                    f"blob bytes are not in hand: only an external address {payload.data!r}; "
                    "no BytesHash can be honestly computed (C-6)"
                )
            return payload.data.hash
        if isinstance(payload.body, ContentRef):
            return payload.body.hash
    return bytes_hash(payload_bytes(payload, store=store), canon=canon)
