"""Espalier — 保证信息不丢(为 LLM)的 agent 上下文基底。

版本 0.1.0(V1)。设计依据 ``DESIGN.md`` 核心模型 v2 章与 ``docs/experiments/V0-PLAN.md`` §3
(冲突处以 §3 为准,代码里标 ``V0-CHOICE``);V1 的切法在 ``docs/experiments/V1-PLAN.md``,
三层名单在 ``docs/experiments/V1-SURFACE.md``(``v0/_surface.py`` 机械生成,owner 2026-09-08 签)。

**三层公开面(V1)**——v0.21 的 245 个顶层公开名按"谁用它"分三层,名字一个不删、
代码一行不搬,只改导出:

* **lite** = 本模块 ``__all__``,175 名。及格线 52 项参考实现引用的全部名字 + 它们签名
  里出现的类型 / 返回值 + 同族补齐(事件全集、异常全集、canon 族、codec 顶层、ContentStore
  族、记录编解码对称)。开发者 ``from espalier import …`` 拿到的就是这一层。
* **expert** = :mod:`espalier.expert`,29 名。透镜扩展点(``Lens`` / ``Shape`` /
  ``register_shape`` …)与给验证器 / 工具作者用的哈希与流水函数(``digest`` /
  ``chain_hash`` / ``seal`` / ``event_from_record`` …)。只被加分线 / 案例 / LLM 跑器引用。
* **internal** = 41 名,不从任何包级 ``__all__`` 导出,只经模块路径可达
  (``espalier.hashes.BYTES_HASH_PREFIX``、``espalier.ids.new_ulid``、
  ``espalier.persist.event_line`` …):前缀常量、域常量、行级编解码、ULID 内部工具。

为什么分层:V0 证明信息装得下、有把手;V1 要让开发者拿来就能用——顶层只留及格线所需,
高级可追溯能力另开一个入口,库内实现细节退回模块路径。分层是**导出面**的事,
分层不改 ``FORMAT_VERSION``;A10 改了 ``Injected`` 的记录形与入 ChainHash 的瘦记录,
``FORMAT_VERSION`` 3 → 4(v0.21 文件走 ``format_version_behind`` 通道,见 :mod:`espalier.persist`);
v1.1 再到 5(C-35 / C-36 加可选字段写全键,owner 2026-09-15 签,同一条通道)。

**A10 与 ``hook.*`` 注记约定(owner 2026-09-08 签)**:库只给自己要解释的信息造字段,
其余走 ``annotations``;边界是"库有函数读的字段不退注记"。机械扫描
(``docs/experiments/V1-FIELD-READERS.md``)证明 ``Injected`` 的六个字段库里零读者,
于是 :class:`~espalier.origin.Injected` 在 V1 是**无字段标记变体**(它的类型仍决定
信任档与领域),六个字段改为持有者 ``annotations`` 里的文档约定键:

======================== ==========================================================
``hook.injector``        哪个 hook / 事件名注入的
``hook.configured_by``   由谁配置(user / project / plugin / …,harness 原词,开域)
``hook.blocking``        是否阻断,写 ``"true"`` / ``"false"``;缺键 = 记录未说
``hook.decision``        harness 原词(deny / block / ask / allow / continue:false / …)
``hook.decision_scope``  call / turn / task / session …
``hook.decision_reason`` 原因原文
======================== ==========================================================

v0.18–v0.21 写的旧记录带这六键时,``block_from_record`` / ``event_from_record`` 把它们
搬进 ``annotations``(同名键已存在则不覆盖),一个字节不丢(A9)。键名是约定不是类型;
harness 想要闭词表自己校验(A0:默认值可有、默认动作不可有)。

已落地的模块:

* :mod:`espalier.ids` —— ``BlockId`` / ``LedgerId`` / ``CanonId`` / ``Seq`` + 单调 ULID
* :mod:`espalier.hashes` —— 八个互不可比的哈希型 + ``canon_json``
* :mod:`espalier.payload` —— ``Text`` / ``Blob`` / ``ContentStore`` + 规范形 ``c1``
* :mod:`espalier.origin` —— 两轴 ``Origin``、``Made`` 十变体、``Remainder``、三张全函数表
* :mod:`espalier.block` —— ``Block`` / ``ChildLink`` / ``Ref`` + TreeHash
* :mod:`espalier.events` —— 十八个事件 + ``SeqRange`` / ``Kept`` / ``Tombstone`` / ``Checkpoint``
* :mod:`espalier.ledger` —— ``Ledger`` / ``OpenComposite`` / ``Retention`` / ``Retrieval``
* :mod:`espalier.view` —— ``View``(渲染输入,H3 的一半)
* :mod:`espalier.persist` —— JSONL 流水、``LedgerHeader``、``LoadReport``
* :mod:`espalier.check` —— ``CheckReport`` / ``Finding``(纯查询,永不拦截)
* :mod:`espalier.manifest` —— ``Manifest`` / ``ManifestEntry`` / ``Absent`` / ``diff``
* :mod:`espalier.render` —— r1 渲染、``RenderSpec`` / ``Rendering`` / ``MediaPart`` / ``Inlay``
* :mod:`espalier.calls` —— H1:``CallHash`` / ``ToolCallHash`` 构造 + 四值 ``Verdict``
* :mod:`espalier.compact` —— ``CompactRequest`` / ``CommitReceipt``(v2.7 压缩生命周期)
* :mod:`espalier.lens` —— ``Skill`` / ``Memory`` / ``ToolResult``(扩展点在 :mod:`espalier.expert`)
* :mod:`espalier.codec` —— 编写面 ``parse`` / ``render_authoring``(c1 往返)

**九个 Ledger 方法不在 ``__all__`` 里**,因为它们是**方法**不是名字:
``served`` / ``returned`` / ``manifest_of`` / ``saw`` / ``verify`` / ``calls_showing``
(H1,实现在 :mod:`espalier.calls`)与 ``prepare_compact`` / ``commit`` /
``commit_with_receipt``(v2.7,实现在 :mod:`espalier.compact`)。那两个模块里的同名函数
收 ledger 作第一参数,是实现;公开 API 是 ``ledger.served(…)`` 那一形。
"""

