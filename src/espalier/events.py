"""账本事件词汇(DESIGN.md v2.6)+ V0-PLAN §3.2 新增的 ``Called`` / ``Returned`` /
``Configured``,v0.18(2026-09-06 签)新增的 ``Resumed`` / ``Merged`` / ``Restored``,
以及 ``SeqRange`` / ``Kept`` / ``Tombstone`` / ``Checkpoint`` 四个值类型。

事件是账本的**唯一真理**:块值、结构、压缩、调用、账本级属性,全部由事件序列折叠得出。
每个事件带四个基字段(v2.6)+ 两个 G-V0-1 字段 + 一个 C-20 字段::

    seq          账本位置
    prev         **可指非尖端 ⇒ 日志成树**(D5):fork/resume = 共享前缀新 leaf
    written_at   机械时间;不入任何身份哈希(v2.1 纪律⑤)
    link         ChainHash,append-only 审计链
    ignorable    读不懂可安全跳过;默认 False = 必须能解析(G-V0-1)
    annotations  作者通道;**不入 ChainHash**(G-V0-1,与 v2.1 纪律③同构)
    actor        操作者(C-20):``Uttered | Authored | Injected | None``;**入 ChainHash**

ChainHash 形制(V0-CHOICE,v2.1 只写了 ``h(前链‖事件瘦记录)``)::

    link = h1:l: digest("espalier/chain/v1", [前一条的 link 或 "", canon_json(瘦记录)])
    瘦记录 = to_record() 去掉顶层 link / annotations,再**递归**去掉
             一切 cited_refs / cited_claims 与一切 *_at 时戳(见 strip_identity_free)

四处取舍写在明处:

* **去 annotations**:G-V0-1 已裁(作者写、不入身份;审计链只覆盖瘦记录)。**只去顶层
  那一个**——块值里的 ``annotations`` 照旧入链(纪律③ 只把它排除出 BytesHash/TreeHash)。
* **去一切时戳**:v2.1 纪律⑤"时戳永不入任何身份哈希",而 ChainHash 是七型之一。
  一条纪律一次执行:事件自己的 ``written_at``、``Recalled.written_at``、
  ``Tombstone.written_at``、``UrlAddress.fetched_at`` 一并剔。
  代价诚实记下:**改写任何时戳都不会被链发现**。要改这条,改的是 v2.1 纪律⑤。
* **去一切 cited_refs**:同上,纪律⑤ 点名的第三样。随行块值里的那份也剔。
* **留 id**(裁决 ①,2026-09-06 签):剔掉它,``Appended`` 就没有判别信息了,审计链不再
  是链。裁决把 v2.1 纪律⑤ 收窄为"``id`` 不入**内容身份**哈希(BytesHash / TreeHash)";
  ChainHash 是审计链这种**结构形制**,含 id 是本职。见 :func:`strip_identity_free`。

**记录判别键叫 ``event``**(裁决 ③,2026-09-06 签,维持):块的 ``kind`` 已被 ``Opened``
随行的块字段占用;事件记录的判别键与块的判别键不同名,反而不易误读。

**随行块值(V0-CHOICE)**:v2.6 的 ``Appended`` 只携 ``block: BlockId`` 与 ``tree_hash``,
v2 章从头到尾没说**块值本身存在哪**。V0 的答案是:引入块的三个事件
(``Opened`` / ``Appended`` / ``Replaced``)在记录里随行携带块值(``block_value``,
``Opened`` 是拆开的 kind/title/origin/refs/block_annotations)。理由:任务书定的 JSONL
"第一行 header、之后每行一个事件"没有第二种行;而账本必须能从文件独自复原块值(A9)。
"""

from __future__ import annotations

from dataclasses import dataclass, replace as dc_replace
from datetime import datetime
from typing import Any, Callable, ClassVar, Literal, Mapping, Sequence

from ._freeze import EMPTY_MAPPING, freeze_mapping, freeze_tuple
from ._records import (
    Record,
    actor_from_record,
    actor_to_record,
    legacy_hook_annotations,
    merge_legacy_annotations,
    block_from_record,
    block_to_record,
    content_ref_from_record,
    content_ref_to_record,
    dt_from_iso,
    dt_to_iso,
    origin_from_record,
    origin_to_record,
    refs_from_record,
    refs_to_record,
)
from .block import Block, Ref
from .hashes import (
    CHAIN_HASH_PREFIX,
    COMPACTION_ID_PREFIX,
    STATE_HASH_PREFIX,
    BytesHash,
    CallHash,
    ChainHash,
    CompactionId,
    ManifestHash,
    StateHash,
    TreeHash,
    canon_json,
    digest,
)
from .ids import BlockId, LedgerId, Seq
from .manifest import InlayKey, Manifest, manifest_from_record, manifest_to_record
from .origin import Authored, Injected, Origin, Uttered
from .payload import ContentRef

__all__ = [
    "SeqRange",
    "Kept",
    "Tombstone",
    "Checkpoint",
    "InlayRecord",
    "Event",
    "Opened",
    "Appended",
    "Closed",
    "Compacted",
    "Revoked",
    "Reparented",
    "Removed",
    "Replaced",
    "Merged",
    "Annotated",
    "Pruned",
    "Restored",
    "Checkpointed",
    "Forked",
    "Resumed",
    "Called",
    "Returned",
    "Configured",
    "Actor",
    "EVENT_KINDS",
    "UnknownEventKind",
    "DOMAIN_CHAIN",
    "DOMAIN_STATE",
    "DOMAIN_COMPACTION",
    "OPAQUE_RECORD_KEYS",
    "strip_identity_free",
    "chain_hash",
    "state_hash",
    "compaction_id",
    "seal",
    "event_from_record",
]


DOMAIN_CHAIN: str = "espalier/chain/v1"
DOMAIN_STATE: str = "espalier/state/v1"
DOMAIN_COMPACTION: str = "espalier/compaction/v1"

