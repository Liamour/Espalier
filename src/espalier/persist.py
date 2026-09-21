"""JSONL 流水:账本头 + 每行一个事件,以及带诊断的加载(G-V0-1 / P-09)。

格式(V0 定 ``format_version = 1``;v0.18 提到 ``2``;v0.21 提到 ``3``;V1 提到 ``4``;v1.1 提到 ``5``)::

    第 1 行   {"header": {...}}          # LedgerHeader
    第 2..n 行 {"event": "...", ...}     # 一行一个事件,次序即写入次序

**为什么 v0.18 是 2 而不是 1**(C-17 + C-20 + 全部新记录键的反驳修补):行的键集没变少,
旧行**读得回**(缺键 ⇒ 默认值);但入 ChainHash 的瘦记录多了 ``actor`` / ``reason`` /
``excluded_why`` / ``remainder`` 一类新键,ManifestHash 公式又按 C-17 换了,于是 v0.17
写的行在 v0.18 读者手里**链全不匹配、``Ledger.verify`` 判 Mismatch**。版本不动,读者就把
"旧写者写的"读成"被篡改"(A9:把不矛盾的记录说成矛盾)。提到 2 让 v0.17 文件走已有的
``format_version_behind`` 通道——拒绝 / 升级仍由 harness 决定(P-09 分工不变)。

**为什么 v0.21 是 3**(裁决 ② + C-18 / ④ / G-V0-3,2026-09-06 签):三处身份哈希公式变了
——复合 TreeHash 含 refs 与自身第四槽、StateHash 含注记、CompactionId 改读
``covered_tree_hashes``(``Compacted`` 记录多一键,入 ChainHash)。v0.18 写的文件仍
逐行读得回(缺键 ⇒ ``None``),但复合块的 ``Appended.tree_hash`` / ``Closed.merkle`` 按
新公式重算对不上、``Checkpointed.state`` 验不过、``Compacted`` 链不匹配——同一条理由,
同一条通道:``format_version_behind``。

**不止那三处公式**:同单 §2 的十条候选(owner 同日签核全部并入)也让**入 ChainHash 的
瘦记录键集**变了——``FileAddress`` 多 ``unit`` / ``base``,``Remainder.have`` 的段从两元
变三元,``Called`` 多 ``inlays`` / ``rendering``,``Compacted`` 多 ``covered_tree_hashes``。
于是 v0.20 文件在新读者手里是**整条链全数不匹配**,不是"只有那三处公式受影响的几行"。
这与 v0.17 → v0.18 是同一回事(键集变 ⇒ 链变),提版本挡的也是同一个误判:把"旧写者
写的"读成"被篡改"。

**为什么 V1 是 4**(A10 落地,``docs/experiments/V1-A10-LIST.md`` §2,owner 2026-09-08 签):
``Injected`` 六个类型化字段退成持有者的 ``hook.*`` 注记,记录形只剩 ``{"made": "Injected"}``。
旧行读得回(六键由 ``block_from_record`` / ``event_from_record`` 搬进 ``annotations``,一个
字节不丢),但**入 ChainHash 的瘦记录键集变了**——v0.21 写者的 ``actor`` / ``block_value.origin.made``
/ ``Opened.origin.made`` 带六键,V1 读者按新形重算的 ``link`` 与旧值全不相等。版本不动,
读者就把"旧写者写的"读成"被篡改"(A9),与 1 → 2、2 → 3 是同一条理由、同一条通道:
``format_version_behind``。V1-A10-LIST §2 写的"``FORMAT_VERSION`` 不必再升……V1 落库时统一
处理"指的就是这里:统一处理 = 提到 4。

**为什么 v1.1 是 5**(C-35 + C-36,owner 2026-09-15 签,``docs/experiments/V1-FM-LIBCHANGE-PLAN.md``
§0 ①):``LlmDerived`` 多一格 ``remainder``、``UrlAddress`` 的 ``address_canon`` 多一键
``version``,按"加可选字段一律写全键"的纪律 ``None`` 也落 ``null`` ⇒ 含这两种值的**入
ChainHash 瘦记录键集变**,外部 Blob 的 TreeHash 第四槽也随 canon 变。v1.0 写的行仍逐行
读得回(缺键 ⇒ ``None``),但新读者按新形重算的 ``link`` 与旧值不等——与 1 → 2、2 → 3、
3 → 4 同一条理由、同一条通道:``format_version_behind``。两条候选合升一次版,不是各升一次;
同批的 C-31 扩(``compact.commit`` 三参)与 C-37(``frontmatter_entries`` 开关)不改记录形。

写入一律 **append + flush + fsync**:崩溃安全的定义就是"已返回的写一定在盘上"。
读取给出 :class:`LoadReport` 而**不是**直接抛异常——A0/P-09:库给字段与报告,
"拒绝 / 跳过 / 升级"是 harness 的决定。:meth:`espalier.Ledger.open` 默认 ``strict=True``
把致命报告转成 :class:`LoadError`,``strict=False`` 则带着报告继续。

四种诊断(全部只记录,不静默):

* **torn tail**:最后一行解析不了——JSON 半截,或撕在一个多字节字符中间、连 UTF-8 都解不开
  (C-39)——⇒ 整行丢弃并记入 ``torn_tail``。
  只对**最后一行**成立;中间行坏了是 ``errors``(那不是崩溃,是损坏)。
  丢弃的是**读**;文件里那几个字节还在,所以报告同时给 ``good_bytes``(最后一条完整行
  结束处的偏移),:meth:`espalier.Ledger.open` 在续写之前据它截齐——不截就等于让下一条
  写粘在半截行后面永久丢失。
* **未知 event 值**:``ignorable=False`` ⇒ 进 ``errors``(致命,拒绝加载);
  ``ignorable=True`` ⇒ 进 ``skipped``(跳过,照常加载)。
  ``ignorable`` 是**基字段**,所以读不懂事件类型也读得到这个标记——这正是它存在的理由。
* **format_version**:落后 / 超前**各自**报错(``format_version_behind`` /
  ``format_version_ahead``),两者都致命,但取值不同,harness 能分开处置。
* **ChainHash**:逐条重算比对,不匹配进 ``chain_mismatches``(**非**致命——链断了是事实,
  要不要拒绝是策略)。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from ._freeze import EMPTY_MAPPING, freeze_mapping, freeze_tuple
from ._records import (
    Record,
    block_from_record,
    block_to_record,
    dt_from_iso,
    dt_to_iso,
    origin_from_record,
    origin_to_record,
)
from .events import Event, UnknownEventKind, chain_hash, event_from_record
from .hashes import ChainHash
from .ids import LedgerId, Seq

__all__ = [
    "FORMAT_VERSION",
    "WRITER_VERSION",
    "LedgerHeader",
    "LoadIssue",
    "LoadReport",
    "LoadError",
    "header_to_record",
    "header_from_record",
    "event_line",
    "header_line",
    "JsonlWriter",
    "load",
    "write_ledger",
    "block_to_record",
    "block_from_record",
    "origin_to_record",
    "origin_from_record",
]

#: 本库能写、能读的账本格式版本(P-09:落后/超前各自报错)。
#: 1 = V0(v0.17 及之前);2 = v0.18(ChainHash 瘦记录键集与 ManifestHash 公式都变了);
#: 3 = v0.21(复合 TreeHash / StateHash / CompactionId 三处公式变了,见模块 docstring);
#: 4 = V1(A10:``Injected`` 记录形去六键,入 ChainHash 的瘦记录键集随之变,见模块 docstring);
#: 5 = v1.1(C-35 + C-36,2026-09-15 签:``LlmDerived`` 多 ``remainder`` 键、``UrlAddress``
#: 的 canon 多 ``version`` 键——按"写全键"纪律 None 也出键,于是含这两种值的**瘦记录键集变**,
#: v1.0 写的行在新读者手里链不匹配,同 1→2 / 2→3 / 3→4 一条理由、一条通道)。
FORMAT_VERSION: int = 5
#: 写入者版本(P-09 第二条:格式版本与写入者版本是两回事)。与 ``pyproject.toml`` 同步。
WRITER_VERSION: str = "espalier/0.1.0"


# --------------------------------------------------------------------------- 账本头


@dataclass(frozen=True)
class LedgerHeader:
    """账本头(V0-PLAN §3.2 / G-V0-2)。**创建即定**的那一半;中途可变的走 ``Configured``。

    ``parent`` / ``inherited_cut`` 是**委派或派生**的父与继承切点;物理分叉的父在
    ``Forked.parent`` 上——G-V0-2 明写两义分开(真实 harness 里"委派的父"与
    "分叉的来源"是两个独立字段,已证它们独立)。V0 的 ``fork()`` 两处都填,因为它两件事都是。
    """

    id: LedgerId
    created_at: datetime
    format_version: int = FORMAT_VERSION
    writer_version: str = WRITER_VERSION
    parent: LedgerId | None = None
    inherited_cut: Seq | None = None
    role: str | None = None
    annotations: Mapping[str, str] = EMPTY_MAPPING

    def __post_init__(self) -> None:
        object.__setattr__(self, "annotations", freeze_mapping(self.annotations))


def header_to_record(header: LedgerHeader) -> Record:
    return {
        "id": header.id,
        "created_at": dt_to_iso(header.created_at),
        "format_version": int(header.format_version),
        "writer_version": header.writer_version,
        "parent": header.parent,
        "inherited_cut": None if header.inherited_cut is None else int(header.inherited_cut),
        "role": header.role,
        "annotations": dict(header.annotations),
    }


def header_from_record(record: Mapping[str, Any]) -> LedgerHeader:
    parent = record["parent"]
    cut = record["inherited_cut"]
    return LedgerHeader(
        id=LedgerId(record["id"]),
        created_at=dt_from_iso(record["created_at"]),
        format_version=int(record["format_version"]),
        writer_version=record["writer_version"],
        parent=LedgerId(parent) if parent is not None else None,
        inherited_cut=Seq(cut) if cut is not None else None,
        role=record["role"],
        annotations=record["annotations"],
    )


# --------------------------------------------------------------------------- 行


def _dump(record: Mapping[str, Any]) -> str:
    """一行 JSON。``ensure_ascii=False``:中文原样落盘,别人 ``cat`` 得懂。"""
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def header_line(header: LedgerHeader) -> str:
    return _dump({"header": header_to_record(header)})


def event_line(event: Event) -> str:
    return _dump(event.to_record())


# --------------------------------------------------------------------------- 写


class JsonlWriter:
    """append-only JSONL 写入器。每次写都 flush + fsync。

    A0:``fsync`` 可关(``fsync=False``,批量导入时省 I/O),但**默认是开**的——
    默认值可以有,默认动作不能有,而"悄悄不落盘"正是最坏的默认动作。
    """

    __slots__ = ("_path", "_handle", "_fsync")

    def __init__(self, path: str | os.PathLike[str], *, fsync: bool = True) -> None:
        self._path = Path(path)
        self._fsync = fsync
        self._handle = self._path.open("a", encoding="utf-8", newline="\n")

    @property
    def path(self) -> Path:
        return self._path

    def write_line(self, line: str) -> None:
        self._handle.write(line + "\n")
        self._handle.flush()
        if self._fsync:
            os.fsync(self._handle.fileno())

    def write_header(self, header: LedgerHeader) -> None:
        self.write_line(header_line(header))

    def append_event(self, event: Event) -> None:
        self.write_line(event_line(event))

    def append_events(self, events: Iterable[Event]) -> None:
        """一批事件:写全部行,**一次** flush + fsync。

        ``commit`` 的四条(v2.7)走这里。它把"已返回的写一定在盘上"从逐条收紧成逐批,
        但**不是事务**:写到第三行断电,文件里就留着两行。那个残留窗口记在
        :mod:`espalier.compact` 的模块 docstring 里。
        """
        for event in events:
            self._handle.write(event_line(event) + "\n")
        self._handle.flush()
        if self._fsync:
            os.fsync(self._handle.fileno())

    def close(self) -> None:
        if not self._handle.closed:
            self._handle.close()

    def __enter__(self) -> "JsonlWriter":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def write_ledger(
    path: str | os.PathLike[str],
    header: LedgerHeader,
    events: Iterable[Event],
    *,
    fsync: bool = True,
) -> None:
    """整本写出(测试与导出用)。文件已存在则**覆盖**。"""
    target = Path(path)
    target.write_text("", encoding="utf-8")
    with JsonlWriter(target, fsync=fsync) as writer:
        writer.write_header(header)
        for event in events:
            writer.append_event(event)


# --------------------------------------------------------------------------- 读


@dataclass(frozen=True)
class LoadIssue:
    """一条加载诊断。``kind`` 是机器可判别的短名,``detail`` 是给人看的。"""

    kind: str
    line: int | None
    detail: str
    seq: Seq | None = None


@dataclass(frozen=True)
class LoadReport:
    """加载结果 + 全部诊断。``ok`` 为假时 :meth:`espalier.Ledger.open` 默认抛错。"""

    path: str | None
    header: LedgerHeader | None
    events: tuple[Event, ...] = ()
    errors: tuple[LoadIssue, ...] = ()
    skipped: tuple[LoadIssue, ...] = ()
    chain_mismatches: tuple[LoadIssue, ...] = ()
    torn_tail: str | None = None
    """被丢弃的那半截尾行(不含它本该有的换行);``None`` = 没有半截尾行。
    文件**只有一行**且那一行读不了时归 ``bad_header``,这里仍是 ``None``——``torn_tail is None``
    不等于"文件完好",要看 :attr:`errors`。

    崩溃可能把尾行撕在**一个多字节字符中间**,那时这半截字节根本不是合法 UTF-8。
    这里仍是 ``str``(不加第二个字段),用 ``errors="surrogateescape"`` 解出来——
    ``report.torn_tail.encode("utf-8", "surrogateescape")`` 逐字节取回原残尾,一个字节不丢。
    代价如实说:这种 ``torn_tail`` 含孤立代理码点,直接 ``print`` 或按严格 UTF-8 编码会抛
    ``UnicodeEncodeError``;要看就 ``ascii(report.torn_tail)``,要存就按 ``surrogateescape``
    编回字节。尾行是合法 UTF-8(只是 JSON 半截)时与普通 ``str`` 无异。
    """

    good_bytes: int | None = None
    """最后一条**完整行**(含它的换行)结束处的字节偏移;``None`` = 文件读不了。

    有 ``torn_tail`` 时这就是**该截到哪里**:半截行之后再 append,新行会粘在它后面,
    于是那条新行永远解析不出来——账本静默丢数据,再写一条就变成致命的
    ``bad_event_line``。:meth:`espalier.Ledger.open` 用它在开写之前截齐(A9:
    "已返回的写一定在盘上"的对偶是"没返回的写不许冒充在盘上")。
    """

    def __post_init__(self) -> None:
        for name in ("events", "errors", "skipped", "chain_mismatches"):
            object.__setattr__(self, name, freeze_tuple(getattr(self, name)))

    @property
    def ok(self) -> bool:
        """没有致命错误。链不匹配与被跳过的事件**不**让它变假——那是事实不是判决。"""
        return not self.errors

    def issues(self) -> tuple[LoadIssue, ...]:
        return self.errors + self.skipped + self.chain_mismatches


class LoadError(Exception):
    """``strict=True`` 时把致命的 :class:`LoadReport` 抛出来。``.report`` 拿全部诊断。"""

    def __init__(self, report: LoadReport) -> None:
        detail = "; ".join(f"{i.kind}: {i.detail}" for i in report.errors) or "unknown"
        super().__init__(f"cannot load ledger {report.path!r}: {detail}")
        self.report = report


def _good_bytes(lines: list[bytes]) -> int:
    """这些**完整行**(每行含一个 ``\\n``)在文件里占的字节数。

    直接数字节而不是记读取位置:``lines`` 是从原始字节按 ``b"\\n"`` 切出来的,行内没有
    任何归一(:func:`load` 特意不走 ``read_text`` 的通用换行),所以两者逐字节相等。
    数字节还让"尾行撕在一个多字节字符中间"也算得出偏移——算这个数不必先解得开码。
    """
    return sum(len(line) + 1 for line in lines)


def load(path: str | os.PathLike[str]) -> LoadReport:
    """读一本 JSONL 账本。**永不抛**格式类异常;一切诊断进 :class:`LoadReport`。

    **格式类异常含"不是合法 UTF-8"**:崩溃可以停在一个多字节字符中间,那半截字节解不开码
    ——但那是记录的形状问题,与"半截 JSON"是同一件事,所以走报告不走异常。
    切行因此在**字节**上做(``0x0A`` 不会出现在任何多字节 UTF-8 序列内部,按 ``b"\\n"``
    切与"先整份解码再切"对合法文件逐行相同),再逐行解码:**没有末尾换行的**尾行解不开走
    ``torn_tail``(读法见 :attr:`LoadReport.torn_tail`);中间行、或**自带换行**的尾行解不开
    走 ``bad_event_line``(那是损坏不是崩溃,不截)且其后的行照读;首行解不开、或文件只有
    一行而它读不了,走 ``bad_header``。
    IO 异常(文件不存在、没有读权限等)**照常抛**——那不是记录的形状,不该压进报告。
    已知未封的一处(改前改后一致):事件行里**显式转义**出的孤立代理码点(JSON ``"\\ud800"``,
    字节层是合法 UTF-8)会在重算链哈希时抛 ``UnicodeEncodeError``。

    读的是**字节**再自己按 ``\\n`` 切行(不用 ``read_text`` 的通用换行):
    ``LoadReport.good_bytes`` 是文件上的真偏移,而通用换行会把 ``\\r\\n`` 折成一个字符,
    偏移就对不上了。
    """
    target = Path(path)
    raw = target.read_bytes()
    ends_with_newline = raw.endswith(b"\n")
    byte_lines = raw.split(b"\n")
    if byte_lines and byte_lines[-1] == b"":
        byte_lines.pop()  # 末尾换行不是空行

    # 逐行解码。解不开的行仍进 ``lines``(``surrogateescape`` 留住原字节,一个不丢),
    # 坏在哪一行记进 ``bad_utf8``——归 torn tail 还是归诊断由**位置**定,和 JSON 解不开
    # 同一套分法。注意不能靠"解出来的串 JSON 也解不开"来判:孤立代理码点在 ``str`` 里
    # 是合法字符,``json.loads`` 照样吃得下。
    lines: list[str] = []
    bad_utf8: dict[int, str] = {}
    for index, chunk in enumerate(byte_lines):
        try:
            lines.append(chunk.decode("utf-8"))
        except UnicodeDecodeError as exc:
            bad_utf8[index] = str(exc)
            lines.append(chunk.decode("utf-8", "surrogateescape"))

    errors: list[LoadIssue] = []
    skipped: list[LoadIssue] = []
    mismatches: list[LoadIssue] = []
    events: list[Event] = []
    header: LedgerHeader | None = None
    torn_tail: str | None = None

    if not lines:
        return LoadReport(
            path=str(target),
            header=None,
            errors=(LoadIssue("empty_file", None, "ledger file has no header line"),),
            good_bytes=0,
        )

    # torn tail:只有**最后一行**解析不了才算崩溃写了一半(D:崩溃恢复)。
    # "解不开码"与"解不开 JSON"同一条路:都是崩溃截出来的半截,区别只在撕在哪个字节。
    # 一处收窄:解不开码的尾行**自带换行**时不算 torn。崩溃撕出来的半截带不上自己的换行
    # (行内没有裸 ``0x0A``),带换行就是一条写完了的行后来坏了——损坏不是崩溃,走
    # ``bad_event_line``。判成 torn 会让 ``Ledger.open`` 默认把一条**完整行**从盘上截掉,
    # 而改前这类文件是抛异常、一个字节不动;不拿一次修复去扩大一个会删盘的默认。
    # (只有一行时仍归 ``bad_header``,与 JSON 那条路一致。)
    last_index = len(lines) - 1
    if last_index in bad_utf8:
        torn = last_index == 0 or not ends_with_newline
    else:
        torn = False
        try:
            json.loads(lines[last_index])
        except (json.JSONDecodeError, ValueError):
            torn = True
    if torn:
        if last_index == 0:
            detail = (
                f"header line is not valid UTF-8: {bad_utf8[0]}"
                if 0 in bad_utf8
                else "header line is not valid JSON"
            )
            errors.append(LoadIssue("bad_header", 1, detail))
            return LoadReport(
                path=str(target), header=None, errors=tuple(errors), good_bytes=0
            )
        torn_tail = lines.pop()
        byte_lines.pop()

    # 留下来的这些行都是完整行:每行末尾都有一个 `\n`,唯一的例外是"什么都没截掉、
    # 而文件本身就没有末尾换行"那一种。
    good = _good_bytes(byte_lines) - (0 if (torn_tail is not None or ends_with_newline) else 1)

    # 头
    if 0 in bad_utf8:
        errors.append(
            LoadIssue("bad_header", 1, f"header line is not valid UTF-8: {bad_utf8[0]}")
        )
        return LoadReport(
            path=str(target),
            header=None,
            errors=tuple(errors),
            torn_tail=torn_tail,
            good_bytes=good,
        )
    try:
        head_record = json.loads(lines[0])
    except (json.JSONDecodeError, ValueError) as exc:
        errors.append(LoadIssue("bad_header", 1, f"header line is not valid JSON: {exc}"))
        return LoadReport(
            path=str(target),
            header=None,
            errors=tuple(errors),
            torn_tail=torn_tail,
            good_bytes=good,
        )
    if not isinstance(head_record, dict) or "header" not in head_record:
        errors.append(LoadIssue("bad_header", 1, "first line has no 'header' key"))
        return LoadReport(
            path=str(target),
            header=None,
            errors=tuple(errors),
            torn_tail=torn_tail,
            good_bytes=good,
        )
    try:
        header = header_from_record(head_record["header"])
    except (KeyError, ValueError, TypeError) as exc:
        errors.append(LoadIssue("bad_header", 1, f"header record is malformed: {exc}"))
        return LoadReport(
            path=str(target),
            header=None,
            errors=tuple(errors),
            torn_tail=torn_tail,
            good_bytes=good,
        )

    if header.format_version < FORMAT_VERSION:
        errors.append(
            LoadIssue(
                "format_version_behind",
                1,
                f"ledger format_version {header.format_version} < reader {FORMAT_VERSION}",
            )
        )
    elif header.format_version > FORMAT_VERSION:
        errors.append(
            LoadIssue(
                "format_version_ahead",
                1,
                f"ledger format_version {header.format_version} > reader {FORMAT_VERSION}",
            )
        )

    # 事件
    links: dict[Seq, ChainHash] = {}
    for offset, line in enumerate(lines[1:], start=2):
        if offset - 1 in bad_utf8:
            errors.append(
                LoadIssue(
                    "bad_event_line", offset, f"line is not valid UTF-8: {bad_utf8[offset - 1]}"
                )
            )
            continue
        if line.strip() == "":
            continue
        try:
            record = json.loads(line)
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(LoadIssue("bad_event_line", offset, f"line is not valid JSON: {exc}"))
            continue
        if not isinstance(record, dict):
            errors.append(LoadIssue("bad_event_line", offset, "line is not a JSON object"))
            continue
        try:
            event = event_from_record(record)
        except UnknownEventKind as exc:
            issue = LoadIssue(
                "unknown_event_kind",
                offset,
                f"unknown event kind {exc.kind!r}",
                seq=Seq(record["seq"]) if isinstance(record.get("seq"), int) else None,
            )
            if bool(record.get("ignorable", False)):
                skipped.append(issue)
            else:
                errors.append(issue)
            continue
        except (KeyError, ValueError, TypeError) as exc:
            errors.append(LoadIssue("bad_event_record", offset, f"malformed event: {exc}"))
            continue

        prev_link = links.get(event.prev) if event.prev is not None else None
        expected = chain_hash(prev_link, event.thin_record())
        if expected != event.link:
            mismatches.append(
                LoadIssue(
                    "chain_mismatch",
                    offset,
                    f"link {event.link} != recomputed {expected}",
                    seq=event.seq,
                )
            )
        links[event.seq] = event.link
        events.append(event)

    return LoadReport(
        path=str(target),
        header=header,
        events=tuple(events),
        errors=tuple(errors),
        skipped=tuple(skipped),
        chain_mismatches=tuple(mismatches),
        torn_tail=torn_tail,
        good_bytes=good,
    )
