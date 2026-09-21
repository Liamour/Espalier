"""``Block`` 核心类型(DESIGN.md v2.3)、``ChildLink``、``Ref`` 与 TreeHash 计算。

``Block`` 值永远是"闭"的;开态住句柄(``OpenComposite``,v2.5,不在本段)。
``children`` 存 ``BlockId``(D2:单一真理树;值树只是 codec 解析边界的输入形,入账即化为
id 树),``gap`` 归收容边——reparent 不再污染子块身份。

**身份纪律**(v2.1,本模块是它的落地处):

* ``kind`` 入 TreeHash、**不**入 BytesHash(去重键与审计键是两个问题);
* ``title`` 是一等字段、**入** TreeHash(两份设计把 title 塞进 annotations,均被判 fatal);
* ``annotations`` **构造性排除**出 BytesHash / TreeHash——它连参数都不是,不可能"忘了排除";
* ``id`` / 时戳 / ``cited_refs`` / ``cited_claims`` 永不入任何身份哈希。

**TreeHash 形制**(v2.1 表 + 裁决 ② / C-18,2026-09-06 签)::

    叶   = h(kind ‖ title ‖ refs 规范序列 ‖ 第四槽)
    复合 = h(kind ‖ title ‖ refs 规范序列 ‖ 第四槽 ‖ 有序 (子TreeHash, gap) 对 ‖ tail_gap)

**第四槽**(叶与复合同一算法):``BytesHash``;``Blob.data`` 是外部地址(字节不在手)时
落 ``{"external": 地址规范记录}``(C-6::func:`espalier.origin.address_canon`,去 ``*_at``
键——两块只存外部、地址不同的附件,身份不得相同);无载荷 ⇒ ``None``。

裁决 ② + C-18(2026-09-06 签):v2.1 的复合公式原文只有 ``kind‖title‖(子,gap)*‖tail_gap``,
于是复合块改 ``refs`` 不改身份(P-40 / P-33 反驳层量到的洞),既有 ``payload`` 又有
``children`` 的块只由子块定身份(P-33.1)。现在两条公式在前四项上合一;两个域名
(``DOMAIN_TREE_LEAF`` / ``DOMAIN_TREE_COMPOSITE``)不变。

字节级 framing 见 :func:`espalier.hashes.digest`;各段先用 ``canon_json`` 编成一个数组,
数组次序即上式的 ``‖`` 次序。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping, Sequence

from ._freeze import freeze_mapping, freeze_tuple
from .hashes import (
    DOMAIN_TREE_COMPOSITE,
    DOMAIN_TREE_LEAF,
    TREE_HASH_PREFIX,
    BytesHash,
    TreeHash,
    canon_json,
    digest,
)
from .ids import CANON_RAW, BlockId, new_block_id
from .origin import ExternalAddress, Origin, Realm, address_canon, default_realm
from .payload import Blob, ContentRef, ContentStore, Payload, Text, payload_bytes_hash

__all__ = [
    "ChildLink",
    "Ref",
    "Claim",
    "Block",
    "ANNOTATION_SPILL_THRESHOLD",
]

#: F-3-D10(**待签核**)阈值,现在只作常量登记,不生效。见 :class:`Block` 的 TODO。
ANNOTATION_SPILL_THRESHOLD: int = 4096


@dataclass(frozen=True)
class ChildLink:
    """收容边:子块 id + 它前面的空行数。

    ``gap`` 住在**边**上而不是子块上,所以 reparent 不改子块身份(D2)。
    """

    child: BlockId
    gap: int = 0


@dataclass(frozen=True)
class Ref:
    """L3 引用。``space`` ∈ "tool"|"skill"|"block"|"memory"|"shape"…,库不解释取值。"""

    space: str
    target: str


@dataclass(frozen=True)
class Claim:
    """模型**声称**引自某个外部地址(C-5,2026-09-06 签)。

    这是证词,不是机械证据(A4):模型说"引自 path:12-40"落这里;解析器切块时的偏移走
    ``Parsed.span`` / ``Transformed.span``。与 ``cited_refs`` 同待遇——永不入任何身份哈希、
    永不并入 ``origin``、render 不渲染。``note`` 是模型原话的一句,库不解释。
    """

    address: ExternalAddress
    note: str | None = None


def _refs_canon(refs: Sequence[Ref]) -> list[list[str]]:
    """refs 的规范序列:有序的 ``[space, target]`` 对。次序是信息,不排序。"""
    return [[ref.space, ref.target] for ref in refs]


@dataclass(frozen=True)
class Block:
    """闭合块。v2.3 全字段。

    构造一般走 :meth:`create`;直接调 ``Block(...)`` 也是公开的(A0:底层构造永远完备,
    接缝前提条款)——只是要自己给 ``id`` 并自己冻容器。
    """

    id: BlockId
    kind: str
    """纯标签,引擎永不解释;唯一判别词(v2.13 禁令:全库零 ``type`` 字段)。"""

    title: str | None
    """一等字段,入 TreeHash。"""

    payload: Payload | None
    """``None`` ⇔ 纯容器复合。"""

    children: tuple[ChildLink, ...]
    tail_gap: int

    origin: Origin
    """机械证据,不可变(A4/A6);构造期必填。"""

    refs: tuple[Ref, ...]
    """L3;入 TreeHash——叶与复合都入(裁决 ②,2026-09-06 签)。"""

    cited_refs: tuple[Ref, ...]
    """模型证词,永不并入 ``origin``(A4),永不入任何身份哈希。"""

    annotations: Mapping[str, str]
    """通用"作者写但不入身份"通道;中文母语名住这里。

    TODO(F-3-D10,**待签核**):约定"单条 annotation 值超
    :data:`ANNOTATION_SPILL_THRESHOLD` 字节时 ``append`` 自动降为 ``Payload``"。
    V0 **不实现**——那是一个默认动作(A0 禁),且会让同一份事实在两处有两种形。
    真要落地,落点在账本的 ``append`` 而不是这里,并且必须留痕。
    """

    cited_claims: tuple[Claim, ...] = ()
    """模型声称的外部引用(C-5)。与 ``cited_refs`` 同待遇:证词、不入任何身份哈希。"""

    _cache: dict[str, object] = field(
        default_factory=dict, init=False, compare=False, repr=False
    )
    """惰性 memoize 的盒子。``init=False`` ⇒ ``dataclasses.replace`` 得新块新盒子。"""

    def __post_init__(self) -> None:
        object.__setattr__(self, "children", freeze_tuple(self.children))
        object.__setattr__(self, "refs", freeze_tuple(self.refs))
        object.__setattr__(self, "cited_refs", freeze_tuple(self.cited_refs))
        object.__setattr__(self, "cited_claims", freeze_tuple(self.cited_claims))
        object.__setattr__(self, "annotations", freeze_mapping(self.annotations))

    # ----------------------------------------------------------------- 构造

    @classmethod
    def create(
        cls,
        payload: Payload | str | None = None,
        *,
        kind: str,
        title: str | None = None,
        origin: Origin,
        children: Iterable[ChildLink] = (),
        refs: Iterable[Ref] = (),
        cited_refs: Iterable[Ref] = (),
        cited_claims: Iterable[Claim] = (),
        annotations: Mapping[str, str] | None = None,
        tail_gap: int = 0,
        id: BlockId | None = None,
    ) -> "Block":
        """建块。``origin`` 构造期必填;``id`` 不给则新发一枚 ULID。

        ``cited_claims``(C-5,2026-09-06 签)与 ``cited_refs`` 并列:模型证词的两个槽。

        V0-CHOICE 两处(v2.3 的 ``create`` 签名没列):

        * 补 ``cited_refs`` 与 ``id`` 两个参数——A0 要求构造面能设到每一个字段,
          否则"模型证词"与"导入时保留原 id"都要绕过公开 API 才写得进去。
        * ``payload`` 收 ``str``:直接包成 ``Text(canon="raw")``。这就是 V0-PLAN §3.1
          "``Text.canon="raw"`` 为 ``append``/``Block.create`` 默认"(F-2-D1)的落地形——
          默认**值**是 raw,而不是默认**动作**做规范化。
        """
        if isinstance(payload, str):
            payload = Text(canon=CANON_RAW, body=payload)
        return cls(
            id=id if id is not None else new_block_id(),
            kind=kind,
            title=title,
            payload=payload,
            children=freeze_tuple(children),
            tail_gap=tail_gap,
            origin=origin,
            refs=freeze_tuple(refs),
            cited_refs=freeze_tuple(cited_refs),
            cited_claims=freeze_tuple(cited_claims),
            annotations=freeze_mapping(annotations),
        )

    # ----------------------------------------------------------------- 派生查询

    @property
    def is_composite(self) -> bool:
        """有子块即复合。TreeHash 走哪条公式由它决定。"""
        return bool(self.children)

    @property
    def child_ids(self) -> tuple[BlockId, ...]:
        return tuple(link.child for link in self.children)

    @property
    def realm(self) -> Realm:
        """派生自 ``origin``:``Parsed``/``Authored`` → authoring,其余 → runtime。

        ``RenderSpec.realm_of`` 可覆写(v2.3)。
        """
        return default_realm(self.origin)

    # ----------------------------------------------------------------- 身份哈希

    def bytes_hash(self, *, store: ContentStore | None = None) -> BytesHash | None:
        """规范字节摘要;无载荷 ⇒ ``None``。

        ``kind`` 不入(v2.1 纪律②);``title`` / ``refs`` / ``annotations`` 都不入——
        BytesHash 是 **CAS 去重键**,只关心字节与它的规范形声明(D-X14-2)。

        C-6(2026-09-06 签):``Blob.data`` 是外部地址(字节不在手)⇒ ``None``,不编造。
        """
        if self.payload is None:
            return None
        if isinstance(self.payload, Blob) and not isinstance(self.payload.data, ContentRef):
            return None
        cached = self._cache.get("bytes_hash")
        if cached is not None:
            return cached  # type: ignore[return-value]
        value = payload_bytes_hash(self.payload, store=store)
        self._cache["bytes_hash"] = value
        return value

    def tree_hash(
        self,
        resolve: Callable[[BlockId], TreeHash] | None = None,
        *,
        store: ContentStore | None = None,
    ) -> TreeHash:
        """结构身份。惰性 memoize;闭合块任何模式必得值。

        * **叶**(无子块)可直接算,不需要 ``resolve``;载荷外置且 canon 非 raw 时需 ``store``。
        * **复合**需要子块的 TreeHash。``children`` 存的是 id(D2),所以要一个
          ``resolve``。v2.6 让 ``Appended`` 事件**恒携子块自身 TreeHash、永不补写**,
          账本因此总能在 ``append`` 时把这个函数喂进来并缓存结果。

        缺 ``resolve`` 的复合块抛 ``ValueError``——不返回"半个身份"。

        **裁决 ② + C-18(2026-09-06 签)**:复合公式 =
        ``[kind, title, refs 规范序列, 第四槽, (子TreeHash, gap)*, tail_gap]``,前四项与叶
        公式同一算法(:meth:`_own_fourth`);域名仍是 ``DOMAIN_TREE_COMPOSITE``。于是:

        1. 复合块的 ``refs`` 入 TreeHash——改 refs 即改身份(v2.3 "refs 入 TreeHash"
           对两条公式同样成立)。
        2. 既有 ``payload`` 又有 ``children`` 的块,其自身载荷与子块**都**定身份。
           v2.3 的模型里 ``payload=None ⇔ 纯容器复合``,类型允许而库不拦(A0),
           这种块的取值此处显式定义,不再只由子块决定(P-33.1)。
        """
        cached = self._cache.get("tree_hash")
        if cached is not None:
            return cached  # type: ignore[return-value]

        fourth = self._own_fourth(store=store)
        if self.is_composite:
            if resolve is None:
                raise ValueError(
                    f"block {self.id} is composite; tree_hash needs a resolve(BlockId) -> TreeHash"
                )
            child_pairs = [[str(resolve(link.child)), link.gap] for link in self.children]
            body = canon_json(
                [self.kind, self.title, _refs_canon(self.refs), fourth, child_pairs, self.tail_gap]
            )
            value = TreeHash(TREE_HASH_PREFIX + digest(DOMAIN_TREE_COMPOSITE, (body,)))
        else:
            body = canon_json([self.kind, self.title, _refs_canon(self.refs), fourth])
            value = TreeHash(TREE_HASH_PREFIX + digest(DOMAIN_TREE_LEAF, (body,)))

        self._cache["tree_hash"] = value
        return value

    def _own_fourth(self, *, store: ContentStore | None = None) -> object:
        """TreeHash 的**第四槽**——叶与复合同一算法(裁决 ② + C-18):

        * 有字节在手 ⇒ :meth:`bytes_hash`;
        * ``Blob.data`` 是外部地址(C-6)⇒ ``{"external": 地址规范记录}``,不编造字节摘要;
        * 无载荷 ⇒ ``None``。
        """
        fourth: object = self.bytes_hash(store=store)
        payload = self.payload
        if (
            fourth is None
            and isinstance(payload, Blob)
            and not isinstance(payload.data, ContentRef)
        ):
            # C-6:字节不在手,身份落地址——两块只存外部、地址不同的附件身份不得相同。
            fourth = {"external": address_canon(payload.data)}
        return fourth