#: C-9(2026-09-06 签):增 ``"error"``,与 ``CallOutcome`` 同为 {完成, 中断, 错误} 三域。
Outcome = Literal["complete", "interrupted", "error"]
CallOutcome = Literal["ok", "error", "interrupted"]
Disposition = Literal["deleted", "archived"]
#: C-20:事件的操作者。三个变体都是"谁"——话语者 / 亲笔者 / 注入者。
Actor = Uttered | Authored | Injected


class UnknownEventKind(ValueError):
    """记录里的 ``event`` 值本库不认得。``persist`` 按 ``ignorable`` 决定报错还是跳过。"""

    def __init__(self, kind: object) -> None:
        super().__init__(f"unknown event kind: {kind!r}")
        self.kind = kind


# --------------------------------------------------------------------------- 值类型


@dataclass(frozen=True)
class SeqRange:
    """**半开**区间 ``[start, stop)``(v2.6;全库禁用 "span" 一词)。"""

    start: Seq
    stop: Seq

    def __post_init__(self) -> None:
        if self.stop < self.start:
            raise ValueError(f"SeqRange stop < start: [{self.start}, {self.stop})")

    def __contains__(self, seq: object) -> bool:
        return isinstance(seq, int) and self.start <= seq < self.stop

    def __len__(self) -> int:
        return int(self.stop) - int(self.start)

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(range(int(self.start), int(self.stop)))

    def seqs(self) -> tuple[Seq, ...]:
        return tuple(Seq(s) for s in range(int(self.start), int(self.stop)))

    def to_record(self) -> Record:
        return {"start": int(self.start), "stop": int(self.stop)}

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "SeqRange":
        return cls(start=Seq(record["start"]), stop=Seq(record["stop"]))


