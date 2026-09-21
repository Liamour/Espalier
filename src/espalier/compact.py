"""压缩生命周期(DESIGN.md v2.7 + V0-PLAN §3.2 的 H1 合流)。

两步,中间隔着一次模型调用(**库不调模型**,A8):

    req = ledger.prepare_compact(targets)      # 纯读、零事件:自行渲染压缩视图并定影
    summary_text = harness_calls_the_model(req.prompt)
    block = ledger.commit(req, summary_text, model=…, params=…)   # 原子写四条

``prepare`` **自行渲染**压缩视图并把 manifest 定影(v2.7),``commit`` 机械把它转成
``CallHash``——于是"摘要器当时看到了什么"这条链一次都不断(E-4)。

**原子性(V0-CHOICE,第三段第一个要裁的形状)**:``commit`` 要落四条事件
(``Called(purpose="compact")`` + ``Appended(summary)`` + ``Returned`` + ``Compacted``),
而 V0 的 ``emit`` 是逐条写、逐条 fsync,没有事务。V0 的做法是
:meth:`espalier.Ledger.emit_all` —— **先在内存里把四条全部构造并封链,一条构造不出来就
一条都不写**(校验失败 ⇒ 零事件),然后一次写四行 + 一次 fsync。它挡住的是"校验到一半
才发现不行"这类失败;挡不住的是"写第三行时断电"——那时文件里会留下两行,
:meth:`espalier.Ledger.open` 的 torn-tail 规则只认最后一行,所以恢复出来会是一次
**没有 Compacted 的半截压缩**。这个残留窗口如实记在这里,不假装它不存在:要彻底关掉它,
得给 JSONL 加一条事务标记行,那是格式层的改动,不在 V0 的射程里。

**``targets ≡ covers ∖ kept``**(v2.7):等式成立 ⇒ ``Compacted.targets`` 留 ``None``,
读者自己算;不成立 ⇒ 携显式 targets。``commit`` **不因为等式不成立而拒绝**——
compaction 是 harness 的决定,库只如实记账(check 永不拦截的同一条纪律)。

**被覆盖块的内容身份**(G-V0-3 裁决,2026-09-06 签):``prepare`` 在钉住 ``base_seq``
的同时算出 ``covers``(``[min seq(targets), base_seq]``)与 ``covered``——``covers ∖ kept``
里**闭合**块按账本次序的 TreeHash 序列——封进 :class:`CompactRequest`;``commit`` 把它
原样写进 ``Compacted.covered_tree_hashes``,``Compacted.identity`` 只读它。区间内还开着的
复合没有 TreeHash(未闭合),不入这个序列;它们已按 v2.7 视同隐式 pin 进了 ``kept``
(见 :attr:`CompactRequest.open_descendants`),本就在 ``covers ∖ kept`` 之外。

**instruction 入清单**(C-30,2026-09-06 签):给了 ``instruction`` 时,``prepare`` 把它作为
第一条 ``ManifestEntry(source=其 BlockId)`` 写进清单,**坐标按 prompt**——prompt 的字节是
``指令文本 + "\\n\\n" + 渲染字节``,于是压缩视图那些条目的 ``byte_range`` / ``escapes`` /
``fence_offsets`` 整体后移;``CompactRequest.rendering`` 因此就是**prompt 的** ``Rendering``
(``rendering.text == prompt``,``rendering.manifest == manifest``),``verify(rendering=)`` /
``verify_shown`` 拿它逐条对得上。E-4.Q7 量到的洞是:指令文本进了 prompt 却不进 manifest,
"摘要器看到了什么"在这一格上说了假话。不给 ``instruction`` 时清单与 v0.18 逐字节相同。
"""

from __future__ import annotations

from dataclasses import dataclass, replace as dc_replace
from datetime import datetime
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Sequence

from ._freeze import freeze_tuple
from .block import Block
from .calls import call_hash, inlay_records, params_canon, put_inlays
from .events import Appended, Called, Compacted, Kept, Returned, SeqRange
from .hashes import TreeHash, bytes_hash
from .ids import CANON_RAW, BlockId, Seq
from .manifest import Manifest, ManifestEntry
from .origin import Arrived, LlmDerived, Origin
from .payload import Text
from .render import RenderSpec, Rendering, render

