"""``render``:指定渲染形式 r1(DESIGN.md v2.8/2.9 + V0-PLAN §3.2 的 H3 半边)。

``render`` 是**纯函数**:同 ``(target, spec, as_of)`` → 同字节。它永不读环境时钟、永不
执行调用者代码、永不调模型(A8)。Inlay 由 harness 在 render 之前物化,render 只接产物。

七条固定映射(v2.8):

1. **编写面**:``title`` → ATX 标题**按树深**;深度 > 6 用非标题信号并记实际深度。
2. **运行面**:复合边界开合 ``kind`` 信封——``<<<esp {kind} id={id} trust={t}>>> …
   <<<esp end {id}>>>``;开合条件 = **信任变化 ∨ 复合边界**;同信任连续叶段不重复围。
3. **防伪 = 递归自闭合转义**(D6):正文行匹配 ``^\\*<<<esp`` 或含 ``<!-- esp:`` 者
   再前置一杠;逆变换剥一层。
4. ``gap`` / ``tail_gap`` 重放空行。
5. ``Blob`` → 占位行 + 独立 :class:`MediaPart`,``ManifestEntry.part`` 绑定。
6. 折叠块 → 一行摘要 + ``((esp:expand id))``。
7. ``Manifest.expandable()`` 返回本次**真实发出**的折叠把手集。

**render 不变量**(X13 D-X13-15):*输出中每一条第 0 列 ``<<<esp`` 行都是 render 自己发出
的信封行*。这是字节级判定,比"解析器解析得动"严——严格解析器会在第一条坏行上中止,
从而掩盖字节里已经出现的伪围栏行。:func:`verify_fence_invariant` 是那条判定,
:attr:`Rendering.fence_offsets` 是它的证据。

X13 十七条规范空白在 V0 的读法(每条都是 **V0-CHOICE**,与 X13 参考实现同侧):

======================  ====================================================================
D-X13-1 属性字符集      白名单 ``[^\\s<>]+``;不合法 **抛** :class:`RenderError`(不静默、
                        不降级)。X13:该白名单对语料里 290 个真实 kind 名拒收 0 个
D-X13-2 ``life``        **不渲染**——judge.md 已裁 Life 枚举退役,信封头里不再有它
D-X13-3 ``trust``       渲染成枚举**名**(``TOOL`` / ``USER`` …),同样受白名单管
D-X13-4 "行"的定义      仅以 ``\\n`` 分行;转义侧与解析侧同一个定义;渲染后不再做任何行归一
D-X13-5 顺序            **c1 在前(仅编写面)、转义在后**;渲染输出不再归一
D-X13-6 行首谓词        严格第 0 列,转义侧与解析侧同一个谓词
D-X13-7 ``<!-- esp:``   "含"取**行内任意位置**(judge.md D6(a) 的理由);杠加在行首;
                        锚点行 = 开信封行之后独占一行 ``<!-- esp:id={id} -->``
D-X13-8 双规则同行      只加一杠、只剥一杠
D-X13-9 叶子定界        空正文 ⇒ 一条空行;正文自带的尾换行原样保留
D-X13-11 大小写         区分大小写,两侧一致
D-X13-12 头终止         行尾 ``>>>``(且属性禁 ``>`` 使二者等价)
D-X13-13 id 唯一        同一次渲染内 id 重复 ⇒ :class:`RenderError`(render 不变量)
D-X13-14 转义区间       以**字节区间**入 ``Manifest.escapes``
D-X13-17 规范化形式     转义与解析都在渲染输出那一种形式上;render 之后**不得**再做任何
                        兼容规范化(NFKC/NFKD 会把全角尖括号映成 ASCII,凭空造出围栏行)
======================  ====================================================================

**六处 V0 补签名**(v2.8 引用了却没给的东西,理由逐条写在字段旁):``MediaPart``、
``RenderSpec.role_of`` / ``.fold``、``Rendering.findings`` / ``.fence_offsets``、
``render(..., resolve=)``。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Final, Mapping, Sequence

from ._freeze import EMPTY_MAPPING, freeze_mapping, freeze_tuple
from .block import Block, ChildLink
from .check import Finding
from .hashes import bytes_hash
from .ids import CANON_C1, CANON_RAW, BlockId
from .manifest import (
    Absent,
    InlayKey,
    Manifest,
    ManifestEntry,
    Source,
    SpecDigest,
    spec_digest,
)
from .origin import Arrived, Computed, Origin, Realm, address_canon, default_realm, trust_class
from .payload import Blob, ContentRef, ContentStore, Payload, canonicalize, payload_size
from .view import View

__all__ = [
    "FENCE_MARK",
    "ANCHOR_MARK",
    "ATTR_PATTERN",
    "RenderError",
    "IdMark",
    "Inlay",
    "MediaPart",
    "RenderSpec",
    "Rendering",
    "DEFAULT_ROLE_OF",
    "default_role",
    "hits_escape",
    "escape_line",
    "unescape_line",
    "escape_text",
    "unescape_text",
    "fence_open_line",
    "fence_close_line",
    "anchor_line",
    "render",
    "verify_fence_invariant",
]


# --------------------------------------------------------------------------- 文法常量

#: 信封标记。区分大小写(D-X13-11 V0-CHOICE)。
FENCE_MARK: Final[str] = "<<<esp"
#: 锚点标记(v2.8 ③ 的第二条转义规则)。
ANCHOR_MARK: Final[str] = "<!-- esp:"
#: 属性值白名单(D-X13-1 V0-CHOICE):非空、无任何空白、无尖括号。
ATTR_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[^\s<>]+$")

_ESCAPE_RE: Final[re.Pattern[str]] = re.compile(r"^\\*<<<esp")


class RenderError(Exception):
    """render 做不了这件事。**只在字节层面无法诚实输出时抛**——属性值破坏信封边界、
    同一次渲染里 id 重复。一致性问题一律走 ``check``,不在这里抛。"""


def hits_escape(line: str) -> bool:
    """这一行要不要加杠(v2.8 ③)。两条规则取**析取**,只加一杠(D-X13-8)。"""
    return bool(_ESCAPE_RE.match(line)) or ANCHOR_MARK in line


def escape_line(line: str) -> str:
    """行级转义。``hit('\\\\'+L) ⇔ hit(L)``,所以它在行集合上单射、可逆(X13 §2.1)。"""
    return "\\" + line if hits_escape(line) else line


def unescape_line(line: str) -> str:
    """行级逆变换:剥一层。只剥一层(D-X13-8)。"""
    if line.startswith("\\") and hits_escape(line):
        return line[1:]
    return line


def escape_text(text: str) -> tuple[str, tuple[int, ...]]:
    """整段转义。返回 ``(转义后文本, 被转义的行下标)``。只以 ``\\n`` 分行(D-X13-4)。"""
    lines = text.split("\n")
    escaped = [escape_line(line) for line in lines]
    hit = tuple(i for i, (a, b) in enumerate(zip(lines, escaped)) if a != b)
    return "\n".join(escaped), hit


def unescape_text(text: str) -> str:
    """整段逆变换。``unescape_text(escape_text(x)[0]) == x``。"""
    return "\n".join(unescape_line(line) for line in text.split("\n"))


def _attr(name: str, value: object) -> str:
    """校验并给出一个信封属性值。不合白名单 ⇒ :class:`RenderError`(D-X13-1)。"""
    text = str(value)
    if not ATTR_PATTERN.match(text):
        raise RenderError(
            f"envelope attribute {name}={text!r} is not in the r1 whitelist [^\\s<>]+ "
            "(D-X13-1:属性值带换行/空白/尖括号能把信封头劈成两条围栏行,是纯机械破出)"
        )
    return text


def fence_open_line(kind: str, block_id: BlockId, trust: object) -> str:
    """``<<<esp {kind} id={id} trust={t}>>>``。**没有 ``life=``**(D-X13-2)。"""
    trust_text = trust.name if isinstance(trust, Enum) else str(trust)
    return (
        f"{FENCE_MARK} {_attr('kind', kind)} id={_attr('id', block_id)} "
        f"trust={_attr('trust', trust_text)}>>>"
    )


def fence_close_line(block_id: BlockId) -> str:
    return f"{FENCE_MARK} end {_attr('id', block_id)}>>>"


def anchor_line(block_id: BlockId) -> str:
    """``<!-- esp:id={id} -->``,开信封行之后独占一行(D-X13-7(c) 的 X13 那一形)。"""
    return f"{ANCHOR_MARK}id={_attr('id', block_id)} -->"


# --------------------------------------------------------------------------- 规格


class IdMark(Enum):
    """id 锚点的三档(v2.8)。

    V0-CHOICE:**信封头恒带 ``id=``**——闭合行要靠它配对,没有 id 就没有信封。
    ``IdMark`` 管的是**另发一条锚点行**这件事:``NONE`` 不发;``ANCHORS`` 每个信封开行
    之后发一条;``ALL`` 再给每个叶段也发一条。design-L 记的"块尾内联"那一形 V0 未取
    (D-X13-7(c):两形状 owner 未裁,内联形零实例)。
    """

    NONE = 0
    ANCHORS = 1
    ALL = 2


@dataclass(frozen=True)
class Inlay:
    """渲染期计算的产物(v2.9)。**harness 在 render 前物化**;render 只接产物(A8)。

    参与 manifest、无存储身份。"默认不落账"是 r1 惯例而非机制拒收——``append`` 接受
    任何 Origin(A0)。

    ``after``(C-7 ①,2026-09-06 签):锚——落在该**顶层**块之后;``None`` = 最前
    (v0.17 的行为不变)。锚块不在本次渲染的顶层序列里(被排除 / 不在场)时 Inlay 落尾,
    并报 ``anchor_absent``(warning)——不静默丢。
    """

    key: InlayKey
    origin: Computed
    text: str
    after: BlockId | None = None


@dataclass(frozen=True)
class MediaPart:
    """独立消息部件(v2.8 ⑤)。**v2 章只作类型注解出现过一次、无签名**,此处补齐。

    三个字段就是 P-16 的信息层三条:字节(``data``:CAS 取回键)、``mime``、以及
    "与哪次调用的哪个部件绑定"(``index`` ↔ ``ManifestEntry.part``)。
    ``data`` 存 ``ContentRef`` 而不是裸 bytes:部件可以很大,取回是 store 的事,
    而 ``ContentRef.size`` 让不取回也能做预算(v2.2 的同一条理由)。
    """

    index: int
    mime: str
    data: ContentRef


#: ``Arrived`` → wire 角色的默认全函数表(G-V0-4 要 ``ManifestEntry.role``)。
#: **可被 ``RenderSpec.role_of`` 整表替换**——与 ``trust_of`` / ``realm_of`` 同型。
DEFAULT_ROLE_OF: Final[Mapping[Arrived, str]] = {
    Arrived.USER_SLOT: "user",
    Arrived.ASSISTANT_SLOT: "assistant",
    Arrived.TOOL_RESULT_SLOT: "tool",
    Arrived.ATTACHMENT: "user",
    Arrived.SYSTEM_PROMPT: "system",
    Arrived.NOTIFICATION: "user",
    Arrived.LOG_ONLY: "log",
    Arrived.IMPORT: "user",
    Arrived.UNKNOWN: "user",
}


def default_role(origin: Origin) -> str:
    """默认 wire 角色 = ``arrived`` 的函数。

    V0-CHOICE 两处:① 角色取自 **arrived**(账本机械保证的那一轴,D-CAP-7)而不是
    ``made``(那是适配器的证词);② ``LOG_ONLY`` 落 ``"log"`` —— 它**不是** wire 角色,
    渲染里出现它本身就是一条 Finding(``log_only_rendered``),不拿 ``"user"`` 遮掉。
    """
    return DEFAULT_ROLE_OF.get(origin.arrived, "user")


def _fn_name(fn: Callable[..., Any]) -> str:
    return f"{getattr(fn, '__module__', '?')}.{getattr(fn, '__qualname__', repr(fn))}"


@dataclass(frozen=True)
class RenderSpec:
    """渲染规格(v2.8 + 三处 V0 补签名)。

    ``fence`` 默认开、**可显式关**(真生效);关掉之后"信任未标记"是 ``check`` 的
    Deviation,不是 render 的强制——A0。V0 把那条 Deviation 就地报成
    :attr:`Rendering.findings` 里的 ``trust_undeclared``,不必等到 check。

    **三处 V0 补签名**:

    * ``role_of``:G-V0-4 要条目带 role,而 v2.8 没给 render 任何取 role 的入口。
      与 ``trust_of`` / ``realm_of`` 同型:一张可整表替换的全函数表。
    * ``fold``:v2.8 ⑥ 要"折叠块一行摘要",却没有任何"哪些块折叠"的入口——没有入口
      的机制等于不存在(A0)。折叠**策略**仍在 harness 手上,库只收结果。
    * ``exclude``:§3.2 已给(与 ``View.without`` 合并进 ``Manifest.excluded``)。

    **C-7(2026-09-06 签)三处**:

    * ``absent``:``((锚, Absent), …)``——"发出了、但账本上没有"的条目,落在锚块之后
      (``None`` = 最前),render 产出 ``ManifestEntry(source=Absent, byte_range=(o, o),
      shown=bytes_hash(b""))``,``role`` / ``message_index`` 取锚块的。无锚 ⇒ ``"system"``
      (C-23,2026-09-06 签:无锚 Inlay 与无锚 Absent 统一;v0.18 的 Absent 曾落
      ``ManifestEntry`` 的默认值 ``"user"``,两条路不一致)。
    * ``exclude_why``:``{id: 理由}``;render 把 ``exclude ∪ exclude_why.keys()`` 当排除集,
      理由随行到 ``Manifest.excluded_why``。
    * ``Inlay.after``:见 :class:`Inlay`。
    """

    form: str = "r1"
    ids: IdMark = IdMark.NONE
    fence: bool = True
    trust_of: Callable[[Origin], object] = trust_class
    realm_of: Callable[[Origin], Realm] = default_realm
    role_of: Callable[[Origin], str] = default_role
    inlays: tuple[Inlay, ...] = ()
    exclude: frozenset[BlockId] = frozenset()
    fold: frozenset[BlockId] = frozenset()
    absent: tuple[tuple[BlockId | None, Absent], ...] = ()
    exclude_why: Mapping[BlockId, str] = EMPTY_MAPPING

    def __post_init__(self) -> None:
        object.__setattr__(self, "inlays", freeze_tuple(self.inlays))
        object.__setattr__(self, "exclude", frozenset(self.exclude))
        object.__setattr__(self, "fold", frozenset(self.fold))
        object.__setattr__(
            self, "absent", tuple((anchor, absent) for anchor, absent in self.absent)
        )
        object.__setattr__(self, "exclude_why", freeze_mapping(self.exclude_why))

    @property
    def excluded_ids(self) -> frozenset[BlockId]:
        """[派] 本规格的排除集 = ``exclude ∪ exclude_why.keys()``(C-7 ③)。"""
        return frozenset(self.exclude) | frozenset(self.exclude_why)

    def with_(self, **changes: Any) -> "RenderSpec":
        """派生一份改了几处的规格(A0:frozen 值要有改法)。"""
        from dataclasses import replace as dc_replace

        return dc_replace(self, **changes)

    def digest(self, *, as_of: datetime | None = None) -> SpecDigest:
        """规格摘要,进 ``Manifest.spec_digest`` ⇒ 进 ``ManifestHash``。

        V0-CHOICE:三张可替换的表按 ``模块.限定名`` 入摘要——换一张表就换一个摘要,
        这是能做到的最诚实的近似;同名不同体的两个 lambda 分不开,如实记在这里。
        ``as_of`` 也入摘要:同一份视图在两个"现在"下渲染,得到的是两次不同的实发。
        """
        return spec_digest(
            {
                "form": self.form,
                "ids": self.ids.name,
                "fence": self.fence,
                "trust_of": _fn_name(self.trust_of),
                "realm_of": _fn_name(self.realm_of),
                "role_of": _fn_name(self.role_of),
                "inlays": [
                    [str(i.key), i.origin.provider, i.origin.params_canon, i.text, i.after]
                    for i in self.inlays
                ],
                "exclude": sorted(self.exclude),
                "fold": sorted(self.fold),
                "absent": [[anchor, absent.reason] for anchor, absent in self.absent],
                "exclude_why": sorted((str(k), v) for k, v in self.exclude_why.items()),
                "as_of": None if as_of is None else as_of.isoformat(),
            }
        )


@dataclass(frozen=True)
class Rendering:
    """render 的三件返回(v2.8)+ 两件 V0 补签名。

    * ``findings``:未声明信任、log-only 被渲染、编写面 c1 改了字节、子块取不回——
      这些都是**事实**,render 既不该静默吞掉也不该抛(A0/A9),于是有了这一格。
    * ``fence_offsets``:render 自己发出的每一条信封行的字节偏移。它是 D-X13-15 那条
      render 不变量的证据,:func:`verify_fence_invariant` 用它做字节级判定。
    * ``inlays``(C-27,2026-09-06 签):本次**真实发出**的 Inlay,按发出次序。它们的
      来源事实(provider / params / 锚)随 :func:`espalier.calls.served` 落进
      ``Called.inlays``——``Rendering`` 不带,``served`` 就只拿得到 manifest 里的键。
    """

    text: str
    parts: tuple[MediaPart, ...]
    manifest: Manifest
    findings: tuple[Finding, ...] = ()
    fence_offsets: tuple[int, ...] = ()
    inlays: tuple[Inlay, ...] = ()

    def __post_init__(self) -> None:
        for name in ("parts", "findings", "fence_offsets", "inlays"):
            object.__setattr__(self, name, freeze_tuple(getattr(self, name)))

    @property
    def data(self) -> bytes:
        """输出的 UTF-8 字节。``ManifestEntry.byte_range`` 就是这串字节上的坐标。"""
        return self.text.encode("utf-8")

    def segment(self, entry: ManifestEntry) -> bytes:
        """取某条条目的实发字节(E-1 的下半段)。"""
        start, stop = entry.byte_range
        return self.data[start:stop]


def verify_fence_invariant(rendering: Rendering) -> tuple[int, ...]:
    """render 不变量的**字节级**判定(D-X13-15)。

    返回**违规**的字节偏移元组:输出里第 0 列以 ``<<<esp`` 开头、而 render 从未在该偏移
    发出过信封行的那些行。空元组 = 不变量成立。

    为什么按字节判而不按解析器事件判:严格解析器会在第一条不成形的行上中止,从而掩盖
    字节里已经出现的伪围栏行(X13 修复轮 2 在全表捉到 5 处这种情形)。
    """
    data = rendering.data
    emitted = set(rendering.fence_offsets)
    marker = FENCE_MARK.encode("utf-8")
    offending: list[int] = []
    offset = 0
    for line in data.split(b"\n"):
        if line.startswith(marker) and offset not in emitted:
            offending.append(offset)
        offset += len(line) + 1
    return tuple(offending)


# --------------------------------------------------------------------------- 渲染内核


@dataclass
class _Draft:
    """条目草稿。``shown`` 在最后一步从**最终字节**里算,于是它永远钉的是实发字节。"""

    source: Source
    start: int
    stop: int
    part: int | None = None
    fence: str | None = None
    role: str = "user"
    message_index: int = 0
    folded: bool = False


class _Out:
    """带字节计数的输出缓冲。偏移一律按 **UTF-8 字节**算(byte_range 的坐标系)。"""

    __slots__ = ("_chunks", "_size")

    def __init__(self) -> None:
        self._chunks: list[str] = []
        self._size = 0

    @property
    def offset(self) -> int:
        return self._size

    def write(self, text: str) -> None:
        if not text:
            return
        self._chunks.append(text)
        self._size += len(text.encode("utf-8"))

    def text(self) -> str:
        return "".join(self._chunks)


class _Renderer:
    """一次渲染的全部可变状态。``render()`` 建一个、用一次、丢掉——所以它仍是纯函数。"""

    def __init__(
        self,
        spec: RenderSpec,
        *,
        resolve: Callable[[BlockId], Any] | None,
        store: ContentStore | None,
        as_of: datetime | None,
        exclude: frozenset[BlockId] = frozenset(),
        at_seq: Any = None,
        leaf: Any = None,
    ) -> None:
        self.spec = spec
        self.resolve = resolve
        self.store = store
        self.as_of = as_of
        #: **本次渲染真正生效的排除集** = ``RenderSpec.exclude`` ∪ ``View.without``。
        #: §3.2 说这两个入口"合并进 ``Manifest.excluded``",那它们在**下钻子块时**也必须
        #: 同义——只认一个而 ``Manifest.excluded`` 两个都报,manifest 就说了假话
        #: (声称排除、字节却发了出去)。见 :func:`render`。
        self.exclude = frozenset(exclude)
        #: 渲染这一刻的时间线坐标(``View.at_seq`` / ``View.leaf``)。开态复合取子块走账本
        #: 边表,不带上它们就会取到 ``at_seq`` 之后写进来的子块——同一个
        #: ``(view, spec, as_of)`` 在账本继续写入后给出不同字节,render 就不再是纯函数。
        self.at_seq = at_seq
        self.leaf = leaf
        self.out = _Out()
        self.drafts: list[_Draft] = []
        self.parts: list[MediaPart] = []
        self.findings: list[Finding] = []
        self.escapes: list[tuple[int, int]] = []
        self.fence_offsets: list[int] = []
        self.inlays: list[Inlay] = []
        self.seen_ids: set[BlockId] = set()
        self.message_index = -1
        self.last_role: str | None = None

    # ---- 报告

    def note(
        self, rule: str, severity: str, subject: str, detail: str
    ) -> None:
        self.findings.append(
            Finding(rule=rule, severity=severity, subject=subject, detail=detail)  # type: ignore[arg-type]
        )

    # ---- 低层写

    def gap(self, count: int) -> None:
        for _ in range(max(0, int(count))):
            self.out.write("\n")

    def line(self, text: str) -> int:
        start = self.out.offset
        self.out.write(text)
        self.out.write("\n")
        return start

    def fence_open(
        self, kind: str, block_id: BlockId, trust: object
    ) -> tuple[int, int] | None:
        """写一条开信封行,返回它的字节区间(不含行尾换行);``fence=False`` ⇒ ``None``。"""
        if not self.spec.fence:
            return None
        line = fence_open_line(kind, block_id, trust)
        start = self.line(line)
        self.fence_offsets.append(start)
        span = (start, start + len(line.encode("utf-8")))
        if self.spec.ids in (IdMark.ANCHORS, IdMark.ALL):
            self.line(anchor_line(block_id))
        return span

    def fence_close(self, block_id: BlockId) -> None:
        if not self.spec.fence:
            return
        start = self.line(fence_close_line(block_id))
        self.fence_offsets.append(start)

    def body(self, text: str) -> tuple[int, int]:
        """写一段正文:**逐行转义**、以 ``\\n`` 相连,返回它的字节区间。

        **每一行都自带行终止符**(X13 G7/G9 的读法):正文按 ``\\n`` 切成的每一行各占输出
        的一行,所以 ``"a\\n"`` 是两行("a" 与空行)、``""`` 是一条空行。少了最后那个终止符,
        正文自带的尾换行就会被下一行的行首吃掉,往返立刻不成立(X13 seed F42/F45)。

        返回的区间**不含**那个收尾的换行——它是框架不是正文,于是
        ``rendering.segment(entry)`` 逐字节等于转义后的正文(A9 的反面:也不多算)。
        """
        lines = text.split("\n")
        start = self.out.offset
        for index, raw_line in enumerate(lines):
            if index:
                self.out.write("\n")
            escaped = escape_line(raw_line)
            at = self.out.offset
            self.out.write(escaped)
            if escaped != raw_line:
                self.escapes.append((at, self.out.offset))
        stop = self.out.offset
        self.out.write("\n")
        return start, stop

    # ---- 条目

    def entry(
        self,
        source: Source,
        span: tuple[int, int],
        *,
        role: str,
        fence: str | None = None,
        part: int | None = None,
        folded: bool = False,
    ) -> None:
        if role != self.last_role:
            self.message_index += 1
            self.last_role = role
        self.drafts.append(
            _Draft(
                source=source,
                start=span[0],
                stop=span[1],
                part=part,
                fence=fence if self.spec.fence else None,
                role=role,
                message_index=self.message_index,
                folded=folded,
            )
        )

    # ---- 取块

    def realm_of(self, origin: Origin) -> Realm:
        return self.spec.realm_of(origin)

    def role_of(self, origin: Origin, block_id: BlockId | None = None) -> str:
        """wire 角色 + ``log_only_rendered`` 警告。

        ``block_id`` 是 ``Finding.subject``:说不出是哪一块的警告等于没说(A9)。
        它可空只为一处——裸 Inlay 没有块 id;那一路不走这里。
        """
        role = self.spec.role_of(origin)
        if origin.arrived is Arrived.LOG_ONLY:
            self.note(
                "log_only_rendered",
                "warning",
                str(block_id) if block_id is not None else "",
                "a block that arrived LOG_ONLY is being rendered into the model's view",
            )
        return role

    def claim_id(self, block_id: BlockId) -> None:
        """同一次渲染内 id 唯一(D-X13-13:列为 render 不变量)。"""
        if block_id in self.seen_ids:
            raise RenderError(
                f"block id {block_id} appears twice in one rendering; "
                "闭合行按 id 配对,重复 id 会让信封归属不可判(D-X13-13)"
            )
        self.seen_ids.add(block_id)

    def children_of(self, node: Any) -> tuple[tuple[Any, int], ...]:
        """子节点与它们的 ``gap``。开态复合走账本边表(``so_far()`` 丢 gap)。

        边表按**本次渲染的** ``at_seq`` / ``leaf`` 取(``resolve`` 早就这么做了,边表这一路
        原先漏了):不带时间坐标的边表是"账本当下",会让纯函数在账本继续写入后改答案。
        """
        if isinstance(node, Block):
            links: Sequence[ChildLink] = node.children
        else:  # OpenComposite:边表在账本上
            links = node.ledger.children(node.id, at_seq=self.at_seq, leaf=self.leaf)
        out: list[tuple[Any, int]] = []
        for link in links:
            if link.child in self.exclude:
                continue
            child = self.resolve(link.child) if self.resolve is not None else None
            if child is None:
                self.note(
                    "unresolved_child",
                    "warning",
                    str(node.id),
                    f"child {link.child} cannot be resolved here; it is not rendered",
                )
                continue
            out.append((child, link.gap))
        return tuple(out)

    def payload_text(self, block: Block) -> tuple[str | None, str | None]:
        """块的正文与"取不回的理由"。二者恰有一个非 ``None``。"""
        payload = block.payload
        if payload is None:
            return "", None
        if isinstance(payload, Blob):
            return None, "blob"
        body = payload.body
        if isinstance(body, str):
            text = body
        else:
            if self.store is None or not self.store.has(body.hash):
                return None, f"payload {body.hash} is not in reach of this rendering"
            try:
                text = self.store.get(body).decode("utf-8")
            except (KeyError, UnicodeDecodeError) as exc:
                return None, f"payload {body.hash} cannot be decoded as text: {exc}"
        if self.realm_of(block.origin) == "authoring" and payload.canon == CANON_C1:
            canonical = canonicalize(text, CANON_C1)
            if canonical != text:
                self.note(
                    "canon_changed_bytes",
                    "warning",
                    str(block.id),
                    "authoring render canonicalised the payload to c1 and the bytes changed "
                    "(D-X13-5:c1 在前、转义在后;这一步改了字节,如实报出来)",
                )
            text = canonical
        return text, None

    def authoring_title(self, node: Any) -> str:
        """编写面标题行的正文(D-X13-5:**c1 在前、转义在后**)。

        V0-CHOICE:``title`` 没有自己的 ``canon`` 声明(它不是载荷),而编写面就是 c1 的
        辖区,所以编写面渲染的标题一律先过 c1、再由 :meth:`body` 逐行转义。改了字节就报
        ``canon_changed_bytes``——和载荷那一路同一条规矩,不静默(A9)。
        运行面的 ``title``(:meth:`emit_composite`)不走这里:运行期默认 ``raw``,
        静默改字节正是 X14 抓到的 L1 丢失。
        """
        title = node.title or ""
        canonical = canonicalize(title, CANON_C1)
        if canonical != title:
            self.note(
                "canon_changed_bytes",
                "warning",
                str(node.id),
                "authoring render canonicalised the title to c1 and the bytes changed "
                "(D-X13-5:c1 在前、转义在后;这一步改了字节,如实报出来)",
            )
        return canonical

    # ---- 叶

    def emit_leaf(self, block: Block, *, fence: str | None, depth: int) -> None:
        self.claim_id(block.id)
        role = self.role_of(block.origin, block.id)
        if self.spec.ids is IdMark.ALL:
            self.line(anchor_line(block.id))

        if block.id in self.spec.fold:
            span = self.body(self._fold_summary(block))
            self.entry(block.id, span, role=role, fence=fence, folded=True)
            return

        payload = block.payload
        if isinstance(payload, Blob):
            if not isinstance(payload.data, ContentRef):
                # C-6:字节不在手——没有 MediaPart 可发,占位行说清它在哪、并报 finding。
                span = self.body(self._external_placeholder(block, payload))
                self.entry(block.id, span, role=role, fence=fence)
                return
            index = len(self.parts)
            self.parts.append(
                MediaPart(index=index, mime=payload.mime, data=payload.data)
            )
            span = self.body(
                f"((esp:media part={index} mime={payload.mime} "
                f"bytes={payload_size(payload)}))"
            )
            self.entry(block.id, span, role=role, fence=fence, part=index)
            return

        text, problem = self.payload_text(block)
        if text is None:
            self.note("payload_unresolved", "warning", str(block.id), problem or "")
            span = self.body(f"((esp:absent {block.id}))")
            self.entry(block.id, span, role=role, fence=fence)
            return

        span = self.body(text)
        self.entry(block.id, span, role=role, fence=fence)

    def _external_placeholder(self, block: Block, payload: Blob) -> str:
        """外部附件(C-6)的占位行。字节不在手就说不在手,不发一个空 MediaPart 冒充。"""
        where = address_canon(payload.data)
        locator = self._address_locator(where)
        self.note(
            "payload_external",
            "info",
            str(block.id),
            f"blob bytes are not in hand; only an external address {locator!r} ({where['address']})",
        )
        size = _size_or_none(payload)
        tail = "" if size is None else f" bytes={size}"
        # 占位行不是信封行(不受 D-X13-1 白名单管),定位符原样写;伪围栏由 ``body`` 的逐行转义挡。
        return f"((esp:media external={locator or where['address']} mime={payload.mime}{tail}))"

    @staticmethod
    def _address_locator(where: dict[str, object]) -> str:
        """占位行里的定位符:模型视图不丢地址信息(A9)。

        ``FileAddress`` ⇒ ``path``;``UrlAddress`` ⇒ ``url``;``OpaqueAddress`` ⇒
        ``scheme?k=v&…``(params 按键排序;溢出内容的取回定位符靠 params 里的 id 才找得回去,
        只写 scheme 会把它从模型视图里抹掉)。
        """
        if where.get("path"):
            return str(where["path"])
        if where.get("url"):
            return str(where["url"])
        scheme = str(where.get("scheme") or "")
        params = where.get("params")
        if isinstance(params, dict) and params:
            query = "&".join(f"{k}={params[k]}" for k in sorted(params, key=str))
            return f"{scheme}?{query}"
        return scheme

    def _fold_summary(self, block: Block) -> str:
        """折叠块的一行摘要 + 展开把手(v2.8 ⑥)。机械、确定,不含任何策略。"""
        text, _ = self.payload_text(block)
        snippet = ""
        if block.title:
            snippet = block.title
        elif text:
            snippet = next((line for line in text.split("\n") if line.strip()), "")
        snippet = snippet.replace("\n", " ")[:80]
        size = _size_or_none(block.payload) if block.payload is not None else 0
        shown = "?" if size is None else str(size)
        return f"{block.kind}: {snippet} ({shown}B) ((esp:expand {block.id}))"

    # ---- 锚定条目(C-7)

    def emit_inlay(self, inlay: Inlay, *, role: str) -> None:
        span = self.body(inlay.text)
        self.entry(inlay.key, span, role=role)
        self.inlays.append(inlay)

    def emit_absent(self, absent: Absent, *, role: str) -> None:
        """零字节条目:``byte_range=(o, o)``,``shown`` 在 ``finish`` 里从空切片算出。"""
        at = self.out.offset
        self.entry(absent, (at, at), role=role)

    # ---- 复合

    def emit_composite(self, node: Any, *, depth: int) -> None:
        self.claim_id(node.id)
        origin: Origin = node.origin
        trust = self.spec.trust_of(origin)
        role = self.role_of(origin, node.id)
        frame = self.fence_open(node.kind, node.id, trust)
        if frame is not None:
            # V0-CHOICE:**复合自己发出的字节就是它的信封头**,所以那一行以它为来源入
            # manifest。于是 E-1(字节区间 → 块)在框架行上也答得出,``block_ids()`` 也
            # 含得住"这次渲染里出现过哪些复合"(X16 要的那件事)。叶段共用的那道围栏
            # **不**记条目——它的标签已经在每个成员的 ``fence`` 上了,再记一条就成了
            # 把第一个叶子的 id 冒充成一个不存在的容器。
            self.entry(node.id, frame, role=role, fence=node.kind)

        if node.title:
            span = self.body(node.title)
            self.entry(node.id, span, role=role, fence=node.kind)

        # v2.3 说 ``payload=None ⇔ 纯容器复合``,但类型允许两者兼有,而库不拦(A0)。
        # 既然字节在那里就必须发出去(A9),此处显式定义它的渲染:正文在子块之前。
        payload = getattr(node, "payload", None)
        if payload is not None:
            text, problem = self.payload_text(node)
            if text is None:
                self.note("payload_unresolved", "warning", str(node.id), problem or "")
                span = self.body(f"((esp:absent {node.id}))")
                self.entry(node.id, span, role=role, fence=node.kind)
            elif text:
                span = self.body(text)
                self.entry(node.id, span, role=role, fence=node.kind)

        self.emit_sequence(
            self.children_of(node),
            depth=depth + 1,
            outer_trust=trust,
            outer_fence=node.kind,
        )
        self.gap(getattr(node, "tail_gap", 0) or 0)
        self.fence_close(node.id)

    # ---- 编写面

    def emit_authoring(self, node: Any, *, depth: int) -> None:
        """编写面:``title`` → ATX **按树深**(v2.8 ①)。

        V0-CHOICE:"树深"只数**发过标题的**祖先——一个无标题的文档根不该把它下面的
        ``# 一级标题`` 压成 ``##``。深度 > 6 时改用非标题信号,并把实际深度写在那一行里。
        """
        self.claim_id(node.id)
        origin: Origin = node.origin
        role = self.role_of(origin, node.id)
        inner_depth = depth

        if node.title:
            inner_depth = depth + 1
            level = depth + 1
            title = self.authoring_title(node)
            if level <= 6:
                span = self.body("#" * level + " " + title)
            else:
                # v2.8 ①:深度 > 6 用非标题信号,并在 manifest 记实际深度——深度就写在
                # 发出的那一行里,于是它被 byte_range 与 shown 一并钉住(V0-CHOICE)。
                span = self.body(f"((esp:depth {level})) {title}")
                self.note(
                    "depth_over_six",
                    "info",
                    str(node.id),
                    f"authoring title at tree depth {level} exceeds ATX's six levels",
                )
            self.entry(node.id, span, role=role)

        payload = getattr(node, "payload", None)
        if payload is not None:
            if isinstance(payload, Blob) and not isinstance(payload.data, ContentRef):
                span = self.body(self._external_placeholder(node, payload))
                self.entry(node.id, span, role=role)
            elif isinstance(payload, Blob):
                index = len(self.parts)
                self.parts.append(
                    MediaPart(index=index, mime=payload.mime, data=payload.data)
                )
                span = self.body(f"((esp:media part={index} mime={payload.mime}))")
                self.entry(node.id, span, role=role, part=index)
            else:
                text, problem = self.payload_text(node)
                if text is None:
                    self.note("payload_unresolved", "warning", str(node.id), problem or "")
                    span = self.body(f"((esp:absent {node.id}))")
                else:
                    span = self.body(text)
                self.entry(node.id, span, role=role)

        for child, gap in self.children_of(node):
            self.gap(gap)
            self.emit_node(child, depth=inner_depth, outer_trust=None, outer_fence=None)
        self.gap(getattr(node, "tail_gap", 0) or 0)

    # ---- 调度

    @staticmethod
    def _is_composite(node: Any) -> bool:
        if isinstance(node, Block):
            return node.is_composite
        return True  # OpenComposite 恒为复合(它的内容是账本上的边)

    def emit_node(
        self, node: Any, *, depth: int, outer_trust: object, outer_fence: str | None
    ) -> None:
        if self.realm_of(node.origin) == "authoring":
            self.emit_authoring(node, depth=depth)
        elif self._is_composite(node):
            self.emit_composite(node, depth=depth)
        else:
            trust = self.spec.trust_of(node.origin)
            if outer_trust is not None and trust == outer_trust:
                self.emit_leaf(node, fence=outer_fence, depth=depth)
            else:
                self.fence_open(node.kind, node.id, trust)
                self.emit_leaf(node, fence=node.kind, depth=depth)
                self.fence_close(node.id)

    def emit_sequence(
        self,
        items: Sequence[tuple[Any, int]],
        *,
        depth: int,
        outer_trust: object,
        outer_fence: str | None,
    ) -> None:
        """一层兄弟。**同信任连续叶段不重复围**(v2.8 ②)就在这里落地。"""
        index = 0
        total = len(items)
        while index < total:
            node, gap = items[index]
            authoring = self.realm_of(node.origin) == "authoring"
            if authoring or self._is_composite(node):
                self.gap(gap)
                self.emit_node(
                    node, depth=depth, outer_trust=outer_trust, outer_fence=outer_fence
                )
                index += 1
                continue

            trust = self.spec.trust_of(node.origin)
            if outer_trust is not None and trust == outer_trust:
                self.gap(gap)
                self.emit_leaf(node, fence=outer_fence, depth=depth)
                index += 1
                continue

            # 一段同信任的连续叶子 ⇒ 一道围栏
            end = index
            while end < total:
                candidate, _ = items[end]
                if self.realm_of(candidate.origin) == "authoring":
                    break
                if self._is_composite(candidate):
                    break
                if self.spec.trust_of(candidate.origin) != trust:
                    break
                end += 1
            run = items[index:end]
            head = run[0][0]
            self.gap(run[0][1])
            self.fence_open(head.kind, head.id, trust)
            for position, (member, member_gap) in enumerate(run):
                if position:
                    self.gap(member_gap)
                self.emit_leaf(member, fence=head.kind, depth=depth)
            self.fence_close(head.id)
            index = end

    # ---- 收尾

    def finish(
        self,
        excluded: Sequence[BlockId],
        spec_hash: SpecDigest,
        excluded_why: Mapping[BlockId, str] = EMPTY_MAPPING,
    ) -> Rendering:
        text = self.out.text()
        data = text.encode("utf-8")
        entries = tuple(
            ManifestEntry(
                source=draft.source,
                byte_range=(draft.start, draft.stop),
                shown=bytes_hash(data[draft.start : draft.stop], canon=CANON_RAW),
                part=draft.part,
                fence=draft.fence,
                role=draft.role,
                message_index=draft.message_index,
                folded=draft.folded,
            )
            for draft in self.drafts
        )
        if not self.spec.fence:
            self.findings.append(
                Finding(
                    rule="trust_undeclared",
                    severity="warning",
                    subject="",
                    detail="RenderSpec.fence is off: this rendering declares no trust at all "
                    "(v2.8:未标记是 check 的 Deviation,不是 render 的强制)",
                )
            )
        manifest = Manifest(
            entries=entries,
            excluded=tuple(excluded),
            spec_digest=spec_hash,
            escapes=tuple(self.escapes),
            excluded_why={k: v for k, v in excluded_why.items() if k in set(excluded)},
        )
        return Rendering(
            text=text,
            parts=tuple(self.parts),
            manifest=manifest,
            findings=tuple(self.findings),
            fence_offsets=tuple(self.fence_offsets),
            inlays=tuple(self.inlays),
        )


def _size_or_none(payload: Payload) -> int | None:
    """``payload_size`` 的不抛版:字节不在手(C-6 外部附件无 total)⇒ ``None``。"""
    try:
        return payload_size(payload)
    except KeyError:
        return None


# --------------------------------------------------------------------------- 入口


def render(
    target: View | Block | Any,
    spec: RenderSpec = RenderSpec(),
    *,
    as_of: datetime | None = None,
    resolve: Callable[[BlockId], Any] | None = None,
    store: ContentStore | None = None,
) -> Rendering:
    """把一个视图 / 一个块 / 一个开态复合渲染成 r1(v2.8)。**纯函数**。

    ``target`` 收 :class:`~espalier.View`(账本的一个切面)、``Block``、或
    ``OpenComposite``——X16:**渲染必须接受开态**(74.2% 的轮 ≥2 次请求),开态的内容
    经账本边表取,``shown`` 照样把它钉死。

    **两个 V0 补参数**(v2.8 的 ``render`` 签名没有,但没有它们就渲染不了裸块):

    * ``resolve``:``children`` 存的是 id(D2),裸 ``Block`` 手上没有账本就解不开子块。
      给 ``View`` 时自动接上账本,不必自己传。
    * ``store``:外置载荷的取回处。同样在给 ``View`` 时自动接上。

    ``as_of`` 只进 ``spec_digest``:库**永不读环境时钟**,陈旧度注记是 harness 在 render
    之前物化成 :class:`Inlay` 的事(v2.9/A8)。

    **两个排除入口是同义的**(§3.2):``View.without`` 与 ``RenderSpec.exclude`` 在这里并成
    一个集合,顶层过滤与子块下钻共用它,然后一并留痕进 ``Manifest.excluded``。
    C-7 ③:``RenderSpec.exclude_why`` 的键也在这个集合里,理由随行进 ``Manifest.excluded_why``。

    **锚定(C-7 ①②)**:``Inlay.after`` / ``RenderSpec.absent`` 的锚是**顶层**块;锚块
    发完(含它的闭合信封)之后紧接着发锚定条目,``role`` 取锚块的。无锚者在最前,``role``
    一律 ``"system"``(C-23,2026-09-06 签:Inlay 与 Absent 两条路统一;锚丢失落尾者同);
    锚块不在顶层序列里的落尾并报 ``anchor_absent``。同信任连续叶段的围栏在锚点处断开——
    中间插了别的内容,本来就不该同围。
    """
    at_seq: Any = None
    leaf: Any = None
    spec_exclude = spec.excluded_ids
    if isinstance(target, View):
        ledger = target.ledger
        at_seq, leaf = target.at_seq, target.leaf
        # 两个排除入口在这里**合成一个集合**(§3.2:"与 View.without 合并进
        # Manifest.excluded")。合并必须发生在**渲染之前**而不是只发生在留痕上:
        # 下钻子块时只认其中一个,就会出现"manifest 声称排除、字节却发了出去"。
        exclude = spec_exclude | frozenset(target.without)
        items: tuple[Any, ...] = tuple(
            node for node in target.blocks() if node.id not in exclude
        )
        if resolve is None:
            def resolve_from_view(block_id: BlockId) -> Any:
                return ledger.find(block_id, at_seq=target.at_seq, leaf=target.leaf)

            resolve = resolve_from_view
        if store is None:
            store = ledger.store
        base_excluded = list(target.excluded())
    else:
        exclude = spec_exclude
        items = (target,) if target.id not in exclude else ()
        base_excluded = []

    for block_id in sorted(spec_exclude):
        if block_id not in base_excluded:
            base_excluded.append(block_id)

    renderer = _Renderer(
        spec,
        resolve=resolve,
        store=store,
        as_of=as_of,
        exclude=exclude,
        at_seq=at_seq,
        leaf=leaf,
    )

    # 锚定表(C-7,2026-09-06 签;v0.17 的"Inlay 一律在最前"是 after=None 的特例)。
    inlays_after: dict[BlockId | None, list[Inlay]] = {}
    for inlay in spec.inlays:
        inlays_after.setdefault(inlay.after, []).append(inlay)
    absent_after: dict[BlockId | None, list[Absent]] = {}
    for anchor, absent in spec.absent:
        absent_after.setdefault(anchor, []).append(absent)

    for inlay in inlays_after.pop(None, ()):
        renderer.emit_inlay(inlay, role="system")
    for absent in absent_after.pop(None, ()):
        renderer.emit_absent(absent, role="system")  # C-23:与无锚 Inlay 同 role

    segment: list[tuple[Any, int]] = []
    for node in items:
        segment.append((node, 0))
        if node.id not in inlays_after and node.id not in absent_after:
            continue
        renderer.emit_sequence(tuple(segment), depth=0, outer_trust=None, outer_fence=None)
        segment = []
        # C-7 偏离(已申报):单子只对 absent 写了"role 取锚块的";锚定的 Inlay 这里也取锚块的
        # role(同一 message_index)。无锚 Inlay / Absent 一律 system(C-23,2026-09-06 签)
        # ——锚定的意思就是"跟在那条消息里",无锚的意思就是"harness 放在最前的那一段"。
        role = spec.role_of(node.origin)
        for inlay in inlays_after.pop(node.id, ()):
            renderer.emit_inlay(inlay, role=role)
        for absent in absent_after.pop(node.id, ()):
            renderer.emit_absent(absent, role=role)
    if segment:
        renderer.emit_sequence(tuple(segment), depth=0, outer_trust=None, outer_fence=None)

    for anchor, inlays in inlays_after.items():
        for inlay in inlays:
            renderer.note(
                "anchor_absent",
                "warning",
                str(inlay.key),
                f"Inlay.after={anchor} is not a top-level block of this rendering; placed at the end",
            )
            renderer.emit_inlay(inlay, role="system")
    for anchor, absents in absent_after.items():
        for absent in absents:
            renderer.note(
                "anchor_absent",
                "warning",
                str(anchor),
                f"absent entry {absent.reason!r} is anchored after {anchor}, which is not a "
                "top-level block of this rendering; placed at the end",
            )
            renderer.emit_absent(absent, role="system")  # C-23

    return renderer.finish(base_excluded, spec.digest(as_of=as_of), spec.exclude_why)