from __future__ import annotations

from .block import Block, ChildLink, Claim, Ref
from .calls import (
    Mismatch,
    Stale,
    Unverifiable,
    Verdict,
    Verified,
    call_hash,
    find_called,
    inlay_records,
    params_canon,
    put_inlays,
    tool_call_hash,
    verify_shown,
)
from .check import CheckReport, Finding, Severity, check_ledger
from .codec import (
    KIND_CODE,
    KIND_DOCUMENT,
    KIND_OPAQUE,
    KIND_PARAGRAPH,
    KIND_SECTION,
    LEVEL_KEY,
    frontmatter_entries,
    parse,
    parse_tree,
    render_authoring,
)
from .compact import CommitReceipt, CompactRequest
from .lens import KIND_FRONTMATTER, Memory, Skill, SkillFlow, ToolResult
from .manifest import (
    Absent,
    InlayKey,
    Manifest,
    ManifestDiff,
    ManifestEntry,
    Source,
    SpecDigest,
    inlay_key,
    is_inlay_key,
    manifest_from_record,
    manifest_hash,
    manifest_to_record,
)
from .render import (
    FENCE_MARK,
    IdMark,
    Inlay,
    MediaPart,
    RenderError,
    RenderSpec,
    Rendering,
    default_role,
    fence_close_line,
    fence_open_line,
    hits_escape,
    render,
    unescape_text,
    verify_fence_invariant,
)
from .events import (
    EVENT_KINDS,
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
    InlayRecord,
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
    SeqRange,
    Tombstone,
    compaction_id,
    strip_identity_free,
)
from .ledger import (
    BlockNotFound,
    DuplicateBlockId,
    Ledger,
    LedgerError,
    OpenComposite,
    OpenCompositeAtBoundary,
    PruneReport,
    Retention,
    Retrieval,
    StillOpen,
)
from .persist import (
    FORMAT_VERSION,
    WRITER_VERSION,
    LedgerHeader,
    LoadError,
    LoadIssue,
    LoadReport,
    block_from_record,
    block_to_record,
    load,
    origin_from_record,
    origin_to_record,
    write_ledger,
)
from .view import View
from .hashes import (
    BytesHash,
    CallHash,
    ChainHash,
    CompactionId,
    ManifestHash,
    StateHash,
    ToolCallHash,
    TreeHash,
    bytes_hash,
    canon_json,
)
from .ids import (
    CANON_C1,
    CANON_RAW,
    BlockId,
    CanonId,
    LedgerId,
    Seq,
    UlidFactory,
    default_ulid_factory,
    is_ulid,
    new_block_id,
    new_ledger_id,
)
from .origin import (
    LINEAGE_FIELDS,
    MADE_VARIANTS,
    Arrived,
    Authored,
    CodeSite,
    Computed,
    ExternalAddress,
    FileAddress,
    Injected,
    LlmDerived,
    Made,
    OpaqueAddress,
    Origin,
    Parsed,
    Realm,
    Recalled,
    RecoveryClass,
    Remainder,
    Segment,
    Templated,
    ToolReturned,
    Transformed,
    TrustClass,
    UrlAddress,
    Uttered,
    address_canon,
    default_realm,
    origin_sources,
    recovery_classes,
    trust_class,
)
from .payload import (
    Blob,
    ContentRef,
    ContentStore,
    MemoryContentStore,
    Payload,
    Text,
    c1,
    canonicalize,
    payload_bytes,
    payload_bytes_hash,
    payload_size,
)