if TYPE_CHECKING:  # pragma: no cover
    from .ledger import Ledger

__all__ = [
    "CompactRequest",
    "CommitReceipt",
    "prepare_compact",
    "commit",
]


@dataclass(frozen=True)
class CompactRequest:
    """``prepare_compact`` 的产物(v2.7)。**纯值**:拿着它可以隔一段时间再 commit。

    ``base_seq`` 钉住账本位置:prepare 与 commit 之间(实测中位 2.6 分钟)新写进来的块
    按构造**界外**——它们不在 ``covers`` 里,``CommitReceipt.conflicts`` 会把它们列出来。

    ``open_descendants``:区间内还开着的复合。v2.7 定的处置是"枚举 + **视同隐式 pin**",
    所以它们已经被并进 :attr:`keep` 的 ``pins`` 里了(开着的东西没有 Block 值,压缩它
    等于压掉一个还在写的半成品)。
    """

    targets: tuple[BlockId, ...]
    base_seq: Seq
    manifest: Manifest
    prompt: str
    instruction: BlockId | None = None
    keep: Kept = Kept()
    open_descendants: tuple[BlockId, ...] = ()
    rendering: Rendering | None = None
    """定影那一次渲染的全文(A0 观察面:prompt 只是文本,findings / parts 也是事实)。
    C-30:给了 ``instruction`` 时这是 **prompt 的** ``Rendering``(指令在前),
    ``rendering.text == prompt`` 且 ``rendering.manifest == manifest`` 恒成立。"""
    covered: tuple[TreeHash, ...] | None = None
    """``covers ∖ kept`` 里闭合块按账本次序的 TreeHash(G-V0-3,2026-09-06 签)。

    **``None`` = 这份请求没说**(手工构造、或从别处搬来的请求);只有
    :func:`prepare_compact` 定影出来的才是元组,``()`` 则是"已知覆盖了零块"。
    ``commit`` **原样透传**——``None`` 落成 ``Compacted.covered_tree_hashes = None``,
    于是 ``Compacted.identity`` 是 ``None``、``check`` 报 ``identity_unavailable``(info)。
    默认给 ``()`` 会让"没说"冒充"零块",算出一个**看起来正当却与被覆盖内容无关**的
    CompactionId(A9);默认**值**可以有,默认**动作**不可以有(A0)。"""

    def __post_init__(self) -> None:
        object.__setattr__(self, "targets", freeze_tuple(self.targets))
        object.__setattr__(self, "open_descendants", freeze_tuple(self.open_descendants))
        if self.covered is not None:
            object.__setattr__(self, "covered", freeze_tuple(self.covered))


@dataclass(frozen=True)
class CommitReceipt:
    """``commit`` 的回执(v2.7:"CommitReceipt 报告窗口内冲突与 open_descendants 处置")。

    ``commit`` 本身按 v2.7 的签名返回 ``Block``;要看回执走
    :meth:`espalier.Ledger.commit_with_receipt`(A0:观察面不能只存在于返回值的缝里)。
    """

    summary: Block
    called: Called
    appended: Appended
    returned: Returned
    compacted: Compacted
    targets_match: bool
    conflicts: tuple[BlockId, ...] = ()
    open_descendants: tuple[BlockId, ...] = ()

    def __post_init__(self) -> None:
        for name in ("conflicts", "open_descendants"):
            object.__setattr__(self, name, freeze_tuple(getattr(self, name)))


def _descendants(ledger: "Ledger", roots: Iterable[BlockId], *, at_seq: Seq | None) -> set[BlockId]:
    """存储树上的后代闭包(含自己)。"""
    seen: set[BlockId] = set()
    frontier = list(roots)
    while frontier:
        current = frontier.pop()
        if current in seen:
            continue
        seen.add(current)
        for link in ledger.children(current, at_seq=at_seq):
            frontier.append(link.child)
    return seen


