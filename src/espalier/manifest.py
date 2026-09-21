"""``Manifest``:一次渲染实发了什么(DESIGN.md v2.10 + V0-PLAN §3.2 的 G-V0-4 完备项)。

Manifest 是 **"LLM 这次看到了什么"的唯一指纹**。它不是渲染的副产品,而是渲染的**第二个
返回值**:每条 :class:`ManifestEntry` 把"输出字节的哪一段"钉到"账本上的哪个身份"。

v2.10 给了五个字段(``source`` / ``byte_range`` / ``shown`` / ``part`` / ``fence``);
G-V0-4 又补了三件(``role`` / ``message_index`` / ``source`` 可指 :class:`Absent`)与三个
查询(``diff`` / ``entries_in`` / ``fence_count``)。本模块是这两处的合流。

**为什么 ``shown`` 不等于块的 ``BytesHash``**:``shown`` 钉的是**实发字节**——转义之后、
折叠之后、占位之后的那一段。同一个块渲染两次可以有两个不同的 ``shown``(一次全文、一次
折叠摘要),而它的 ``BytesHash`` 一直没变。两个哈希回答两个问题,不可互相顶替。

**三处 V0-CHOICE**:

1. ``InlayKey`` 与 ``BlockId`` 在运行期都是 ``str``,类型标注分不开它们。所以
   ``inlay_key()`` 造出的键**带 ``inlay:`` 前缀**,:func:`is_inlay_key` 是那条机械判据。
   没有前缀就只能靠"这个 id 在不在账本上"来猜,而猜出来的判别键不配做判别键。
   ``InlayKey`` 定义在这里而不是与 ``Inlay`` 同居 :mod:`espalier.render`,是因为
   ``ManifestEntry.source`` 要用它,而 render 依赖 manifest、反向依赖不成立。
2. ``SpecDigest`` **不进** :data:`espalier.HASH_PREFIXES`。那张表是"八个互不可比的
   **身份**型"的表(每一型都是某样东西的取回键);SpecDigest 摘的是**渲染规格**,
   从不作为取回键出现。它有自己的前缀 ``h1:d:``,显名入型(v2.10 的要求),但不冒充第九个身份型。
3. ``Manifest.escapes``(D-X13-14):v2.8 ③ 说"转义区间入 manifest"却没说单位;V0 取
   **字节区间**,与 ``byte_range`` 同一坐标系(行号要再定义一次"行",而 D-X13-4 正是
   因为"行"没定义才成为缺口)。``escapes`` **不入 ManifestHash**——转义区间是实发字节的
   函数、已被 ``shown`` 钉住。

**ManifestHash 公式(C-17,2026-09-06 签)**::

    ManifestHash = h(entries ‖ spec_digest ‖ excluded ‖ excluded_why)

v2.1 原式是 ``h(entries‖spec_digest)``;C-17 把 ``excluded``(排除留痕)与 ``excluded_why``
(C-7 ③ 的排除理由映射)一并纳入——排除是留痕,留痕要入指纹。规范序列是
``[[entries…], spec, [excluded…], {id: why}]``,见 :func:`manifest_hash`。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Mapping, NewType, Sequence

from ._freeze import EMPTY_MAPPING, freeze_mapping, freeze_tuple
from .hashes import (
    MANIFEST_HASH_PREFIX,
    BytesHash,
    ManifestHash,
    canon_json,
    digest,
)
from .ids import BlockId

__all__ = [
    "DOMAIN_MANIFEST",
    "DOMAIN_SPEC",
    "DOMAIN_INLAY",
    "SpecDigest",
    "SPEC_DIGEST_PREFIX",
    "spec_digest",
    "EMPTY_SPEC_DIGEST",
    "InlayKey",
    "INLAY_KEY_PREFIX",
    "inlay_key",
    "is_inlay_key",
    "Absent",
    "Source",
    "ManifestEntry",
    "ManifestDiff",
    "Manifest",
    "manifest_hash",
    "manifest_bytes",
    "manifest_to_record",
    "manifest_from_record",
]

DOMAIN_MANIFEST: Final[str] = "espalier/manifest/v1"
DOMAIN_SPEC: Final[str] = "espalier/spec/v1"
DOMAIN_INLAY: Final[str] = "espalier/inlay/v1"


# --------------------------------------------------------------------------- SpecDigest

#: 渲染规格摘要的前缀。见模块 docstring 的 V0-CHOICE ②:它不是身份型,不入 HASH_PREFIXES。
SPEC_DIGEST_PREFIX: Final[str] = "h1:d:"

SpecDigest = NewType("SpecDigest", str)


def spec_digest(payload: Mapping[str, Any]) -> SpecDigest:
    """渲染规格 → ``SpecDigest``。输入是 ``RenderSpec`` 自己摊平出来的规范映射。

    v2.10 只要求"第八哈希域显名入型,不以裸 str 潜入";形制与其它域一致
    (:func:`espalier.digest` 的域名 + 长度 framing)。
    """
    return SpecDigest(SPEC_DIGEST_PREFIX + digest(DOMAIN_SPEC, (canon_json(payload),)))


#: 空规格的摘要。给"手工造一个 Manifest"的调用者一个诚实的默认值(A0:默认值可以有)。
EMPTY_SPEC_DIGEST: Final[SpecDigest] = spec_digest({})


# --------------------------------------------------------------------------- InlayKey

#: :class:`espalier.Inlay` 的键前缀。运行期判别 ``BlockId`` / ``InlayKey`` 的唯一机械判据。
INLAY_KEY_PREFIX: Final[str] = "inlay:"

InlayKey = NewType("InlayKey", str)


def inlay_key(provider: str, params: Mapping[str, Any] | None = None) -> InlayKey:
    """确定性 id ``= f(provider, canon(params))``(v2.9)。同 provider 同参数 ⇒ 同键。"""
    body = digest(DOMAIN_INLAY, (provider.encode("utf-8"), canon_json(params or {})))
    return InlayKey(INLAY_KEY_PREFIX + body[:32])


def is_inlay_key(value: object) -> bool:
    """纯查询:这个 ``source`` 取值是不是 Inlay 键。永不抛。"""
    return isinstance(value, str) and value.startswith(INLAY_KEY_PREFIX)


# --------------------------------------------------------------------------- 条目


@dataclass(frozen=True)
class Absent:
    """**发出了、但账本上没有**(G-V0-4)。

    典型来源:非 ant 转录里被 ``isLoggableMessage`` 丢掉的 attachment——它确实进了模型,
    只是没进转录。没有这一格,manifest 就只能在"少一条"和"伪造一个 BlockId"之间选,
    两个都是丢信息(A9)。``reason`` 是给人看的一句话,库不解释。
    """

    reason: str


#: ``ManifestEntry.source`` 的三种取值。
Source = BlockId | InlayKey | Absent


def _source_record(source: Source) -> Any:
    if isinstance(source, Absent):
        return {"absent": source.reason}
    return str(source)


def _source_from_record(record: Any) -> Source:
    if isinstance(record, Mapping):
        return Absent(reason=record["absent"])
    if is_inlay_key(record):
        return InlayKey(record)
    return BlockId(record)


def _source_key(source: Source) -> tuple[str, str]:
    """``diff`` 用的可比键。三种取值落在三个命名空间里,永不互撞。"""
    if isinstance(source, Absent):
        return ("absent", source.reason)
    if is_inlay_key(source):
        return ("inlay", str(source))
    return ("block", str(source))


@dataclass(frozen=True)
class ManifestEntry:
    """一条实发条目。

    ``role`` 与 ``message_index`` 是 G-V0-4 补的两件:前者是 wire 角色,后者是
    **条目 → wire 消息的分组**(同一个 ``message_index`` 的若干条目合成一条消息;
    次序由 ``entries`` 的顺序承担,不由 seq 反推)。两者都有默认值,便于手工构造
    (A0:默认值可以有);``render`` 一律显式填。

    ``folded``(V0-CHOICE)标记"这一条是折叠把手,不是全文"——v2.8 ⑦ 要
    ``Manifest.expandable()`` 返回"本次真实发出的折叠把手集",而 v2.10 的五个字段里
    没有任何一个记得住"这条是折叠的"。伪造的展开请求靠它机械查拒。
    """

    source: Source
    byte_range: tuple[int, int]
    shown: BytesHash
    part: int | None = None
    fence: str | None = None
    role: str = "user"
    message_index: int = 0
    folded: bool = False

    def __post_init__(self) -> None:
        start, stop = self.byte_range
        object.__setattr__(self, "byte_range", (int(start), int(stop)))

    @property
    def block_id(self) -> BlockId | None:
        """``source`` 是块 id 时给出它;Inlay / Absent ⇒ ``None``。"""
        if isinstance(self.source, Absent) or is_inlay_key(self.source):
            return None
        return BlockId(self.source)

    @property
    def size(self) -> int:
        return self.byte_range[1] - self.byte_range[0]

    def overlaps(self, byte_range: tuple[int, int]) -> bool:
        """半开区间相交判定(``entries_in`` / E-1 用)。"""
        start, stop = byte_range
        return self.byte_range[0] < stop and start < self.byte_range[1]

    def canon(self) -> list[Any]:
        """入 ``ManifestHash`` 的规范序列。次序即语义,不排序。"""
        return [
            _source_record(self.source),
            [self.byte_range[0], self.byte_range[1]],
            str(self.shown),
            self.part,
            self.fence,
            self.role,
            self.message_index,
            self.folded,
        ]

    def to_record(self) -> dict[str, Any]:
        return {
            "source": _source_record(self.source),
            "byte_range": [self.byte_range[0], self.byte_range[1]],
            "shown": str(self.shown),
            "part": self.part,
            "fence": self.fence,
            "role": self.role,
            "message_index": self.message_index,
            "folded": self.folded,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "ManifestEntry":
        start, stop = record["byte_range"]
        return cls(
            source=_source_from_record(record["source"]),
            byte_range=(int(start), int(stop)),
            shown=BytesHash(record["shown"]),
            part=record["part"],
            fence=record["fence"],
            role=record["role"],
            message_index=int(record["message_index"]),
            folded=bool(record["folded"]),
        )


# --------------------------------------------------------------------------- diff


@dataclass(frozen=True)
class ManifestDiff:
    """两份 manifest 之间的差(G-V0-4;CAPABILITIES B6)。

    按 **``(source, shown)``** 比:同一个块以同样的字节再次发出 ⇒ 不算变化,哪怕它挪了
    位置(那算 ``moved``)。这正是几家真实 harness 各自要答的同一个问题:请求头里的
    "变了没有"判定、对上一次渲染做 diff、哪些内容要重新宣告。

    ``moved`` 的元素是 ``(旧条目, 新条目)`` 对——只报"位置变了",不报变成了什么,
    因为 ``(source, shown)`` 相同就意味着实发字节相同。
    """

    added: tuple[ManifestEntry, ...] = ()
    removed: tuple[ManifestEntry, ...] = ()
    moved: tuple[tuple[ManifestEntry, ManifestEntry], ...] = ()

    def __post_init__(self) -> None:
        for name in ("added", "removed", "moved"):
            object.__setattr__(self, name, freeze_tuple(getattr(self, name)))

    @property
    def empty(self) -> bool:
        """三格全空 ⇒ 两次实发的条目集合与次序逐条相同。"""
        return not (self.added or self.removed or self.moved)

    def __len__(self) -> int:
        return len(self.added) + len(self.removed) + len(self.moved)


# --------------------------------------------------------------------------- Manifest


def manifest_hash(
    entries: Sequence[ManifestEntry],
    spec: SpecDigest,
    excluded: Sequence[BlockId] = (),
    excluded_why: Mapping[BlockId, str] = EMPTY_MAPPING,
) -> ManifestHash:
    """``h(entries ‖ spec_digest ‖ excluded ‖ excluded_why)``(v2.1 + C-17,2026-09-06 签)。

    规范序列 ``[[entries…], spec, [excluded…], {id: why}]``;``excluded`` 保次序(次序由
    :class:`Manifest` 的 ``excluded`` 字段文档定义:按来路分段,**不是**视图顶层次序),
    ``excluded_why`` 由 ``canon_json`` 按键排序。
    """
    body = canon_json(
        [
            [e.canon() for e in entries],
            str(spec),
            [str(b) for b in excluded],
            {str(k): v for k, v in excluded_why.items()},
        ]
    )
    return ManifestHash(MANIFEST_HASH_PREFIX + digest(DOMAIN_MANIFEST, (body,)))


@dataclass(frozen=True)
class Manifest:
    """一次渲染的实发清单(v2.10)。**全库唯一名**(v2.13 禁令)。"""

    entries: tuple[ManifestEntry, ...] = ()
    excluded: tuple[BlockId, ...] = ()
    """排除是决策,须留痕(v2.10;thinking 2.23× 的教训)。次序**按来路分段**,不是整份
    按视图顶层次序(次序承重:入 ManifestHash,见 :func:`manifest_hash`):

    1. ``View.without`` 里此刻在**账本顶层**的,按**账本**顶层次序(``View.roots`` 不改这个
       次序——它只改 ``entries`` 的次序);
    2. ``View.without`` 的其余 id(嵌套在复合里的子块、账本上根本不存在的),按 id
       字典序——前两段由 :meth:`espalier.View.excluded` 给出,**不做在场过滤**;
    3. 只从 ``RenderSpec.exclude`` 来、前两段没列过的,由 :func:`espalier.render` 按
       ``sorted`` 追在最后,**即便它本身在顶层**也落这里。

    两个排除入口在"排不排"上同义(§3.2),在**次序**上不同义:同一个顶层 id 走
    ``without`` 落第 1 段、走 ``RenderSpec.exclude`` 落第 3 段。
    """

    spec_digest: SpecDigest = EMPTY_SPEC_DIGEST
    escapes: tuple[tuple[int, int], ...] = ()
    """被转义的**字节区间**(D-X13-14 V0-CHOICE)。不入 ManifestHash,见模块 docstring。"""

    excluded_why: Mapping[BlockId, str] = EMPTY_MAPPING
    """排除的理由(C-7 ③,2026-09-06 签):``RenderSpec.exclude_why`` 随行到这里;键 ⊆
    ``excluded``(render 保证)。``excluded`` 的元素类型不改——全仓消费者按 id 用它。入 ManifestHash。"""

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", freeze_tuple(self.entries))
        object.__setattr__(self, "excluded", freeze_tuple(self.excluded))
        object.__setattr__(
            self, "escapes", tuple((int(a), int(b)) for a, b in self.escapes)
        )
        object.__setattr__(self, "excluded_why", freeze_mapping(self.excluded_why))

    # ----------------------------------------------------------------- 身份

    def hash(self) -> ManifestHash:
        """本次实发的唯一指纹。v2.10 给的就是这个名字(裸 ``hash()`` 的退役只管块)。

        C-17:``excluded`` 与 ``excluded_why`` 一并入指纹。
        """
        return manifest_hash(self.entries, self.spec_digest, self.excluded, self.excluded_why)

    # ----------------------------------------------------------------- 查询

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.entries)

    def sources(self) -> tuple[Source, ...]:
        return tuple(e.source for e in self.entries)

    def block_ids(self) -> tuple[BlockId, ...]:
        """出现在本次实发里的块 id,去重、保次序。"""
        seen: dict[BlockId, None] = {}
        for entry in self.entries:
            block_id = entry.block_id
            if block_id is not None:
                seen.setdefault(block_id, None)
        return tuple(seen)

    def of_source(self, source: Source) -> tuple[ManifestEntry, ...]:
        """同一个来源的全部条目(一个块可以在一次渲染里出现多次)。"""
        key = _source_key(source)
        return tuple(e for e in self.entries if _source_key(e.source) == key)

    def entries_in(self, byte_range: tuple[int, int]) -> tuple[ManifestEntry, ...]:
        """与给定**字节区间**相交的条目(E-1:渲染字节区间 → 块 → 出身)。"""
        return tuple(e for e in self.entries if e.overlaps(byte_range))

    def fence_count(self) -> int:
        """带围栏标签的条目数(L5;X18 的"围栏道数"用它对账)。"""
        return sum(1 for e in self.entries if e.fence is not None)

    def expandable(self) -> frozenset[BlockId]:
        """本次**真实发出**的折叠把手集(v2.8 ⑦)。伪造的展开请求可机械查拒。"""
        return frozenset(
            block_id
            for block_id in (e.block_id for e in self.entries if e.folded)
            if block_id is not None
        )

    def messages(self) -> tuple[tuple[int, tuple[ManifestEntry, ...]], ...]:
        """按 ``message_index`` 分组(G-V0-4:条目→wire 消息)。保出现次序。"""
        groups: dict[int, list[ManifestEntry]] = {}
        for entry in self.entries:
            groups.setdefault(entry.message_index, []).append(entry)
        return tuple((index, tuple(items)) for index, items in sorted(groups.items()))

    def diff(self, other: "Manifest") -> ManifestDiff:
        """``self`` 是旧、``other`` 是新:``added`` 在新里、``removed`` 在旧里。

        同键重复出现时按出现次序配对(同一段字节发两遍是合法的,不能被去重吞掉)。
        """
        def key(entry: ManifestEntry) -> tuple[tuple[str, str], str]:
            return (_source_key(entry.source), str(entry.shown))

        mine: dict[tuple[tuple[str, str], str], list[tuple[int, ManifestEntry]]] = {}
        theirs: dict[tuple[tuple[str, str], str], list[tuple[int, ManifestEntry]]] = {}
        for index, entry in enumerate(self.entries):
            mine.setdefault(key(entry), []).append((index, entry))
        for index, entry in enumerate(other.entries):
            theirs.setdefault(key(entry), []).append((index, entry))

        added: list[tuple[int, ManifestEntry]] = []
        removed: list[tuple[int, ManifestEntry]] = []
        moved: list[tuple[int, tuple[ManifestEntry, ManifestEntry]]] = []

        for key, olds in mine.items():
            news = theirs.get(key, [])
            for (old_index, old), (new_index, new) in zip(olds, news):
                if old_index != new_index:
                    moved.append((new_index, (old, new)))
            if len(olds) > len(news):
                removed.extend(olds[len(news) :])
        for key, news in theirs.items():
            olds = mine.get(key, [])
            if len(news) > len(olds):
                added.extend(news[len(olds) :])

        return ManifestDiff(
            added=tuple(e for _, e in sorted(added, key=lambda pair: pair[0])),
            removed=tuple(e for _, e in sorted(removed, key=lambda pair: pair[0])),
            moved=tuple(pair for _, pair in sorted(moved, key=lambda pair: pair[0])),
        )

    # ----------------------------------------------------------------- 记录

    def to_record(self) -> dict[str, Any]:
        return manifest_to_record(self)

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "Manifest":
        return manifest_from_record(record)

    def to_bytes(self) -> bytes:
        """CAS 存取用的规范序列(§3.1:Manifest 以 ManifestHash 存 CAS)。"""
        return manifest_bytes(self)


def manifest_to_record(manifest: Manifest) -> dict[str, Any]:
    return {
        "entries": [e.to_record() for e in manifest.entries],
        "excluded": list(manifest.excluded),
        "spec_digest": str(manifest.spec_digest),
        "escapes": [[a, b] for a, b in manifest.escapes],
        "excluded_why": {str(k): v for k, v in manifest.excluded_why.items()},
    }


def manifest_from_record(record: Mapping[str, Any]) -> Manifest:
    return Manifest(
        entries=tuple(ManifestEntry.from_record(e) for e in record["entries"]),
        excluded=tuple(BlockId(b) for b in record["excluded"]),
        spec_digest=SpecDigest(record["spec_digest"]),
        escapes=tuple((int(a), int(b)) for a, b in record["escapes"]),
        excluded_why={BlockId(k): str(v) for k, v in (record.get("excluded_why") or {}).items()},
    )


def manifest_bytes(manifest: Manifest) -> bytes:
    """Manifest 的规范字节。同值 → 同字节 ⇒ 放进 CAS 即自动去重。"""
    return canon_json(manifest_to_record(manifest))
