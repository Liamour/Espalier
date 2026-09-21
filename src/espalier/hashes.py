"""身份与哈希纪律(DESIGN.md v2.1)+ V0-PLAN 的第八型 ``CompactionId``。

八个**互不可比**的 NewType,每型一途:

======================  =========  ================================================
型                      前缀       定义(v2.1 表;第八型见 V0-PLAN §3.1)
======================  =========  ================================================
``BytesHash``           ``h1:b:``  规范字节摘要;**按存储字节 + canon 字段算**(D-X14-2)
``TreeHash``            ``h1:t:``  叶 = h(kind‖title‖refs‖第四槽);复合 = h(kind‖title‖refs‖第四槽‖(子TreeHash,gap)*‖tail_gap)(裁决 ② + C-18)
``ManifestHash``        ``h1:m:``  h(entries‖spec_digest‖excluded‖excluded_why)(C-17)
``CallHash``            ``h1:k:``  h(ManifestHash‖model‖params 规范序列)
``ToolCallHash``        ``h1:a:``  h(tool‖args 规范序列),上下文无关
``ChainHash``           ``h1:l:``  h(前链‖事件瘦记录)
``StateHash``           ``h1:s:``  h(检查点累积态规范序列化,含注记;裁决 ④),同时即 CAS 取回键
``CompactionId``        ``h1:c:``  h(摘要 TreeHash‖被覆盖块 TreeHash 序列‖kept)(G-V0-3 跨副本稳定身份,内容寻址)
======================  =========  ================================================

纪律(v2.1):① ``canon`` 是**入哈希字段**(D-X1-4),不是摘要串前缀——规范形升级发新
``CanonId``,不重铸旧身份;② ``kind`` 入 TreeHash、不入 BytesHash;③ ``annotations``
构造性排除出 BytesHash / TreeHash;④ ``title`` 一等字段、入 TreeHash;⑤ id / 时戳 /
``cited_refs`` 永不入**内容身份**哈希(BytesHash / TreeHash)。

纪律⑤ 的管辖范围按裁决 ①(2026-09-06 签)收窄:它管的是内容身份;ChainHash / StateHash /
ManifestHash / CompactionId 是审计链、检查点、清单、压缩身份四种**结构形制**,含 ``id`` 是
本职(``ManifestEntry.source``、``Kept`` 四组、``Appended.block`` 都是 id)。时戳与
``cited_refs`` 仍不入八型中的任何一型。

**framing(V0-CHOICE)**:v2.1 用 ``‖`` 记连接,没定字节级形制。裸连接有歧义
(``h("ab","c") == h("a","bc")``),会让"同哈希"这件事失去意义,所以 :func:`digest`
用「域名 + NUL + 每段 8 字节大端长度前缀」框住每一段。域名让不同用途的同形输入不撞。

**canon_json(V0-CHOICE)**:只收 JSON 原生类型 + ``Mapping`` / 序列 / 集合。
``datetime`` / ``Enum`` 一律 ``TypeError``——要入哈希请调用者先自己定死格式,库不替
调用者选时间格式(选了就是静默的语义决定)。``float`` 允许但禁 NaN/Inf。
集合按元素排序后序列化(要求元素可比)。
"""

from __future__ import annotations

import hashlib
import json
from types import MappingProxyType
from typing import Final, Iterable, Mapping, NewType, Sequence

from .ids import CanonId

__all__ = [
    "BytesHash",
    "TreeHash",
    "ManifestHash",
    "CallHash",
    "ToolCallHash",
    "ChainHash",
    "StateHash",
    "CompactionId",
    "BYTES_HASH_PREFIX",
    "TREE_HASH_PREFIX",
    "MANIFEST_HASH_PREFIX",
    "CALL_HASH_PREFIX",
    "TOOL_CALL_HASH_PREFIX",
    "CHAIN_HASH_PREFIX",
    "STATE_HASH_PREFIX",
    "COMPACTION_ID_PREFIX",
    "HASH_PREFIXES",
    "canon_json",
    "sha256_hex",
    "digest",
    "bytes_hash",
    "hash_prefix",
    "hash_body",
    "is_hash",
]

BytesHash = NewType("BytesHash", str)
TreeHash = NewType("TreeHash", str)
ManifestHash = NewType("ManifestHash", str)
CallHash = NewType("CallHash", str)
ToolCallHash = NewType("ToolCallHash", str)
ChainHash = NewType("ChainHash", str)
StateHash = NewType("StateHash", str)
#: V0-PLAN §3.1「跨副本身份(G-V0-3)」的第八型。
CompactionId = NewType("CompactionId", str)