@dataclass(frozen=True)
class Kept:
    """压缩时**保留**的块,按四个位置分组(v2.6)。"""

    head: tuple[BlockId, ...] = ()
    anchors: tuple[BlockId, ...] = ()
    tail: tuple[BlockId, ...] = ()
    pins: tuple[BlockId, ...] = ()

    def __post_init__(self) -> None:
        for name in ("head", "anchors", "tail", "pins"):
            object.__setattr__(self, name, freeze_tuple(getattr(self, name)))

    def all_ids(self) -> tuple[BlockId, ...]:
        """四组拼接,**保留组内次序、不去重**——去重会丢"同一块被两处保留"这件事。"""
        return self.head + self.anchors + self.tail + self.pins

    def canon(self) -> list[list[str]]:
        """入 ``CompactionId`` 的规范序列:四组各自成列,次序即语义。"""
        return [list(self.head), list(self.anchors), list(self.tail), list(self.pins)]

    def to_record(self) -> Record:
        return {
            "head": list(self.head),
            "anchors": list(self.anchors),
            "tail": list(self.tail),
            "pins": list(self.pins),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "Kept":
        return cls(
            head=tuple(BlockId(b) for b in record["head"]),
            anchors=tuple(BlockId(b) for b in record["anchors"]),
            tail=tuple(BlockId(b) for b in record["tail"]),
            pins=tuple(BlockId(b) for b in record["pins"]),
        )


@dataclass(frozen=True)
class Tombstone:
    """删除留痕(v2.6)。凡曾被哈希或曾入任何 Manifest 者,``bytes_hash`` 必携(N1 收边)。

    ``origin_summary`` 是**字符串**:块没了,出身对象也就没了取回处,留一句机械摘要
    (``"变体名/到达通道"``)总比什么都不留强。它不参与任何身份。
    """

    block: BlockId
    tree_hash: TreeHash | None
    bytes_hash: BytesHash | None
    origin_summary: str
    policy: str
    written_at: datetime

    def to_record(self) -> Record:
        return {
            "block": self.block,
            "tree_hash": self.tree_hash,
            "bytes_hash": self.bytes_hash,
            "origin_summary": self.origin_summary,
            "policy": self.policy,
            "written_at": dt_to_iso(self.written_at),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "Tombstone":
        tree = record["tree_hash"]
        raw = record["bytes_hash"]
        return cls(
            block=BlockId(record["block"]),
            tree_hash=TreeHash(tree) if tree is not None else None,
            bytes_hash=BytesHash(raw) if raw is not None else None,
            origin_summary=record["origin_summary"],
            policy=record["policy"],
            written_at=dt_from_iso(record["written_at"]),
        )


@dataclass(frozen=True)
class Checkpoint:
    """检查点(v2.6)。存**累积状态**而非摘要,校验是查询非闸门(D-X10-1)。

    ``state`` 是 :func:`state_hash` 算出的 ``StateHash``;状态文档本身由
    ``Ledger.state_document(at_seq=, leaf=)`` **重算**得到——它是账本前缀的纯函数,
    因此"可取回"不必再存一份(V0-CHOICE;v2.1 说 StateHash "同时即 CAS 取回键",
    V0 里那个 CAS 就是账本自己)。
    """

    at_seq: Seq
    leaf: Seq
    state: StateHash
    link: ChainHash


@dataclass(frozen=True)
class InlayRecord:
    """一条 Inlay 的**来源事实**(C-27,2026-09-06 签),随 ``Called.inlays`` 入记录。

    只带 ``provider`` / ``params_canon`` / ``after``——**不带文本**:文本由 manifest 里那条
    Inlay 条目的 ``shown`` 对账(``served`` 把实发段字节 ``put`` 进 CAS,CAS 键恒等于
    ``shown``,见 :func:`espalier.calls.served`)。于是"渲染期算出来的那段是谁按什么参数
    算的"在重载后取得回(E-1.Q6 / E-7.Q6:取回而非只验证),而 ``CallHash`` 一个字节不动
    ——它仍是 ``h(ManifestHash ‖ model ‖ params)``。
    """

    provider: str
    params_canon: str = ""
    after: BlockId | None = None

    def to_record(self) -> Record:
        return {"provider": self.provider, "params_canon": self.params_canon, "after": self.after}

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "InlayRecord":
        after = record.get("after")
        return cls(
            provider=record["provider"],
            params_canon=record.get("params_canon", ""),
            after=BlockId(after) if after is not None else None,
        )


# --------------------------------------------------------------------------- 哈希构造


def chain_hash(prev_link: ChainHash | None, thin: Mapping[str, Any]) -> ChainHash:
    """``h(前链 ‖ 事件瘦记录规范序列)``。首事件的 ``prev_link`` 传 ``None``。"""
    head = (prev_link or "").encode("utf-8")
    return ChainHash(CHAIN_HASH_PREFIX + digest(DOMAIN_CHAIN, (head, canon_json(thin))))


def state_hash(document: bytes) -> StateHash:
    """``h(检查点累积态规范序列化)``。输入是 ``Ledger.state_document()`` 的字节。

    裁决 ④(2026-09-06 签):状态文档里每个 ``blocks[id]`` 与 ``open[]`` 条目携带当前
    ``annotations``,于是 StateHash **含注记**——注记被改,检查点验得出。纪律③ 把
    annotations 排除出 BytesHash / TreeHash 的理由是 CAS 去重与结构身份,不是检查点的理由。
    """
    return StateHash(STATE_HASH_PREFIX + digest(DOMAIN_STATE, (document,)))


def compaction_id(
    summary_tree_hash: TreeHash, covered: Sequence[TreeHash], kept: Kept
) -> CompactionId:
    """G-V0-3 跨副本稳定身份 = ``h(摘要 TreeHash ‖ 被覆盖块 TreeHash 序列 ‖ kept 规范序列)``。

    ``covered`` 是被覆盖块(``covers ∖ kept.all_ids()``)按账本次序的 TreeHash 列表——
    **次序即语义**,不排序。

    G-V0-3 裁决(2026-09-06 签):原公式第二项是 ``covers: SeqRange``(一段 seq 区间),
    于是只在**保 seq** 的复制下跨副本同值;被回放到新账本顶部、seq 重编号后就不同值
    (v0 P-03.6 量到的限制)。换成内容寻址后,同一批块回放到 seq 不同的两本账本,
    ``identity`` 同值。它仍不含 ``base_seq``、``covers`` 与账本 id:那些正是副本间会变的东西。
    """
    body = canon_json(
        [str(summary_tree_hash), [str(h) for h in covered], kept.canon()]
    )
    return CompactionId(COMPACTION_ID_PREFIX + digest(DOMAIN_COMPACTION, (body,)))


# --------------------------------------------------------------------------- 瘦记录


#: 记录里**取值由作者定键名**的那些映射。剔时戳时不下钻它们——``annotations`` 的键是
#: 作者写的,里面出现一个叫 ``reviewed_at`` 的键不代表那是机械时戳,凭键名剔掉它就是
#: 在改作者的数据(A9)。
OPAQUE_RECORD_KEYS: frozenset[str] = frozenset(
    {"annotations", "block_annotations", "external_ids", "usage", "resolved", "reason"}
)


def strip_identity_free(value: Any, *, _top: bool = False) -> Any:
    """把记录里**永不入身份哈希**的字段递归剔掉(v2.1 纪律⑤ + G-V0-1)。

    剔三类键:

    * ``cited_refs`` / ``cited_claims`` —— 模型证词(纪律⑤ 点名;后者是 C-5 的同待遇槽);
    * 任何 ``*_at`` —— 一切机械时戳(``written_at`` / ``fetched_at`` / ``created_at``…);
      注意 ``at_seq`` 不在此列(它是位置不是时间,``_seq`` 结尾)。
    * ``link`` 与 ``annotations`` —— **只在顶层**(``_top=True``):链自己不入链,
      事件的作者通道按 G-V0-1 不入链;而块值里的 ``annotations`` 照旧入链
      (纪律③ 只把它排除出 BytesHash/TreeHash,审计链仍盖住它)。

    :data:`OPAQUE_RECORD_KEYS` 里的映射整体保留、**不下钻**。

    **``id`` 留在链里(裁决 ①,2026-09-06 签)**:``Appended`` 除了 ``block`` /
    ``block_value.id`` 之外几乎没有别的判别信息,剔掉 id 会让"追加了哪一块"从审计链上
    消失,链就不再是链了。裁决取的是"纪律⑤ 收窄":``id`` 不入**内容身份**哈希
    (BytesHash / TreeHash);ChainHash / StateHash / ManifestHash / CompactionId 是审计链、
    检查点、清单、压缩身份四种**结构形制**,含 id 是本职。代码不动,只有文案改。
    与之对称的代价照旧:**改写任何时戳都不会被链发现**(事件自己的、块里嵌的,一概如此)。
    """
    if isinstance(value, dict):
        out: Record = {}
        for key, item in value.items():
            if key in ("cited_refs", "cited_claims") or key.endswith("_at"):
                continue
            if _top and key in ("link", "annotations"):
                continue
            out[key] = item if key in OPAQUE_RECORD_KEYS else strip_identity_free(item)
        return out
    if isinstance(value, list):
        return [strip_identity_free(item) for item in value]
    return value


# --------------------------------------------------------------------------- 事件基类


@dataclass(frozen=True, kw_only=True)
class Event:
    """事件基类。全部字段 **keyword-only**(子类要加必填字段,基类又有默认值)。"""

    #: 记录里的 ``event`` 取值。子类必填;禁用 ``type`` 作键名(v2.13)。
    EVENT: ClassVar[str] = ""
    #: 取值是 ``Seq`` 的**自有**字段名(不含 ``seq`` / ``prev``)。fork 深拷贝重编号按它走。
    SEQ_FIELDS: ClassVar[tuple[str, ...]] = ()

    seq: Seq
    prev: Seq | None
    written_at: datetime
    link: ChainHash
    ignorable: bool = False
    annotations: Mapping[str, str] = EMPTY_MAPPING
    actor: Actor | None = None
    """操作者(C-20,2026-09-06 签)。记录键 ``actor``,按 Made 记录形编解码;**入 ChainHash**
    ——它不是 ``*_at``、不是 annotations。模型删记忆的操作者写 ``Uttered(role="model",
    ledger=…)``;``None`` = 记录未说。落基类而不是逐事件加:同一个字段一处定义。"""

    def __post_init__(self) -> None:
        object.__setattr__(self, "annotations", freeze_mapping(self.annotations))

    # ------------------------------------------------------------- 记录

    def body(self) -> Record:
        """子类自有字段 → 记录片段。基类无自有字段。"""
        return {}

    @classmethod
    def body_from_record(cls, record: Mapping[str, Any]) -> dict[str, Any]:
        return {}

    def to_record(self) -> Record:
        record: Record = {
            "event": self.EVENT,
            "seq": int(self.seq),
            "prev": None if self.prev is None else int(self.prev),
            "written_at": dt_to_iso(self.written_at),
            "link": str(self.link),
            "ignorable": bool(self.ignorable),
            "annotations": dict(self.annotations),
            "actor": actor_to_record(self.actor),
        }
        record.update(self.body())
        return record

    @staticmethod
    def from_record(record: Mapping[str, Any]) -> "Event":
        """记录 → 事件(按 ``event`` 值分派)。与 :func:`event_from_record` 同一个函数。"""
        return event_from_record(record)

    def thin_record(self) -> Record:
        """入 ChainHash 的瘦记录。

        三步:① 去 ``link``(链自己不入链);② 去 ``annotations``(G-V0-1:作者通道不入
        身份);③ **递归**去掉每一个 ``cited_refs`` 与每一个 ``*_at`` 时戳——纪律⑤
        "时戳 / cited_refs 永不入任何身份哈希"对 ChainHash 同样有效,而它们随块值、随
        ``Tombstone``、随 ``UrlAddress``、随 ``Recalled`` 一路嵌在记录里。
        见 :func:`strip_identity_free`。
        """
        return strip_identity_free(self.to_record(), _top=True)

    # ------------------------------------------------------------- 变换

    def with_seqs(self, remap: Callable[[Seq], Seq]) -> "Event":
        """按 ``remap`` 重编 ``seq`` / ``prev`` 与自有 seq 字段(fork 深拷贝用)。

        ``link`` 不在这里重算——重编号后的链必须由账本重新封(:func:`seal`)。
        """
        changes: dict[str, Any] = {"seq": remap(self.seq)}
        if self.prev is not None:
            changes["prev"] = remap(self.prev)
        for name in self.SEQ_FIELDS:
            value = getattr(self, name)
            if value is not None:
                changes[name] = remap(value)
        return dc_replace(self, **changes)


def seal(event: Event, prev_link: ChainHash | None) -> Event:
    """算出 ``link`` 并装回事件。账本每次写事件的最后一步。"""
    return dc_replace(event, link=chain_hash(prev_link, event.thin_record()))


# --------------------------------------------------------------------------- 结构事件


@dataclass(frozen=True, kw_only=True)
class Opened(Event):
    """开一个复合(v2.5 句柄形)。kind/origin/title/into/gap 全部定于 open。

    V0-CHOICE:v2.6 的 ``Opened`` 没有 ``origin`` / ``refs`` / ``block_annotations``,
    可那样一来复合块的出身在重载后就没了(A9),而 ``Block.create`` 能设的字段复合块设不了
    (A0)。三者补上;``block_annotations`` 之所以不叫 ``annotations``,是因为基类已经用了
    那个名字表示**事件自己的**作者通道——两个通道不能同名。
    """

    EVENT: ClassVar[str] = "opened"

    composite: BlockId
    kind: str
    origin: Origin
    title: str | None = None
    into: BlockId | None = None
    gap: int = 0
    refs: tuple[Ref, ...] = ()
    block_annotations: Mapping[str, str] = EMPTY_MAPPING

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "refs", freeze_tuple(self.refs))
        object.__setattr__(self, "block_annotations", freeze_mapping(self.block_annotations))

    def body(self) -> Record:
        return {
            "composite": self.composite,
            "kind": self.kind,
            "title": self.title,
            "into": self.into,
            "gap": self.gap,
            "origin": origin_to_record(self.origin),
            "refs": refs_to_record(self.refs),
            "block_annotations": dict(self.block_annotations),
        }

    @classmethod
    def body_from_record(cls, record: Mapping[str, Any]) -> dict[str, Any]:
        into = record["into"]
        origin = origin_from_record(record["origin"])
        if origin is None:
            raise ValueError(
                f"opened record for {record['composite']!r} has no origin; "
                "复合的出身定于 open,缺了就复原不出块(A9)"
            )
        # V1(A10):复合的出身记在事件上而不在块记录里,所以 ``block_from_record`` 那条路
        # 走不到它——v0.18–v0.21 写的 ``Injected`` 六键在这里搬进 ``block_annotations``
        # (闭合后就是复合块的 ``annotations``);同名键已存在则不覆盖。
        legacy = legacy_hook_annotations((record.get("origin") or {}).get("made"))
        return {
            "composite": BlockId(record["composite"]),
            "kind": record["kind"],
            "title": record["title"],
            "into": BlockId(into) if into is not None else None,
            "gap": int(record["gap"]),
            "origin": origin,
            "refs": refs_from_record(record["refs"]),
            "block_annotations": merge_legacy_annotations(record["block_annotations"], legacy),
        }


@dataclass(frozen=True, kw_only=True)
class Appended(Event):
    """把一个**闭合块**写进账本。``tree_hash`` 恒携子块自身 TreeHash,永不补写(v2.6)。"""

    EVENT: ClassVar[str] = "appended"

    block: BlockId
    into: BlockId | None = None
    gap: int = 0
    tree_hash: TreeHash
    block_value: Block | None = None
    """随行块值(V0-CHOICE,见模块 docstring)。``None`` 只出现在外来记录里。"""

    def body(self) -> Record:
        return {
            "block": self.block,
            "into": self.into,
            "gap": self.gap,
            "tree_hash": str(self.tree_hash),
            "block_value": None if self.block_value is None else block_to_record(self.block_value),
        }

    @classmethod
    def body_from_record(cls, record: Mapping[str, Any]) -> dict[str, Any]:
        into = record["into"]
        value = record["block_value"]
        return {
            "block": BlockId(record["block"]),
            "into": BlockId(into) if into is not None else None,
            "gap": int(record["gap"]),
            "tree_hash": TreeHash(record["tree_hash"]),
            "block_value": block_from_record(value) if value is not None else None,
        }


@dataclass(frozen=True, kw_only=True)
class Closed(Event):
    """闭合一个复合。``outcome="interrupted"`` 是 resume 方补的收尾(v2.5 崩溃安全)。

    V0-CHOICE:v2.6 的 ``Closed`` 没有 ``tail_gap``,而 v2.5 的 ``close(tail_gap=)`` 收了它
    ——不落在事件上就复原不出块(``tail_gap`` 入 TreeHash)。补。
    """

    EVENT: ClassVar[str] = "closed"

    composite: BlockId
    merkle: TreeHash
    outcome: Outcome = "complete"
    tail_gap: int = 0
    reason: Mapping[str, str] | None = None
    """结构化载荷(C-9,2026-09-06 签),开域键,如 ``{"kind": "aborted", "cause": "user"}``。
    入链、不下钻(:data:`OPAQUE_RECORD_KEYS`)。"""

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.reason is not None:
            object.__setattr__(self, "reason", freeze_mapping(self.reason))

    def body(self) -> Record:
        return {
            "composite": self.composite,
            "merkle": str(self.merkle),
            "outcome": self.outcome,
            "tail_gap": self.tail_gap,
            "reason": None if self.reason is None else dict(self.reason),
        }

    @classmethod
    def body_from_record(cls, record: Mapping[str, Any]) -> dict[str, Any]:
        reason = record.get("reason")
        return {
            "composite": BlockId(record["composite"]),
            "merkle": TreeHash(record["merkle"]),
            "outcome": record["outcome"],
            "tail_gap": int(record["tail_gap"]),
            "reason": None if reason is None else dict(reason),
        }


# --------------------------------------------------------------------------- 压缩与修订


@dataclass(frozen=True, kw_only=True)
class Compacted(Event):
    """一次压缩(v2.6/2.7)。

    V0-CHOICE 两处:

    * 补 ``summary_tree_hash``:G-V0-3 的 ``identity`` 要"摘要 TreeHash",而 v2.6 的
      ``Compacted`` 只有 ``summary: BlockId``——不带上就算不出跨副本身份。
    * 补 ``targets``:v2.7 原文"校验 ``targets ≡ covers∖kept``,不成立则 ``Compacted``
      携显式 targets"。默认 ``None`` = 等式成立,读者自己算。

    G-V0-3 裁决(2026-09-06 签):补 ``covered_tree_hashes``——被覆盖块
    (``covers ∖ kept``)按账本次序的 TreeHash 序列。它随事件入记录、入 ChainHash,
    :attr:`identity` 只读它;``covers: SeqRange`` 保留为**位置事实**(check 的
    ``covers_out_of_range`` 与读者算 ``targets`` 仍用它),``with_seqs`` 只 remap 它。
    ``None`` = 记录未说(v0.18 及之前的写者没有这一格;或 ``commit`` 收到的
    ``CompactRequest.covered`` 就是 ``None``——手工构造不填):``identity`` 也是 ``None``,
    ``check`` 报 ``identity_unavailable``(info),不编造。``()`` = 已知覆盖了零块。
    """

    EVENT: ClassVar[str] = "compacted"
    SEQ_FIELDS: ClassVar[tuple[str, ...]] = ("base_seq",)

    summary: BlockId
    summary_tree_hash: TreeHash
    covers: SeqRange
    kept: Kept
    base_seq: Seq
    targets: tuple[BlockId, ...] | None = None
    covered_tree_hashes: tuple[TreeHash, ...] | None = None
    """被覆盖块的 TreeHash 序列(G-V0-3,2026-09-06 签)。``None`` = 记录未说,不编造。"""

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.targets is not None:
            object.__setattr__(self, "targets", freeze_tuple(self.targets))
        if self.covered_tree_hashes is not None:
            object.__setattr__(self, "covered_tree_hashes", freeze_tuple(self.covered_tree_hashes))

    @property
    def identity(self) -> CompactionId | None:
        """G-V0-3 跨副本稳定身份;见 :func:`compaction_id`。

        ``covered_tree_hashes`` 是 ``None``(旧记录)⇒ ``None``:身份的输入不在手,不编造。
        """
        if self.covered_tree_hashes is None:
            return None
        return compaction_id(self.summary_tree_hash, self.covered_tree_hashes, self.kept)

    def with_seqs(self, remap: Callable[[Seq], Seq]) -> "Event":
        shifted = super().with_seqs(remap)
        covers = SeqRange(start=remap(self.covers.start), stop=remap(self.covers.stop))
        return dc_replace(shifted, covers=covers)

    def body(self) -> Record:
        return {
            "summary": self.summary,
            "summary_tree_hash": str(self.summary_tree_hash),
            "covers": self.covers.to_record(),
            "kept": self.kept.to_record(),
            "base_seq": int(self.base_seq),
            "targets": None if self.targets is None else list(self.targets),
            "covered_tree_hashes": (
                None
                if self.covered_tree_hashes is None
                else [str(h) for h in self.covered_tree_hashes]
            ),
        }

    @classmethod
    def body_from_record(cls, record: Mapping[str, Any]) -> dict[str, Any]:
        targets = record["targets"]
        covered = record.get("covered_tree_hashes")  # G-V0-3:旧记录缺键 ⇒ None(不编造)
        return {
            "summary": BlockId(record["summary"]),
            "summary_tree_hash": TreeHash(record["summary_tree_hash"]),
            "covers": SeqRange.from_record(record["covers"]),
            "kept": Kept.from_record(record["kept"]),
            "base_seq": Seq(record["base_seq"]),
            "targets": None if targets is None else tuple(BlockId(t) for t in targets),
            "covered_tree_hashes": (
                None if covered is None else tuple(TreeHash(h) for h in covered)
            ),
        }


@dataclass(frozen=True, kw_only=True)
class Revoked(Event):
    """撤销一条记录(P-21 回退)。

    V0-CHOICE:**只留痕,不改折叠出来的状态**。撤销一条 ``Appended`` 之后块还在视图里,
    ``revoked_seqs()`` 与 ``check`` 报告它被撤销过。"撤销后哪些东西该消失"是策略
    (回退是否重放工具、是否连带子块),库不替 harness 决定;要它消失请显式
    ``remove()`` / ``replace()``。C-14(2026-09-06 签)维持此语义:"块回来"是另一个动词
    :class:`Restored`,不让一个事件有两种效果。
    """

    EVENT: ClassVar[str] = "revoked"
    SEQ_FIELDS: ClassVar[tuple[str, ...]] = ("target_seq",)

    target_seq: Seq

    def body(self) -> Record:
        return {"target_seq": int(self.target_seq)}

    @classmethod
    def body_from_record(cls, record: Mapping[str, Any]) -> dict[str, Any]:
        return {"target_seq": Seq(record["target_seq"])}


@dataclass(frozen=True, kw_only=True)
class Reparented(Event):
    """改**逻辑父**。存储父由 ``Appended`` 一次定死永不改;双父两轴永不混写(v2.6)。"""

    EVENT: ClassVar[str] = "reparented"

    block: BlockId
    logical_parent: BlockId

    def body(self) -> Record:
        return {"block": self.block, "logical_parent": self.logical_parent}

    @classmethod
    def body_from_record(cls, record: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "block": BlockId(record["block"]),
            "logical_parent": BlockId(record["logical_parent"]),
        }


@dataclass(frozen=True, kw_only=True)
class Removed(Event):
    """生删 plumbing(v2.6)。块从视图消失,``Tombstone`` 留在账上。"""

    EVENT: ClassVar[str] = "removed"

    block: BlockId
    tombstone: Tombstone

    def body(self) -> Record:
        return {"block": self.block, "tombstone": self.tombstone.to_record()}

    @classmethod
    def body_from_record(cls, record: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "block": BlockId(record["block"]),
            "tombstone": Tombstone.from_record(record["tombstone"]),
        }


@dataclass(frozen=True, kw_only=True)
class Replaced(Event):
    """新块顶掉旧块的位置;旧块**仍可取回**(append-only)。"""

    EVENT: ClassVar[str] = "replaced"

    old: BlockId
    new: BlockId
    tree_hash: TreeHash | None = None
    block_value: Block | None = None
    """新块的随行值与 TreeHash(V0-CHOICE,同 ``Appended``)。"""

    def body(self) -> Record:
        return {
            "old": self.old,
            "new": self.new,
            "tree_hash": None if self.tree_hash is None else str(self.tree_hash),
            "block_value": None if self.block_value is None else block_to_record(self.block_value),
        }

    @classmethod
    def body_from_record(cls, record: Mapping[str, Any]) -> dict[str, Any]:
        tree = record["tree_hash"]
        value = record["block_value"]
        return {
            "old": BlockId(record["old"]),
            "new": BlockId(record["new"]),
            "tree_hash": TreeHash(tree) if tree is not None else None,
            "block_value": block_from_record(value) if value is not None else None,
        }


@dataclass(frozen=True, kw_only=True)
class Merged(Event):
    """多块并作一块(C-13,2026-09-06 签)。新块占 ``olds[0]`` 的位置,其余 olds 从位置层
    摘掉;每个 old 的块值**仍在账上可取回**、**不落墓碑**——同 ``Replaced`` 的 append-only
    语义。``superseded[old] = new`` 对每个 old 成立;反向索引见 ``Ledger.supersedes``(C-15)。
    一对一仍走 ``Replaced``——不改 ``Replaced.old`` 的类型。
    """

    EVENT: ClassVar[str] = "merged"

    olds: tuple[BlockId, ...]
    new: BlockId
    tree_hash: TreeHash | None = None
    block_value: Block | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "olds", freeze_tuple(self.olds))

    def body(self) -> Record:
        return {
            "olds": list(self.olds),
            "new": self.new,
            "tree_hash": None if self.tree_hash is None else str(self.tree_hash),
            "block_value": None if self.block_value is None else block_to_record(self.block_value),
        }

    @classmethod
    def body_from_record(cls, record: Mapping[str, Any]) -> dict[str, Any]:
        tree = record["tree_hash"]
        value = record["block_value"]
        return {
            "olds": tuple(BlockId(b) for b in record["olds"]),
            "new": BlockId(record["new"]),
            "tree_hash": TreeHash(tree) if tree is not None else None,
            "block_value": block_from_record(value) if value is not None else None,
        }


