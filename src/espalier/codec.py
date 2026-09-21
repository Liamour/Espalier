"""编写面 codec:``parse`` / ``render_authoring``(V0-PLAN §3.2;蓝本是 P1 原型)。

蓝本:``prototypes/PROTOTYPE-codec-roundtrip.html`` 里的 ``EspalierCodec``(X1 在 327 个
真实 .md 上实测 c1 往返 100%)。本模块是它的 Python 实装,加上 Espalier 的三件事:
**id 树**(D2:gap 归收容边)、**出身**(每段带 ``Parsed``)、**按段接回**(D-CAP-5)。

**往返不变量**::

    render_authoring(parse_tree(text)) == c1(text)          # 字节级,X1 的那条
    parse(render_authoring(x)) 与 x 逐字段同构(id 除外)     # 结构级

``Block.__eq__`` 含 ``id``,而每次 parse 发的是新 ULID,所以"逐字段相等"在字面上不可能
成立;要 id 也相等就得让 parse 收一张 id 表——那是导入面的事,不是往返的事。V0 因此
把不变量拆成上面两条,两条都在 ``tests/test_codec.py`` 里断言。

**五处 V0-CHOICE**:

1. **``parse`` 返回 ``Block``(根)**,而子块是分开的值(``children`` 存 id,D2)。
   于是另有 :func:`parse_tree` 一并给出 ``{id: Block}`` 索引——没有它,根块的子块就没人
   拿得住(A0:机制要完备)。``parse()`` 是它的第一个返回值。
2. **标题层级落 ``annotations["md.level"]``**。Markdown 允许跳级(``#`` 之后直接 ``###``),
   而树深不记得跳过的那一级。层级不入 TreeHash 是这一choice 的代价,如实记下:两份只差
   跳级的文档 TreeHash 相同、字节不同。(入 ``kind`` 就能进 TreeHash,但那会让 ``kind``
   变成一个带参数的判别词,代价更大。)
3. **frontmatter 双轨**:``payload`` 是**原文**(含两条 ``---``),键值另落
   ``annotations``。于是往返走原文、读取走键值,两者永不打架;重复键最后一个生效。
   **两轨各丢什么(C-37,2026-09-15 签)**:原文轨在**所选规范形内**不丢一个字节——
   frontmatter 段(含两条 ``---``)整段进 ``payload``,往返即证(不变量是上面那条
   ``== c1(text)``);默认 ``canon=CANON_C1`` 会先把 CRLF 归 LF、把只含空白的行归空行
   (见 :mod:`espalier.payload` 的 c1 定义),这一步在切块**之前**,所以"源文件字节"与
   ``payload`` 在这两种输入上不等。
   键值轨只认顶层 ``key: value`` 行,**缩进续行不进取值**——``hooks:`` 这类条目在
   ``annotations`` 上落成空串,嵌套结构只在原文轨里。要把续行也收进取值,单独调
   :func:`frontmatter_entries` 并开 ``keep_continuation=True``(它**不**经 :func:`parse` /
   :func:`parse_tree` 透传:这两条路写进 ``annotations`` 的仍是默认口径)。
4. ``path`` 是 :func:`parse` 的新参数:``Parsed.path`` 是必填字段,而 §3.2 的签名里没有
   它。默认 ``""`` = 这段文本不来自文件。
5. **``carried_of``**:D-CAP-5 说"manifest 给则按段 bytes_hash 匹配 shown 接回
   ``Parsed.carried``",但 manifest 只给得出 ``BlockId``,给不出那个块的 ``Origin``。
   给了 ``carried_of`` 就用它取回真出身;没给就落一条
   ``Transformed(op="manifest.shown", sources=[那个块])`` —— 把边留下,不假装知道出身。

**切块偏移入 ``Parsed.span``**(C-24,2026-09-06 签):解析器切每一段时手上就有它在源文本里
的位置,v0.18 没写(值在手未写)。现在每个叶段与每个小节标题行都带
``span = FileAddress(path, offset=起始行, limit=行数, total=总行数, unit="line", base=0,
version=version)``——以**行**计而不是字节:c1 只动行尾与纯空白行,不动行数,于是同一份
文件以 raw 或 c1 解析,行偏移相同、字节偏移不同;偏移要经得起规范化,就得落在
规范化不动的那根轴上。文档根没有自己的字节,``span`` 留 ``None``;``path=""``(文本不来自
文件)照样写偏移——它相对的是被解析的那段文本。``version`` 是新参数(默认 ``None``),
调用者知道文件版本就传进来,D-X15-8"地址可过期"的半边才有落点。

``total`` 是 ``body.split("\\n")`` 的计数,**不是**"有内容的行数":末尾换行之后的那个空串
照样算一行,于是 ``"a\\n"`` 的 ``total`` 是 2 而不是 1。这是切块自己用的那把尺——
``offset`` / ``limit`` 与它同一套坐标,拿 ``total`` 去和别处按"行数"数出来的数字比对之前,
先确认对方用的是哪一把。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Final, Mapping, Sequence

from .block import Block, ChildLink
from .ids import CANON_C1, BlockId, CanonId, UlidFactory, new_block_id
from .hashes import bytes_hash
from .ids import CANON_RAW
from .lens import KIND_FRONTMATTER, Shape
from .manifest import Manifest
from .origin import Arrived, FileAddress, Origin, Parsed, Transformed
from .payload import Text, canonicalize

__all__ = [
    "KIND_DOCUMENT",
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

KIND_DOCUMENT: Final[str] = "md.document"
#: ``KIND_FRONTMATTER`` 与 :mod:`espalier.lens` 同一个名字同一个取值——codec 写它、
#: 透镜读它,两处只能有一个定义处,定义处在 lens(读的那一侧定义词汇)。
KIND_SECTION: Final[str] = "md.section"
KIND_PARAGRAPH: Final[str] = "md.paragraph"
KIND_CODE: Final[str] = "md.code"
KIND_OPAQUE: Final[str] = "md.opaque"

#: 标题层级住这个 annotation 键(V0-CHOICE ②)。
LEVEL_KEY: Final[str] = "md.level"

_HEADING = re.compile(r"^(#{1,6}) (.*)$")
_RULE = re.compile(r"^(-{3,}|\*{3,}|_{3,})\s*$")
_LIST_ITEM = re.compile(r"^\s*([-*+]|\d+[.)])\s")
_LIST_CONT = re.compile(r"^\s+\S")
_OPAQUE_START = re.compile(r"^(\||<|>)")
_FM_ENTRY = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):\s?(.*)$")


def _is_blank(line: str) -> bool:
    return line.strip() == ""


def _is_fence(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("```") or stripped.startswith("~~~")


def frontmatter_entries(
    lines: Sequence[str], *, keep_continuation: bool = False
) -> dict[str, str]:
    """``key: value`` 行 → 映射。**重复键最后一个生效**;不成对的行原样留在正文里。

    **口径(C-37 甲,2026-09-15 签;此前从未声明过,只有实现)**:

    * 只收**顶层** ``key: value`` 行——键名匹配 ``[A-Za-z_][A-Za-z0-9_-]*`` 且**行首无缩进**
      (正则 :data:`_FM_ENTRY`)。于是键名里的点号与中文键都不算键行。
    * **取值 = 冒号后的余量**:首个空白被 ``\\s?`` 吃掉一个,``"a: 1"`` / ``"a:1"`` /
      ``"a:\\t1"`` 三种写法同值 ``"1"``;再多的空白留在取值里(``"a:   1"`` ⇒ ``"  1"``)。
    * **续行归 payload 原文**(V0-CHOICE ③ 的双轨):默认下缩进续行一概不看,于是
      ``hooks:`` 这类"键在下一层"的条目在映射里是**空串**——不是"没有内容",是这条派生轨
      只认顶层行。整段原文(规范化后的那一份)在 frontmatter 子块的 ``payload`` 里,
      要结构走那一份。
    * 首个键行**之前**的行不进映射(还没有键可挂)。

    ``keep_continuation=True``(C-37 乙)**只改取值文本**,不改键集、**不产生 per-key 槽**——
    memdir 的 ``metadata.modified``(``v0/refimpl/p27_memory_time_axes.py:38``)开着也仍不是
    一个键,它只是 ``metadata`` 这一条的续行文本;per-key 属 G-34 前半,不在本单:
    每遇键行开一个新条目,其后**每一条不匹配** :data:`_FM_ENTRY` 的行(含空行、含缩进行)
    **原样**追加为前一个键的续行,以 ``"\\n"`` 连接;**键行余量为空时,第一条**续行不产生
    前导换行(``["hooks:", "  a"]`` ⇒ ``{"hooks": "  a"}``),其后的续行一概以 ``"\\n"``
    连接、空行也不例外(``["hooks:", "", "  a"]`` ⇒ ``{"hooks": "\\n  a"}``,空行条数不丢)。
    库**不判断**续行是不是 YAML、不去缩进、不解析(A5):还回来的是原样文本,怎么读是
    调用者的事。

    开着时的四条边界,如实写在这里(前三条有对应测试):

    * ``"hooks:   x"`` 与 ``"hooks:"`` + 续行 ``"  x"`` 同值 ``"  x"``——本函数分不开它们;
      同理 ``["a:"]`` 与 ``["a:", ""]`` 都是 ``{"a": ""}``(那一条空行正落在"第一条续行不加
      前导换行"这条豁免上),这是豁免本身的推论,不是丢行;
    * **空行也算续行**:``["a: 1", "", "b: 2"]`` ⇒ ``a`` 是 ``"1\\n"``(尾随换行),
      这是最容易吓一跳的一条;
    * ``"a.b: 1"`` 不匹配键名字符集 ⇒ 被当作前一个键的续行。这是老行为(默认下它同样
      不是键)在开关下的延伸,点名不改;
    * **与 C-091 交叉**::data:`espalier.block.ANNOTATION_SPILL_THRESHOLD`
      (``block.py:60``,4096)今天只是未签的 F-3-D10 占位常量、全库零实现点
      (``block.py:130-137`` 自述"V0 **不实现**"),所以开关开出来的长取值进 ``annotations``
      **不受它管**,不会被降为 ``Payload``;要限长是调用者自己的事。

    **不透传** :func:`parse` / :func:`parse_tree`(§0 ③ 越界零容忍):frontmatter 子块的
    ``payload`` 是所选规范形内的整段原文(见模块 docstring V0-CHOICE ③),要续行的调用者
    自己切一次行、调一次本函数即可。
    """
    entries: dict[str, str] = {}
    last: str | None = None
    continued = False  # 本键是否已收过续行(重复键重开时一并重置)
    for line in lines:
        match = _FM_ENTRY.match(line)
        if match:
            last = match.group(1)
            entries[last] = match.group(2)  # 重复键:整条覆盖(续行也一并重开)
            continued = False
        elif keep_continuation and last is not None:
            current = entries[last]
            if not continued and current == "":
                entries[last] = line  # 余量为空:**第一条**续行不产生前导换行
            else:
                entries[last] = f"{current}\n{line}"
            continued = True
    return entries


# --------------------------------------------------------------------------- parse


@dataclass
class _Segment:
    """一个扁平段落:类型、原文行、它前面的空行数、起始行号(0 起,C-24)、以及(标题才有的)层级。"""

    kind: str
    lines: list[str]
    gap: int
    start: int
    level: int | None = None
    title: str | None = None


def _segments(lines: Sequence[str]) -> tuple[list[_Segment], int]:
    """把 c1 文本切成扁平段 + 文末空行数。切法照抄 P1 原型的分支次序。"""
    out: list[_Segment] = []
    index = 0
    gap = 0
    total = len(lines)

    if total and lines[0] == "---":
        end = 1
        while end < total and lines[end].strip() != "---":
            end += 1
        if end < total:
            out.append(_Segment(kind=KIND_FRONTMATTER, lines=list(lines[: end + 1]), gap=0, start=0))
            index = end + 1

    while index < total:
        line = lines[index]
        if _is_blank(line):
            gap += 1
            index += 1
            continue

        start = index
        heading = _HEADING.match(line)
        if heading:
            out.append(
                _Segment(
                    kind=KIND_SECTION,
                    lines=[line],
                    gap=gap,
                    start=start,
                    level=len(heading.group(1)),
                    title=heading.group(2),
                )
            )
            index += 1
        elif _is_fence(line):
            run = [line]
            index += 1
            while index < total:
                current = lines[index]
                run.append(current)
                index += 1
                if _is_fence(current):
                    break
            out.append(_Segment(kind=KIND_CODE, lines=run, gap=gap, start=start))
        elif _RULE.match(line) or _OPAQUE_START.match(line) or _LIST_ITEM.match(line):
            run: list[str] = []
            while index < total and not _is_blank(lines[index]):
                run.append(lines[index])
                index += 1
            out.append(_Segment(kind=KIND_OPAQUE, lines=run, gap=gap, start=start))
        else:
            run = [lines[index]]
            index += 1
            while index < total:
                current = lines[index]
                if (
                    _is_blank(current)
                    or _HEADING.match(current)
                    or _is_fence(current)
                    or _LIST_ITEM.match(current)
                    or _OPAQUE_START.match(current)
                    or _RULE.match(current)
                ):
                    break
                run.append(current)
                index += 1
            out.append(_Segment(kind=KIND_PARAGRAPH, lines=run, gap=gap, start=start))
        gap = 0

    return out, gap


def parse_tree(
    text: str,
    *,
    codec: str = "md",
    shape: Shape | None = None,
    canon: CanonId = CANON_C1,
    manifest: Manifest | None = None,
    origin: Origin,
    path: str = "",
    carried_of: Callable[[BlockId], Origin | None] | None = None,
    ulids: UlidFactory | None = None,
    kind: str = KIND_DOCUMENT,
    title: str | None = None,
    version: str | None = None,
) -> tuple[Block, dict[BlockId, Block]]:
    """完整版:返回 ``(根块, {id: 块})``。:func:`parse` 是它的第一个返回值。

    ``origin`` 是**这段文本自己的**出身(用户敲的、工具读回来的、文件读进来的);每个块
    拿到的是 ``Parsed(path, codec, shape_name, canon, carried=那个出身, span=切块偏移)``
    ——解析只是搬运,书写者另有其人(与 ``Recalled.carried`` 同一条读法)。
    ``version``(C-24)进每个 ``span`` 的 ``FileAddress.version``:调用者知道读的是哪一版
    文件就传进来,库不猜。
    """
    body = canonicalize(text, canon)
    lines = body.split("\n")
    segments, tail_gap = _segments(lines)
    total_lines = len(lines)

    def span_of(segment: _Segment) -> FileAddress:
        """C-24:这段在源文本里的行区间(0 起),以行计——见模块 docstring。"""
        return FileAddress(
            path=path,
            offset=segment.start,
            limit=len(segment.lines),
            total=total_lines,
            version=version,
            unit="line",
            base=0,
        )

    next_id: Callable[[], BlockId] = (
        ulids.next_block_id if ulids is not None else new_block_id
    )
    shown_index: dict[str, BlockId] = {}
    if manifest is not None:
        for entry in manifest.entries:
            source = entry.block_id
            if source is not None:
                shown_index.setdefault(str(entry.shown), source)

    def origin_for(segment_text: str | None, span: FileAddress | None = None) -> Origin:
        """``segment_text=None`` = 这个块没有自己的字节(文档根),不参与按段接回、无 ``span``。"""
        carried: Origin | None = origin
        if shown_index and segment_text is not None:
            key = str(bytes_hash(segment_text.encode("utf-8"), canon=CANON_RAW))
            source = shown_index.get(key)
            if source is not None:
                recovered = carried_of(source) if carried_of is not None else None
                carried = (
                    recovered
                    if recovered is not None
                    else Origin(
                        made=Transformed(
                            op="manifest.shown", params_canon=key, sources=(source,)
                        ),
                        arrived=Arrived.IMPORT,
                    )
                )
        return Origin(
            made=Parsed(
                path=path,
                codec=codec,
                shape_name=shape.name if shape is not None else None,
                canon=canon,
                carried=carried,
                span=span,
            ),
            arrived=origin.arrived,
            channel=origin.channel,
        )

    blocks: dict[BlockId, Block] = {}

    @dataclass
    class _Open:
        """还开着的小节:层级、子链接表,以及它自己那些定于开启时刻的事实。"""

        id: BlockId
        level: int
        links: list[ChildLink]
        title: str | None = None
        notes: dict[str, str] | None = None
        origin: Origin | None = None

    root_id = next_id()
    stack: list[_Open] = [_Open(id=root_id, level=0, links=[])]

    def close_to(level: int) -> None:
        while len(stack) > 1 and stack[-1].level >= level:
            open_section = stack.pop()
            blocks[open_section.id] = Block(
                id=open_section.id,
                kind=KIND_SECTION,
                title=open_section.title,
                payload=None,
                children=tuple(open_section.links),
                tail_gap=0,
                origin=open_section.origin or origin_for(None),
                refs=(),
                cited_refs=(),
                annotations=open_section.notes or {},
            )

    for segment in segments:
        segment_text = "\n".join(segment.lines)
        if segment.kind == KIND_SECTION:
            close_to(segment.level or 1)
            block_id = next_id()
            stack[-1].links.append(ChildLink(child=block_id, gap=segment.gap))
            stack.append(
                _Open(
                    id=block_id,
                    level=segment.level or 1,
                    links=[],
                    title=segment.title,
                    notes={LEVEL_KEY: str(segment.level)},
                    origin=origin_for(segment_text, span_of(segment)),
                )
            )
            continue

        block_id = next_id()
        notes: dict[str, str] = {}
        if segment.kind == KIND_FRONTMATTER:
            notes = frontmatter_entries(segment.lines[1:-1])
        blocks[block_id] = Block(
            id=block_id,
            kind=segment.kind,
            title=None,
            payload=Text(canon=canon, body=segment_text),
            children=(),
            tail_gap=0,
            origin=origin_for(segment_text, span_of(segment)),
            refs=(),
            cited_refs=(),
            annotations=notes,
        )
        stack[-1].links.append(ChildLink(child=block_id, gap=segment.gap))

    close_to(1)
    root = Block(
        id=root_id,
        kind=kind,
        title=title,
        payload=None,
        children=tuple(stack[0].links),
        tail_gap=tail_gap,
        origin=origin_for(None),
        refs=(),
        cited_refs=(),
        annotations={},
    )
    blocks[root_id] = root
    return root, blocks


def parse(
    text: str,
    *,
    codec: str = "md",
    shape: Shape | None = None,
    canon: CanonId = CANON_C1,
    manifest: Manifest | None = None,
    origin: Origin,
    path: str = "",
    carried_of: Callable[[BlockId], Origin | None] | None = None,
    ulids: UlidFactory | None = None,
    kind: str = KIND_DOCUMENT,
    title: str | None = None,
    version: str | None = None,
) -> Block:
    """§3.2 的签名。子块要拿在手上请用 :func:`parse_tree`(V0-CHOICE ①)。"""
    return parse_tree(
        text,
        codec=codec,
        shape=shape,
        canon=canon,
        manifest=manifest,
        origin=origin,
        path=path,
        carried_of=carried_of,
        ulids=ulids,
        kind=kind,
        title=title,
        version=version,
    )[0]


# --------------------------------------------------------------------------- render


def _resolver(blocks: Any) -> Callable[[BlockId], Block | None]:
    if blocks is None:
        return lambda _block_id: None
    if callable(blocks):
        return blocks  # type: ignore[return-value]
    if isinstance(blocks, Mapping):
        return lambda block_id: blocks.get(block_id)
    find = getattr(blocks, "find", None)
    if callable(find):
        def from_ledger(block_id: BlockId) -> Block | None:
            item = find(block_id)
            return item if isinstance(item, Block) else None

        return from_ledger
    raise TypeError(f"cannot resolve blocks from {type(blocks).__name__}")


def render_authoring(block: Block, *, blocks: Any = None) -> str:
    """编写面渲染:把块树写回 Markdown 字节。

    ``blocks`` 是子块的来源(:func:`parse_tree` 的索引、一本 ``Ledger``、或一个函数)。
    ``children`` 存 id(D2),所以没有它就只渲染得出根块自己那一段。

    与 :func:`espalier.render` 的编写面路径的分工:这里用**块记着的层级**
    (``annotations["md.level"]``),为的是字节往返;那里按**树深**,为的是 v2.8 ① 给模型
    看的一致缩进。两个渲染器回答两个问题,谁也不该顶替谁。
    """
    resolve = _resolver(blocks)
    out: list[str] = []

    def emit(node: Block, depth: int) -> None:
        if node.kind == KIND_SECTION:
            level = int(node.annotations.get(LEVEL_KEY, str(max(1, depth))))
            out.append("#" * level + " " + (node.title or ""))
        else:
            payload = node.payload
            if isinstance(payload, Text) and isinstance(payload.body, str):
                out.extend(payload.body.split("\n"))
        for link in node.children:
            child = resolve(link.child)
            out.extend([""] * link.gap)
            if child is not None:
                emit(child, depth + 1)
        out.extend([""] * node.tail_gap)

    emit(block, 0)
    return "\n".join(out)