def _instruction_text(instruction: Block | None) -> str:
    if instruction is None:
        return ""
    payload = instruction.payload
    if isinstance(payload, Text) and isinstance(payload.body, str):
        return payload.body
    return ""


#: prompt 里指令文本与渲染字节之间的分隔(v0.17 起就是这两个换行,C-30 只是把它写成名字)。
INSTRUCTION_SEPARATOR: str = "\n\n"


def _with_instruction(rendering: Rendering, instruction: Block, spec: RenderSpec) -> Rendering:
    """把指令块接在渲染前面,得到 **prompt 的** ``Rendering``(C-30)。

    * 指令文本原样在前(与 v0.18 的 ``prompt`` 字节相同——不转义、不围栏,保住既有行为),
      之后 :data:`INSTRUCTION_SEPARATOR`,再是渲染字节;指令文本为空(载荷不是内联文本)
      时 prompt 就是渲染字节,指令条目是零字节 ``(0, 0)``——它确实在这次调用里,只是没有
      可发的字节(与 ``Absent`` 的零字节条目同一读法)。
    * 第一条条目 ``source = instruction.id``,``shown`` 按 prompt 字节算;``role`` 走
      ``spec.role_of(instruction.origin)``;它占 ``message_index = 0``,后面的条目在
      首条 role 相同时并入同一条消息、不同时整体 +1(与 render 的分组规则同一条)。
    * 渲染条目的 ``byte_range``、``escapes``、``fence_offsets`` 整体后移;``excluded`` /
      ``excluded_why`` / ``spec_digest`` / ``parts`` / ``findings`` / ``inlays`` 原样搬。

    **指令文本不转义、不围栏**(保住 v0.18 的 prompt 字节;``escapes`` 里也不会多出它的
    条目)。代价如实记下:指令首行若正好是 ``<<<esp`` 那样的围栏行,
    :func:`espalier.verify_fence_invariant` 对 ``req.rendering`` 会把它报成一处违规——
    那是真的,prompt 里确实出现了一行伪围栏,库不该假装没有。要不要让指令也走
    ``body()`` 转义(prompt 字节因此与 v0.18 不同)是**另一条提案**,记为候选,不在 C-30
    的射程里:C-30 只把"指令进 manifest"这一格补上,不动 prompt 的字节。
    """
    head = _instruction_text(instruction)
    head_bytes = head.encode("utf-8")
    text = f"{head}{INSTRUCTION_SEPARATOR}{rendering.text}" if head else rendering.text
    shift = len(head_bytes) + len(INSTRUCTION_SEPARATOR.encode("utf-8")) if head else 0
    role = spec.role_of(instruction.origin)
    entries = rendering.manifest.entries
    bump = 0 if entries and entries[0].role == role else 1
    first = ManifestEntry(
        source=instruction.id,
        byte_range=(0, len(head_bytes)),
        shown=bytes_hash(head_bytes, canon=CANON_RAW),
        role=role,
        message_index=0,
    )
    shifted = tuple(
        dc_replace(
            entry,
            byte_range=(entry.byte_range[0] + shift, entry.byte_range[1] + shift),
            message_index=entry.message_index + bump,
        )
        for entry in entries
    )
    old = rendering.manifest
    manifest = Manifest(
        entries=(first,) + shifted,
        excluded=old.excluded,
        spec_digest=old.spec_digest,
        escapes=tuple((a + shift, b + shift) for a, b in old.escapes),
        excluded_why=old.excluded_why,
    )
    return Rendering(
        text=text,
        parts=rendering.parts,
        manifest=manifest,
        findings=rendering.findings,
        fence_offsets=tuple(offset + shift for offset in rendering.fence_offsets),
        inlays=rendering.inlays,
    )


def _covers(ledger: "Ledger", targets: Sequence[BlockId], base_seq: Seq) -> SeqRange:
    """位置事实:``[min seq(targets), base_seq]``(半开写成 ``stop = base_seq + 1``)。"""
    stop = Seq(int(base_seq) + 1)
    seqs = [int(ledger.seq_of(block_id, at_seq=base_seq)) for block_id in targets]
    start = Seq(min(seqs)) if seqs else stop
    return SeqRange(start=start, stop=stop)