@dataclass(frozen=True, kw_only=True)
class Annotated(Event):
    """改一个块的 ``annotations``,**块 id 与 TreeHash 都不变**。

    V0-CHOICE(v2.6 没有这个事件,补的理由是 A0):纪律③ 说 ``annotations`` 是"作者写但
    不入身份"的通道,可在只有 ``Block.create`` 一个写入口时,事后要补一条注记就只能
    ``replace()``,而 ``replace`` 拒收同 id ⇒ 必须换一枚 BlockId。于是"不入身份的通道"
    在实践中改一次就换一次身份——dict 级 CRUD 的 U 缺了一个动词。

    ``mode="merge"``(默认)按键合并,``mode="replace"`` 整表替换(**删键**唯一的走法)。
    两种都是纯值语义:折叠时用新映射造一个等价的块,``Appended.tree_hash`` 一个字节不动
    ——annotations 构造性排除出 TreeHash,所以这本来就该成立,这里只是让它真的成立。
    开态复合也收:注记落在 ``_OpenState`` 上,``close()`` 时随块一起定影。
    """

    EVENT: ClassVar[str] = "annotated"

    block: BlockId
    block_annotations: Mapping[str, str] = EMPTY_MAPPING
    mode: Literal["merge", "replace"] = "merge"

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "block_annotations", freeze_mapping(self.block_annotations))

    def applied_to(self, current: Mapping[str, str]) -> Mapping[str, str]:
        """把本事件作用在一份现有注记上,返回新映射。折叠与预演共用它。"""
        if self.mode == "replace":
            return freeze_mapping(self.block_annotations)
        merged = dict(current)
        merged.update(self.block_annotations)
        return freeze_mapping(merged)

    def body(self) -> Record:
        return {
            "block": self.block,
            "block_annotations": dict(self.block_annotations),
            "mode": self.mode,
        }

    @classmethod
    def body_from_record(cls, record: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "block": BlockId(record["block"]),
            "block_annotations": record["block_annotations"],
            "mode": record["mode"],
        }