__all__ = [
    # ---- ids
    "BlockId",
    "LedgerId",
    "CanonId",
    "Seq",
    "CANON_RAW",
    "CANON_C1",
    "UlidFactory",
    "default_ulid_factory",
    "is_ulid",
    "new_block_id",
    "new_ledger_id",
    # ---- hashes
    "BytesHash",
    "TreeHash",
    "ManifestHash",
    "CallHash",
    "ToolCallHash",
    "ChainHash",
    "StateHash",
    "CompactionId",
    "canon_json",
    "bytes_hash",
    # ---- payload
    "ContentRef",
    "ContentStore",
    "MemoryContentStore",
    "Text",
    "Blob",
    "Payload",
    "c1",
    "canonicalize",
    "payload_bytes",
    "payload_bytes_hash",
    "payload_size",
    # ---- origin
    "Arrived",
    "CodeSite",
    "FileAddress",
    "UrlAddress",
    "OpaqueAddress",
    "ExternalAddress",
    "address_canon",
    "Remainder",
    "Segment",
    "Uttered",
    "Authored",
    "Parsed",
    "Templated",
    "Transformed",
    "LlmDerived",
    "ToolReturned",
    "Injected",
    "Computed",
    "Recalled",
    "Made",
    "MADE_VARIANTS",
    "Origin",
    "LINEAGE_FIELDS",
    "origin_sources",
    "RecoveryClass",
    "recovery_classes",
    "TrustClass",
    "trust_class",
    "default_realm",
    "Realm",
    # ---- block
    "ChildLink",
    "Ref",
    "Claim",
    "Block",
    # ---- events
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
    "SeqRange",
    "Kept",
    "Tombstone",
    "Checkpoint",
    "InlayRecord",
    "EVENT_KINDS",
    "strip_identity_free",
    "compaction_id",
    # ---- persist
    "FORMAT_VERSION",
    "WRITER_VERSION",
    "LedgerHeader",
    "LoadIssue",
    "LoadReport",
    "LoadError",
    "load",
    "write_ledger",
    "block_to_record",
    "block_from_record",
    "origin_to_record",
    "origin_from_record",
    # ---- ledger
    "Ledger",
    "OpenComposite",
    "Retention",
    "PruneReport",
    "Retrieval",
    "LedgerError",
    "StillOpen",
    "BlockNotFound",
    "DuplicateBlockId",
    "OpenCompositeAtBoundary",
    # ---- view
    "View",
    # ---- check
    "CheckReport",
    "Finding",
    "Severity",
    "check_ledger",
    # ---- manifest
    "SpecDigest",
    "InlayKey",
    "inlay_key",
    "is_inlay_key",
    "Absent",
    "Source",
    "ManifestEntry",
    "ManifestDiff",
    "Manifest",
    "manifest_hash",
    "manifest_to_record",
    "manifest_from_record",
    # ---- render
    "FENCE_MARK",
    "RenderError",
    "IdMark",
    "Inlay",
    "MediaPart",
    "RenderSpec",
    "Rendering",
    "default_role",
    "hits_escape",
    "unescape_text",
    "fence_open_line",
    "fence_close_line",
    "render",
    "verify_fence_invariant",
    # ---- calls(H1)
    "call_hash",
    "tool_call_hash",
    "params_canon",
    "find_called",
    "verify_shown",
    "inlay_records",
    "put_inlays",
    "Verified",
    "Mismatch",
    "Stale",
    "Unverifiable",
    "Verdict",
    # ---- compact(v2.7)
    "CompactRequest",
    "CommitReceipt",
    # ---- lens(v2.11;扩展点在 espalier.expert)
    "SkillFlow",
    "Skill",
    "Memory",
    "ToolResult",
    # ---- codec
    "KIND_DOCUMENT",
    "KIND_FRONTMATTER",
    "KIND_SECTION",
    "KIND_PARAGRAPH",
    "KIND_CODE",
    "KIND_OPAQUE",
    "LEVEL_KEY",
    "parse",
    "parse_tree",
    "render_authoring",
    "frontmatter_entries",
]