def _covered_tree_hashes(
    ledger: "Ledger", covers: SeqRange, keep: Kept, base_seq: Seq
) -> tuple[TreeHash, ...]:
    """``covers ∖ kept`` 里**闭合**块按账本次序(seq 升序)的 TreeHash(G-V0-3)。

    ``block_ids(at_seq=base_seq)`` 只给闭合块且已按 seq 排序;开态复合没有 TreeHash,
    不入序列(见模块 docstring)。

    **``kept`` 里点名的复合本身不入序列,但它的子块入**:过滤只看 ``block_id not in
    kept_ids``,子块自己的 id 不在 ``kept`` 里、seq 又在 ``covers`` 内,于是照进。后果:
    一个被 ``kept`` 保下来的复合,**它的子内容变了 ⇒ CompactionId 变**。这不是新规矩,
    是既有 ``targets ≡ covers ∖ kept`` 读法(v2.7)的直接后果——那条等式按 **id** 做差,
    从来不含"保住父块就连同保住整棵子树"的意思;要连子树一起保,把子块也写进
    :class:`espalier.Kept`。
    """
    kept_ids = set(keep.all_ids())
    return tuple(
        ledger.tree_hash_of(block_id, at_seq=base_seq)
        for block_id in ledger.block_ids(at_seq=base_seq)
        if block_id not in kept_ids and int(ledger.seq_of(block_id, at_seq=base_seq)) in covers
    )


def prepare_compact(
    ledger: "Ledger",
    targets: Sequence[BlockId],
    *,
    instruction: Block | None = None,
    keep: Kept | None = None,
    spec: RenderSpec | None = None,
    as_of: datetime | None = None,
) -> CompactRequest:
    """定影一次压缩请求。**纯读、零事件**(v2.7)。

    做四件事:钉 ``base_seq``;枚举区间内的开复合并把它们并进 ``pins``;渲染压缩视图
    (``roots=targets``)得 manifest 与 prompt;把这些封进一个不可变的
    :class:`CompactRequest`。
    """
    from .ledger import BlockNotFound, LedgerError

    chosen = tuple(targets)
    if ledger.tip is None:
        raise LedgerError("cannot prepare a compaction on an empty ledger")
    for block_id in chosen:
        if not ledger.has(block_id):
            raise BlockNotFound(f"cannot compact {block_id}: it is not on this ledger")

    base_seq = Seq(int(ledger.tip))
    scope = _descendants(ledger, chosen, at_seq=base_seq)
    open_descendants = tuple(
        handle.id for handle in ledger.open_composites(at_seq=base_seq) if handle.id in scope
    )

    base_keep = keep if keep is not None else Kept()
    pins = tuple(base_keep.pins) + tuple(
        block_id for block_id in open_descendants if block_id not in base_keep.pins
    )
    merged = Kept(
        head=base_keep.head, anchors=base_keep.anchors, tail=base_keep.tail, pins=pins
    )

    view = ledger.view(roots=chosen, at_seq=base_seq)
    render_spec = spec if spec is not None else RenderSpec()
    rendering = render(view, render_spec, as_of=as_of)
    if instruction is not None:
        rendering = _with_instruction(rendering, instruction, render_spec)  # C-30

    covers = _covers(ledger, chosen, base_seq)
    covered = _covered_tree_hashes(ledger, covers, merged, base_seq)

    return CompactRequest(
        targets=chosen,
        base_seq=base_seq,
        manifest=rendering.manifest,
        prompt=rendering.text,
        instruction=None if instruction is None else instruction.id,
        keep=merged,
        open_descendants=open_descendants,
        rendering=rendering,
        covered=covered,
    )