@dataclass(frozen=True, kw_only=True)
class Pruned(Event):
    """熟删 porcelain(v2.6):按 ``Retention`` 策略剪枝,``disposition`` 记去向。"""

    EVENT: ClassVar[str] = "pruned"

    block: BlockId
    disposition: Disposition
    tombstone: Tombstone

    def body(self) -> Record:
        return {
            "block": self.block,
            "disposition": self.disposition,
            "tombstone": self.tombstone.to_record(),
        }

    @classmethod
    def body_from_record(cls, record: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "block": BlockId(record["block"]),
            "disposition": record["disposition"],
            "tombstone": Tombstone.from_record(record["tombstone"]),
        }


@dataclass(frozen=True, kw_only=True)
class Restored(Event):
    """块回来(C-14,2026-09-06 签)。``of_seq`` 指向那条 ``Removed`` / ``Pruned``。

    折叠:块回到原存储父、原索引处(索引超界则落尾),墓碑清除。``Revoked`` 语义**不动**
    (仍只留痕)——"这条记录作废"与"块回来"是两个动词,不让一个事件有两种效果。
    """

    EVENT: ClassVar[str] = "restored"
    SEQ_FIELDS: ClassVar[tuple[str, ...]] = ("of_seq",)

    block: BlockId
    of_seq: Seq

    def body(self) -> Record:
        return {"block": self.block, "of_seq": int(self.of_seq)}

    @classmethod
    def body_from_record(cls, record: Mapping[str, Any]) -> dict[str, Any]:
        return {"block": BlockId(record["block"]), "of_seq": Seq(record["of_seq"])}


