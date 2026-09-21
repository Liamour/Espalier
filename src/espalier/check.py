"""``check``:纯查询的一致性报告(v2.6 ``Ledger.check``)。

**check 永不拦截任何操作**。这条不是风格,是 v2 章反复写死的:构造器永不拒收(A7)、
持有宣称是机制而非闸门(N3)、检查点校验是查询非闸门(D-X10-1)。所以本模块只读、
只报告,一个异常都不抛。

十条规则(前七条是第二段的;两条 N3 的声明半边是第三段补的;``broken_prev_chain``
是修复轮补的——被跳过的 ignorable 事件会在事件树上留下断点):

======================  ============================================================
``dangling_child``      子链接指向"此刻不在场"的块(从未写入 / 写在 ``at_seq`` 之后 /
                        已被墓碑)。**时间相对**(D-X10-2):报告带 ``at_seq`` 折叠位置,
                        因为同一条链接在 t1 悬空、在 t2 不悬空,两者都是事实
``dangling_source``     出身的血缘边(``origin_sources``)指向此刻不在场的块。同上时间相对
``foreign_source``      C-16(2026-09-06 签):顶层 ``made`` 是 ``LlmDerived`` / ``Recalled``
                        且 ``ledger not in (None, 本账本 id)`` 时,其 sources 边指向的是
                        **别的账本**——不判悬空,报 **info**;经 ``Recalled.carried>`` 前缀
                        到达的边按该 ``Recalled.ledger`` 同判。``lineage_of`` 不动(跨账本边照列)
``shown_mismatch``      C-7 ④:给了 ``renderings``(``{CallHash: Rendering}``)时,对应
``byte_range_invalid``  ``Called`` 随行 manifest 的条目逐条重算 ``shown`` / 验区间不成立。
                        **error**:manifest 与字节对不上就是记录自相矛盾
``logical_cycle``       逻辑父轴(``Reparented``)成环(D-X12-5)
``unclosed_composite``  ``Opened`` 无 ``Closed``。**不是错**:崩溃恢复时它正是要枚举的东西
                        (severity=info),``within`` / ``at_seq`` 下同样如实报
``broken_prev_chain``   某条事件的 ``prev`` 指向不在场的事件(典型来源:``ignorable=True``
                        的未知事件被 ``load`` 跳过)。**warning**:折叠停在断点、账本照常
                        可用,断点之前的前缀在这条线上取不到——是事实不是判决。
                        全账本级,``within`` 限定下不报(它不属于任何子树)
``covers_out_of_range`` ``Compacted.covers`` 里有账本上不存在的 seq
``kept_absent``         ``Compacted.kept`` 点名保留的块此刻不在场。**warning 不是 error**:
                        "压缩时保留了它"与"后来又删了它"可以都是真的,报告说出来就够
``identity_unavailable`` G-V0-3(2026-09-06 签):``Compacted.covered_tree_hashes`` 是
                        ``None``(v0.18 及之前的写者没有这一格;或本轮写者手工构造的
                        ``CompactRequest.covered`` 就没说)⇒ ``identity`` 算不出。
                        **info**:没说不是错,身份的输入不在手就如实说,不编造
``no_recovery_handle``  A7 改述:字节**不在**账本/CAS(外置载荷且 store 取不到),
                        而 ``recovery_classes(origin)`` 又是空集 ⇒ 三类把手一个都没有
``shape_mismatch``      块携 ``Ref(space="shape")`` 自我宣称了一个形状,而 ``Lens.check``
                        说它不合形。**warning**:宣称与事实不符是事实,不是判决——N3 定案
                        "持有宣称是机制,**永不因宣称失败拦截任何操作**"
``unknown_shape``       宣称了一个本库没登记的形状。**info**:第三方 Shape 没 import 进来
                        是常态,不是错(C1/C3:调用者自有 Shape 与库内建同权)
``span_version_mismatch`` V1(A10 清单 §3,2026-09-08 签):``Transformed.span.version`` /
                        ``Parsed.span.version`` 非空,持有者的血缘边指向**在场**的源块,而
                        version 与其中**任何一块**的 TreeHash 都不等。**warning**:内容寻址的
                        把手对不上是事实不是判决。边为空 / 源不在场 / version 为空:不猜,不报
======================  ============================================================

``within`` 把检查限定在某个子树(N3 寻址的半边,结构性关闭):只检查 ``within`` 自己与它
在**存储树**上的后代。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Mapping

from ._freeze import freeze_tuple
from .block import Block
from .hashes import CallHash
from .ids import BlockId, LedgerId, Seq
from .lens import check_declared, declared_shapes
from .origin import (
    LlmDerived,
    Origin,
    Parsed,
    Recalled,
    Transformed,
    origin_sources,
    recovery_classes,
)
from .payload import ContentRef, Text

if TYPE_CHECKING:  # pragma: no cover
    from .ledger import Ledger
    from .render import Rendering

__all__ = ["Severity", "Finding", "CheckReport", "check_ledger"]

Severity = Literal["error", "warning", "info"]


@dataclass(frozen=True)
class Finding:
    """一条发现。``subject`` 是块 id 或 seq 的字符串形——一个字段容两种主语,不另设轴。"""

    rule: str
    severity: Severity
    subject: str
    detail: str
    at_seq: Seq | None = None
    """折叠位置。悬空是时间相对的(D-X10-2),所以每条发现都带着"在哪一刻看的"。"""

    within: BlockId | None = None


@dataclass(frozen=True)
class CheckReport:
    """检查结果。``ok`` 只看 ``error`` 档——warning / info 是事实,不是判决。"""

    findings: tuple[Finding, ...] = ()
    at_seq: Seq | None = None
    within: BlockId | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "findings", freeze_tuple(self.findings))

    @property
    def ok(self) -> bool:
        return not any(f.severity == "error" for f in self.findings)

    def of(self, rule: str) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.rule == rule)

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.findings)

    def __len__(self) -> int:
        return len(self.findings)


def _scope(
    ledger: "Ledger", within: BlockId | None, *, at_seq: Seq | None, leaf: Seq | None
) -> set[BlockId] | None:
    """``within`` 的存储树后代闭包(含自己);``None`` = 全账本。"""
    if within is None:
        return None
    seen: set[BlockId] = set()
    frontier = [within]
    while frontier:
        current = frontier.pop()
        if current in seen:
            continue
        seen.add(current)
        for link in ledger.children(current, at_seq=at_seq, leaf=leaf):
            frontier.append(link.child)
    return seen


def edge_ledger(origin: Origin, via: str) -> LedgerId | None:
    """一条血缘边**归哪本账**(C-16):沿 ``via`` 路径下钻,取路上**最内层**带非空 ``ledger``
    的 ``LlmDerived`` / ``Recalled`` 的 ``ledger``;一路都没有 ⇒ ``None``(本账本)。

    ``via`` 形如 ``"Recalled.carried>LlmDerived.sources"``:前缀段决定要经过哪几层
    ``carried``,末段是出边的变体。

    C-16 偏离(已申报):单子原话是"经 ``Recalled.carried>`` 前缀到达的边按该 ``Recalled.ledger``
    同判";这里取路上最内层非空的 ``ledger``,所以 ``Recalled(ledger=None,
    carried=LlmDerived(ledger=Z))`` 的边报 ``foreign_source(Z)`` 而不是 ``dangling_source``——
    出边是谁的就归谁的账,信息更多。
    """
    made = origin.made
    governing: LedgerId | None = None
    segments = via.split(">")
    for index, segment in enumerate(segments):
        if isinstance(made, (LlmDerived, Recalled)) and made.ledger is not None:
            governing = made.ledger
        if index == len(segments) - 1:
            break
        if segment in ("Recalled.carried", "Parsed.carried") and isinstance(made, (Recalled, Parsed)):
            carried = made.carried
            if carried is None:
                break
            made = carried.made
        else:  # pragma: no cover - via 与 origin 不对应只可能来自伪造输入
            break
    return governing


def check_ledger(
    ledger: "Ledger",
    *,
    at_seq: Seq | None = None,
    within: BlockId | None = None,
    leaf: Seq | None = None,
    renderings: "Mapping[CallHash, Rendering] | None" = None,
) -> CheckReport:
    """跑上面那些规则,返回 :class:`CheckReport`。纯查询,零事件,永不抛。

    ``renderings``(C-7 ④):``{CallHash: Rendering}``——harness 手上还留着的渲染全文;
    给了就对相应 ``Called`` 的随行 manifest 逐条重验 ``shown`` 与区间。
    """
    findings: list[Finding] = []
    scope = _scope(ledger, within, at_seq=at_seq, leaf=leaf)
    fold_at = ledger.effective_at_seq(at_seq=at_seq, leaf=leaf)

    def in_scope(block_id: BlockId) -> bool:
        return scope is None or block_id in scope

    present = set(ledger.block_ids(at_seq=at_seq, leaf=leaf))
    open_ids = {handle.id for handle in ledger.open_composites(at_seq=at_seq, leaf=leaf)}
    live = present | open_ids

    def why_absent(target: BlockId) -> str:
        tombstone = ledger.tombstone_of(target)
        if tombstone is not None:
            return "tombstoned"
        try:
            seq = ledger.seq_of(target)
        except KeyError:
            return "never written to this ledger"
        return f"written at seq {seq}, after the fold"

    # ---- 1/2:悬空(子链接与血缘边),时间相对
    for holder in sorted(live):
        if not in_scope(holder):
            continue
        for link in ledger.children(holder, at_seq=at_seq, leaf=leaf):
            if link.child not in live:
                findings.append(
                    Finding(
                        rule="dangling_child",
                        severity="error",
                        subject=holder,
                        detail=f"child {link.child} is absent here ({why_absent(link.child)})",
                        at_seq=fold_at,
                        within=within,
                    )
                )
        item = ledger.find(holder, at_seq=at_seq, leaf=leaf)
        origin = item.origin if item is not None else None
        if origin is None:
            continue
        for source, via in origin_sources(origin):
            if source in live:
                continue
            foreign = edge_ledger(origin, via)
            if foreign is not None and foreign != ledger.id:
                findings.append(
                    Finding(
                        rule="foreign_source",
                        severity="info",
                        subject=holder,
                        detail=f"{via} -> {source} lives on ledger {foreign}, not here "
                        "(C-16:跨账本来源不判悬空)",
                        at_seq=fold_at,
                        within=within,
                    )
                )
                continue
            findings.append(
                Finding(
                    rule="dangling_source",
                    severity="error",
                    subject=holder,
                    detail=f"{via} -> {source} is absent here ({why_absent(source)})",
                    at_seq=fold_at,
                    within=within,
                )
            )
        # ---- 2b:机械源区间的版本把手(V1,A10 清单 §3,2026-09-08 签)
        # ``Transformed.span.version`` / ``Parsed.span.version`` 是内容寻址的把手:它声称
        # "这段区间取自 TreeHash 为 version 的那份源"。只在能对账时对账——持有者的血缘
        # 边指向账上在场的块,而 version 与其中任何一块的 TreeHash 都不等 ⇒ warning。
        # 边为空 / 源不在场 / version 为空:不猜,不报(A9:没有证据不下判)。
        made = origin.made
        span = made.span if isinstance(made, (Transformed, Parsed)) else None
        version = getattr(span, "version", None) if span is not None else None
        if version:
            candidates = [s for s, _ in origin_sources(origin) if s in live]
            if candidates:
                hashes = set()
                for s in candidates:
                    try:
                        hashes.add(str(ledger.tree_hash_of(s, at_seq=at_seq, leaf=leaf)))
                    except KeyError:
                        continue
                if hashes and str(version) not in hashes:
                    findings.append(
                        Finding(
                            rule="span_version_mismatch",
                            severity="warning",
                            subject=holder,
                            detail=f"span.version {version} matches none of the lineage sources'"
                            f" TreeHash ({', '.join(sorted(hashes))})",
                            at_seq=fold_at,
                            within=within,
                        )
                    )

    # ---- 3:逻辑父轴无环(D-X12-5)
    logical = ledger.logical_parents(at_seq=at_seq, leaf=leaf)
    for start in sorted(logical):
        if not in_scope(start):
            continue
        seen: list[BlockId] = []
        cursor: BlockId | None = start
        while cursor is not None and cursor not in seen:
            seen.append(cursor)
            cursor = logical.get(cursor)
        if cursor is not None:
            cycle = seen[seen.index(cursor):] + [cursor]
            findings.append(
                Finding(
                    rule="logical_cycle",
                    severity="error",
                    subject=start,
                    detail="logical parent cycle: " + " -> ".join(cycle),
                    at_seq=fold_at,
                    within=within,
                )
            )

    # ---- 4:Opened 无 Closed
    for handle in ledger.open_composites(at_seq=at_seq, leaf=leaf):
        if not in_scope(handle.id):
            continue
        findings.append(
            Finding(
                rule="unclosed_composite",
                severity="info",
                subject=handle.id,
                detail=f"composite kind={handle.kind!r} opened at seq {handle.opened_seq}, never closed",
                at_seq=fold_at,
                within=within,
            )
        )

    # ---- 4b:prev 断链(被跳过的 ignorable 事件 / 残缺记录)
    if within is None:
        for event_seq, missing_prev in ledger.broken_links():
            findings.append(
                Finding(
                    rule="broken_prev_chain",
                    severity="warning",
                    subject=str(event_seq),
                    detail=f"prev {missing_prev} is not on this ledger; the chain stops here "
                    "(读不懂而被跳过的 ignorable 事件会留下这种断点:账本照常可用,"
                    "只是断点之前的前缀在这条线上取不到)",
                    at_seq=fold_at,
                    within=within,
                )
            )

    # ---- 5:Compacted.covers ⊆ 已有 seq
    known_seqs = ledger.event_seqs(at_seq=at_seq, leaf=leaf)
    for compacted in ledger.compactions(at_seq=at_seq, leaf=leaf):
        if within is not None and not in_scope(compacted.summary):
            continue
        missing = [s for s in compacted.covers.seqs() if s not in known_seqs]
        if missing:
            shown = ", ".join(str(s) for s in missing[:8])
            more = "" if len(missing) <= 8 else f" (+{len(missing) - 8} more)"
            findings.append(
                Finding(
                    rule="covers_out_of_range",
                    severity="error",
                    subject=str(compacted.seq),
                    detail=f"covers [{compacted.covers.start}, {compacted.covers.stop}) "
                    f"includes seqs absent here: {shown}{more}",
                    at_seq=fold_at,
                    within=within,
                )
            )
        gone = [block_id for block_id in compacted.kept.all_ids() if block_id not in live]
        if gone:
            findings.append(
                Finding(
                    rule="kept_absent",
                    severity="warning",
                    subject=str(compacted.seq),
                    detail="kept blocks are absent here: " + ", ".join(dict.fromkeys(gone)),
                    at_seq=fold_at,
                    within=within,
                )
            )
        if compacted.covered_tree_hashes is None:
            findings.append(
                Finding(
                    rule="identity_unavailable",
                    severity="info",
                    subject=str(compacted.seq),
                    detail="Compacted has no covered_tree_hashes (written before G-V0-3); "
                    "identity cannot be computed and is None(不编造)",
                    at_seq=fold_at,
                    within=within,
                )
            )

    # ---- 6:A7 改述(字节不在账者,三类至少居一)
    store = ledger.store
    for block_id in sorted(present):
        if not in_scope(block_id):
            continue
        block = ledger.find(block_id, at_seq=at_seq, leaf=leaf)
        if not isinstance(block, Block) or block.payload is None:
            continue
        ref = block.payload.body if isinstance(block.payload, Text) else block.payload.data
        if not isinstance(ref, ContentRef):
            continue  # 内联 ⇒ 字节就在账上 ⇒ 自身即强复现
        if store is not None and store.has(ref.hash):
            continue
        if recovery_classes(block.origin):
            continue
        findings.append(
            Finding(
                rule="no_recovery_handle",
                severity="warning",
                subject=block_id,
                detail=(
                    f"payload bytes {ref.hash} are neither in the ledger's store nor reachable: "
                    f"recovery_classes({type(block.origin.made).__name__}) is empty"
                ),
                at_seq=fold_at,
                within=within,
            )
        )

    # ---- 7/8:N3 形状宣称(v2.11 定案:持有宣称是机制,永不拦截)
    def resolve_here(block_id: BlockId) -> Block | None:
        item = ledger.find(block_id, at_seq=at_seq, leaf=leaf)
        return item if isinstance(item, Block) else None

    for block_id in sorted(present):
        if not in_scope(block_id):
            continue
        block = resolve_here(block_id)
        if block is None or not declared_shapes(block):
            continue
        for report in check_declared(block, resolve=resolve_here):
            for error in report.errors:
                unknown = error.rule_id == "shape.unknown"
                findings.append(
                    Finding(
                        rule="unknown_shape" if unknown else "shape_mismatch",
                        severity="info" if unknown else "warning",
                        subject=block_id,
                        detail=f"declared shape {report.shape!r}: {error}",
                        at_seq=fold_at,
                        within=within,
                    )
                )

    # ---- 9:manifest 与渲染字节对账(C-7 ④)
    if renderings:
        from .calls import verify_shown

        for called in ledger.calls(at_seq=at_seq, leaf=leaf):
            rendering = renderings.get(called.call)
            if rendering is None or called.manifest_value is None:
                continue
            mismatch = verify_shown(called.manifest_value, rendering)
            if mismatch is None:
                continue
            rule = "byte_range_invalid" if mismatch.detail.startswith("byte_range_invalid") else "shown_mismatch"
            findings.append(
                Finding(
                    rule=rule,
                    severity="error",
                    subject=str(called.seq),
                    detail=f"{mismatch.detail}; expected {mismatch.expected}, actual {mismatch.actual}",
                    at_seq=fold_at,
                    within=within,
                )
            )

    return CheckReport(findings=tuple(findings), at_seq=fold_at, within=within)
