"""出身:两轴 ``Origin``、``Made`` 十变体、地址、``Remainder``、恢复档与信任档。

形状按 **V0-PLAN §3.2**(与 v2.4 冲突处以 §3.2 为准,冲突点在下面逐处标 ``V0-CHOICE``)。

两轴(v2.14-⑨,V0 选两轴)::

    Origin(made: Made, arrived: Arrived, channel: str | None)

X11 实测:``made`` 与 ``arrived`` 在现实中独立变化(10 个 n≥10 的非对角格),单轴要覆盖
须再造 7–9 处嵌套变体。D-CAP-7 的读法一并写在这里:

* **``arrived`` 是账本机械保证的**——块从哪个通道到达,是写入方自己的位置事实;
* **``made`` 是摄入适配器的证词**——"这段字节是谁做出来的"由适配器声称,库不能证。
  一切 origin-based 查询的可信度上界就是适配器对 ``made`` 的诚实度。

``channel`` 是 harness 自己的通道名(证词),库不解释。

十变体一律**不含 Origin 后缀**(v2.13)。``Grafted`` 推迟(v2.14-⑤):fork/resume 的
出身变化由事件面承载,真 IMPORT 等真实调用者,落地必用包裹形。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal, Mapping

from ._freeze import EMPTY_MAPPING, freeze_mapping, freeze_tuple
from .hashes import CallHash, ToolCallHash
from .ids import CANON_C1, BlockId, CanonId, LedgerId, is_ulid

__all__ = [
    "Arrived",
    "CodeSite",
    "FileAddress",
    "UrlAddress",
    "OpaqueAddress",
    "ExternalAddress",
    "address_canon",
    "Segment",
    "Remainder",
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
]


# --------------------------------------------------------------------------- 到达轴


class Arrived(Enum):
    """到达通道(V0-PLAN §3.2)。账本机械保证的那一轴(D-CAP-7)。"""

    USER_SLOT = 1
    ASSISTANT_SLOT = 2
    TOOL_RESULT_SLOT = 3
    ATTACHMENT = 4
    SYSTEM_PROMPT = 5
    NOTIFICATION = 6
    LOG_ONLY = 7
    IMPORT = 8
    UNKNOWN = 9


# --------------------------------------------------------------------------- 地址


@dataclass(frozen=True)
class CodeSite:
    """代码位置。

    V0-CHOICE:v2.4 在 ``Uttered`` / ``Authored`` 上引用了 ``CodeSite`` 却没给签名
    (幽灵清零条款的一个洞)。V0 取最小三字段;``line`` / ``symbol`` 可空。
    """

    file: str
    line: int | None = None
    symbol: str | None = None


@dataclass(frozen=True)
class FileAddress:
    """文件地址。``version`` 是 D-X15-8「地址可过期」的半边:记下当时读的是哪一版。

    C-26 + C-29(2026-09-06 签;两条同根合一):``offset`` / ``limit`` / ``cap`` / ``total``
    的**单位**与**起点**原先只能靠约定(E-3.Q3 / P-07.3:``Claim.address`` 的引文区间无法
    与 ``Remainder.have`` 对账)。现在两格显式落在地址上:

    * ``unit``:``"line"`` / ``"byte"`` / ``"char"`` / ``"token"``…(开域,与 ``Remainder.unit``
      同一词汇);``None`` = **记录未说**——不给默认值,假设同一单位正是 X15 抓到的错。
    * ``base``:``0`` / ``1``,``offset`` 从 0 还是从 1 数;``None`` = 记录未说。
      **只收真 ``int`` 的 0 / 1**,不 ``int()`` 强转:``True`` 与 ``"1"`` 曾被静默收成 ``1``,
      而 ``bool`` 与字符串在这一格上多半是调用者把别的东西塞错了位置——静默转换会把一个
      写错的记录变成一个看起来对的记录(A9)。真不知道就写 ``None``。

    两格都入 :func:`address_canon`(同一 ``path:offset`` 以行计与以字节计是两个地址)。
    """

    path: str
    offset: int = 0
    limit: int | None = None
    cap: int | None = None
    total: int | None = None
    version: str | None = None
    unit: str | None = None
    base: Literal[0, 1] | None = None

    def __post_init__(self) -> None:
        base = self.base
        if base is not None and not (type(base) is int and base in (0, 1)):
            raise ValueError(f"FileAddress.base must be 0, 1 or None, got {base!r}")


@dataclass(frozen=True)
class UrlAddress:
    """URL 地址。``version`` 是 C-36(2026-09-15 签)补的那一格:同一个 URL 两次取回
    取到的**不是同一份东西**时,拿什么把它们分开。

    * ``version``:``None`` = **记录未说**;**无条件入** :func:`address_canon`(``None``
      落 ``null``——§0 ① 写全键,与 ``FileAddress.version`` 同格同待遇)。取值库不解释
      (A5)——etag、快照 id、内容哈希都写得进;库也不去取(A8)。不校验格式。
    * ``fetched_at`` 仍**不入身份**(v2.1 纪律⑤),所以 harness 不给 ``version`` 时,
      同一 URL 两次取回照旧规范成同一个地址——本格只是"有格可填"。
    """

    url: str
    fetched_at: datetime
    version: str | None = None


@dataclass(frozen=True)
class OpaqueAddress:
    """A5 的精神延伸到地址域:库看不懂的定位符(如把溢出内容另存之后给出的取回定位符)照样能存。"""

    scheme: str
    params: Mapping[str, str] = EMPTY_MAPPING

    def __post_init__(self) -> None:
        object.__setattr__(self, "params", freeze_mapping(self.params))


ExternalAddress = FileAddress | UrlAddress | OpaqueAddress


def address_canon(address: ExternalAddress) -> dict[str, object]:
    """地址的**身份规范记录**:判别键 ``"address"`` + 各字段,**不含任何 ``*_at`` 时戳**
    (v2.1 纪律⑤)。C-6(2026-09-06 签)的叶 TreeHash 第四槽用它;``_records`` 的地址
    记录形在它之上补时戳,两处只有这一个定义处。
    """
    if isinstance(address, FileAddress):
        return {
            "address": "FileAddress",
            "path": address.path,
            "offset": address.offset,
            "limit": address.limit,
            "cap": address.cap,
            "total": address.total,
            "version": address.version,
            "unit": address.unit,  # C-26 / C-29:单位与起点是地址身份的一部分
            "base": address.base,
        }
    if isinstance(address, UrlAddress):
        # C-36:``version`` 无条件出键(None 落 null),与 FileAddress 分支同构。
        return {"address": "UrlAddress", "url": address.url, "version": address.version}
    if isinstance(address, OpaqueAddress):
        return {
            "address": "OpaqueAddress",
            "scheme": address.scheme,
            "params": dict(address.params),
        }
    raise TypeError(f"address_canon has no entry for {type(address).__name__}")


# --------------------------------------------------------------------------- Remainder


#: :class:`Segment` 的"这个位置没给"哨兵。不能用 ``None``——``None`` 在 ``unit`` 上是一个
#: **有意义的值**("这一段没说单位"),拿它当"没给"就把两件事混成一件。
_UNSET: object = object()


class Segment(tuple):
    """``Remainder.have`` 的一段:区间 ``(start, stop)`` + 它自己的 ``unit``(C-21,2026-09-06 签)。

    记录形恒为三元 ``[start, stop, unit]``(单子字面)。值形**偏离申报**:不是裸三元组,
    而是区间二元组的子类、单位挂在 ``.unit`` 上——于是 v0.18 起遍地的
    ``for start, stop in have`` / ``have[0][1]`` / ``have == ((a, b),)`` / ``len(have[0])``
    照旧成立(refimpl / bonus / llm 八处消费者,改库这一步不动它们),而单位一格没丢。

    **两种构造形**(``dataclasses.asdict`` 逼出来的,不是为了好看):

    * ``Segment(start, stop, unit)`` —— 正常形,``unit`` 可省(= ``None`` = 这一段没说单位);
    * ``Segment(iterable)`` —— 长度 2 或 3 的可迭代物,长度 2 时 ``unit`` 落 ``None``。
      ``asdict`` 对 tuple 子类按 ``type(obj)(生成器)`` 重建,而 ``Segment`` 自己只装得下
      两个元素(``unit`` 在 ``__dict__`` 里),生成器因此只吐 ``(start, stop)``——单参形不接,
      ``asdict(Remainder(...))`` 就直接 ``TypeError``。**如实记下代价**:走 ``asdict`` 的
      往返,与 ``Remainder.unit`` 不同的段单位会掉回继承值(拿得回三元的是
      :meth:`to_record` / ``_records``,那条路一格不丢)。

    ``unit`` 只收 ``str`` 或 ``None``:非 ``str`` 抛 ``ValueError`` 而**不** ``str()`` 强转
    ——``str(None) == "None"`` 那样的"单位"是编造出来的事实(A9)。``None`` 进
    :class:`Remainder` 时按 ``Remainder.unit`` 补(默认**值**,不是默认动作)。

    等值:与另一个 ``Segment`` 比**连单位一起比**(``(0, 10, "line") != (0, 10, "byte")``,
    往返测试才抓得住丢单位);与裸二元组比只比区间——那个二元组本来就没说单位。
    于是**等值关系对裸二元组不传递**:``(0, 10) == Segment(0, 10, "line")``、
    ``(0, 10) == Segment(0, 10, "byte")``,而两个 ``Segment`` 互不相等。这是有意的:
    "没说单位"与"说了 line"之间没有矛盾可言,不该因为都等于同一个二元组就被判相等。
    (``__hash__`` 同理只取区间——相等的裸二元组同哈希,单位不同只是碰撞。)
    不可变:构造后 ``unit`` 不可改。
    """

    # 不声明 __slots__:tuple 子类不能有具名 slot,``unit`` 住实例 __dict__(``__setattr__`` 封死)。
    unit: str | None

    def __new__(cls, start: object, stop: object = _UNSET, unit: object = _UNSET) -> "Segment":
        if stop is _UNSET and unit is _UNSET:  # 单参形:Segment(iterable),asdict 走这条
            parts = tuple(start)  # type: ignore[call-overload]
            if len(parts) == 2:
                start, stop = parts
                unit = None
            elif len(parts) == 3:
                start, stop, unit = parts
            else:
                raise ValueError(
                    f"Segment(iterable) takes 2 or 3 elements, got {len(parts)}: {parts!r}"
                )
        elif stop is _UNSET:  # pragma: no cover - Segment(start, unit=…) 这种写法没有意义
            raise TypeError("Segment(start, stop, unit) needs a stop")
        if unit is _UNSET:
            unit = None
        if unit is not None and not isinstance(unit, str):
            raise ValueError(f"Segment.unit must be a str or None, got {unit!r}")
        self = tuple.__new__(cls, (int(start), int(stop)))  # type: ignore[arg-type]
        object.__setattr__(self, "unit", unit)
        return self

    @property
    def start(self) -> int:
        return self[0]

    @property
    def stop(self) -> int:
        return self[1]

    @property
    def interval(self) -> tuple[int, int]:
        return (self[0], self[1])

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(f"Segment is immutable; cannot set {name!r}")

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Segment):
            return tuple.__eq__(self, other) and self.unit == other.unit
        return tuple.__eq__(self, other)

    def __ne__(self, other: object) -> bool:
        result = self.__eq__(other)
        return result if result is NotImplemented else not result

    def __hash__(self) -> int:
        return tuple.__hash__(self)  # 与相等的裸二元组同哈希;单位不同只是碰撞,不是矛盾

    def __repr__(self) -> str:
        return f"Segment({self[0]}, {self[1]}, {self.unit!r})"

    def __reduce__(self):  # type: ignore[no-untyped-def]
        return (Segment, (self[0], self[1], self.unit))

    def to_record(self) -> list[object]:
        return [self[0], self[1], self.unit]


@dataclass(frozen=True)
class Remainder:
    """截断 / 省略的把手(v2.14-⑩,D-X15-1..9)。

    * ``address=None`` 就是**诚实的 Lost**(D-X15-1):没有地址时类型不逼调用者伪造一个。
    * ``have`` 是已持有区间,**可多段**(D-X15-7:head+tail 两段是常态)。
      C-21(2026-09-06 签):每段是 ``(start, stop, unit)`` **三元组**——段自带单位。
      有的 harness 做首尾截断时两段只有 byte 长、省略量只有 token(P-02.1 唯一残余):两段以
      ``"byte"`` 计、``total`` 以 ``"token"`` 计,一条记录写得下。构造时给两元组
      ``(start, stop)`` 即**缺省继承** ``Remainder.unit``(默认值,不是默认动作);
      记录形恒为三元 ``[start, stop, unit]``,旧的两元记录读回时同样补 ``unit``。
    * ``unit`` **逐字段**给(D-X15-2):"line"|"byte"|"char"|"token"|"item"…
      不设默认——假设同一单位正是 X15 抓到的错。它仍是 ``total`` 的单位,也是
      ``have`` 段缺省时继承的单位。**必须是 ``str``**:非 ``str``(``None`` 在内)抛
      ``ValueError``,不做 ``str()`` 强转——``Remainder(unit=None)`` 若被放过,那些继承它的
      段就会带上一个叫 ``"None"`` 的单位,那是库编出来的事实(A9)。真不知道单位就别构造
      ``Remainder``,或写一个说得出口的词。
    * ``hit`` 是值集(D-X15-3):``{"limit","cap","eof","collapse","compact","max_tokens"…}``;
      ``eof`` 表达"部分覆盖但不是截断"。
    * ``continues`` 是续读链(D-X15-4 形 ①):指向下一段的块。
    * ``total`` 在此(全文总量);``FileAddress.total`` 是地址自己的总量,两者不同轴。
    * ``totals``(C-1,2026-09-06 签):**其它单位**的总量,如 ``{"line": 1200, "token": 8000}``
      ——三单位并存的记录只需多一格;``unit`` 仍是 ``have`` / ``total`` 的单位。
    * **这一格的 ``None`` 读什么,由持有者决定**(2026-09-15 签):``ToolReturned`` /
      ``Parsed`` / ``Recalled`` 上 ``remainder=None`` 读"未截断";``LlmDerived`` 上读
      "没有证词"(C-35)——模型轴上 stop_reason 常在手,没记下不等于没截断。按槽写通用代码
      (如按 :func:`dataclasses.fields` 扫各变体的 ``remainder`` 槽)时**不要把两种读法合并**。
      它与 ``address=None`` 也不是同一个 ``None``:后者是 Lost(有 ``Remainder``、没地址)。
    """

    address: ExternalAddress | None
    have: tuple[Segment, ...]
    total: int | None
    unit: str
    hit: frozenset[str] = frozenset()
    continues: BlockId | None = None
    totals: Mapping[str, int] = EMPTY_MAPPING

    def __post_init__(self) -> None:
        if not isinstance(self.unit, str):
            raise ValueError(f"Remainder.unit must be a str, got {self.unit!r}")
        segments: list[Segment] = []
        for segment in self.have:
            if isinstance(segment, Segment):
                if segment.unit is not None:
                    segments.append(segment)
                    continue
                start, stop, unit = segment[0], segment[1], self.unit  # 没说单位 ⇒ 继承
            else:
                parts = tuple(segment)
                if len(parts) == 2:  # C-21:两元组 ⇒ 单位继承 Remainder.unit(默认值)
                    start, stop = parts
                    unit = self.unit
                elif len(parts) == 3:
                    start, stop, unit = parts
                    if unit is None:  # 三元但单位写了 None:同样是"没说",同样继承
                        unit = self.unit
                else:
                    raise ValueError(
                        f"Remainder.have segment must be (start, stop) or (start, stop, unit), got {segment!r}"
                    )
            segments.append(Segment(start=start, stop=stop, unit=unit))  # type: ignore[arg-type]
        object.__setattr__(self, "have", tuple(segments))
        object.__setattr__(self, "hit", frozenset(self.hit))
        object.__setattr__(self, "totals", freeze_mapping(self.totals))

    def have_in(self, unit: str) -> tuple[tuple[int, int], ...]:
        """[派] 以 ``unit`` 计的那些段的区间 ``(start, stop)``(C-21)。
        不做单位换算——库不知道一 token 几个字节。"""
        return tuple(segment.interval for segment in self.have if segment.unit == unit)

    @property
    def lost(self) -> bool:
        """[派] 没有任何取回把手 ⇒ 这段字节是丢的。"""
        return self.address is None and self.continues is None


# --------------------------------------------------------------------------- Made 十变体


@dataclass(frozen=True)
class Uttered:
    """用户话语与 harness 转述输入——运行期最大宗。

    §3.2 对 v2.4 的两处改:``role`` 增 ``"model"``(D-X11-2:**另一账本的模型**,
    X11 无争议 82 单元);增 ``ledger``(那个模型属于哪本账)。
    C-3(2026-09-06 签):``role`` 增 ``"unknown"``——记录没说是谁说的,就显式写"不知道"。
    """

    role: Literal["user", "harness", "model", "unknown"]
    ledger: LedgerId | None = None
    site: CodeSite | None = None


@dataclass(frozen=True)
class Authored:
    """代码字面量 / 人亲笔。

    §3.2 增 ``by``(G-2f / D-X11-4):35.5% 字节的作者不在记录里,需要一个**显式的
    author-unknown 值**,不得用 "Authored 即人写" 冒充。
    """

    by: Literal["human", "model", "external", "unknown"]
    site: CodeSite | None = None


@dataclass(frozen=True)
class Parsed:
    """编写面解析产物。§3.2 增 ``carried``(D-CAP-5:写回携带出身,按段接回)。

    ``canon`` 默认 ``c1``:F-2-D1 已裁"``parse()`` 才用 c1",而 ``Parsed`` 正是
    ``parse()`` 的出身。这是默认**值**,不是默认动作——真正做规范化的是
    :meth:`espalier.Text.canonical`。

    * ``remainder``(C-2,2026-09-06 签):语义同 ``ToolReturned.remainder``——截断是
      "这块怎么做出来"的事实,落出身;``None`` = 未截断,``address is None`` = Lost。
    * ``span``(C-5,2026-09-06 签):解析器切出这块时的**源区间**(机械,含 ``version``)。
      模型说"引自 path:12-40"不走这里,走 ``Block.cited_claims``(A4:证词与机械分槽)。
    """

    path: str
    codec: str
    shape_name: str | None = None
    canon: CanonId = CANON_C1
    carried: "Origin | None" = None
    remainder: Remainder | None = None
    span: FileAddress | None = None


@dataclass(frozen=True)
class Templated:
    """模板 + 绑定。原名 "rendered",改名避 ``render()`` 撞名(v2.13)。

    ``resolved`` 存 ``BlockId`` 保血缘——存字符串值会断血缘,三方设计里那一版被判破。
    """

    template: BlockId
    resolved: Mapping[str, BlockId] = EMPTY_MAPPING

    def __post_init__(self) -> None:
        object.__setattr__(self, "resolved", freeze_mapping(self.resolved))


@dataclass(frozen=True)
class Transformed:
    """机械变换。``sources`` 是**事实字段**,不寄生于复现把手(非全函数洞的修复)。

    C-4(2026-09-06 签):``sources`` 三值——``None`` = **未记录**,``()`` = **已知为空**,
    非空 = 构成关系。``origin_sources`` 对 ``None`` 不出边。
    C-5(2026-09-06 签):``span`` 是机械切块的源区间(同 ``Parsed.span``)。
    """

    op: str
    params_canon: str = ""
    sources: tuple[BlockId, ...] | None = None
    span: FileAddress | None = None

    def __post_init__(self) -> None:
        if self.sources is not None:
            object.__setattr__(self, "sources", freeze_tuple(self.sources))


@dataclass(frozen=True)
class LlmDerived:
    """模型轮与 compact 产物统一在此;``call`` 机械绑定"模型看到了什么"。

    §3.2 增 ``ledger``(D-CAP-10:跨账本跳点)。

    C-4(2026-09-06 签):``sources`` 三值——``None`` = **未记录**,D-CAP-9"整个 manifest"
    的读法**只对 None 生效**;``()`` = **已知为空**;非空 = 构成关系。``origin_sources``
    对 ``None`` 不出边。

    C-35(2026-09-15 签):``remainder`` 这一格长到模型轴上——模型侧被截断
    (``max_tokens`` 早已在 :class:`Remainder` 自己的 ``hit`` 值集里)从此有变体可挂,
    不必走块 annotations 的自造键。``None`` = **这一格没有证词**(不是"未截断":模型轴上
    ``stop_reason`` 常在手,没写多半是没记)。库自己永不填它——``compact.commit`` 替调用者
    造摘要块时 ``remainder`` 仍是 ``None``(A8)。
    """

    call: CallHash
    ledger: LedgerId | None = None
    sources: tuple[BlockId, ...] | None = None
    instruction: BlockId | None = None
    model: str | None = None
    remainder: Remainder | None = None

    def __post_init__(self) -> None:
        if self.sources is not None:
            object.__setattr__(self, "sources", freeze_tuple(self.sources))


@dataclass(frozen=True)
class ToolReturned:
    """工具结果。§3.2 按 H2 / D-CAP-2 补齐:

    * ``tool``:v2.4 只有 ``call``(纯哈希、上下文无关),**工具名丢了**;
    * ``touched``:碰了世界的哪里(读/写地址,含读全者);
    * ``remainder``:``None`` = 未截断;``Remainder.address is None`` = Lost(D-X15-1)。
    * ``call``(C-19,2026-09-06 签):``ToolCallHash | None``,**仍无默认值**——``None``
      是一句证词("这次调用没有可算的哈希"),须显式写,与 ``Origin.arrived`` 同理。
    * ``outcome``(C-11,2026-09-06 签):``"ok" | "error" | "protocol_error" |
      "input_required"``;``ok`` 退为派生属性(``outcome == "ok"``)保住旧读法。
      ``resultType`` 一类 harness 原词走 ``annotations``。
    """

    call: ToolCallHash | None
    tool: str
    attempt: int = 0
    outcome: Literal["ok", "error", "protocol_error", "input_required"] = "ok"
    touched: tuple[ExternalAddress, ...] = ()
    remainder: Remainder | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "touched", freeze_tuple(self.touched))

    @property
    def ok(self) -> bool:
        """[派] ``outcome == "ok"``(C-11)。三个非成功态在 ``outcome`` 上分得开。"""
        return self.outcome == "ok"


@dataclass(frozen=True)
class Injected:
    """hook 注入的**标记变体**(V1,A10 落地,owner 2026-09-08 签)。

    v0.18 曾给它六个类型化字段(``injector`` / ``configured_by`` / ``blocking`` /
    ``decision`` / ``decision_scope`` / ``decision_reason``,C-3 / C-12);机械扫描
    (``docs/experiments/V1-FIELD-READERS.md``)证明库里**没有任何函数读它们**——
    ``trust_class`` / ``recovery_classes`` / ``default_realm`` 只读"它是 ``Injected``"这件事。
    按 A10 边界("库有函数读的字段不退注记"),六个字段整体退到块的 ``annotations``,
    变体本身保留:它的类型仍决定信任档(THIRD_PARTY)与领域。

    **注记键约定(文档约定,不是类型;harness 想要闭词表自己校验)**:

    ======================== ==========================================================
    ``hook.injector``        哪个 hook / 事件名注入的(v0.18 的 ``injector``)
    ``hook.configured_by``   由谁配置(user / project / plugin / …,harness 原词,开域)
    ``hook.blocking``        是否阻断,写 ``"true"`` / ``"false"``;缺键 = 记录未说
    ``hook.decision``        harness 原词(deny / block / ask / allow / continue:false / …)
    ``hook.decision_scope``  call / turn / task / session …
    ``hook.decision_reason`` 原因原文
    ======================== ==========================================================

    v0.18–v0.21 写的旧记录带这六键时,``block_from_record`` / ``event_from_record``
    把它们**搬进** ``annotations``(同名键已存在则不覆盖),一个字节不丢(A9)。
    V0-S 口径 2:库不解释的概念走 annotations ⇒ P-05.2 / P-50.3 / P-51.1 的承载仍成立。
    """


@dataclass(frozen=True)
class Computed:
    """渲染期计算(Inlay 的出身)。harness 在 render 前物化,库只接产物(A8)。"""

    provider: str
    params_canon: str = ""


@dataclass(frozen=True)
class Recalled:
    """记忆有书写者:信任沿 ``carried`` 递归;``carried=None`` 显式落保守档。

    §3.2 增 ``ledger``(D-CAP-10)。D-X11-3:导入路径上 ``carried=None`` 是常态。
    ``remainder``(C-2,2026-09-06 签):语义同 ``ToolReturned.remainder``。
    """

    memory: str
    written_at: datetime
    carried: "Origin | None" = None
    ledger: LedgerId | None = None
    remainder: Remainder | None = None


Made = (
    Uttered
    | Authored
    | Parsed
    | Templated
    | Transformed
    | LlmDerived
    | ToolReturned
    | Injected
    | Computed
    | Recalled
)

#: 十变体的运行期元组。全函数映射表的测试按它枚举——加变体不加进这里,测试就会红。
MADE_VARIANTS: tuple[type, ...] = (
    Uttered,
    Authored,
    Parsed,
    Templated,
    Transformed,
    LlmDerived,
    ToolReturned,
    Injected,
    Computed,
    Recalled,
)


# --------------------------------------------------------------------------- 两轴 Origin


@dataclass(frozen=True)
class Origin:
    """机械证据,不可变(A4/A6)。两轴 + harness 通道名。

    ``arrived`` **没有默认值**(§3.2 字面):它是 D-CAP-7 里"账本机械保证的那一轴",
    给它一个静默默认等于让摄入适配器不填也能过,而事后 ``UNKNOWN`` 与"真的不知道"就
    分不开了。真不知道就显式写 ``Arrived.UNKNOWN`` —— 那是一句证词,不是一个省略。
    (A0 允许默认**值**;这里不给,是因为省略与断言在这一轴上必须可分。)
    """

    made: Made
    arrived: Arrived
    channel: str | None = None


def _as_made(origin: "Origin | Made") -> Made:
    """两个档函数都收 ``Origin`` 或裸 ``Made``——A0,不逼调用者拆包。"""
    return origin.made if isinstance(origin, Origin) else origin


# --------------------------------------------------------------------------- 血缘字段


#: ``Made`` 上那些**取值是 BlockId** 的字段——账本的血缘索引(D-CAP-4 ``lineage_of``)
#: 与 ``check`` 的悬空引用扫描都按这张表走。第四张全函数表:加变体要同时改
#: union / ``MADE_VARIANTS`` / 两张档表 / 本表 / ``_records`` 的两个编解码。
LINEAGE_FIELDS: tuple[str, ...] = (
    "LlmDerived.sources",
    "LlmDerived.instruction",
    "Transformed.sources",
    "Templated.template",
    "Templated.resolved",
    "Recalled.carried",
    "Recalled.memory",
    "Parsed.carried",
)


def origin_sources(o: "Origin | Made", *, _prefix: str = "") -> tuple[tuple[BlockId, str], ...]:
    """出身里**指向别的块**的边:``((block_id, 经哪个字段), …)``,次序即字段声明次序。

    这是 ``Ledger.lineage_of(direction="up")`` 与 ``check`` 悬空源扫描共用的取边函数
    ——两处走同一张表,才不会一处认得而另一处认不得。

    **V0-CHOICE 两处**:

    1. V0 任务书列了五个血缘字段(``LlmDerived.sources``/``instruction``、
       ``Transformed.sources``、``Templated.resolved``、``Recalled.carried``、
       ``Parsed.carried``);本表**多一个** ``Templated.template``——它同样是 BlockId,
       漏掉它就是丢一条边(A9)。
    2. ``Remainder.continues`` **不在**本表:那是续读链(D-X15-4),与"这块字节由哪些块
       做出来"不同轴,混进来会让 ``lineage_of`` 答非所问。要查续读链走
       ``ToolReturned.remainder.continues``。

    ``carried`` 是**嵌套 Origin** 而不是 BlockId,所以沿它递归下去,``via`` 记成
    ``"Recalled.carried>LlmDerived.sources"`` 这样的路径——不丢"经过了一层记忆"这件事。

    C-4(2026-09-06 签):``sources is None``(未记录)**不出边**;``()`` 与 ``None``
    在这里同样零边,但前者是"已知为空"的证词,后者是省略——分辨它们看字段本身。
    """
    made = _as_made(o)
    edges: list[tuple[BlockId, str]] = []

    def via(name: str) -> str:
        return _prefix + name

    if isinstance(made, LlmDerived):
        edges.extend((s, via("LlmDerived.sources")) for s in made.sources or ())
        if made.instruction is not None:
            edges.append((made.instruction, via("LlmDerived.instruction")))
    elif isinstance(made, Transformed):
        edges.extend((s, via("Transformed.sources")) for s in made.sources or ())
    elif isinstance(made, Templated):
        edges.append((made.template, via("Templated.template")))
        edges.extend((b, via("Templated.resolved")) for b in made.resolved.values())
    elif isinstance(made, Recalled):
        # V1(A10 清单 §3,2026-09-08 签):``memory`` 若是一个块 id(ULID 形),它就是
        # 指向记忆块的血缘边;若是存储标签(``"vendor/vector-store"`` 之类)则不是边。
        # 只按形状判,不猜:非 ULID 的字符串零边。
        if is_ulid(made.memory):
            edges.append((BlockId(made.memory), via("Recalled.memory")))
        if made.carried is not None:
            edges.extend(origin_sources(made.carried, _prefix=via("Recalled.carried>")))
    elif isinstance(made, Parsed):
        if made.carried is not None:
            edges.extend(origin_sources(made.carried, _prefix=via("Parsed.carried>")))
    elif isinstance(made, (Uttered, Authored, ToolReturned, Injected, Computed)):
        pass
    else:  # pragma: no cover - 加了变体没加表就在这里炸
        raise TypeError(f"origin_sources has no entry for {type(made).__name__}")

    return tuple(edges)


# --------------------------------------------------------------------------- 恢复档


class RecoveryClass(Enum):
    """A7 三档取回把手。"""

    LEDGER = 1
    RECIPE = 2
    ADDRESS = 3


def recovery_classes(o: "Origin | Made") -> frozenset[RecoveryClass]:
    """出身**自己提供**了哪几类取回把手。全函数,逐变体显式定值。

    A7 改述(定案):凡规范字节已在账本 / CAS 者**自身即强复现**——那一档由账本判定,
    不由 origin 判定,所以这里的返回值**不含**"字节就在账上"这件事。"三类至少居一"
    只约束字节不在账者,且这个检查只活在 ``check``,构造器永不拒收(空把手是合法事实)。

    逐变体(V0-CHOICE,每个洞显式定值;v2.4 只给了函数名没给表):

    ==================  ==========================================  ==============================
    变体                档                                          理由
    ==================  ==========================================  ==============================
    ``Uttered``         ∅                                           话语没有外部把手
    ``Authored``        {ADDRESS} 当 ``site`` 非空                   源码位置是可过期的地址
    ``Parsed``          {ADDRESS} ∪ rc(carried)                     ``path``;C-2 的 remainder 地址同档
    ``Templated``       {LEDGER, RECIPE}                            template+resolved 皆 BlockId
    ``Transformed``     {RECIPE} ∪ {LEDGER} 当 ``sources`` 非空      op+params 是配方
    ``LlmDerived``      {RECIPE} ∪ {LEDGER} 当 sources/instruction   call+model+params 可 replay
                        ∪ {ADDRESS} 当 remainder.address 非 None     C-35:同 ToolReturned 那一行
    ``ToolReturned``    {RECIPE} ∪ {ADDRESS} 当有地址                ToolCallHash → 回放缓存
    ``Injected``        ∅                                           注入者不是配方
    ``Computed``        {RECIPE}                                    provider+params 可重算
    ``Recalled``        {ADDRESS} ∪ rc(carried)                     ``memory`` 是记忆存储里的地址
    ==================  ==========================================  ==============================
    """
    made = _as_made(o)
    classes: set[RecoveryClass] = set()

    if isinstance(made, Uttered):
        pass
    elif isinstance(made, Authored):
        if made.site is not None:
            classes.add(RecoveryClass.ADDRESS)
    elif isinstance(made, Parsed):
        classes.add(RecoveryClass.ADDRESS)
        if made.carried is not None:
            classes |= recovery_classes(made.carried)
    elif isinstance(made, Templated):
        classes.add(RecoveryClass.LEDGER)
        classes.add(RecoveryClass.RECIPE)
    elif isinstance(made, Transformed):
        classes.add(RecoveryClass.RECIPE)
        if made.sources:
            classes.add(RecoveryClass.LEDGER)
    elif isinstance(made, LlmDerived):
        classes.add(RecoveryClass.RECIPE)
        if made.sources or made.instruction is not None:
            classes.add(RecoveryClass.LEDGER)
        # C-35:与 ToolReturned 同槽同口径——截断掉的那段有地址就是一把 ADDRESS 把手。
        if made.remainder is not None and made.remainder.address is not None:
            classes.add(RecoveryClass.ADDRESS)
    elif isinstance(made, ToolReturned):
        classes.add(RecoveryClass.RECIPE)
        if made.touched:
            classes.add(RecoveryClass.ADDRESS)
        if made.remainder is not None and made.remainder.address is not None:
            classes.add(RecoveryClass.ADDRESS)
    elif isinstance(made, Injected):
        pass
    elif isinstance(made, Computed):
        classes.add(RecoveryClass.RECIPE)
    elif isinstance(made, Recalled):
        classes.add(RecoveryClass.ADDRESS)
        if made.carried is not None:
            classes |= recovery_classes(made.carried)
    else:  # pragma: no cover - 加了变体没加表就在这里炸,不静默返回空集
        raise TypeError(f"recovery_classes has no entry for {type(made).__name__}")

    return frozenset(classes)


# --------------------------------------------------------------------------- 信任档


class TrustClass(Enum):
    AUTHOR = 1
    USER = 2
    MODEL = 3
    TOOL = 4
    THIRD_PARTY = 5
    COMPUTED = 6


def trust_class(o: "Origin | Made") -> TrustClass:
    """逐变体全函数映射表。**可被 ``RenderSpec.trust_of`` 整表替换**——这是默认表,不是法律。

    两条口径:

    * **信任不传播**(D8):摘要块的信任视图由调用者经 ``sources`` 下钻或自供 combine,
      本表不沿 ``sources`` 递归。唯二递归的是 ``Recalled.carried`` 与 ``Parsed.carried``
      ——那不是传播,是"记忆/解析只是搬运,书写者另有其人"(v2.4 原文)。
    * **作者未知落保守档 ``THIRD_PARTY``**(D-X11-4;D-X18-3′ 与之相反,owner 未裁,
      V0 取保守侧)。

    逐变体(V0-CHOICE 标在未定项上):

    =========================  ================  ====================================
    变体                       档                备注
    =========================  ================  ====================================
    ``Uttered(role=user)``     USER
    ``Uttered(role=model)``    MODEL             D-X11-2 另一账本的模型
    ``Uttered(role=harness)``  THIRD_PARTY       **V0-CHOICE**(X18 记未定,取保守)
    ``Uttered(role=unknown)``  THIRD_PARTY       C-3:不知道是谁说的 ⇒ 保守档
    ``Authored(by=human)``     AUTHOR
    ``Authored(by=model)``     MODEL
    ``Authored(by=external)``  THIRD_PARTY
    ``Authored(by=unknown)``   THIRD_PARTY       D-X11-4 保守档
    ``Parsed``                 carried 或        **V0-CHOICE**:文件字节作者不明 ⇒ 保守
                               THIRD_PARTY
    ``Templated``              THIRD_PARTY       **V0-CHOICE**:合成者是 harness,与
                                                 ``Uttered(harness)`` 同档
    ``Transformed``            THIRD_PARTY       **V0-CHOICE**:变换后的字节可携任意上游
                                                 作者,不传播 ⇒ 保守;下钻走 sources
    ``LlmDerived``             MODEL             X18 指出 TrustClass 无 DERIVED 成员;
                                                 V0 归 MODEL,不新增成员
    ``ToolReturned``           TOOL              C-11:四种 ``outcome`` 同档——失败的工具
                                                 结果仍是工具说的话
    ``Injected``               THIRD_PARTY       **V0-CHOICE**(X18 记未定,取保守);C-3:
                                                 ``blocking`` 三值不改档,None 与 True 同落此。
                                                 **偏离申报**:改库单 C-3 波及栏写"按
                                                 ``blocking is True`` 判",但两张表(本表与
                                                 :func:`recovery_classes`)v0.17 起就不读
                                                 ``blocking``——固定 THIRD_PARTY / ∅,无对应
                                                 代码路径,与 C-4 / C-19 同类,不新造分档
    ``Computed``               COMPUTED          Inlay:从出身事实机械算出,无外部内容
    ``Recalled``               carried 或        v2.4 原文:沿 carried 递归;
                               THIRD_PARTY       carried=None 显式落保守档
    =========================  ================  ====================================
    """
    made = _as_made(o)

    if isinstance(made, Uttered):
        if made.role == "user":
            return TrustClass.USER
        if made.role == "model":
            return TrustClass.MODEL
        return TrustClass.THIRD_PARTY  # role == "harness" | "unknown"(C-3)
    if isinstance(made, Authored):
        if made.by == "human":
            return TrustClass.AUTHOR
        if made.by == "model":
            return TrustClass.MODEL
        return TrustClass.THIRD_PARTY  # "external" | "unknown"
    if isinstance(made, Parsed):
        if made.carried is not None:
            return trust_class(made.carried)
        return TrustClass.THIRD_PARTY
    if isinstance(made, Templated):
        return TrustClass.THIRD_PARTY
    if isinstance(made, Transformed):
        return TrustClass.THIRD_PARTY
    if isinstance(made, LlmDerived):
        return TrustClass.MODEL
    if isinstance(made, ToolReturned):
        return TrustClass.TOOL
    if isinstance(made, Injected):
        return TrustClass.THIRD_PARTY
    if isinstance(made, Computed):
        return TrustClass.COMPUTED
    if isinstance(made, Recalled):
        if made.carried is not None:
            return trust_class(made.carried)
        return TrustClass.THIRD_PARTY
    raise TypeError(f"trust_class has no entry for {type(made).__name__}")


# --------------------------------------------------------------------------- realm


Realm = Literal["authoring", "runtime"]


def default_realm(o: "Origin | Made") -> Realm:
    """``Block.realm`` 的默认派生:``Parsed`` / ``Authored`` → 编写面,其余 → 运行面。

    ``RenderSpec.realm_of`` 可整表覆写(v2.3 注:调用者可为 LLM 产出的结构化长文选
    编写面渲染)。
    """
    made = _as_made(o)
    if isinstance(made, (Parsed, Authored)):
        return "authoring"
    return "runtime"
