"""``Ledger``:append-only 事件账本(DESIGN.md v2.5/2.6 + V0-PLAN §3.2)。

**两模式同 API(A3)**::

    Ledger.create(None, header=...)        # dev:零流水,全在内存
    Ledger.create(path, header=...)        # track:JSONL append + fsync
    Ledger.open(path)                      # 重载;崩溃恢复从这里开始

A3 作用域限定条款(v2.6 定案):两模式在**相同记录之上**行为与返回相同;记录本身的多寡
是模式的定义差。dev 模式没有跨进程恢复的记录,不是"行为不同"。

**事件是唯一真理**:块值、结构、压缩、调用、账本级属性全部由事件序列折叠得出;
``prev`` 可指非尖端 ⇒ 日志成树(D5),于是"看哪条线"(``leaf``)与"看哪一刻"(``at_seq``)
是两个独立参数,几乎每个查询都收这两个。

**崩溃恢复**:未 close 的复合在日志上就是 ``Opened`` 无 ``Closed``;``open()`` 之后
``open_composites()`` 枚举它们,``close(outcome="interrupted")`` 追加一条 ``Closed``——
**不改写**任何既有行(v2.5)。

**存储父与逻辑父两轴永不混写**(v2.6):存储父由 ``Appended.into`` 一次定死;
``reparent`` 只动逻辑父轴。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace as dc_replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Mapping, Sequence

from ._freeze import freeze_mapping, freeze_tuple
from .block import Block, ChildLink, Ref
from .calls import (
    Verdict,
    calls_showing as _calls_showing,
    manifest_of as _manifest_of,
    returned as _returned,
    saw as _saw,
    served as _served,
    verify as _verify,
)
from .check import CheckReport, check_ledger
from .compact import (
    CommitReceipt,
    CompactRequest,
    commit as _commit,
    prepare_compact as _prepare_compact,
)
from .events import (
    Annotated,
    Appended,
    Called,
    Checkpoint,
    Checkpointed,
    Closed,
    Compacted,
    Configured,
    Event,
    Forked,
    Kept,
    Merged,
    Opened,
    Pruned,
    Removed,
    Reparented,
    Replaced,
    Restored,
    Resumed,
    Returned,
    Revoked,
    Tombstone,
    seal,
    state_hash,
)
from .hashes import (
    BytesHash,
    CallHash,
    ChainHash,
    ManifestHash,
    TreeHash,
    canon_json,
)
from .ids import BlockId, LedgerId, Seq, UlidFactory, default_ulid_factory, new_ledger_id
from .manifest import Manifest
from .origin import (
    ExternalAddress,
    LlmDerived,
    Origin,
    Parsed,
    Recalled,
    ToolReturned,
    origin_sources,
)
from .payload import Blob, ContentRef, ContentStore, MemoryContentStore
from .persist import (
    FORMAT_VERSION,
    JsonlWriter,
    LedgerHeader,
    LoadError,
    LoadReport,
    load,
)
from .render import RenderSpec, Rendering
from .view import View

__all__ = [
    "LedgerError",
    "StillOpen",
    "BlockNotFound",
    "DuplicateBlockId",
    "OpenCompositeAtBoundary",
    "OpenComposite",
    "Retention",
    "PruneReport",
    "Retrieval",
    "Ledger",
]


# --------------------------------------------------------------------------- 异常


class LedgerError(Exception):
    """账本层的错误基类。**只在"这件事做不了"时抛**;一致性问题一律走 ``check``。"""


class StillOpen(LedgerError):
    """``get_block`` 撞上开态复合(v2.6:窄化访问器不返回半成品)。"""


class BlockNotFound(LedgerError, KeyError):
    """此刻的账本上没有这个 id。同时是 ``KeyError``,便于 ``dict`` 式的调用者接住。"""


class DuplicateBlockId(LedgerError):
    """这个 id 已经在账本上了。写两次同一个 id 会让"块 → seq"不再是函数。"""


class OpenCompositeAtBoundary(LedgerError):
    """要求闭合边界的操作(fork)撞上了未闭合的复合(见过的真实 harness 也是这么拒的)。"""


# --------------------------------------------------------------------------- 策略与返回型


@dataclass(frozen=True)
class Retention:
    """``prune`` 的策略(v2.6 ``Retention`` 沿用已定,V0 取最简两维)。

    * ``kinds``:块的 ``kind`` 落在这个集合里;
    * ``before_seq``:块的 ``Appended`` / ``Opened`` seq **小于**它。

    **两维是 AND**(都给就取交集,更保守);**一维都不给则一个都不剪**——空策略剪空,
    不是"剪全部"(A0:默认值可以有,默认动作不能有)。
    """

    kinds: frozenset[str] = frozenset()
    before_seq: Seq | None = None
    disposition: Literal["deleted", "archived"] = "deleted"
    name: str = "v0-retention"

    def __post_init__(self) -> None:
        object.__setattr__(self, "kinds", frozenset(self.kinds))

    @property
    def selective(self) -> bool:
        return bool(self.kinds) or self.before_seq is not None


@dataclass(frozen=True)
class PruneReport:
    """``prune`` 的回执:剪了谁、留了什么痕。"""

    pruned: tuple[BlockId, ...] = ()
    tombstones: tuple[Tombstone, ...] = ()
    events: tuple[Pruned, ...] = ()

    def __post_init__(self) -> None:
        for name in ("pruned", "tombstones", "events"):
            object.__setattr__(self, name, freeze_tuple(getattr(self, name)))

    def __len__(self) -> int:
        return len(self.pruned)


@dataclass(frozen=True)
class Retrieval:
    """``retrieve`` 的返回(v2.6 D10:三类复现在返回类型上可见)。

    V0 补**第四格** ``unknown``:"这个 id 我从没听说过"与"它丢了"是两件事,
    挤进 ``lost`` 就要伪造一个 ``Tombstone``(A9 反过来也管:不造信息)。

    一个块可以**同时**在 ``present`` 与 ``external``:手上这段字节在账上,截断掉的
    那部分要拿地址去世界里重读(A8:库不去读,harness 去读)。同一个块也可以在
    ``external`` 里占**多条**——``Remainder.address`` 与 ``ToolReturned.touched``
    的每个地址各占一条(H2:"碰了世界的哪里"含读全者)。
    C-22(2026-09-06 签):``Blob.data`` 是外部地址(C-6,字节只存外部)的块,那个地址
    也列进 ``external``——它不是出身的把手,是**载荷本身**的所在,排在出身地址之前。
    """

    present: tuple[Block, ...] = ()
    lost: tuple[Tombstone, ...] = ()
    external: tuple[tuple[BlockId, ExternalAddress], ...] = ()
    unknown: tuple[BlockId, ...] = ()

    def __post_init__(self) -> None:
        for name in ("present", "lost", "external", "unknown"):
            object.__setattr__(self, name, freeze_tuple(getattr(self, name)))


# --------------------------------------------------------------------------- 折叠状态


@dataclass
class _OpenState:
    """开态复合在折叠状态里的样子。它**没有 Block 值**(v2.5:半成品永不渗入下游)。"""

    id: BlockId
    kind: str
    title: str | None
    origin: Origin
    into: BlockId | None
    gap: int
    refs: tuple[Ref, ...]
    annotations: Mapping[str, str]
    opened_seq: Seq


@dataclass
class _State:
    """一条时间线在某一刻的折叠结果。私有;外面看到的是 Ledger 的各个访问器。"""

    blocks: dict[BlockId, Block] = field(default_factory=dict)
    tree_hashes: dict[BlockId, TreeHash] = field(default_factory=dict)
    links: dict[BlockId, list[ChildLink]] = field(default_factory=dict)
    storage_parent: dict[BlockId, BlockId | None] = field(default_factory=dict)
    logical_parent: dict[BlockId, BlockId] = field(default_factory=dict)
    top: list[BlockId] = field(default_factory=list)
    open: dict[BlockId, _OpenState] = field(default_factory=dict)
    tombstones: dict[BlockId, Tombstone] = field(default_factory=dict)
    superseded: dict[BlockId, BlockId] = field(default_factory=dict)
    supersedes: dict[BlockId, list[BlockId]] = field(default_factory=dict)
    """新 → 旧的反向索引(C-15),覆盖 ``Replaced`` 与 ``Merged``。"""
    killed: dict[BlockId, tuple[Block | None, int | None, Seq]] = field(default_factory=dict)
    """墓碑块的取回位:``(块值, 顶层索引或 None, 那条 Removed/Pruned 的 seq)``(C-14)。"""
    settings: dict[str, str] = field(default_factory=dict)
    revoked: set[Seq] = field(default_factory=set)
    compactions: list[Compacted] = field(default_factory=list)
    calls: list[Called] = field(default_factory=list)
    returns: list[Returned] = field(default_factory=list)
    outcomes: dict[BlockId, str] = field(default_factory=dict)
    seq_of: dict[BlockId, Seq] = field(default_factory=dict)
    seqs: set[Seq] = field(default_factory=set)
    last_seq: Seq | None = None


def _attach(state: _State, child: BlockId, into: BlockId | None, gap: int) -> None:
    state.storage_parent[child] = into
    if into is None:
        state.top.append(child)
    else:
        state.links.setdefault(into, []).append(ChildLink(child=child, gap=gap))


def _claim(state: _State, child: BlockId, parent: BlockId) -> None:
    """整值 append 进来的复合,把它 ``children`` 里还没有父的子块认领走。"""
    if state.storage_parent.get(child) is None:
        state.storage_parent[child] = parent
        if child in state.top:
            state.top.remove(child)


def _materialize(state: _State, open_state: _OpenState, tail_gap: int) -> Block:
    """开态 + tail_gap → 闭合 Block。``Closed`` 的折叠与 ``close()`` 的预演共用它。"""
    return Block(
        id=open_state.id,
        kind=open_state.kind,
        title=open_state.title,
        payload=None,
        children=tuple(state.links.get(open_state.id, ())),
        tail_gap=tail_gap,
        origin=open_state.origin,
        refs=open_state.refs,
        cited_refs=(),
        annotations=open_state.annotations,
    )


def _register(state: _State, block: Block, tree_hash: TreeHash, seq: Seq) -> None:
    state.blocks[block.id] = block
    state.tree_hashes[block.id] = tree_hash
    state.links[block.id] = list(block.children)
    state.seq_of[block.id] = seq
    for link in block.children:
        _claim(state, link.child, block.id)


def _kill(state: _State, block: BlockId, tombstone: Tombstone, seq: Seq) -> None:
    """块从视图消失。位置与块值记在 ``killed`` 里,``Restored`` 据此把它放回原处(C-14)。

    子块在父的边表里的链接**不摘**——那条链接此刻悬空是事实,``check`` 报 ``dangling_child``
    (D-X10-2 时间相对);顶层块从 ``top`` 摘掉并记下索引。

    **落地形状与改库单字面不同(反驳补记)**:单子写的是记 ``(parent, index, gap)``,
    这里记的是 ``killed[block] = (块值, 顶层索引或 None, 那条 Removed/Pruned 的 seq)``。
    父与 gap 不必另记——子块在父边表里的链接从不摘,``Restored`` 时块值回到 ``blocks``
    就自然回到原父原位;只有顶层块需要索引(``storage_parent`` 仍在)。语义等价:
    Restored 回原索引 / 子块回父 / 无位置块(被 Replaced / Merged 顶掉后才 Removed 的旧块,
    ``top_index=None``)不凭空发位置 / prune 后 restore / revoke 不恢复,五条都在
    ``tests/test_v018.py`` 的 C-14 组里断言。
    """
    top_index = state.top.index(block) if block in state.top else None
    state.killed[block] = (state.blocks.get(block), top_index, seq)
    state.tombstones[block] = tombstone
    state.blocks.pop(block, None)
    if top_index is not None:
        state.top.remove(block)


def _take_position(state: _State, old: BlockId, new: BlockId) -> None:
    """``new`` 占 ``old`` 的位置(``Replaced`` / ``Merged`` 共用)。"""
    parent = state.storage_parent.get(old)
    state.storage_parent[new] = parent
    if parent is None:
        if old in state.top:
            state.top[state.top.index(old)] = new
        elif new not in state.top:
            state.top.append(new)
    else:
        links = state.links.setdefault(parent, [])
        for index, link in enumerate(links):
            if link.child == old:
                links[index] = ChildLink(child=new, gap=link.gap)
                break
        else:
            links.append(ChildLink(child=new, gap=0))


def _drop_position(state: _State, block: BlockId) -> None:
    """把一个块从位置层摘掉(``Merged`` 的 ``olds[1:]``):块值仍在账上,不落墓碑。"""
    if block in state.top:
        state.top.remove(block)
    parent = state.storage_parent.get(block)
    if parent is not None:
        links = state.links.get(parent)
        if links:
            links[:] = [link for link in links if link.child != block]


def _apply(state: _State, event: Event) -> None:
    """把一条事件折进状态。**这是账本语义的唯一定义处**。"""
    state.last_seq = event.seq
    state.seqs.add(event.seq)

    if isinstance(event, Opened):
        state.open[event.composite] = _OpenState(
            id=event.composite,
            kind=event.kind,
            title=event.title,
            origin=event.origin,
            into=event.into,
            gap=event.gap,
            refs=event.refs,
            annotations=event.block_annotations,
            opened_seq=event.seq,
        )
        state.seq_of[event.composite] = event.seq
        _attach(state, event.composite, event.into, event.gap)

    elif isinstance(event, Appended):
        if event.block_value is not None:
            _register(state, event.block_value, event.tree_hash, event.seq)
        else:
            state.tree_hashes[event.block] = event.tree_hash
            state.seq_of[event.block] = event.seq
        _attach(state, event.block, event.into, event.gap)

    elif isinstance(event, Closed):
        open_state = state.open.pop(event.composite, None)
        if open_state is not None:
            block = _materialize(state, open_state, event.tail_gap)
            state.blocks[block.id] = block
            state.tree_hashes[block.id] = event.merkle
        state.outcomes[event.composite] = event.outcome

    elif isinstance(event, Compacted):
        state.compactions.append(event)

    elif isinstance(event, Revoked):
        state.revoked.add(event.target_seq)

    elif isinstance(event, Reparented):
        state.logical_parent[event.block] = event.logical_parent

    elif isinstance(event, Removed):
        _kill(state, event.block, event.tombstone, event.seq)

    elif isinstance(event, Pruned):
        _kill(state, event.block, event.tombstone, event.seq)

    elif isinstance(event, Restored):
        # C-14:块回来——回原存储父、原索引(超界落尾),墓碑清除。
        # 原位置是"无"(被 Replaced / Merged 顶掉后才 Removed 的旧块,``_kill`` 记 ``top_index=None``)
        # 就仍是"无":不凭空发顶层位置。
        entry = state.killed.pop(event.block, None)
        state.tombstones.pop(event.block, None)
        if entry is not None:
            value, top_index, _seq = entry
            if value is not None:
                state.blocks[event.block] = value
            if (
                top_index is not None
                and state.storage_parent.get(event.block) is None
                and event.block not in state.top
            ):
                state.top.insert(min(top_index, len(state.top)), event.block)

    elif isinstance(event, Replaced):
        if event.block_value is not None and event.tree_hash is not None:
            _register(state, event.block_value, event.tree_hash, event.seq)
        elif event.tree_hash is not None:
            state.tree_hashes[event.new] = event.tree_hash
            state.seq_of[event.new] = event.seq
        _take_position(state, event.old, event.new)
        state.superseded[event.old] = event.new
        state.supersedes.setdefault(event.new, []).append(event.old)

    elif isinstance(event, Merged):
        # C-13:新块占 olds[0] 的位置,其余 olds 从位置层摘掉;块值都还在,不落墓碑。
        if event.block_value is not None and event.tree_hash is not None:
            _register(state, event.block_value, event.tree_hash, event.seq)
        elif event.tree_hash is not None:
            state.tree_hashes[event.new] = event.tree_hash
            state.seq_of[event.new] = event.seq
        if event.olds:
            _take_position(state, event.olds[0], event.new)
            for old in event.olds[1:]:
                _drop_position(state, old)
        elif event.new not in state.top:
            state.storage_parent.setdefault(event.new, None)
            state.top.append(event.new)
        for old in event.olds:
            state.superseded[old] = event.new
        state.supersedes.setdefault(event.new, []).extend(event.olds)

    elif isinstance(event, Annotated):
        block = state.blocks.get(event.block)
        if block is not None:
            # annotations 不入 TreeHash,所以这里**只换块值、不碰 tree_hashes**:
            # 同一个 id、同一个 TreeHash、新的注记(A0 的 U 动词)。
            state.blocks[event.block] = dc_replace(
                block, annotations=event.applied_to(block.annotations)
            )
        else:
            open_state = state.open.get(event.block)
            if open_state is not None:
                open_state.annotations = event.applied_to(open_state.annotations)

    elif isinstance(event, Configured):
        state.settings[event.name] = event.value

    elif isinstance(event, Called):
        state.calls.append(event)

    elif isinstance(event, Returned):
        state.returns.append(event)

    # Checkpointed / Forked / Resumed:纯记录,不改折叠状态


# --------------------------------------------------------------------------- 开复合句柄


class OpenComposite:
    """开着的复合(v2.5 句柄形)。**没有 Block 值**——它是账本上 ``Opened + Appended(into=)``
    的折叠视图,半成品永不渗入下游类型系统。

    句柄是**账本状态的窗口**,不是快照:``so_far()`` 每次都重新折叠。崩溃恢复时
    ``ledger.open_composites()`` 重新造出等价的句柄,``close(outcome="interrupted")`` 收尾。
    """

    __slots__ = ("_ledger", "_opened")

    def __init__(self, ledger: "Ledger", opened: Opened) -> None:
        self._ledger = ledger
        self._opened = opened

    # ---- 事实(全部定于 open)

    @property
    def id(self) -> BlockId:
        return self._opened.composite

    @property
    def kind(self) -> str:
        return self._opened.kind

    @property
    def title(self) -> str | None:
        return self._opened.title

    @property
    def origin(self) -> Origin:
        return self._opened.origin

    @property
    def into(self) -> BlockId | None:
        return self._opened.into

    @property
    def gap(self) -> int:
        return self._opened.gap

    @property
    def refs(self) -> tuple[Ref, ...]:
        return self._opened.refs

    @property
    def annotations(self) -> Mapping[str, str]:
        """此刻的注记:``Opened.block_annotations`` 再叠上后来的 ``Annotated``。

        句柄是**账本状态的窗口**而不是快照,所以这里给折叠值;复合已经闭合(窗口关了)
        就退回开启事件上那一份。
        """
        open_state = self._ledger._state().open.get(self.id)
        if open_state is not None:
            return open_state.annotations
        return self._opened.block_annotations

    @property
    def opened_seq(self) -> Seq:
        return self._opened.seq

    @property
    def opened(self) -> Opened:
        """开启事件本身(A0:句柄不藏证据)。"""
        return self._opened

    @property
    def ledger(self) -> "Ledger":
        return self._ledger

    def is_open(self) -> bool:
        return self.id in self._ledger._state().open

    # ---- 操作

    def append(self, child: Block, *, gap: int = 0, **event_fields: Any) -> Appended:
        """往复合里追加一个**闭合**子块。"""
        return self._ledger.append(child, into=self.id, gap=gap, **event_fields)

    def open_child(self, **kwargs: Any) -> "OpenComposite":
        """在这个复合里再开一个复合(嵌套开态是合法的)。"""
        kwargs.setdefault("into", self.id)
        return self._ledger.open_composite(**kwargs)

    def so_far(self) -> tuple[Block | OpenComposite, ...]:
        """**纯查询,零事件**:此刻已经进来的子块。

        V0-CHOICE:v2.5 写的是 ``tuple[Block, ...]``,但嵌套的子复合若还开着就没有
        Block 值。丢掉它等于丢信息(A9),所以返回型放宽到 ``Block | OpenComposite``。
        """
        ledger = self._ledger
        state = ledger._state()
        out: list[Block | OpenComposite] = []
        for link in state.links.get(self.id, ()):
            item = ledger.find(link.child)
            if item is not None:
                out.append(item)
        return tuple(out)

    def close(
        self,
        *,
        outcome: Literal["complete", "interrupted", "error"] = "complete",
        tail_gap: int = 0,
        reason: Mapping[str, str] | None = None,
        **event_fields: Any,
    ) -> Block:
        """闭合。开→闭 = 构造的完成,不违 A6。``close`` 只收 ``outcome`` / ``tail_gap`` /
        ``reason``——kind/origin/title/into 定于 open,链上不可能出现双 kind。

        C-9(2026-09-06 签):``outcome`` 增 ``"error"``;``reason`` 是结构化载荷
        (开域键,如 ``{"kind": "aborted", "cause": "user"}``),入链不下钻。
        """
        ledger = self._ledger
        state = ledger._state()
        open_state = state.open.get(self.id)
        if open_state is None:
            raise LedgerError(f"composite {self.id} is not open (already closed?)")
        prospective = _materialize(state, open_state, tail_gap)
        merkle = ledger._tree_hash_of_value(prospective, state)
        ledger.emit(
            Closed,
            composite=self.id,
            merkle=merkle,
            outcome=outcome,
            tail_gap=tail_gap,
            reason=reason,
            **event_fields,
        )
        return ledger.get_block(self.id)

    def __repr__(self) -> str:
        return f"OpenComposite(id={self.id!r}, kind={self.kind!r}, open={self.is_open()})"

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, OpenComposite)
            and other._ledger is self._ledger
            and other.id == self.id
        )

    def __hash__(self) -> int:
        return hash((id(self._ledger), self.id))


# --------------------------------------------------------------------------- 账本


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _origin_summary(origin: Origin) -> str:
    """墓碑上留的一句机械摘要:``"变体名/到达通道"``。不参与任何身份。"""
    return f"{type(origin.made).__name__}/{origin.arrived.name}"


def _external_addresses(block: Block) -> tuple[ExternalAddress, ...]:
    """``retrieve`` 列进 ``Retrieval.external`` 的地址,按块给,去重保次序。

    三处来源(D10:三类复现在返回类型上可见——只给一处,调用者就得绕回
    ``block.origin.made`` 自己拆):

    1. **载荷本身**(C-22,2026-09-06 签):``Blob.data`` 是外部地址 ⇒ 字节只存外部,
       那个地址就是这块字节的所在,排在最前;
    2. ``ToolReturned.remainder.address``(截断掉的那段去哪儿重读)与 ``touched``
       (这次工具碰了世界的哪里,H2 含读全者)——remainder 在前;
    3. ``Parsed`` / ``Recalled`` / ``LlmDerived`` 的 ``remainder.address``
       (C-2;``LlmDerived`` 由 C-35 于 2026-09-15 并入——同一个槽,同一个读法)。
    """
    addresses: list[ExternalAddress] = []

    def add(address: ExternalAddress | None) -> None:
        if address is not None and address not in addresses:
            addresses.append(address)

    payload = block.payload
    if isinstance(payload, Blob) and not isinstance(payload.data, ContentRef):
        add(payload.data)
    made = block.origin.made
    if isinstance(made, ToolReturned):
        if made.remainder is not None:
            add(made.remainder.address)
        for address in made.touched:
            add(address)
    elif isinstance(made, (Parsed, Recalled, LlmDerived)):
        if made.remainder is not None:
            add(made.remainder.address)
    return tuple(addresses)


class Ledger:
    """append-only 事件账本。dict 级完备容器(A0)+ 两模式同 API(A3)。"""

    __slots__ = (
        "_header",
        "_path",
        "_writer",
        "_store",
        "_clock",
        "_ulids",
        "_events",
        "_by_seq",
        "_next_seq",
        "_tip",
        "_cache",
        "_load_report",
    )

    # ----------------------------------------------------------------- 构造

    def __init__(
        self,
        *,
        header: LedgerHeader,
        path: str | os.PathLike[str] | None = None,
        events: Iterable[Event] = (),
        store: ContentStore | None = None,
        clock: Callable[[], datetime] | None = None,
        ulids: UlidFactory | None = None,
        writer: JsonlWriter | None = None,
        load_report: LoadReport | None = None,
    ) -> None:
        self._header = header
        self._path = Path(path) if path is not None else None
        self._writer = writer
        self._store: ContentStore = store if store is not None else MemoryContentStore()
        self._clock: Callable[[], datetime] = clock if clock is not None else _utc_now
        self._ulids: UlidFactory = ulids if ulids is not None else default_ulid_factory
        self._events: list[Event] = []
        self._by_seq: dict[Seq, Event] = {}
        self._next_seq: int = 0
        self._tip: Seq | None = None
        self._cache: dict[tuple[Seq | None, Seq | None], _State] = {}
        self._load_report = load_report
        for event in events:
            self._index(event)

    @classmethod
    def create(
        cls,
        path: str | os.PathLike[str] | None = None,
        *,
        header: LedgerHeader,
        store: ContentStore | None = None,
        clock: Callable[[], datetime] | None = None,
        ulids: UlidFactory | None = None,
        fsync: bool = True,
    ) -> "Ledger":
        """开新账本。``path=None`` ⇒ dev 零流水(内存);给了路径 ⇒ track(JSONL)。

        目标文件已存在且非空时抛 ``FileExistsError``——覆盖别人的账本永远不该是默认动作。
        """
        writer: JsonlWriter | None = None
        if path is not None:
            target = Path(path)
            if target.exists() and target.stat().st_size > 0:
                raise FileExistsError(f"ledger already exists: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            writer = JsonlWriter(target, fsync=fsync)
            writer.write_header(header)
        return cls(
            header=header, path=path, store=store, clock=clock, ulids=ulids, writer=writer
        )

    @classmethod
    def open(
        cls,
        path: str | os.PathLike[str],
        *,
        store: ContentStore | None = None,
        clock: Callable[[], datetime] | None = None,
        ulids: UlidFactory | None = None,
        strict: bool = True,
        fsync: bool = True,
        append: bool = True,
        truncate_torn_tail: bool = True,
    ) -> "Ledger":
        """重载一本 track 账本。

        ``strict=True``(默认)时,致命的 :class:`~espalier.LoadReport` 抛
        :class:`~espalier.LoadError`;``strict=False`` 则带着报告继续
        (``ledger.load_report``)——P-09:"拒绝 / 跳过 / 升级"是 harness 的决定,
        库只给字段与报告。

        **torn tail 与续写**(V0-CHOICE):崩溃可能在文件尾留下半截行。``load()`` 已经
        把它丢弃(``LoadReport.torn_tail``),但**文件里它还在**;若就这么以 ``"a"`` 模式
        续写,新行会粘在半截行后面,于是那条新行永远解析不回来——账本静默丢数据,再写
        一条更让粘连行变成中间的致命 ``bad_event_line``,账本彻底打不开。所以
        ``append=True`` 时本方法在开写之前按 ``LoadReport.good_bytes`` 把文件**截齐**。

        这不违 v2.5 的"resume 后补 close——不改写任何既有行":半截行不是"既有行",
        它是一次**没有返回**的写(``append`` 一律 flush+fsync,已返回的写一定完整在盘上)。
        要保住那几个字节做取证就传 ``truncate_torn_tail=False``——那时库**拒绝**给出一个
        可写的账本(``append=True`` 下抛 :class:`LedgerError`),处置权交回 harness;
        ``append=False`` 只读打开则从来不碰文件。
        """
        report = load(path)
        if strict and not report.ok:
            raise LoadError(report)
        if report.header is None:  # pragma: no cover - ok 为假时必已抛
            raise LoadError(report)
        if append and report.torn_tail is not None:
            if not truncate_torn_tail or report.good_bytes is None:
                raise LedgerError(
                    f"ledger {path} ends in a torn line ({len(report.torn_tail)} chars); "
                    "appending after it would silently lose the next write. "
                    "用 truncate_torn_tail=True 截齐,或 append=False 只读打开"
                )
            os.truncate(path, report.good_bytes)
        writer = JsonlWriter(path, fsync=fsync) if append else None
        return cls(
            header=report.header,
            path=path,
            events=report.events,
            store=store,
            clock=clock,
            ulids=ulids,
            writer=writer,
            load_report=report,
        )

    def close(self) -> None:
        """关掉底层文件句柄。dev 模式是空操作。"""
        if self._writer is not None:
            self._writer.close()
            self._writer = None

    def __enter__(self) -> "Ledger":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __repr__(self) -> str:
        mode = "track" if self._path is not None else "dev"
        return f"Ledger(id={self._header.id!r}, mode={mode}, events={len(self._events)})"

    # ----------------------------------------------------------------- 壳

    @property
    def header(self) -> LedgerHeader:
        return self._header

    @property
    def id(self) -> LedgerId:
        return self._header.id

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def tracked(self) -> bool:
        """``True`` = track(有流水);``False`` = dev(零流水)。A3 的那条定义差。"""
        return self._path is not None

    @property
    def store(self) -> ContentStore:
        return self._store

    @property
    def ulids(self) -> UlidFactory:
        """本账本发 id 用的工厂。库自己造块时(``commit`` 的摘要)走它,于是注入一个确定性
        工厂就能让整条流水线确定(A0:观察面 + 可注入)。"""
        return self._ulids

    @property
    def load_report(self) -> LoadReport | None:
        """``open()`` 那次的诊断;``create()`` 出来的账本是 ``None``。"""
        return self._load_report

    # ----------------------------------------------------------------- 写入原语

    def _index(self, event: Event) -> None:
        if event.seq in self._by_seq:
            raise LedgerError(f"duplicate event seq {event.seq}")
        self._events.append(event)
        self._by_seq[event.seq] = event
        self._next_seq = max(self._next_seq, int(event.seq) + 1)
        self._tip = event.seq
        self._cache.clear()

    def emit(
        self, event_cls: type[Event], *, written_at: datetime | None = None, **fields: Any
    ) -> Event:
        """**唯一的写原语**:分配 ``seq`` / ``prev`` / ``written_at`` / ``link``,落盘,返回事件。

        所有带类型的写方法都从这里走。它是公开的:v2 章之后要加的事件类型
        (``Called`` 的更高层封装、渲染侧的新事件)不必等库改签名(A0)。

        ``written_at`` 可显式给:导入既有转录、fork 深拷贝时,原记录的机械时间是事实
        (P-10),不该被"写进来的那一刻"顶掉。不给就取账本的时钟。
        """
        prev = self._tip
        prev_link = self._by_seq[prev].link if prev is not None else None
        event = event_cls(
            seq=Seq(self._next_seq),
            prev=prev,
            written_at=written_at if written_at is not None else self._clock(),
            link=ChainHash(""),
            **fields,
        )
        event = seal(event, prev_link)
        self._index(event)
        if self._writer is not None:
            self._writer.append_event(event)
        return event

    @property
    def next_seq(self) -> Seq:
        """下一条事件会拿到的 ``seq``。批量写时要**先知道** seq 才填得了
        ``Returned.called_seq`` 这样的自指字段(A0 观察面)。"""
        return Seq(self._next_seq)

    def emit_all(
        self,
        specs: Sequence[tuple[type[Event], Mapping[str, Any]]],
        *,
        written_at: datetime | None = None,
    ) -> tuple[Event, ...]:
        """**一批事件一次落盘**:先在内存里全部构造并封链,再一次写、一次 fsync。

        V0-CHOICE(v2.7 的 "原子落 Appended + Compacted" 要一个批量原语,而 v2.6 只给了
        逐条的 ``emit``):任一条构造不出来 ⇒ **一条都不写**,账本上不留半截。它挡的是
        校验类失败;写到一半断电的残留窗口见 :mod:`espalier.compact`。
        """
        prev = self._tip
        prev_link = self._by_seq[prev].link if prev is not None else None
        seq = self._next_seq
        built: list[Event] = []
        for event_cls, fields in specs:
            event = event_cls(
                seq=Seq(seq),
                prev=prev,
                written_at=written_at if written_at is not None else self._clock(),
                link=ChainHash(""),
                **dict(fields),
            )
            event = seal(event, prev_link)
            built.append(event)
            prev = event.seq
            prev_link = event.link
            seq += 1
        for event in built:
            self._index(event)
        if self._writer is not None:
            self._writer.append_events(built)
        return tuple(built)

    def replay(self, event: Event) -> Event:
        """把一条**既有事件原样**写进本账本:``seq`` / ``prev`` / ``written_at`` /
        ``annotations`` 全部保留,只重算 ``link``。

        这是导入面的原语(fork 深拷贝、摄入别人的转录时保住机械时间与位置)。它很利:
        ``seq`` 由调用者定,所以重复 seq 与悬空 ``prev`` 都会当场拒绝。

        链会重算:同样的前缀 + 同样的瘦记录 ⇒ 同样的 ``link``,所以原样拷贝出来的前缀
        与源账本**逐条同链**;源账本的链要是错的,这里给出的是对的。
        """
        if event.seq in self._by_seq:
            raise LedgerError(f"cannot replay: seq {event.seq} is already on this ledger")
        if event.prev is not None and event.prev not in self._by_seq:
            raise LedgerError(f"cannot replay: prev {event.prev} is not on this ledger yet")
        prev_link = self._by_seq[event.prev].link if event.prev is not None else None
        sealed = seal(event, prev_link)
        self._index(sealed)
        if self._writer is not None:
            self._writer.append_event(sealed)
        return sealed

    def branch_at(self, seq: Seq | None) -> Seq | None:
        """把**写游标**挪到 ``seq``:下一条事件的 ``prev`` 就是它,于是日志分叉(D5)。

        V0-CHOICE:v2.6 写了"``prev`` 可指非尖端 ⇒ 日志成树",却没给动它的 API。
        这个方法就是那个 API;返回挪动前的游标,方便挪回去。``None`` = 回到无父(新根)。
        """
        previous = self._tip
        if seq is not None and seq not in self._by_seq:
            raise LedgerError(f"cannot branch at unknown seq {seq}")
        self._tip = seq
        self._cache.clear()  # 折叠缓存里 leaf=None 那些键跟着游标走,必须一起作废
        return previous

    # ----------------------------------------------------------------- 折叠

    def _chain(self, leaf: Seq | None) -> tuple[Event, ...]:
        """从根到 ``leaf`` 的那条事件链(升序)。``leaf=None`` ⇒ 当前写游标那条。

        **断链停在断点,不抛**:``prev`` 指向的事件可能根本不在场——``ignorable=True``
        的未知事件被 ``load`` 跳过(§3.2 明写这是**可安全跳过**的),或者外来记录本身残缺。
        那时这条链只到断点为止,后面的前缀取不到,如实少一段;断点本身留痕在
        :meth:`broken_links`,由 ``check`` 报出来(``broken_prev_chain``)。
        原先在这里裸下标,于是"跳过一条读不懂的事件"会让此后每一个折叠查询炸成
        ``KeyError`` —— ``ignorable`` 这条 delta 的全部意义正是"读不懂也能接着用"。
        """
        cursor = leaf if leaf is not None else self._tip
        if cursor is None:
            return ()
        if cursor not in self._by_seq:
            raise LedgerError(f"unknown leaf seq {cursor}")
        path: list[Event] = []
        seen: set[Seq] = set()
        while cursor is not None:
            if cursor in seen:  # pragma: no cover - prev 成环只可能来自伪造记录
                raise LedgerError(f"prev cycle at seq {cursor}")
            seen.add(cursor)
            event = self._by_seq.get(cursor)
            if event is None:  # 断链:前缀到此为止
                break
            path.append(event)
            cursor = event.prev
        path.reverse()
        return tuple(path)

    def broken_links(self) -> tuple[tuple[Seq, Seq], ...]:
        """``prev`` 指向不在场事件的每一处断链:``((事件 seq, 取不到的 prev), …)``,按 seq 升序。

        典型来源是被 ``load`` 跳过的 ``ignorable=True`` 未知事件(那条 seq 上没有事件了,
        而它后面那条还指着它)。**这是事实不是判决**:账本照常可用,只是断点之前的前缀
        在这条线上取不到。``check`` 把它报成 ``broken_prev_chain``(warning)。
        """
        return tuple(
            (event.seq, event.prev)
            for event in sorted(self._events, key=lambda e: int(e.seq))
            if event.prev is not None and event.prev not in self._by_seq
        )

    def _state(self, *, at_seq: Seq | None = None, leaf: Seq | None = None) -> _State:
        key = (leaf, at_seq)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        state = _State()
        for event in self._chain(leaf):
            if at_seq is not None and event.seq > at_seq:
                break
            _apply(state, event)
        self._cache[key] = state
        return state

    def _resolve(self, state: _State) -> Callable[[BlockId], TreeHash]:
        def resolve(block_id: BlockId) -> TreeHash:
            try:
                return state.tree_hashes[block_id]
            except KeyError:
                raise LedgerError(
                    f"child {block_id} has no TreeHash on this ledger; "
                    "把子块先 append 进来,或者用 open_composite 建复合"
                ) from None

        return resolve

    def _tree_hash_of_value(self, block: Block, state: _State) -> TreeHash:
        return block.tree_hash(self._resolve(state), store=self._store)

    # ----------------------------------------------------------------- 事件面查询

    def events(
        self, *, at_seq: Seq | None = None, leaf: Seq | None = None, all_branches: bool = False
    ) -> tuple[Event, ...]:
        """事件序列。默认走 ``leaf`` 那条链;``all_branches=True`` 给出文件里的全部事件。"""
        source = tuple(self._events) if all_branches else self._chain(leaf)
        if at_seq is None:
            return source
        return tuple(e for e in source if e.seq <= at_seq)

    def event_at(self, seq: Seq) -> Event:
        try:
            return self._by_seq[seq]
        except KeyError:
            raise LedgerError(f"no event at seq {seq}") from None

    def event_seqs(
        self, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> frozenset[Seq]:
        return frozenset(self._state(at_seq=at_seq, leaf=leaf).seqs)

    def effective_at_seq(
        self, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> Seq | None:
        """这次折叠实际停在哪一条事件上。``check`` 的报告带的就是它(D-X10-2)。"""
        return self._state(at_seq=at_seq, leaf=leaf).last_seq

    @property
    def tip(self) -> Seq | None:
        """当前写游标(下一条事件的 ``prev``)。"""
        return self._tip

    def leaves(self) -> tuple[Seq, ...]:
        """事件树的叶子:没有任何事件以它为 ``prev``(v2.6:fork/resume = 共享前缀新 leaf)。"""
        parents = {e.prev for e in self._events if e.prev is not None}
        return tuple(sorted(e.seq for e in self._events if e.seq not in parents))

    def revoked_seqs(
        self, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> frozenset[Seq]:
        return frozenset(self._state(at_seq=at_seq, leaf=leaf).revoked)

    # ----------------------------------------------------------------- 块面写入

    def append(
        self,
        block: Block,
        *,
        into: BlockId | None = None,
        gap: int = 0,
        **event_fields: Any,
    ) -> Appended:
        """把一个**闭合块**写进账本(v2.6)。``into`` 必须是**开着**的复合或 ``None``。"""
        state = self._state()
        if block.id in state.blocks or block.id in state.open or block.id in state.tombstones:
            raise DuplicateBlockId(f"block {block.id} is already on this ledger")
        if into is not None and into not in state.open:
            if into in state.blocks:
                raise LedgerError(
                    f"cannot append into {into}: it is closed (A6:闭合块不再改;"
                    "要往里加东西请在 open 期做)"
                )
            raise BlockNotFound(f"no open composite {into}")
        tree_hash = self._tree_hash_of_value(block, state)
        event = self.emit(
            Appended,
            block=block.id,
            into=into,
            gap=gap,
            tree_hash=tree_hash,
            block_value=block,
            **event_fields,
        )
        return event  # type: ignore[return-value]

    def open_composite(
        self,
        *,
        kind: str,
        origin: Origin,
        title: str | None = None,
        into: BlockId | None = None,
        gap: int = 0,
        refs: Iterable[Ref] = (),
        annotations: Mapping[str, str] | None = None,
        id: BlockId | None = None,
        **event_fields: Any,
    ) -> OpenComposite:
        """开一个复合(v2.5)。``id`` 开启即分配,**轮中即可被引用**。"""
        state = self._state()
        composite = id if id is not None else self._ulids.next_block_id()
        if composite in state.blocks or composite in state.open:
            raise DuplicateBlockId(f"block {composite} is already on this ledger")
        if into is not None and into not in state.open:
            raise LedgerError(f"cannot open inside {into}: it is not an open composite")
        event = self.emit(
            Opened,
            composite=composite,
            kind=kind,
            origin=origin,
            title=title,
            into=into,
            gap=gap,
            refs=freeze_tuple(refs),
            block_annotations=freeze_mapping(annotations),
            **event_fields,
        )
        return OpenComposite(self, event)  # type: ignore[arg-type]

    def open_composites(
        self, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> tuple[OpenComposite, ...]:
        """此刻还开着的复合(崩溃恢复的入口,v2.5)。按 ``Opened`` 的 seq 升序。"""
        state = self._state(at_seq=at_seq, leaf=leaf)
        opens = sorted(state.open.values(), key=lambda o: int(o.opened_seq))
        return tuple(
            OpenComposite(self, self._by_seq[o.opened_seq])  # type: ignore[arg-type]
            for o in opens
        )

    def configure(self, name: str, value: str, **event_fields: Any) -> Configured:
        """写一条中途可变的账本级属性(G-V0-2)。末条生效。"""
        return self.emit(Configured, name=name, value=value, **event_fields)  # type: ignore[return-value]

    def resumed(self, **event_fields: Any) -> Resumed:
        """落一条 ``Resumed``(C-8,2026-09-06 签):**显式**记下"会话从这里恢复"。

        ``tip_before`` 不给就取此刻的写游标(默认**值**,来自账本状态;``Ledger.open``
        **不**自动写这条——A0:默认动作不能有)。纯记录事件,不改折叠状态。
        """
        event_fields.setdefault("tip_before", self._tip)
        return self.emit(Resumed, **event_fields)  # type: ignore[return-value]

    def revoke(self, target_seq: Seq, **event_fields: Any) -> Revoked:
        """撤销一条记录(P-21)。只留痕、不改状态,见 :class:`~espalier.Revoked`。"""
        if target_seq not in self._by_seq:
            raise LedgerError(f"cannot revoke unknown seq {target_seq}")
        return self.emit(Revoked, target_seq=target_seq, **event_fields)  # type: ignore[return-value]

    def reparent(
        self, id: BlockId, logical_parent: BlockId, **event_fields: Any
    ) -> Reparented:
        """改**逻辑父**(v2.6)。存储父由 ``Appended`` 定死,这里碰不到它。

        成环不拦(``check`` 报 ``logical_cycle``,D-X12-5);目标不存在则拒——那不是
        一致性问题,是这次写入无从落地。
        """
        state = self._state()
        for block_id in (id, logical_parent):
            if block_id not in state.blocks and block_id not in state.open:
                raise BlockNotFound(f"no block {block_id} on this ledger")
        return self.emit(  # type: ignore[return-value]
            Reparented, block=id, logical_parent=logical_parent, **event_fields
        )

    def _tombstone_for(self, block_id: BlockId, state: _State, policy: str) -> Tombstone:
        block = state.blocks.get(block_id)
        raw: BytesHash | None = None
        if block is not None:
            try:
                raw = block.bytes_hash(store=self._store)
            except (KeyError, ValueError):  # 外置内容取不回:如实留空,不编一个
                raw = None
        return Tombstone(
            block=block_id,
            tree_hash=state.tree_hashes.get(block_id),
            bytes_hash=raw,
            origin_summary=_origin_summary(block.origin) if block is not None else "",
            policy=policy,
            written_at=self._clock(),
        )

    def remove(self, id: BlockId, *, policy: str = "remove", **event_fields: Any) -> Removed:
        """生删 plumbing(v2.6)。块从视图消失,``Tombstone`` 留在账上。

        V0-CHOICE:v2.6 的签名返回 ``None``,V0 返回事件——调用者要拿到 ``Tombstone``
        总不能再去扫一遍账本(A0 观察面)。
        """
        state = self._state()
        if id in state.open:
            raise StillOpen(f"composite {id} is still open; close it before removing")
        if id not in state.blocks:
            raise BlockNotFound(f"no live block {id} on this ledger")
        tombstone = self._tombstone_for(id, state, policy)
        return self.emit(Removed, block=id, tombstone=tombstone, **event_fields)  # type: ignore[return-value]

    def replace(self, id: BlockId, block: Block, **event_fields: Any) -> Replaced:
        """用新块顶掉旧块的位置。旧块**仍在账上可取回**(append-only)。

        V0-CHOICE:同 ``remove``,返回事件而非 ``None``。
        """
        state = self._state()
        if id not in state.blocks and id not in state.open:
            raise BlockNotFound(f"no block {id} on this ledger")
        if block.id in state.blocks or block.id in state.open:
            raise DuplicateBlockId(f"block {block.id} is already on this ledger")
        tree_hash = self._tree_hash_of_value(block, state)
        return self.emit(  # type: ignore[return-value]
            Replaced,
            old=id,
            new=block.id,
            tree_hash=tree_hash,
            block_value=block,
            **event_fields,
        )

    def merge(self, ids: Sequence[BlockId], block: Block, **event_fields: Any) -> Merged:
        """多块并作一块(C-13,2026-09-06 签)。新块占 ``ids[0]`` 的位置,其余从位置层摘掉;
        每个旧块**仍在账上可取回**、不落墓碑(同 ``Replaced`` 的 append-only 语义)。
        一对一请走 :meth:`replace`。

        已知边界(单子未写):与 :meth:`replace` 一样接受**开态复合**作旧块——新块顶掉它的
        位置,它自己仍是 ``unclosed_composite``,``check`` 照报。
        """
        olds = tuple(ids)
        if not olds:
            raise LedgerError("merge needs at least one old block")
        if len(set(olds)) != len(olds):
            raise LedgerError(f"merge ids repeat: {olds}")
        state = self._state()
        for old in olds:
            if old not in state.blocks and old not in state.open:
                raise BlockNotFound(f"no block {old} on this ledger")
        if block.id in state.blocks or block.id in state.open or block.id in olds:
            raise DuplicateBlockId(f"block {block.id} is already on this ledger")
        tree_hash = self._tree_hash_of_value(block, state)
        return self.emit(  # type: ignore[return-value]
            Merged,
            olds=olds,
            new=block.id,
            tree_hash=tree_hash,
            block_value=block,
            **event_fields,
        )

    def restore(self, id: BlockId, **event_fields: Any) -> Restored:
        """块回来(C-14,2026-09-06 签):对着那条 ``Removed`` / ``Pruned`` 写一条
        ``Restored(of_seq=…)``,折叠后块回到原存储父、原索引处,墓碑清除。
        没有墓碑的块抛 :class:`LedgerError`。``Revoked`` 语义不动(仍只留痕)。
        """
        state = self._state()
        if id not in state.tombstones:
            raise LedgerError(f"block {id} has no tombstone on this ledger; nothing to restore")
        entry = state.killed.get(id)
        if entry is None:  # pragma: no cover - 墓碑与 killed 同步写入,只可能来自伪造状态
            raise LedgerError(f"block {id} is tombstoned but its removal seq is unknown")
        return self.emit(Restored, block=id, of_seq=entry[2], **event_fields)  # type: ignore[return-value]

    def annotate(
        self,
        id: BlockId,
        annotations: Mapping[str, str],
        *,
        mode: Literal["merge", "replace"] = "merge",
        **event_fields: Any,
    ) -> Annotated:
        """改一个块的 ``annotations``:**id 不变、TreeHash 不变**,落一条 ``Annotated``。

        A0 的 U 动词(v2.6 缺):``annotations`` 是纪律③ 的"作者写但不入身份"通道,可它
        原先只在 ``Block.create`` 时写得进去——事后要补一条中文母语名就得 ``replace()``,
        而 ``replace`` 拒收同 id ⇒ 换一枚 BlockId。于是"不入身份的通道"改一次换一次身份。

        ``mode="merge"``(默认)按键合并;``mode="replace"`` 整表替换,这是**删键**唯一的
        走法。开态复合也收:注记随 ``close()`` 一起定影。
        """
        state = self._state()
        if id not in state.blocks and id not in state.open:
            raise BlockNotFound(f"no block {id} on this ledger")
        if mode not in ("merge", "replace"):
            raise ValueError(f"mode must be 'merge' or 'replace', got {mode!r}")
        return self.emit(  # type: ignore[return-value]
            Annotated,
            block=id,
            block_annotations=freeze_mapping(annotations),
            mode=mode,
            **event_fields,
        )

    def prune(self, policy: Retention, **event_fields: Any) -> PruneReport:
        """熟删 porcelain(v2.6)。按 :class:`Retention` 选块,逐块写 ``Pruned``。"""
        state = self._state()
        if not policy.selective:
            return PruneReport()
        victims: list[BlockId] = []
        for block_id in state.top + [b for b in state.blocks if b not in state.top]:
            block = state.blocks.get(block_id)
            if block is None:
                continue
            if policy.kinds and block.kind not in policy.kinds:
                continue
            if policy.before_seq is not None:
                seq = state.seq_of.get(block_id)
                if seq is None or seq >= policy.before_seq:
                    continue
            if block_id not in victims:
                victims.append(block_id)

        tombstones: list[Tombstone] = []
        events: list[Pruned] = []
        for block_id in victims:
            live = self._state()
            tombstone = self._tombstone_for(block_id, live, policy.name)
            event = self.emit(
                Pruned,
                block=block_id,
                disposition=policy.disposition,
                tombstone=tombstone,
                **event_fields,
            )
            tombstones.append(tombstone)
            events.append(event)  # type: ignore[arg-type]
        return PruneReport(
            pruned=tuple(victims), tombstones=tuple(tombstones), events=tuple(events)
        )

    # ----------------------------------------------------------------- 块面查询

    def find(
        self, id: BlockId, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> Block | OpenComposite | None:
        """取块;没有就返回 ``None``(不抛)。``get`` 是它的抛错版。"""
        state = self._state(at_seq=at_seq, leaf=leaf)
        block = state.blocks.get(id)
        if block is not None:
            return block
        open_state = state.open.get(id)
        if open_state is not None:
            return OpenComposite(self, self._by_seq[open_state.opened_seq])  # type: ignore[arg-type]
        return None

    def get(
        self, id: BlockId, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> Block | OpenComposite:
        item = self.find(id, at_seq=at_seq, leaf=leaf)
        if item is None:
            raise BlockNotFound(f"no block {id} on this ledger at this fold")
        return item

    def get_block(
        self, id: BlockId, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> Block:
        """窄化访问器;开态抛 :class:`StillOpen`(v2.6)。"""
        item = self.get(id, at_seq=at_seq, leaf=leaf)
        if isinstance(item, OpenComposite):
            raise StillOpen(f"composite {id} is still open; use get() or so_far()")
        return item

    def has(self, id: BlockId, *, at_seq: Seq | None = None, leaf: Seq | None = None) -> bool:
        return self.find(id, at_seq=at_seq, leaf=leaf) is not None

    def block_ids(
        self, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> tuple[BlockId, ...]:
        """此刻在场的**闭合**块 id(不含开态、不含墓碑)。次序按写入 seq。"""
        state = self._state(at_seq=at_seq, leaf=leaf)
        return tuple(
            sorted(state.blocks, key=lambda b: int(state.seq_of.get(b, Seq(0))))
        )

    def top_level(
        self, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> tuple[BlockId, ...]:
        """账本顶层次序:``into=None`` 写进来、又没被别的块认领作子块的那些。"""
        return tuple(self._state(at_seq=at_seq, leaf=leaf).top)

    def children(
        self, id: BlockId, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> tuple[ChildLink, ...]:
        """**存储**子链接(v2.6)。

        V0-CHOICE:取值来自账本的边表而非 ``get(id).children`` 那个不可变值——
        ``replace`` 之后边表指新块,而块值作为证据保持原样(A6)。两处会不一致,
        这是刻意的:一个是"账本现在怎么长",一个是"当时写下的是什么"。
        """
        state = self._state(at_seq=at_seq, leaf=leaf)
        return tuple(state.links.get(id, ()))

    def parent(
        self, id: BlockId, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> BlockId | None:
        """**存储父**(由 ``Appended.into`` / ``Opened.into`` / 整值 append 的认领定)。"""
        return self._state(at_seq=at_seq, leaf=leaf).storage_parent.get(id)

    def logical_parent(
        self, id: BlockId, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> BlockId | None:
        """**逻辑父**(由 ``Reparented`` 定)。与存储父两轴永不混写(v2.6)。"""
        return self._state(at_seq=at_seq, leaf=leaf).logical_parent.get(id)

    def logical_parents(
        self, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> Mapping[BlockId, BlockId]:
        return dict(self._state(at_seq=at_seq, leaf=leaf).logical_parent)

    def outcome_of(
        self, id: BlockId, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> str | None:
        """复合闭合时的 ``outcome``(``"complete"`` / ``"interrupted"`` / ``"error"``,C-9);
        没闭合过 ⇒ ``None``。"""
        return self._state(at_seq=at_seq, leaf=leaf).outcomes.get(id)

    def tombstone_of(
        self, id: BlockId, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> Tombstone | None:
        return self._state(at_seq=at_seq, leaf=leaf).tombstones.get(id)

    def superseded_by(
        self, id: BlockId, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> BlockId | None:
        """``Replaced`` / ``Merged`` 的一跳(v2.6 + C-13)。要走到底自己循环——链长是调用者
        的问题,不是库的。"""
        return self._state(at_seq=at_seq, leaf=leaf).superseded.get(id)

    def supersedes(
        self, new: BlockId, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> tuple[BlockId, ...]:
        """**新 → 旧**的反向索引(C-15,2026-09-06 签):这块顶掉了谁,覆盖 ``Replaced``
        与 ``Merged``;没顶过谁 ⇒ ``()``。``lineage_of`` 不动——替换不是血缘。"""
        return tuple(self._state(at_seq=at_seq, leaf=leaf).supersedes.get(new, ()))

    def tree_hash_of(
        self, id: BlockId, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> TreeHash:
        """账本记下的 TreeHash(``Appended.tree_hash`` / ``Closed.merkle``,永不补写)。"""
        state = self._state(at_seq=at_seq, leaf=leaf)
        try:
            return state.tree_hashes[id]
        except KeyError:
            raise BlockNotFound(f"no TreeHash for {id} on this ledger") from None

    # ----------------------------------------------------------------- 反向索引(D-CAP-4)

    def seq_of(
        self, block: BlockId, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> Seq:
        """块 → 它进账本那条事件的 seq(``Appended`` 或 ``Opened``)。

        V0-CHOICE:复合用 ``Opened`` 的 seq——那才是它在账本上的位置(id 开启即分配、
        轮中即可被引用),``Closed`` 只是构造完成。

        与另外三个反向索引一样收 ``at_seq`` + ``leaf``(v2.6"看哪条线 / 看哪一刻"两参数):
        ``at_seq`` 之后才写进来的块在那一刻**还不在账上**,这里如实报
        :class:`BlockNotFound`,而不是给一个折叠外的答案。
        """
        state = self._state(at_seq=at_seq, leaf=leaf)
        try:
            return state.seq_of[block]
        except KeyError:
            raise BlockNotFound(f"block {block} was never written to this ledger") from None

    def blocks_with(
        self,
        h: BytesHash | TreeHash,
        *,
        at_seq: Seq | None = None,
        leaf: Seq | None = None,
    ) -> tuple[BlockId, ...]:
        """按 ``BytesHash`` 或 ``TreeHash`` 反查块(D-CAP-4;P-11 的兄弟去重靠它)。

        一个哈希可能命中多块——那正是去重要的答案,所以返回元组而不是单值。
        """
        state = self._state(at_seq=at_seq, leaf=leaf)
        hit: list[BlockId] = []
        for block_id in self.block_ids(at_seq=at_seq, leaf=leaf):
            if state.tree_hashes.get(block_id) == h:
                hit.append(block_id)
                continue
            block = state.blocks[block_id]
            try:
                if block.bytes_hash(store=self._store) == h:
                    hit.append(block_id)
            except (KeyError, ValueError):
                continue
        return tuple(hit)

    def lineage_of(
        self,
        block: BlockId,
        *,
        direction: Literal["up", "down"] = "up",
        max_depth: int | None = None,
        at_seq: Seq | None = None,
        leaf: Seq | None = None,
    ) -> tuple[tuple[BlockId, str], ...]:
        """血缘的双向游走(D-CAP-4)。返回 ``((块 id, 经哪个血缘字段), …)``,BFS 次序。

        字段表在 :data:`espalier.LINEAGE_FIELDS`(``origin_sources`` 走同一张表,
        所以 ``check`` 认得的边这里一条不少)。``direction="down"`` 是反向索引:
        谁把我当来源。同一个块经多条边到达时,**记第一次到达的那条边**。
        """
        state = self._state(at_seq=at_seq, leaf=leaf)
        if direction not in ("up", "down"):
            raise ValueError(f"direction must be 'up' or 'down', got {direction!r}")

        def origin_of(block_id: BlockId) -> Origin | None:
            item = state.blocks.get(block_id)
            if item is not None:
                return item.origin
            open_state = state.open.get(block_id)
            return open_state.origin if open_state is not None else None

        if direction == "up":
            def step(current: BlockId) -> list[tuple[BlockId, str]]:
                origin = origin_of(current)
                return list(origin_sources(origin)) if origin is not None else []
        else:
            reverse: dict[BlockId, list[tuple[BlockId, str]]] = {}
            holders = list(state.blocks) + list(state.open)
            for holder in holders:
                origin = origin_of(holder)
                if origin is None:
                    continue
                for source, via in origin_sources(origin):
                    reverse.setdefault(source, []).append((holder, via))

            def step(current: BlockId) -> list[tuple[BlockId, str]]:
                return list(reverse.get(current, ()))

        out: list[tuple[BlockId, str]] = []
        seen: set[BlockId] = {block}
        frontier: list[tuple[BlockId, str]] = step(block)
        depth = 1
        while frontier and (max_depth is None or depth <= max_depth):
            next_frontier: list[tuple[BlockId, str]] = []
            for target, via in frontier:
                if target in seen:
                    continue
                seen.add(target)
                out.append((target, via))
                next_frontier.extend(step(target))
            frontier = next_frontier
            depth += 1
        return tuple(out)

    def compactions(
        self, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> tuple[Compacted, ...]:
        """压缩窗口链 = ``Compacted`` 事件序列(V0-PLAN §3.1:扫账本,不加 ``previous`` 字段)。"""
        return tuple(self._state(at_seq=at_seq, leaf=leaf).compactions)

    def calls(
        self,
        *,
        purpose: str | None = None,
        at_seq: Seq | None = None,
        leaf: Seq | None = None,
    ) -> tuple[Called, ...]:
        """``Called`` 事件序列;``purpose`` 过滤主线/副线(P-14)。"""
        events = self._state(at_seq=at_seq, leaf=leaf).calls
        if purpose is None:
            return tuple(events)
        return tuple(e for e in events if e.purpose == purpose)

    def returns(
        self,
        *,
        called_seq: Seq | None = None,
        at_seq: Seq | None = None,
        leaf: Seq | None = None,
    ) -> tuple[Returned, ...]:
        """``Returned`` 事件序列;``called_seq`` 过滤到某一次调用(P-19 的重试链)。"""
        events = self._state(at_seq=at_seq, leaf=leaf).returns
        if called_seq is None:
            return tuple(events)
        return tuple(e for e in events if e.called_seq == called_seq)

    # ----------------------------------------------------------------- H1(D-CAP-1)

    def served(
        self,
        rendering: "Rendering",
        *,
        model: str,
        params: Mapping[str, Any] | None = None,
        purpose: str = "main",
        keep_rendering: bool = False,
        **event_fields: Any,
    ) -> Called:
        """**发出**一次模型调用:落 ``Called``,manifest 随行 + 进 CAS。见 :mod:`espalier.calls`。

        C-27:``rendering.inlays`` 的来源事实落 ``Called.inlays``,实发段进 CAS。
        C-28:``keep_rendering=True`` 才把整份渲染字节存进 CAS(``Called.rendering``);默认关。
        """
        return _served(
            self,
            rendering,
            model=model,
            params=params,
            purpose=purpose,
            keep_rendering=keep_rendering,
            **event_fields,
        )

    def returned(
        self,
        called: Called | Seq,
        *,
        outcome: str = "ok",
        output: BlockId | None = None,
        usage: Mapping[str, int] | None = None,
        external_ids: Mapping[str, str] | None = None,
        reason: Mapping[str, str] | None = None,
        **event_fields: Any,
    ) -> Returned:
        """一次调用回来(或没回来)。``usage`` = P-17,``external_ids`` = P-18,都不入身份;
        ``reason`` = C-9 的结构化载荷(入链、不下钻)。"""
        return _returned(
            self,
            called,
            outcome=outcome,
            output=output,
            usage=usage,
            external_ids=external_ids,
            reason=reason,
            **event_fields,
        )

    def manifest_of(
        self,
        key: CallHash | ManifestHash | Seq,
        *,
        at_seq: Seq | None = None,
        leaf: Seq | None = None,
    ) -> Manifest:
        """按 ``CallHash`` / ``ManifestHash`` / ``Seq`` 取回"模型这次看到了什么"。"""
        return _manifest_of(self, key, at_seq=at_seq, leaf=leaf)

    def saw(
        self, block: BlockId, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> Manifest | None:
        """这块的作者当时看到了什么;出身不是 ``LlmDerived`` ⇒ ``None``。"""
        return _saw(self, block, at_seq=at_seq, leaf=leaf)

    def verify(
        self,
        block: BlockId,
        *,
        rendering: "Rendering | None" = None,
        at_seq: Seq | None = None,
        leaf: Seq | None = None,
    ) -> Verdict:
        """四值判决 ``Verified | Mismatch | Stale | Unverifiable``。纯查询,永不拦截。

        ``rendering``(C-7 ④,2026-09-06 签):给了就逐条重算 ``shown`` 并验区间,
        不符 ⇒ ``Mismatch``。
        """
        return _verify(self, block, rendering=rendering, at_seq=at_seq, leaf=leaf)

    def calls_showing(
        self, block: BlockId, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> tuple[Seq, ...]:
        """从块找去向(E-6 / D-CAP-4):哪几次调用把这块发出去过。"""
        return _calls_showing(self, block, at_seq=at_seq, leaf=leaf)

    # ----------------------------------------------------------------- 压缩(v2.7)

    def prepare_compact(
        self,
        targets: Sequence[BlockId],
        *,
        instruction: Block | None = None,
        keep: Kept | None = None,
        spec: "RenderSpec | None" = None,
        as_of: datetime | None = None,
    ) -> CompactRequest:
        """定影一次压缩请求。**纯读、零事件**。见 :mod:`espalier.compact`。"""
        return _prepare_compact(
            self, targets, instruction=instruction, keep=keep, spec=spec, as_of=as_of
        )

    def commit(
        self,
        req: CompactRequest,
        result: str | Block,
        *,
        model: str | None = None,
        params: Mapping[str, Any] | None = None,
        **options: Any,
    ) -> Block:
        """原子写 ``Called`` + ``Appended`` + ``Returned`` + ``Compacted``,返回摘要块(v2.7)。

        ``**options`` **原样**转给 :func:`espalier.compact.commit`——签名在那边,这里不复述。
        C-31 扩(2026-09-15 签)之后那边多收三个关键字,从这个入口一样传得进来:
        ``usage=``(落这次压缩的 ``Returned.usage``)、``keep_rendering=``(整份实发字节进
        CAS、``ContentRef`` 留在 ``Called.rendering``)、以及 ``ignorable`` / ``annotations``
        / ``actor`` 三个基类字段(**广播给四条事件**;别的 ``**event_fields`` 键在那边先于任何
        ``store.put`` 就 ``TypeError``)。
        C-38(2026-09-15 签)再多一个 ``external_ids=``(只落这次压缩的
        ``Returned.external_ids``,不广播),同样从这个入口传得进去。
        """
        return _commit(self, req, result, model=model, params=params, **options).summary

    def commit_with_receipt(
        self,
        req: CompactRequest,
        result: str | Block,
        *,
        model: str | None = None,
        params: Mapping[str, Any] | None = None,
        **options: Any,
    ) -> CommitReceipt:
        """同 :meth:`commit`,但给回执(窗口内冲突、targets 等式、开复合处置)。

        ``**options`` 与 :meth:`commit` 同一条路:原样转给 :func:`espalier.compact.commit`,
        C-31 扩的 ``usage`` / ``keep_rendering`` / 基类三格,以及 C-38 的 ``external_ids``
        (只落 ``Returned.external_ids``,不广播),从这里都传得进去。
        """
        return _commit(self, req, result, model=model, params=params, **options)

    # ----------------------------------------------------------------- 账本级属性

    def setting(
        self, name: str, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> str | None:
        """按 ``at_seq`` 求值的账本级属性(G-V0-2)。**末条生效**;没写过 ⇒ ``None``。"""
        return self._state(at_seq=at_seq, leaf=leaf).settings.get(name)

    def settings(
        self, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> Mapping[str, str]:
        return dict(self._state(at_seq=at_seq, leaf=leaf).settings)

    def lineage(self) -> tuple[LedgerId, ...]:
        """``Forked`` 谱系(v2.6:回放缓存沿此查)。从自己开始,一代代往上。

        因为 ``fork`` 原样拷贝继承前缀,祖辈的 ``Forked`` 事件也跟着拷了下来,所以这里
        **不必打开任何父账本文件**就能走出多代:seq 从大到小 = 从近到远。
        没有任何 ``Forked`` 时退回 ``header.parent``(委派/派生那一义)。
        """
        chain: list[LedgerId] = [self._header.id]
        forks = sorted(
            (e for e in self._events if isinstance(e, Forked)),
            key=lambda e: int(e.seq),
            reverse=True,
        )
        for event in forks:
            if event.parent not in chain:
                chain.append(event.parent)
        if len(chain) == 1 and self._header.parent is not None:
            chain.append(self._header.parent)
        return tuple(chain)

    # ----------------------------------------------------------------- 视图与取回

    def view(
        self,
        *,
        leaf: Seq | None = None,
        at_seq: Seq | None = None,
        roots: Iterable[BlockId] | None = None,
        without: Iterable[BlockId] = (),
        include_open: bool = True,
    ) -> View:
        """建一个 :class:`~espalier.View`(v2.6 + §3.2 的四个自由度)。纯查询,零事件。"""
        return View(
            ledger=self,
            leaf=leaf,
            at_seq=at_seq,
            roots=None if roots is None else tuple(roots),
            without=frozenset(without),
            include_open=include_open,
        )

    def retrieve(
        self,
        ids: Sequence[BlockId],
        *,
        at_seq: Seq | None = None,
        leaf: Seq | None = None,
    ) -> Retrieval:
        """三类复现(D10)+ 第四格 ``unknown``。见 :class:`Retrieval`。"""
        state = self._state(at_seq=at_seq, leaf=leaf)
        present: list[Block] = []
        lost: list[Tombstone] = []
        external: list[tuple[BlockId, ExternalAddress]] = []
        unknown: list[BlockId] = []
        for block_id in ids:
            block = state.blocks.get(block_id)
            if block is not None:
                present.append(block)
                external.extend((block_id, address) for address in _external_addresses(block))
                continue
            tombstone = state.tombstones.get(block_id)
            if tombstone is not None:
                lost.append(tombstone)
                continue
            if block_id in state.open:
                continue  # 开态没有 Block 值;它在 open_composites() 里,不在这里
            unknown.append(block_id)
        return Retrieval(
            present=tuple(present),
            lost=tuple(lost),
            external=tuple(external),
            unknown=tuple(unknown),
        )

    def check(
        self,
        *,
        at_seq: Seq | None = None,
        within: BlockId | None = None,
        leaf: Seq | None = None,
        renderings: "Mapping[CallHash, Rendering] | None" = None,
    ) -> CheckReport:
        """一致性报告(v2.6)。**纯查询,永不拦截任何操作**。见 :mod:`espalier.check`。

        ``renderings``(C-7 ④):``{CallHash: Rendering}``,给了就对账 ``shown`` 与区间。
        """
        return check_ledger(self, at_seq=at_seq, within=within, leaf=leaf, renderings=renderings)

    # ----------------------------------------------------------------- 检查点

    def state_document(
        self, *, at_seq: Seq | None = None, leaf: Seq | None = None
    ) -> bytes:
        """检查点的**累积状态**本身(不是摘要):规范 JSON 字节,可读、可比、可验。

        V0-CHOICE 两处:

        * v2.1 说 ``StateHash`` "同时即 CAS 取回键";V0 里那个 CAS 就是账本自己——
          状态是账本前缀的纯函数,重算即取回,不必再存一份(存两份就会不一致)。
        * 文档里**不含账本 id**:它描述的是状态,不是容器。于是 fork 副本上的检查点
          照样验得过——D-X10-1 说"状态可验",副本上验不过的校验点比不留还糟。

        裁决 ④(2026-09-06 签):每个 ``blocks[id]`` 与 ``open[]`` 条目携带
        ``"annotations"``——``Annotated`` 叠加后的**当前**注记映射(``canon_json`` 键排序)。
        于是 StateHash 含注记,``Checkpointed`` / :meth:`verify_checkpoint` 自动跟随:
        注记被改,检查点验得出。TreeHash 照旧不含注记(纪律③ 管的是内容身份)。
        """
        state = self._state(at_seq=at_seq, leaf=leaf)
        chain = self._chain(leaf)
        leaf_seq = int(chain[-1].seq) if chain else None
        document = {
            "at_seq": None if state.last_seq is None else int(state.last_seq),
            "leaf": leaf_seq,
            "top_level": list(state.top),
            "blocks": {
                block_id: {
                    "tree_hash": str(state.tree_hashes.get(block_id, "")),
                    "parent": state.storage_parent.get(block_id),
                    "logical_parent": state.logical_parent.get(block_id),
                    "children": [[l.child, l.gap] for l in state.links.get(block_id, ())],
                    "annotations": dict(block.annotations),
                }
                for block_id, block in sorted(state.blocks.items())
            },
            "open": [
                {
                    "id": open_state.id,
                    "kind": open_state.kind,
                    "children": [
                        [l.child, l.gap] for l in state.links.get(open_state.id, ())
                    ],
                    "annotations": dict(open_state.annotations),
                }
                for open_state in sorted(state.open.values(), key=lambda o: o.id)
            ],
            "tombstoned": sorted(state.tombstones),
            "superseded": dict(sorted(state.superseded.items())),
            "settings": dict(sorted(state.settings.items())),
        }
        return canon_json(document)

    def checkpoint(
        self, *, at_seq: Seq | None = None, leaf: Seq | None = None, **event_fields: Any
    ) -> Checkpoint:
        """落一个检查点(v2.6)。存**态**不是摘要;校验是查询非闸门(D-X10-1)。"""
        chain = self._chain(leaf)
        if not chain:
            raise LedgerError("cannot checkpoint an empty ledger")
        state = self._state(at_seq=at_seq, leaf=leaf)
        if state.last_seq is None:
            raise LedgerError("cannot checkpoint before the first event")
        leaf_seq = Seq(int(chain[-1].seq))
        digest = state_hash(self.state_document(at_seq=at_seq, leaf=leaf))
        event = self.emit(
            Checkpointed,
            state=digest,
            at_seq=state.last_seq,
            leaf=leaf_seq,
            **event_fields,
        )
        return Checkpoint(
            at_seq=state.last_seq, leaf=leaf_seq, state=digest, link=event.link
        )

    def checkpoints(self, *, leaf: Seq | None = None) -> tuple[Checkpoint, ...]:
        """账本上落过的检查点(从 ``Checkpointed`` 事件重建)。"""
        return tuple(
            Checkpoint(at_seq=e.at_seq, leaf=e.leaf, state=e.state, link=e.link)
            for e in self._chain(leaf)
            if isinstance(e, Checkpointed)
        )

    def verify_checkpoint(self, checkpoint: Checkpoint) -> bool:
        """重算那一刻的状态并比对。**纯查询**——不匹配不拦任何操作(D-X10-1)。"""
        try:
            recomputed = state_hash(
                self.state_document(at_seq=checkpoint.at_seq, leaf=checkpoint.leaf)
            )
        except LedgerError:
            return False
        return recomputed == checkpoint.state

    # ----------------------------------------------------------------- fork(X12 乙形)

    def fork(
        self,
        path: str | os.PathLike[str] | None = None,
        *,
        at_seq: Seq | None = None,
        leaf: Seq | None = None,
        id: LedgerId | None = None,
        role: str | None = None,
        annotations: Mapping[str, str] | None = None,
        store: ContentStore | None = None,
        clock: Callable[[], datetime] | None = None,
        ulids: UlidFactory | None = None,
        fsync: bool = True,
    ) -> "Ledger":
        """X12 **乙形**:一文件一账本 + ``Forked`` + ``lineage()``(V0-PLAN §3.1)。

        做四件事:

        1. **闭合边界检查**:``at_seq`` 处还有开着的复合 ⇒ 抛
           :class:`OpenCompositeAtBoundary`(真实 harness 的会话分叉也是这么拒的)。
        2. 新账本头带 ``parent`` 与 ``inherited_cut``(G-V0-2:继承切点"创建即定"进头,
           于是不打开父账本也读得出继承了到哪)。
        3. **深拷贝**到闭合边界:``leaf`` 那条链上 ``seq <= at_seq`` 的事件**原样**重写
           (``replay``),seq / prev / 机械时间一概不动。
        4. 然后写 ``Forked(parent, at_seq)``,seq = ``cut + 1``。

        **V0-CHOICE(与任务书字面的一处偏离,理由写在这里,留给 owner 裁)**:
        任务书说"子账本首事件 ``Forked``"。V0 把它放在**继承前缀之后**——它是子账本
        *自己的*第一条事件,前面那些是继承来的、不属于它。这么做是因为
        **G-V0-3 与 seq 重编号不可兼得**:``Compacted.identity`` 含 ``covers``(一段
        seq 区间),要"副本间同值"就不能给拷贝重新编号;而要让 ``Forked`` 占物理第一行
        又保持"文件序 = seq 序 = 单链",就必须重编号。两者取一,V0 取 G-V0-3——
        因为那是这条 delta 存在的全部理由。副产品有三个,都是好的:继承前缀的
        ``ChainHash`` 与父账本**逐条相同**;拷来的 ``Checkpointed`` 在副本上照样验得过;
        ``lineage()`` 能沿着一路拷下来的 ``Forked`` 走出**多代**谱系,而不只是一跳。

        G-V0-3 裁决(2026-09-06 签)后的补记:``identity`` 改读 ``covered_tree_hashes``
        (内容寻址),不再含 ``covers``,于是上面"不可兼得"的前提已不成立——重编号的
        回放也能同值。``Forked`` 的位置与保 seq 深拷贝**照旧**:三个副产品仍然成立,
        改不改位置是另一条提案,不在 v0.21 单子里。
        """
        source = self._chain(leaf)
        if not source:
            raise LedgerError("cannot fork an empty ledger")
        cut = at_seq if at_seq is not None else Seq(int(source[-1].seq))
        if self.open_composites(at_seq=cut, leaf=leaf):
            raise OpenCompositeAtBoundary(
                f"ledger {self.id} has open composites at seq {cut}; "
                "close them (outcome='interrupted' 也算收尾) before forking"
            )

        child_clock = clock if clock is not None else self._clock
        header = LedgerHeader(
            id=id if id is not None else new_ledger_id(),
            created_at=child_clock(),
            format_version=FORMAT_VERSION,
            parent=self._header.id,
            inherited_cut=cut,
            role=role,
            annotations=annotations or {},
        )
        child = Ledger.create(
            path,
            header=header,
            store=store if store is not None else self._store,
            clock=child_clock,
            ulids=ulids if ulids is not None else self._ulids,
            fsync=fsync,
        )
        for event in source:
            if event.seq > cut:
                break
            child.replay(event)
        child.emit(Forked, parent=self._header.id, at_seq=cut)
        return child