#: ``commit`` 的 ``**event_fields`` **白名单**(C-31 扩,2026-09-15 签):四个事件类
#: (``Called`` / ``Appended`` / ``Returned`` / ``Compacted``)都合法的基类三格。
#: 白名单而不是黑名单:黑名单放得过 ``external_ids``(C-31 扩当时的例子;C-38 后它已是具名
#: 参数,不再经这条路)/ ``reason`` / 拼错的键,那些键要到
#: :meth:`espalier.Ledger.emit_all` 构造事件时才炸,而那时 ``store.put`` 已经落了字节,
#: "零事件"就成了"零事件但 CAS 脏了"。
#: 白名单封住的是**键**这一维;三格的**取值**库不校验(A5)——白名单键给了非法取值
#: (``actor="alice"``、``annotations=42``)仍要到 ``emit_all`` 构造记录时才抛 ``TypeError``,
#: 那时 ``req.manifest`` 的字节已进 CAS。这不是本项新开的路:拿一个 ``made`` 非法的
#: ``Block`` 当 ``result`` 在 C-31 扩之前就同形;CAS 是 append-only、按哈希去重,改对取值
#: 重跑同一 ``req`` 时那串字节被正式引用。
COMMIT_EVENT_FIELDS: frozenset[str] = frozenset({"ignorable", "annotations", "actor"})