# --------------------------------------------------------------------------- 账本级


@dataclass(frozen=True, kw_only=True)
class Checkpointed(Event):
    """检查点落账(v2.6)。``state`` 是累积态的 ``StateHash``,可重算可校验(D-X10-1)。"""

    EVENT: ClassVar[str] = "checkpointed"
    SEQ_FIELDS: ClassVar[tuple[str, ...]] = ("at_seq", "leaf")

    state: StateHash
    at_seq: Seq
    leaf: Seq

    def body(self) -> Record:
        return {"state": str(self.state), "at_seq": int(self.at_seq), "leaf": int(self.leaf)}

    @classmethod
    def body_from_record(cls, record: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "state": StateHash(record["state"]),
            "at_seq": Seq(record["at_seq"]),
            "leaf": Seq(record["leaf"]),
        }


@dataclass(frozen=True, kw_only=True)
class Forked(Event):
    """**物理分叉**:本账本是从 ``parent`` 的 ``at_seq`` 处拷出来的(X12 乙形)。

    ``at_seq`` 是**父账本**上的位置,不参与本账本的重编号,所以不进 ``SEQ_FIELDS``。
    与 ``LedgerHeader.parent``(委派/派生)两义分开(G-V0-2)。
    """

    EVENT: ClassVar[str] = "forked"

    parent: LedgerId
    at_seq: Seq

    def body(self) -> Record:
        return {"parent": self.parent, "at_seq": int(self.at_seq)}

    @classmethod
    def body_from_record(cls, record: Mapping[str, Any]) -> dict[str, Any]:
        return {"parent": LedgerId(record["parent"]), "at_seq": Seq(record["at_seq"])}


