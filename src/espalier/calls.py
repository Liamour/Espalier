"""H1:``served`` / ``saw`` / ``verify`` 与 ``CallHash`` / ``ToolCallHash``
(V0-PLAN §3.2 的 D-CAP-1;CAPABILITIES `H1 Manifest 不可取回`)。

**H1 是本轮最重的一条洞**:v2 章有 ``CallHash = h(ManifestHash‖model‖params)``,却没有
任何一处能从 ``CallHash`` 走回那份 ``Manifest``——于是"模型这次看到了什么"是一个算得出
指纹、取不回内容的东西。本模块补上那条取回链:

    块.origin(LlmDerived).call  →  Called 事件  →  Called.manifest_value  →  Manifest

**取回形(V0-CHOICE,§3.1 选"瘦事件"的落地细节)**:``Called`` 事件**随行携带 Manifest**
(与 ``Appended`` 携 ``block_value`` 同构),同时把规范字节 ``put`` 进账本的
``ContentStore``。两件都做,理由各自独立:

* **随行**是 A9 的要求:账本必须能从文件独自复原(``ContentStore`` 在 V0 是内存实现,
  重开进程就空了;dev 模式更是零流水)。带在事件上 ⇒ 重载之后 ``manifest_of`` 照样答得出。
* **进 CAS** 是 §3.1 的要求:同一份 manifest 在重试、fork、副线调用里会重复出现,CAS
  是它的去重居所。注意 ``ContentStore.put`` 算出的键是 ``BytesHash``(存储字节的 CAS 键),
  与 ``ManifestHash``(``h(entries‖spec_digest)``)**不是一个型**——两个键回答两个问题,
  谁也不冒充谁(v2.1 纪律②的同构推论)。

**调用实例按 seq 寻址,``CallHash`` 只作去重键**(B2):同上下文重试得同 ``CallHash``,
所以"第几次调用"这个问题只有事件 seq 答得了。``calls_showing`` / ``manifest_of(seq)``
都建在这条上。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping

from .hashes import (
    CALL_HASH_PREFIX,
    TOOL_CALL_HASH_PREFIX,
    CallHash,
    ManifestHash,
    ToolCallHash,
    bytes_hash,
    canon_json,
    digest,
)
from .ids import CANON_RAW, BlockId, Seq
from .manifest import InlayKey, Manifest, is_inlay_key
from .origin import LlmDerived
from .payload import ContentRef

if TYPE_CHECKING:  # pragma: no cover - 只为类型;运行期不 import,避免与 ledger 成环
    from .events import Called, InlayRecord, Returned
    from .ledger import Ledger
    from .render import Rendering

__all__ = [
    "DOMAIN_CALL",
    "DOMAIN_TOOL_CALL",
    "call_hash",
    "tool_call_hash",
    "params_canon",
    "Verified",
    "Mismatch",
    "Stale",
    "Unverifiable",
    "Verdict",
    "inlay_records",
    "put_inlays",
    "served",
    "returned",
    "find_called",
    "manifest_of",
    "saw",
    "verify",
    "verify_shown",
    "calls_showing",
]

DOMAIN_CALL: str = "espalier/call/v1"
DOMAIN_TOOL_CALL: str = "espalier/toolcall/v1"


# --------------------------------------------------------------------------- 哈希构造


def params_canon(params: Mapping[str, Any] | None) -> str:
    """``params`` 的规范序列(UTF-8 文本形)。``None`` 与 ``{}`` 同形——空参数就是空参数。"""
    return canon_json(params or {}).decode("utf-8")


def call_hash(
    manifest: ManifestHash, model: str, params: Mapping[str, Any] | None = None
) -> CallHash:
    """``h(ManifestHash ‖ model ‖ params 规范序列)``(v2.1)。

    用量、provider 请求 id、外部遥测 id 一律**不进**(P-17/P-18:那些是输出不是输入,
    进来就会让"同上下文重试得同 CallHash"这条性质失效)。
    """
    body = canon_json([str(manifest), model, params_canon(params)])
    return CallHash(CALL_HASH_PREFIX + digest(DOMAIN_CALL, (body,)))


def tool_call_hash(tool: str, args: Any = None) -> ToolCallHash:
    """``h(tool ‖ args 规范序列)``,**上下文无关**(v2.1;配 ``RecordingKey`` 作回放缓存)。

    ``args`` 收任意 JSON 原生值:工具参数不一定是映射(有的 harness 的工具参数就是模型原样
    产出的 JSON 字符串,那就以字符串入哈希——A5:库看不懂也照样存得下)。
    """
    body = canon_json([tool, args])
    return ToolCallHash(TOOL_CALL_HASH_PREFIX + digest(DOMAIN_TOOL_CALL, (body,)))


# --------------------------------------------------------------------------- Verdict


@dataclass(frozen=True)
class Verified:
    """这块确实由那次调用产出,那次调用看到的 manifest 也还对得上,来源全都还在场。"""

    call: CallHash
    manifest: ManifestHash
    called_seq: Seq


@dataclass(frozen=True)
class Mismatch:
    """对不上。``detail`` 说哪一处对不上;``expected`` / ``actual`` 给两个值。"""

    detail: str
    expected: str
    actual: str


@dataclass(frozen=True)
class Stale:
    """对得上,**但账本在那次调用之后动过**:来源被替换、被删、或此刻不在场。

    这不是错——"当时看到的是 A、现在 A 已经被 B 顶掉"两件事都真(append-only 的常态)。
    ``changed`` 列出动过的来源块。
    """

    detail: str
    changed: tuple[BlockId, ...] = ()


@dataclass(frozen=True)
class Unverifiable:
    """没法验。``reason`` 说为什么——**不拿 ``Mismatch`` 冒充"验不了"**(A9 的反面)。"""

    reason: str


#: 四值判决(D-CAP-1 / D17)。
Verdict = Verified | Mismatch | Stale | Unverifiable


# --------------------------------------------------------------------------- H1 四件套


def inlay_records(rendering: "Rendering") -> dict[InlayKey, "InlayRecord"]:
    """``Rendering.inlays`` → ``Called.inlays`` 的映射(C-27,2026-09-06 签)。

    只搬来源事实(provider / params_canon / after),不搬文本——文本走 :func:`put_inlays`
    进 CAS、由 manifest 的 ``shown`` 对账。同一个键出现两次时后者覆盖(键 = f(provider,
    params),两次的来源事实本就相同)。
    """
    from .events import InlayRecord

    return {
        inlay.key: InlayRecord(
            provider=inlay.origin.provider,
            params_canon=inlay.origin.params_canon,
            after=inlay.after,
        )
        for inlay in rendering.inlays
    }


def put_inlays(ledger: "Ledger", rendering: "Rendering") -> tuple[ContentRef, ...]:
    """把每条 Inlay 条目的**实发段字节**(``rendering.segment(entry)``)``put`` 进账本 CAS
    (C-27)。CAS 键 = ``bytes_hash(段, canon=raw)`` = 那条条目的 ``shown``——于是重载后
    ``store.get(ContentRef(hash=entry.shown, size=entry.size))`` 就取得回文本,不必在事件上
    再存一份。返回写进去的引用,按条目次序。
    """
    return tuple(
        ledger.store.put(rendering.segment(entry))
        for entry in rendering.manifest.entries
        if is_inlay_key(entry.source)
    )


def served(
    ledger: "Ledger",
    rendering: "Rendering",
    *,
    model: str,
    params: Mapping[str, Any] | None = None,
    purpose: str = "main",
    keep_rendering: bool = False,
    **event_fields: Any,
) -> "Called":
    """**发出**一次模型调用:落一条 ``Called``,manifest 随行 + 进 CAS。

    A8:库**不调模型**。``served`` 只记录"我们把这份渲染发出去了";真的发请求、拿回结果
    是 harness 的事,回来之后调 :func:`returned`。

    2026-09-06 签的两格(都不入 ``CallHash``):

    * C-27:``rendering.inlays`` 的来源事实落 ``Called.inlays``;每条 Inlay 的实发段字节
      进 CAS(:func:`put_inlays`,键 = ``shown``)。没有 Inlay 就什么都不多写。
      **两路各走各的、互不对账**:``Called.inlays`` 的键来自 ``rendering.inlays``,进 CAS 的
      字节来自 ``rendering.manifest`` 里 ``is_inlay_key(source)`` 的那些条目。库自己
      :func:`espalier.render` 出来的 ``Rendering`` 两路恒一致;harness 手工拼一个
      ``Rendering`` 交进来则可能不一致(``inlays`` 有键而 manifest 无条目 ⇒ 取不回文本;
      manifest 有条目而 ``inlays`` 无键 ⇒ 取得回文本、说不出 provider)。这里**不校验、
      不补齐**:两边都是调用者声称的事实,如实各存各的;要对账走 :func:`verify_shown`。
    * C-28:``keep_rendering=True`` 才把整份 ``rendering.data`` ``put`` 进 CAS 并把
      ``ContentRef`` 留在 ``Called.rendering``;**默认关**——存不存全文是 harness 的决定
      (C-7 ④ 的分工不变),库只给把手。
    """
    from .events import Called  # 局部 import:events 不依赖 calls,反过来才成立

    manifest = rendering.manifest
    manifest_key = manifest.hash()
    ledger.store.put(manifest.to_bytes())  # CAS 去重居所(§3.1)
    put_inlays(ledger, rendering)
    kept = ledger.store.put(rendering.data) if keep_rendering else None
    event = ledger.emit(
        Called,
        call=call_hash(manifest_key, model, params),
        manifest=manifest_key,
        model=model,
        params_canon=params_canon(params),
        purpose=purpose,
        manifest_value=manifest,
        inlays=inlay_records(rendering),
        rendering=kept,
        **event_fields,
    )
    return event  # type: ignore[return-value]


def returned(
    ledger: "Ledger",
    called: "Called | Seq",
    *,
    outcome: str = "ok",
    output: BlockId | None = None,
    usage: Mapping[str, int] | None = None,
    external_ids: Mapping[str, str] | None = None,
    reason: Mapping[str, str] | None = None,
    **event_fields: Any,
) -> "Returned":
    """一次调用**回来**(或没回来)。``outcome`` ∈ ``ok`` / ``error`` / ``interrupted``。

    P-19:失败尝试同样落一条 ``Returned(outcome="error")``——"这次调用没成功"是事实,
    不落就只剩一条永远没有回音的 ``Called``,分不清"失败了"与"还在路上"。
    ``reason``(C-9,2026-09-06 签)是结构化载荷,开域键,如 ``{"kind": "aborted", "cause": "user"}``。
    """
    from .events import Called as CalledEvent, Returned as ReturnedEvent

    called_seq = called.seq if isinstance(called, CalledEvent) else Seq(int(called))
    if called_seq not in ledger.event_seqs():
        from .ledger import LedgerError

        raise LedgerError(f"no event at seq {called_seq} to return from")
    event = ledger.emit(
        ReturnedEvent,
        called_seq=called_seq,
        outcome=outcome,
        output=output,
        usage=usage,
        external_ids=external_ids or {},
        reason=reason,
        **event_fields,
    )
    return event  # type: ignore[return-value]


def verify_shown(manifest: Manifest, rendering: "Rendering") -> Mismatch | None:
    """C-7 ④(2026-09-06 签):拿着**当时的渲染字节**逐条重验 manifest。

    两条判据,任一不成立 ⇒ :class:`Mismatch`(``detail`` 以 ``byte_range_invalid`` /
    ``shown_mismatch`` 开头,``check`` 的 finding 规则名与之同名):

    * 区间合法:``0 ≤ a ≤ b ≤ len(data)``,且条目按出现次序**单调不重叠**
      (``a_i ≥ b_{i-1}``);
    * 字节对得上:``bytes_hash(data[a:b], canon=raw) == shown``。

    ``None`` = 全部对得上。纯函数;``rendering`` 是 harness 手上那份 :class:`Rendering`
    (库不替它存全文——manifest 存的是指纹,全文是 harness 的事)。
    """
    data = rendering.data
    size = len(data)
    last_stop = 0
    for index, entry in enumerate(manifest.entries):
        start, stop = entry.byte_range
        if not (0 <= start <= stop <= size) or start < last_stop:
            return Mismatch(
                detail=f"byte_range_invalid: entry {index} ({entry.source!r}) has byte_range "
                f"[{start}, {stop}) against {size} bytes, previous stop {last_stop}",
                expected=f"0 <= {last_stop} <= a <= b <= {size}",
                actual=f"[{start}, {stop})",
            )
        last_stop = stop
        recomputed = bytes_hash(data[start:stop], canon=CANON_RAW)
        if str(recomputed) != str(entry.shown):
            return Mismatch(
                detail=f"shown_mismatch: entry {index} ({entry.source!r}) bytes [{start}, {stop}) "
                "do not hash to the manifest's shown",
                expected=str(entry.shown),
                actual=str(recomputed),
            )
    return None


def _called_at(
    ledger: "Ledger",
    seq: Seq,
    *,
    at_seq: Seq | None = None,
    leaf: Seq | None = None,
) -> "Called":
    """按 seq 取一条 ``Called``,并且**受同一次折叠约束**。

    三种键(``CallHash`` / ``ManifestHash`` / ``Seq``)必须是同一套时间语义:哈希两键走
    ``ledger.calls()``,本来就只看 ``(at_seq, leaf)`` 折出来的那条线;seq 键原先直接
    ``event_at`` 裸取,于是能取回**另一条分支上的**、或 ``at_seq`` **之后的** Called——
    同一个方法三种键两套语义。这里补上校验,越界如实报。
    """
    from .events import Called

    event = ledger.event_at(seq)
    if not isinstance(event, Called):
        from .ledger import LedgerError

        raise LedgerError(f"event at seq {seq} is {event.EVENT!r}, not a model call")
    if seq not in ledger.event_seqs(at_seq=at_seq, leaf=leaf):
        from .ledger import LedgerError

        raise LedgerError(
            f"the Called at seq {seq} is not on this fold "
            f"(at_seq={at_seq}, leaf={leaf});它在另一条线上或在这一刻之后"
        )
    return event


def find_called(
    ledger: "Ledger",
    key: "CallHash | ManifestHash | Seq",
    *,
    at_seq: Seq | None = None,
    leaf: Seq | None = None,
) -> "Called | None":
    """按 ``CallHash`` / ``ManifestHash`` / ``Seq`` 找那条 ``Called``。

    ``CallHash`` 与 ``ManifestHash`` 都可能命中多条(重试、同一份上下文再发一次),
    取**最近的一条**——调用实例按 seq 寻址,要全部就走 ``ledger.calls()``。

    三种键同受 ``(at_seq, leaf)`` 折叠约束(见 :func:`_called_at`)。
    """
    if isinstance(key, int):
        return _called_at(ledger, Seq(key), at_seq=at_seq, leaf=leaf)
    text = str(key)
    hits = [
        event
        for event in ledger.calls(at_seq=at_seq, leaf=leaf)
        if str(event.call) == text or str(event.manifest) == text
    ]
    return hits[-1] if hits else None


def manifest_of(
    ledger: "Ledger",
    key: "CallHash | ManifestHash | Seq",
    *,
    at_seq: Seq | None = None,
    leaf: Seq | None = None,
) -> Manifest:
    """取回一次调用的 ``Manifest``(H1 的那条链)。取不回时抛,**不返回半个答案**。"""
    from .ledger import LedgerError

    event = find_called(ledger, key, at_seq=at_seq, leaf=leaf)
    if event is None:
        raise LedgerError(f"no model call on this ledger for {key!r}")
    if event.manifest_value is None:
        raise LedgerError(
            f"the Called at seq {event.seq} carries no manifest value; "
            "它是外来记录(别人的账本没带),本库不伪造一个"
        )
    return event.manifest_value


def saw(
    ledger: "Ledger",
    block: BlockId,
    *,
    at_seq: Seq | None = None,
    leaf: Seq | None = None,
) -> Manifest | None:
    """**这块的作者当时看到了什么**:经 ``LlmDerived.call`` 走回那次调用的 manifest。

    出身不是 ``LlmDerived``(用户话语、工具结果、解析产物…)⇒ ``None``:它不是任何一次
    模型调用的产物,"它看到了什么"这个问题对它无意义。
    """
    item = ledger.find(block, at_seq=at_seq, leaf=leaf)
    origin = getattr(item, "origin", None)
    if origin is None or not isinstance(origin.made, LlmDerived):
        return None
    event = find_called(ledger, origin.made.call, at_seq=at_seq, leaf=leaf)
    if event is None or event.manifest_value is None:
        return None
    return event.manifest_value


def verify(
    ledger: "Ledger",
    block: BlockId,
    *,
    rendering: "Rendering | None" = None,
    at_seq: Seq | None = None,
    leaf: Seq | None = None,
) -> Verdict:
    """四值判决(D-CAP-1)。**纯查询**,永不拦截任何操作。

    机械口径(V0-CHOICE;D-CAP-1 只给了四个值名,没给判据):

    ``Unverifiable``  出身不是 ``LlmDerived`` / 账本上没有那条 ``Called`` / 那条
                      ``Called`` 没带 manifest —— 三种"验不了",各自留一句 reason。
    ``Mismatch``      带着的 manifest 自己算出来的 ``ManifestHash`` 与 ``Called.manifest``
                      对不上,或按 (manifest, model, params) 重算的 ``CallHash`` 与块声称的
                      ``call`` 对不上 —— 记录内部自相矛盾。给了 ``rendering``(C-7 ④)
                      还逐条重算 ``shown`` 并验区间,见 :func:`verify_shown`。
    ``Stale``         都对得上,**但**那次调用之后账本动过:manifest 里点名的某个来源块
                      此刻不在场(被删)或已被 ``Replaced`` 顶掉。
    ``Verified``      都对得上,来源也都还在场。
    """
    item = ledger.find(block, at_seq=at_seq, leaf=leaf)
    if item is None:
        return Unverifiable(reason=f"block {block} is not on this ledger at this fold")
    origin = getattr(item, "origin", None)
    if origin is None or not isinstance(origin.made, LlmDerived):
        made = type(origin.made).__name__ if origin is not None else "?"
        return Unverifiable(reason=f"origin is {made}, not LlmDerived: nothing claims a call")

    claimed = origin.made.call
    event = find_called(ledger, claimed, at_seq=at_seq, leaf=leaf)
    if event is None:
        return Unverifiable(reason=f"no Called with {claimed} on this ledger")
    if event.manifest_value is None:
        return Unverifiable(
            reason=f"the Called at seq {event.seq} carries no manifest value"
        )

    recomputed_manifest = event.manifest_value.hash()
    if str(recomputed_manifest) != str(event.manifest):
        return Mismatch(
            detail="the carried manifest does not hash to the ManifestHash on the event",
            expected=str(event.manifest),
            actual=str(recomputed_manifest),
        )
    # params 以事件上的规范序列为准(它才是当时发出去的那一份);因此这里不走
    # ``call_hash(…, params)``——那个会把 params 再规范化一次,而事件上存的已经是规范形。
    body = canon_json([str(recomputed_manifest), event.model, event.params_canon])
    recomputed_call = CallHash(CALL_HASH_PREFIX + digest(DOMAIN_CALL, (body,)))
    if str(recomputed_call) != str(claimed):
        return Mismatch(
            detail="CallHash recomputed from (manifest, model, params) differs from the claim",
            expected=str(claimed),
            actual=str(recomputed_call),
        )

    if rendering is not None:
        shown_mismatch = verify_shown(event.manifest_value, rendering)
        if shown_mismatch is not None:
            return shown_mismatch

    changed: list[BlockId] = []
    for source in event.manifest_value.block_ids():
        if ledger.superseded_by(source, at_seq=at_seq, leaf=leaf) is not None:
            changed.append(source)
        elif not ledger.has(source, at_seq=at_seq, leaf=leaf):
            changed.append(source)
    if changed:
        return Stale(
            detail="sources shown to that call have been replaced or removed since",
            changed=tuple(changed),
        )
    return Verified(
        call=claimed, manifest=ManifestHash(str(event.manifest)), called_seq=event.seq
    )


def calls_showing(
    ledger: "Ledger",
    block: BlockId,
    *,
    at_seq: Seq | None = None,
    leaf: Seq | None = None,
) -> tuple[Seq, ...]:
    """**从块找去向**(E-6 / D-CAP-4):哪几次调用把这块发出去过,按 seq 升序。

    只看 ``Called`` 随行的 manifest;没带 manifest 的外来 ``Called`` 答不了,如实略过
    (不猜"大概也发了")。
    """
    hits: list[Seq] = []
    for event in ledger.calls(at_seq=at_seq, leaf=leaf):
        manifest = event.manifest_value
        if manifest is None:
            continue
        if block in manifest.block_ids():
            hits.append(event.seq)
    return tuple(hits)