def commit(
    ledger: "Ledger",
    req: CompactRequest,
    result: str | Block,
    *,
    model: str | None = None,
    params: Mapping[str, Any] | None = None,
    kind: str = "summary",
    purpose: str = "compact",
    usage: Mapping[str, int] | None = None,
    keep_rendering: bool = False,
    external_ids: Mapping[str, str] | None = None,
    **event_fields: Any,
) -> CommitReceipt:
    """原子落四条事件并返回回执(v2.7 + D-CAP-1)。

    ``result`` 收 ``str | Block``:摘要不强制扁平(A1 在最重要的写入口不退化为字符串边界)。
    给 ``Block`` 时**原样落账**——它的 ``origin`` 是调用者的事实,库不改料(A6);给 ``str``
    时库替你造一个 ``LlmDerived(call=…, sources=targets, instruction=…, model=…)``——
    ``sources`` 是 targets 这个**已知**元组(C-4 的三值语义下它不是 ``None``:压缩的来源
    正是被压缩的那些块,库知道、就写下)。

    C-27 的两路在这里同 :func:`espalier.served`,**两路互不对账**:``Called.inlays`` 的键
    来自 ``req.rendering.inlays``(来源事实),进 CAS 的字节来自 ``req.rendering.manifest``
    里那些 ``is_inlay_key(source)`` 的条目(实发段)。库自己 render 出来的 ``Rendering``
    两路恒一致;harness 手工拼一个 ``Rendering`` 交进来时可以不一致——``inlays`` 里有的
    键 manifest 里没有条目(取不回文本),或 manifest 里的 Inlay 条目 ``inlays`` 里没有
    来源事实。**库不在这里校验、也不补齐**:两边都是 harness 声称的事实,如实各存各的,
    要对账走 :func:`espalier.verify_shown`。

    ``req.covered`` 同样**原样透传**:``None``(请求没说)落成
    ``Compacted.covered_tree_hashes = None``,``identity`` 因此是 ``None``,不编一个。

    **C-31 扩(2026-09-15 签):三格补齐**——压缩路径原先写不进"谁执行的 / 省了多少 /
    当次整份实发字节",而主线 append / replace / annotate / close 收 ``**event_fields``、
    :func:`espalier.served` 收 ``keep_rendering``、:func:`espalier.returned` 收 ``usage``:

    * ``usage``:**原样**落这次压缩的 ``Returned.usage``。库不解释键名、不求和(A5)。
    * ``keep_rendering=True``:把 ``req.rendering.data`` ``put`` 进 CAS 并把 ``ContentRef``
      留在 ``Called.rendering``(与 :func:`espalier.served` 的 C-28 同义)。**默认关**。
      ``req.rendering is None``(手工造的 :class:`CompactRequest`)而开关开着 ⇒
      ``LedgerError`` 且**零事件**:与同函数 inlays 遇 ``None`` 静默跳过**不同调**,理由是
      静默会让 harness 以为整份字节在 CAS 里、事后按 ``Called.rendering`` 去取却取到
      ``None``(A9:不制造一个看起来正当的假象)。
    * ``**event_fields``:**原样广播给四条事件**(``Called`` / ``Appended`` /
      ``Returned`` / ``Compacted``)——"这次压缩是谁执行的"就是四条同一个 ``actor``。
      只接 :data:`COMMIT_EVENT_FIELDS` 里的基类三格 ``ignorable`` / ``annotations`` /
      ``actor``;其余键在**任何 ``store.put`` / 任何 ULID 消耗之前**抛 ``TypeError``(只让
      一条局部 import 在它前面;零事件、零 CAS 写——这一保证覆盖**键**这一维,取值合法性
      见 :data:`COMMIT_EVENT_FIELDS`)。合并次序固定 ``{**own_fields, **event_fields}``。

    ``Ledger.commit`` / ``Ledger.commit_with_receipt`` 的签名不动:它们的 ``**options``
    今天就原样转到这里,三个新参数从那两个入口一样传得进来。

    **身份不变(限本条)**:``Called.body`` 恒输出 ``rendering`` 键、``Returned.body`` 恒
    输出 ``usage``、``to_record`` 恒输出 ``ignorable`` / ``annotations`` / ``actor``,所以
    **本条**三参都不传时不改动任何字节——把摘要块换成调用者自带的块、其余不变,四行 JSON
    与 C-31 扩之前逐字节相同;``CallHash`` / ``CompactionId`` / ``StateHash`` 的公式一字
    未动,``FORMAT_VERSION`` 不因本条升。

    但**同批的 C-35** 给 ``LlmDerived`` 加了 ``remainder`` 并按 §0 ① 无条件写全键,而
    ``result`` 传 ``str`` 时这里自造的摘要块出身正是 ``LlmDerived``:于是默认调用写出的
    ``Appended`` 行多一个 ``"remainder": null``、该行与其后两行的 ``link`` 随之变。那是
    C-35 的记录形变、由 ``FORMAT_VERSION`` 4 → 5 盖住,**不是 C-31 扩造成的**。传了值的那条
    事件起,它与其后各条的 ``ChainHash`` 都变(链式:``usage`` 落 ``Returned``,于是
    ``Returned`` 与 ``Compacted`` 两条变;``actor`` / ``ignorable`` / ``keep_rendering`` 四条
    全变)——那是记录内容不同,不是记录形变。**例外是 ``annotations``**:事件顶层的作者通道
    按 G-V0-1 被 :func:`espalier.events.strip_identity_free` 剔出瘦记录,广播出去的
    ``annotations`` 不动任何链——审计链盖得住压缩的 ``actor``,盖不住它的 ``annotations``。

    **C-38(2026-09-15 签)**:``external_ids`` **只落**这次压缩的 ``Returned.external_ids``
    (P-18 的 provider 请求 / 响应 id 与遥测 id),``None`` ⇒ 空映射,取值库不解释(A5);它是
    ``Returned`` 专属、**不进** :data:`COMMIT_EVENT_FIELDS` 也不广播给另外三条事件。
    ``Returned.body`` 恒输出 ``external_ids`` 键(默认 ``{}``)⇒ 不传时字节不变;传了值那条
    ``Returned`` 起 ``ChainHash`` 变。``reason``(C-9 的出错载荷)**不接**:压缩路径的
    ``outcome`` 恒 ``"ok"``,没有落点。取值非法(非 ``canon_json`` 可编码)与白名单三格
    同形:在 ``emit_all`` 处抛、零事件,但 ``req.manifest`` 的字节已进 CAS(库不校验取值,A5)。
    """
    from .ledger import DuplicateBlockId, LedgerError

    unknown = sorted(set(event_fields) - COMMIT_EVENT_FIELDS)
    if unknown:
        raise TypeError(
            "commit() got unexpected event field(s) "
            f"{', '.join(repr(k) for k in unknown)}; "
            f"**event_fields only takes {sorted(COMMIT_EVENT_FIELDS)}"
        )
    if keep_rendering and req.rendering is None:
        raise LedgerError(
            "commit(keep_rendering=True) needs req.rendering; this CompactRequest has none"
        )

    manifest_key = req.manifest.hash()
    model_name = model or ""
    call = call_hash(manifest_key, model_name, params)

    if isinstance(result, Block):
        summary = result
    else:
        summary = Block.create(
            result,
            kind=kind,
            id=ledger.ulids.next_block_id(),
            origin=Origin(
                made=LlmDerived(
                    call=call,
                    sources=req.targets,
                    instruction=req.instruction,
                    model=model,
                ),
                arrived=Arrived.ASSISTANT_SLOT,
            ),
        )

    if ledger.has(summary.id):
        raise DuplicateBlockId(f"summary block {summary.id} is already on this ledger")

    summary_tree_hash = summary.tree_hash(
        lambda block_id: ledger.tree_hash_of(block_id), store=ledger.store
    )

    covers = _covers(ledger, req.targets, req.base_seq)

    kept_ids = set(req.keep.all_ids())
    covered = {
        block_id
        for block_id in ledger.block_ids(at_seq=req.base_seq)
        if int(ledger.seq_of(block_id)) in covers
    }
    covered |= {
        handle.id
        for handle in ledger.open_composites(at_seq=req.base_seq)
        if int(handle.opened_seq) in covers
    }
    implied = covered - kept_ids
    targets_match = implied == set(req.targets)

    conflicts = tuple(
        block_id
        for block_id in ledger.block_ids()
        if int(ledger.seq_of(block_id)) > int(req.base_seq)
    )

    ledger.store.put(req.manifest.to_bytes())
    # C-27:压缩调用也是一次 Called——Inlay 的来源事实与实发段同样入记录 / 入 CAS。
    inlays = inlay_records(req.rendering) if req.rendering is not None else {}
    if req.rendering is not None:
        put_inlays(ledger, req.rendering)
    # C-31 扩:整份实发字节进 CAS(默认关;req.rendering 为 None 已在函数开头拒过)。
    kept_rendering = ledger.store.put(req.rendering.data) if keep_rendering else None  # type: ignore[union-attr]

    def _fields(own: dict[str, Any]) -> dict[str, Any]:
        """C-31 扩:``{**own_fields, **event_fields}``,次序固定、守卫已先行。"""
        return {**own, **event_fields}

    called_seq = Seq(int(ledger.next_seq))
    events = ledger.emit_all(
        [
            (
                Called,
                _fields(
                    {
                        "call": call,
                        "manifest": manifest_key,
                        "model": model_name,
                        "params_canon": params_canon(params),
                        "purpose": purpose,
                        "manifest_value": req.manifest,
                        "inlays": inlays,
                        "rendering": kept_rendering,
                    }
                ),
            ),
            (
                Appended,
                _fields(
                    {
                        "block": summary.id,
                        "into": None,
                        "gap": 0,
                        "tree_hash": summary_tree_hash,
                        "block_value": summary,
                    }
                ),
            ),
            (
                Returned,
                _fields(
                    {
                        "called_seq": called_seq,
                        "outcome": "ok",
                        "output": summary.id,
                        "usage": usage,
                        # C-38:Returned.external_ids 不是 Optional(EMPTY_MAPPING 默认),
                        # None ⇒ 空映射,与 calls.py `returned` 的 `external_ids or {}` 同写法。
                        "external_ids": external_ids or {},
                    }
                ),
            ),
            (
                Compacted,
                _fields(
                    {
                        "summary": summary.id,
                        "summary_tree_hash": summary_tree_hash,
                        "covers": covers,
                        "kept": req.keep,
                        "base_seq": req.base_seq,
                        "targets": None if targets_match else req.targets,
                        "covered_tree_hashes": req.covered,
                    }
                ),
            ),
        ]
    )
    called, appended, came_back, compacted = events
    if not isinstance(compacted, Compacted):  # pragma: no cover - 只可能是本函数自己写错
        raise LedgerError("commit wrote the wrong event shape")

    return CommitReceipt(
        summary=ledger.get_block(summary.id),
        called=called,  # type: ignore[arg-type]
        appended=appended,  # type: ignore[arg-type]
        returned=came_back,  # type: ignore[arg-type]
        compacted=compacted,
        targets_match=targets_match,
        conflicts=conflicts,
        open_descendants=req.open_descendants,
    )