@dataclass(frozen=True, kw_only=True)
class Resumed(Event):
    """**恢复会话**的纯记录事件(C-8,2026-09-06 签)。不改折叠状态。

    ``tip_before`` 是恢复那一刻的写游标(真实 harness 里"恢复后第一条活事件的位置"的落点);与 fork 的
    ``inherited_cut`` 分轴。由 ``Ledger.resumed()`` **显式**写——``Ledger.open`` 不自动写
    (A0:默认动作不能有)。
    """

    EVENT: ClassVar[str] = "resumed"
    SEQ_FIELDS: ClassVar[tuple[str, ...]] = ("tip_before",)

    tip_before: Seq | None = None

    def body(self) -> Record:
        return {"tip_before": None if self.tip_before is None else int(self.tip_before)}

    @classmethod
    def body_from_record(cls, record: Mapping[str, Any]) -> dict[str, Any]:
        tip = record.get("tip_before")
        return {"tip_before": None if tip is None else Seq(tip)}


@dataclass(frozen=True, kw_only=True)
class Called(Event):
    """一次模型调用**发出**(H1 / D-CAP-1)。调用实例按 ``seq`` 寻址,``call`` 只作去重键。

    ``purpose`` 区分主线与副线(P-14):``"main"|"compact"|"title"|"search"|"memory"…``,
    库不解释取值。``params_canon`` 让 ``CallHash`` 的输入**可取回**(P-14:params 现无处存)。

    V0-CHOICE:补 ``manifest_value`` —— **manifest 随行**(与 ``Appended`` 携
    ``block_value`` 同构)。§3.1 定的"Manifest 以 ManifestHash 存 CAS"照做
    (:func:`espalier.calls.served` 会 ``put`` 一份),但 CAS 在 V0 是内存实现、dev 模式
    更是零流水,只靠它 ``manifest_of`` 就熬不过一次重载——而"模型这次看到了什么"是 H1
    存在的全部理由(A9)。``None`` 只出现在外来记录里,取回时如实报"取不回"、不伪造。

    两格 2026-09-06 签的把手,都**不入 CallHash**、都随记录入 ChainHash、旧记录缺键 ⇒ 默认值:

    * ``inlays``(C-27):``{InlayKey: InlayRecord(provider, params_canon, after)}``——
      本次实发的 Inlay 的来源事实;文本由 manifest 的 ``shown`` 对账、在 CAS 里取。
    * ``rendering``(C-28):``served(..., keep_rendering=True)`` 时整份 ``Rendering.data``
      的 CAS 键;默认 ``None``(默认关,opt-in;不推翻 C-7 ④"库不替 harness 存全文")。
    """

    EVENT: ClassVar[str] = "called"

    call: CallHash
    manifest: ManifestHash
    model: str
    params_canon: str = ""
    purpose: str = "main"
    manifest_value: "Manifest | None" = None
    inlays: Mapping[InlayKey, InlayRecord] = EMPTY_MAPPING
    rendering: ContentRef | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "inlays", freeze_mapping(self.inlays))

    def body(self) -> Record:
        return {
            "call": str(self.call),
            "manifest": str(self.manifest),
            "model": self.model,
            "params_canon": self.params_canon,
            "purpose": self.purpose,
            "manifest_value": (
                None if self.manifest_value is None else manifest_to_record(self.manifest_value)
            ),
            "inlays": {str(k): v.to_record() for k, v in self.inlays.items()},
            "rendering": None if self.rendering is None else content_ref_to_record(self.rendering),
        }

    @classmethod
    def body_from_record(cls, record: Mapping[str, Any]) -> dict[str, Any]:
        value = record.get("manifest_value")
        rendering = record.get("rendering")  # C-28:旧记录缺键 ⇒ None
        return {
            "call": CallHash(record["call"]),
            "manifest": ManifestHash(record["manifest"]),
            "model": record["model"],
            "params_canon": record["params_canon"],
            "purpose": record["purpose"],
            "manifest_value": None if value is None else manifest_from_record(value),
            "inlays": {  # C-27:旧记录缺键 ⇒ 空映射
                InlayKey(k): InlayRecord.from_record(v)
                for k, v in (record.get("inlays") or {}).items()
            },
            "rendering": None if rendering is None else content_ref_from_record(rendering),
        }