BYTES_HASH_PREFIX: Final[str] = "h1:b:"
TREE_HASH_PREFIX: Final[str] = "h1:t:"
MANIFEST_HASH_PREFIX: Final[str] = "h1:m:"
CALL_HASH_PREFIX: Final[str] = "h1:k:"
TOOL_CALL_HASH_PREFIX: Final[str] = "h1:a:"
CHAIN_HASH_PREFIX: Final[str] = "h1:l:"
STATE_HASH_PREFIX: Final[str] = "h1:s:"
COMPACTION_ID_PREFIX: Final[str] = "h1:c:"

#: 型名 → 前缀。给 check / 诊断用;八型一处可读。
HASH_PREFIXES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "BytesHash": BYTES_HASH_PREFIX,
        "TreeHash": TREE_HASH_PREFIX,
        "ManifestHash": MANIFEST_HASH_PREFIX,
        "CallHash": CALL_HASH_PREFIX,
        "ToolCallHash": TOOL_CALL_HASH_PREFIX,
        "ChainHash": CHAIN_HASH_PREFIX,
        "StateHash": STATE_HASH_PREFIX,
        "CompactionId": COMPACTION_ID_PREFIX,
    }
)

#: :func:`digest` 的域名。域名进摘要,不同用途的同形输入永不撞。
DOMAIN_BYTES: Final[str] = "espalier/bytes/v1"
DOMAIN_TREE_LEAF: Final[str] = "espalier/tree.leaf/v1"
DOMAIN_TREE_COMPOSITE: Final[str] = "espalier/tree.composite/v1"


def _normalize(obj: object) -> object:
    """把 Python 值归一成 JSON 可序列化的确定性形。见模块 docstring 的 V0-CHOICE。"""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        if isinstance(obj, float) and (obj != obj or obj in (float("inf"), float("-inf"))):
            raise ValueError("canon_json refuses NaN / Infinity")
        return obj
    if isinstance(obj, Mapping):
        normalized: dict[str, object] = {}
        for key, value in obj.items():
            if not isinstance(key, str):
                raise TypeError(f"canon_json mapping keys must be str, got {type(key).__name__}")
            normalized[key] = _normalize(value)
        return normalized
    if isinstance(obj, (list, tuple)):
        return [_normalize(item) for item in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted(_normalize(item) for item in obj)  # type: ignore[type-var]
    raise TypeError(
        f"canon_json does not accept {type(obj).__name__}; "
        "pre-format datetimes / enums / bytes yourself so the encoding is your decision"
    )


def canon_json(obj: object) -> bytes:
    """规范序列化:键排序、无空白、UTF-8。同值 → 同字节。"""
    return json.dumps(
        _normalize(obj),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """裸 sha256 十六进制摘要。不带域名、不带 framing——只给已经自带形制的输入用。"""
    return hashlib.sha256(data).hexdigest()


def digest(domain: str, parts: Sequence[bytes] | Iterable[bytes]) -> str:
    """带域名与长度 framing 的 sha256 十六进制摘要(不带 ``h1:*:`` 前缀)。

    形制:``sha256(domain_utf8 ‖ 0x00 ‖ (len(part) as u64be ‖ part)*)``。
    """
    hasher = hashlib.sha256()
    hasher.update(domain.encode("utf-8"))
    hasher.update(b"\x00")
    for part in parts:
        hasher.update(len(part).to_bytes(8, "big"))
        hasher.update(part)
    return hasher.hexdigest()


def bytes_hash(data: bytes, *, canon: CanonId) -> BytesHash:
    """规范字节摘要 = h(canon ‖ 存储字节)。

    D-X14-2:v2.1 表原文"text 取 c1 字节"与 RAW 载荷冲突;这里按**存储字节**算,
    并把 ``canon`` 作为**入哈希字段**(D-X1-4)带进摘要。于是同一串字节声明为
    ``raw`` 与声明为 ``c1`` 得到两个不同的 BytesHash——这是要的:规范形是内容身份的
    一部分,不是编码细节。
    """
    return BytesHash(BYTES_HASH_PREFIX + digest(DOMAIN_BYTES, (canon.encode("utf-8"), data)))


def hash_prefix(value: str) -> str:
    """取 ``h1:x:`` 前缀;不带已知前缀时抛 ``ValueError``。"""
    for prefix in HASH_PREFIXES.values():
        if value.startswith(prefix):
            return prefix
    raise ValueError(f"not an espalier hash: {value!r}")


def hash_body(value: str) -> str:
    """去掉 ``h1:x:`` 前缀的摘要本体。"""
    return value[len(hash_prefix(value)) :]


def is_hash(value: object, prefix: str | None = None) -> bool:
    """纯查询:``value`` 是不是(指定型的)espalier 哈希。永不抛。"""
    if not isinstance(value, str):
        return False
    if prefix is not None:
        return value.startswith(prefix) and len(value) > len(prefix)
    try:
        hash_prefix(value)
    except ValueError:
        return False
    return True