@dataclass(frozen=True, kw_only=True)
class Returned(Event):
    """一次模型调用**回来**(或没回来)。``called_seq`` 指向配对的 ``Called``。

    ``usage`` 是 P-17 的分项 token,``external_ids`` 是 P-18 的 provider 请求/响应 id 与
    遥测 id:两者**不入 CallHash / 内容身份哈希**(用量是输出不是输入),**但随记录入
    ChainHash**——它们不在 :func:`strip_identity_free` 剔除的三类键里,整条留在瘦记录中;
    同时列在 :data:`OPAQUE_RECORD_KEYS`,于是内部的作者自定键(哪怕叫 ``*_at``)也一并
    保留、不下钻。改这两格的值,链就变;审计链盖得住它们。
    """

    EVENT: ClassVar[str] = "returned"
    SEQ_FIELDS: ClassVar[tuple[str, ...]] = ("called_seq",)

    called_seq: Seq
    outcome: CallOutcome = "ok"
    output: BlockId | None = None
    usage: Mapping[str, int] | None = None
    external_ids: Mapping[str, str] = EMPTY_MAPPING
    reason: Mapping[str, str] | None = None
    """结构化载荷(C-9),同 ``Closed.reason``:开域键,入链、不下钻。"""

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.usage is not None:
            object.__setattr__(self, "usage", freeze_mapping(self.usage))
        object.__setattr__(self, "external_ids", freeze_mapping(self.external_ids))
        if self.reason is not None:
            object.__setattr__(self, "reason", freeze_mapping(self.reason))

    def body(self) -> Record:
        return {
            "called_seq": int(self.called_seq),
            "outcome": self.outcome,
            "output": self.output,
            "usage": None if self.usage is None else dict(self.usage),
            "external_ids": dict(self.external_ids),
            "reason": None if self.reason is None else dict(self.reason),
        }

    @classmethod
    def body_from_record(cls, record: Mapping[str, Any]) -> dict[str, Any]:
        output = record["output"]
        usage = record["usage"]
        reason = record.get("reason")
        return {
            "called_seq": Seq(record["called_seq"]),
            "outcome": record["outcome"],
            "output": BlockId(output) if output is not None else None,
            "usage": None if usage is None else dict(usage),
            "external_ids": record["external_ids"],
            "reason": None if reason is None else dict(reason),
        }


@dataclass(frozen=True, kw_only=True)
class Configured(Event):
    """中途可变的账本级属性(G-V0-2)。**末条生效**,按 ``at_seq`` 求值。

    取值一律 ``str``:库不解释,harness 自己解码(A5)。结构化值请自己序列化后再存。
    """

    EVENT: ClassVar[str] = "configured"

    name: str
    value: str

    def body(self) -> Record:
        return {"name": self.name, "value": self.value}

    @classmethod
    def body_from_record(cls, record: Mapping[str, Any]) -> dict[str, Any]:
        return {"name": record["name"], "value": record["value"]}


# --------------------------------------------------------------------------- 注册表


#: ``event`` 取值 → 事件类。加事件类要同时加进这里,否则 ``from_record`` 认不得。
EVENT_KINDS: Mapping[str, type[Event]] = {
    cls.EVENT: cls
    for cls in (
        Opened,
        Appended,
        Closed,
        Compacted,
        Revoked,
        Reparented,
        Removed,
        Replaced,
        Merged,
        Annotated,
        Pruned,
        Restored,
        Checkpointed,
        Forked,
        Resumed,
        Called,
        Returned,
        Configured,
    )
}


def event_from_record(record: Mapping[str, Any]) -> Event:
    """记录 → 事件。``event`` 值不认得时抛 :class:`UnknownEventKind`。"""
    kind = record.get("event")
    cls = EVENT_KINDS.get(kind)  # type: ignore[arg-type]
    if cls is None:
        raise UnknownEventKind(kind)
    prev = record["prev"]
    # V1(A10):操作者若是 v0.18–v0.21 的 ``Injected`` 记录,六个 hook 键搬进事件注记。
    legacy = legacy_hook_annotations(record.get("actor"))
    return cls(
        seq=Seq(record["seq"]),
        prev=Seq(prev) if prev is not None else None,
        written_at=dt_from_iso(record["written_at"]),
        link=ChainHash(record["link"]),
        ignorable=bool(record.get("ignorable", False)),
        annotations=merge_legacy_annotations(record.get("annotations"), legacy),
        actor=actor_from_record(record.get("actor")),  # C-20:旧记录缺键 ⇒ None
        **cls.body_from_record(record),
    )
