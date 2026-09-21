"""透镜架构(DESIGN.md v2.11)。

存储层**单一 Block + kind 纯标签**;类型住 API 层透镜——零账本代价、永不强制、
``.block`` 逃生舱永在、调用者自有 Shape 继承即与库内建同权(C1/C3)。

三条纪律,每一条都在下面的代码里能指出落点:

* **永不拦截**:``Lens.check`` 是纯查询;``Lens.of`` 抛 :class:`ShapeError` 只是**这次
  转换**做不了,账本上什么都没发生。N3 的"块自我宣称 ``Ref(space="shape")`` ⇒ check 扫到
  即调对应 ``Lens.check``"同样只产 Finding(见 :mod:`espalier.check`)。
* **A4 证词与证据分家**:``Skill.declared_tools`` 来自 frontmatter(作者写的,证词),
  ``Skill.discovered_tools`` 来自 ``block.refs``(链接扫描落下的,证据)。两条**永不合并**。
* **导入面 required 极小**(X9:85/85):``Skill`` 只要 name / description,一切正文槽
  optional;``build``(创造面)可以要得多(P4:测量只裁导入)。

**四处 V0-CHOICE**(v2.11 引用了却没给的):

1. ``Shape`` 的形:``name`` + ``required`` 字段名 + 一个可选校验回调。够用且不发明词汇。
2. ``ShapeError(rule_id, span)`` 的 ``span``:块正文里的**字节区间**(与
   ``ManifestEntry.byte_range`` 同坐标系);读不出位置时 ``None``,不编一个。
3. ``of`` / ``check`` 收 ``resolve``:``children`` 存 id(D2),透镜要看正文就得能解开子块。
   给 ``Ledger``、给 ``Mapping``、给一个函数都行。
4. ``build(**fields) -> Block`` 只造**根块**:body 子块由调用者传进来(它本来就在调用者
   手上),``name`` / ``description`` 落根块的 ``annotations``——于是造出来的技能块不必
   非有一个 frontmatter 子块,而 ``of`` 两种形都读得出。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, ClassVar, Iterable, Mapping, Sequence

from ._freeze import freeze_mapping, freeze_tuple
from .block import Block, ChildLink, Ref
from .events import Annotated, Pruned, Removed, Revoked
from .ids import BlockId
from .origin import Origin, Recalled, Remainder, ToolReturned
from .payload import Text

__all__ = [
    "ShapeError",
    "Shape",
    "ShapeReport",
    "Resolver",
    "Lens",
    "Step",
    "SkillFlow",
    "SkillChain",
    "Skill",
    "Memory",
    "ToolResult",
    "SHAPES",
    "register_shape",
    "shape_for",
    "declared_shapes",
    "check_declared",
    "SHAPE_SPACE",
    "KIND_FRONTMATTER",
    "MEMORY_CLAIMED_KEYS",
]

#: N3 的宣称空间:``Ref(space="shape", target=形状名)``。
SHAPE_SPACE: str = "shape"
#: codec 给 frontmatter 子块的 ``kind``。
KIND_FRONTMATTER: str = "frontmatter"


class ShapeError(Exception):
    """这块不合这个形。``rule_id`` 机器可判别,``span`` 是块正文里的字节区间(可为 ``None``)。"""

    def __init__(
        self,
        rule_id: str,
        detail: str = "",
        *,
        span: tuple[int, int] | None = None,
        subject: BlockId | None = None,
    ) -> None:
        super().__init__(f"{rule_id}: {detail}" if detail else rule_id)
        self.rule_id = rule_id
        self.detail = detail
        self.span = span
        self.subject = subject

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, ShapeError)
            and (self.rule_id, self.detail, self.span, self.subject)
            == (other.rule_id, other.detail, other.span, other.subject)
        )

    def __hash__(self) -> int:
        return hash((self.rule_id, self.detail, self.span, self.subject))


@dataclass(frozen=True)
class Shape:
    """"show me the skill schema" → **一个对象一处可读**(v2.11 的那句话)。"""

    name: str
    required: tuple[str, ...] = ()
    validate: Callable[[Block, Mapping[str, Any]], Sequence[ShapeError]] | None = None
    kind_hint: str | None = None
    """扫描加速提示。**发现以 Shape 匹配为准**(v2.11),kind 只是提示,不是判据。"""

    def __post_init__(self) -> None:
        object.__setattr__(self, "required", freeze_tuple(self.required))


@dataclass(frozen=True)
class ShapeReport:
    """``Lens.check`` 的结果。纯查询的返回值——它不拦任何东西。"""

    shape: str
    block: BlockId
    errors: tuple[ShapeError, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "errors", freeze_tuple(self.errors))

    @property
    def ok(self) -> bool:
        return not self.errors

    def __len__(self) -> int:
        return len(self.errors)


#: 解子块用的三种入参之一(``Ledger`` / ``Mapping`` / 函数)归一后的形。
Resolver = Callable[[BlockId], Block | None]


def _resolver(source: Any) -> Resolver:
    """把 ``Ledger`` / ``Mapping`` / 函数 / ``None`` 归一成一个 ``BlockId -> Block | None``。"""
    if source is None:
        return lambda _block_id: None
    if callable(source):
        return source  # type: ignore[return-value]
    if isinstance(source, Mapping):
        return lambda block_id: source.get(block_id)
    find = getattr(source, "find", None)
    if callable(find):
        def from_ledger(block_id: BlockId) -> Block | None:
            item = find(block_id)
            return item if isinstance(item, Block) else None

        # 透镜偶尔要看账本本身(C-10 的 ``recorded_invalid_at`` 读事件),而 ``_extract``
        # 只收归一后的函数——把来源挂在函数上,``_ledger_of`` 取回,不改子类接口。
        from_ledger.ledger = source  # type: ignore[attr-defined]
        return from_ledger
    raise TypeError(f"cannot resolve blocks from {type(source).__name__}")


def _ledger_of(resolve: Resolver) -> Any:
    """``resolve`` 若由 ``Ledger`` 归一而来,给回那本账;否则 ``None``。"""
    return getattr(resolve, "ledger", None)


def _children(block: Block, resolve: Resolver) -> tuple[Block, ...]:
    """解得开的子块;解不开的**静默略过**——那是悬空引用,归 ``check`` 报告(A0 分工)。"""
    out: list[Block] = []
    for link in block.children:
        child = resolve(link.child)
        if child is not None:
            out.append(child)
    return tuple(out)


def _text_of(block: Block) -> str:
    payload = block.payload
    if isinstance(payload, Text) and isinstance(payload.body, str):
        return payload.body
    return ""


def _frontmatter(block: Block, children: Sequence[Block]) -> Block | None:
    for child in children:
        if child.kind == KIND_FRONTMATTER:
            return child
    return None


def _facts(block: Block, children: Sequence[Block]) -> Mapping[str, str]:
    """frontmatter 的键值 ∪ 块自己的 ``annotations``(前者优先)。

    两个来源同权是刻意的:``parse`` 出来的技能把 frontmatter 落在子块的 annotations 上,
    ``build`` 出来的技能直接落在根块上——``of`` 两种都读得出,``.block`` 逃生舱两种都在。
    """
    facts: dict[str, str] = dict(block.annotations)
    front = _frontmatter(block, children)
    if front is not None:
        facts.update(front.annotations)
    return facts


class Lens:
    """透镜基类。``.block`` 逃生舱永在(v2.11)。"""

    shape: ClassVar[Shape] = Shape(name="lens")

    __slots__ = ("block", "_fields")

    def __init__(self, block: Block, fields: Mapping[str, Any]) -> None:
        object.__setattr__(self, "block", block)
        object.__setattr__(self, "_fields", freeze_mapping(fields))

    def __getattr__(self, name: str) -> Any:
        try:
            return self._fields[name]
        except KeyError:
            raise AttributeError(name) from None

    def __repr__(self) -> str:
        return f"{type(self).__name__}(block={self.block.id!r})"

    # ----------------------------------------------------------------- 子类接口

    @classmethod
    def _extract(
        cls, block: Block, resolve: Resolver
    ) -> tuple[dict[str, Any], list[ShapeError]]:
        """读出字段与"读的时候发现的问题"。子类实现。"""
        raise NotImplementedError

    # ----------------------------------------------------------------- 公开面

    @classmethod
    def read(
        cls, block: Block, *, resolve: Any = None
    ) -> tuple[dict[str, Any], tuple[ShapeError, ...]]:
        """字段 + 错误,一次读出(``of`` 与 ``check`` 共用它,所以两者永不分歧)。"""
        resolver = _resolver(resolve)
        fields, errors = cls._extract(block, resolver)
        for name in cls.shape.required:
            value = fields.get(name)
            if value is None or value == "":
                errors.append(
                    ShapeError(
                        f"{cls.shape.name}.{name}.missing",
                        f"required field {name!r} is absent",
                        subject=block.id,
                    )
                )
        if cls.shape.validate is not None:
            errors.extend(cls.shape.validate(block, fields))
        return fields, tuple(errors)

    @classmethod
    def of(cls, block: Block, *, resolve: Any = None) -> "Lens":
        """不合形抛第一条 :class:`ShapeError`(v2.11)。账本上什么都没发生。"""
        fields, errors = cls.read(block, resolve=resolve)
        if errors:
            raise errors[0]
        return cls(block, fields)

    @classmethod
    def check(cls, block: Block, *, resolve: Any = None) -> ShapeReport:
        """纯查询;**永不拦截任何账本操作**(v2.11)。"""
        try:
            _fields, errors = cls.read(block, resolve=resolve)
        except Exception as exc:  # pragma: no cover - 自定义 Shape 的回调炸了
            errors = (ShapeError(f"{cls.shape.name}.unreadable", str(exc), subject=block.id),)
        return ShapeReport(shape=cls.shape.name, block=block.id, errors=errors)

    @classmethod
    def matches(cls, block: Block, *, resolve: Any = None) -> bool:
        """Shape 匹配(**发现的判据**);``kind`` 只是扫描提示(v2.11)。"""
        return cls.check(block, resolve=resolve).ok

    @classmethod
    def build(cls, **fields: Any) -> Block:
        """创造面(P4:测量只裁导入)。子类实现。"""
        raise NotImplementedError


# --------------------------------------------------------------------------- 技能


@dataclass(frozen=True)
class Step:
    """流程的一步(v2.11)。``body`` 是块本身——一步不是一个字符串(A1)。"""

    title: str | None
    body: Block
    uses: tuple[Ref, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "uses", freeze_tuple(self.uses))


class SkillFlow(Lens):
    """有序步骤。裸名 ``Flow`` 退役(撞 ``ChainHash``),v2.13。"""

    shape: ClassVar[Shape] = Shape(name="skill.flow", kind_hint="skill.flow")

    steps: tuple[Step, ...]

    @classmethod
    def _extract(
        cls, block: Block, resolve: Resolver
    ) -> tuple[dict[str, Any], list[ShapeError]]:
        steps = tuple(
            Step(title=child.title, body=child, uses=tuple(child.refs))
            for child in _children(block, resolve)
        )
        return {"steps": steps}, []


class SkillChain(Lens):
    """一串引用(v2.11)。``links`` 取 ``block.refs``——链就是引用,不另造字段。"""

    shape: ClassVar[Shape] = Shape(name="skill.chain", kind_hint="skill.chain")

    links: tuple[Ref, ...]

    @classmethod
    def _extract(
        cls, block: Block, resolve: Resolver
    ) -> tuple[dict[str, Any], list[ShapeError]]:
        return {"links": tuple(block.refs)}, []


def _tool_refs(value: str) -> tuple[Ref, ...]:
    """``allowed-tools: Read, Grep`` → 两条 ``Ref(space="tool")``。库不校验工具存不存在。"""
    return tuple(
        Ref(space="tool", target=item.strip())
        for item in value.replace("\n", ",").split(",")
        if item.strip()
    )


class Skill(Lens):
    """技能(v2.11)。**导入面 required 只有 name / description**(X9:85/85)。"""

    shape: ClassVar[Shape] = Shape(
        name="skill", required=("name", "description"), kind_hint="skill"
    )

    name: str
    description: str
    declared_tools: tuple[Ref, ...]
    discovered_tools: tuple[Ref, ...]
    body: tuple[Block, ...]
    flow: SkillFlow | None
    chain: SkillChain | None
    subskills: tuple["Skill", ...]

    @classmethod
    def _extract(
        cls, block: Block, resolve: Resolver
    ) -> tuple[dict[str, Any], list[ShapeError]]:
        children = _children(block, resolve)
        facts = _facts(block, children)
        errors: list[ShapeError] = []

        flow: SkillFlow | None = None
        chain: SkillChain | None = None
        subskills: list[Skill] = []
        body: list[Block] = []
        for child in children:
            if child.kind == KIND_FRONTMATTER:
                continue
            if flow is None and (
                child.kind == SkillFlow.shape.kind_hint
                or (child.kind.endswith(".flow") and SkillFlow.matches(child, resolve=resolve))
            ):
                flow = SkillFlow.of(child, resolve=resolve)  # type: ignore[assignment]
                continue
            if chain is None and child.kind == SkillChain.shape.kind_hint:
                chain = SkillChain.of(child, resolve=resolve)  # type: ignore[assignment]
                continue
            if Skill.matches(child, resolve=resolve):
                subskills.append(Skill.of(child, resolve=resolve))  # type: ignore[arg-type]
                continue
            body.append(child)

        fields: dict[str, Any] = {
            "name": facts.get("name", ""),
            "description": facts.get("description", ""),
            "declared_tools": _tool_refs(facts.get("allowed-tools", "")),
            "discovered_tools": tuple(r for r in block.refs if r.space == "tool"),
            "body": tuple(body),
            "flow": flow,
            "chain": chain,
            "subskills": tuple(subskills),
        }
        return fields, errors

    @classmethod
    def build(
        cls,
        *,
        name: str,
        description: str,
        origin: Origin,
        body: Iterable[Block] = (),
        declared_tools: Iterable[str] = (),
        discovered_tools: Iterable[Ref] = (),
        annotations: Mapping[str, str] | None = None,
        title: str | None = None,
        kind: str = "skill",
        id: BlockId | None = None,
    ) -> Block:
        """造一个技能根块。body 子块由调用者传进来(它们本来就在调用者手上,V0-CHOICE ④)。"""
        facts: dict[str, str] = dict(annotations or {})
        facts["name"] = name
        facts["description"] = description
        tools = [t for t in declared_tools]
        if tools:
            facts["allowed-tools"] = ", ".join(tools)
        return Block.create(
            None,
            kind=kind,
            title=title if title is not None else name,
            origin=origin,
            children=tuple(ChildLink(child=b.id) for b in body),
            refs=tuple(discovered_tools),
            annotations=facts,
            id=id,
        )


# --------------------------------------------------------------------------- 记忆


#: ``Memory`` 的时间键表(C-10,2026-09-06 签):字段名 → facts 里认的键(先到先得)。
#: ``memory.`` 前缀键一并认——harness 把它们落在根块 annotations 上时常带命名空间。
MEMORY_CLAIMED_KEYS: Mapping[str, tuple[str, ...]] = {
    "claimed_written_at": ("written_at", "memory.written_at", "updated"),
    "claimed_valid_from": ("valid_from", "memory.valid_from"),
    "claimed_valid_until": ("valid_until", "memory.valid_until"),
    "claimed_expires_at": ("expires_at", "memory.expires_at"),
}


class Memory(Lens):
    """记忆条目(v2.11)。**A4 在这里拆成两组属性**:

    * 机械证据:``recorded_written_at``(``origin.made`` 是 ``Recalled`` 时它的
      ``written_at``)、``recorded_invalid_at``(C-10:``resolve`` 是 ``Ledger`` 时,最近一条
      指向本块的 ``Revoked``(``target_seq == seq_of(block)``)或 ``Annotated``
      (``block_annotations`` 含 ``status`` 键)的 ``written_at``;C-25(2026-09-06 签)
      再加 ``Removed`` / ``Pruned``(``block == 本块``)——与时序记忆系统里"失效 /
      过期"那一瞬是同一瞬,删块本身就是机械失效,不必再落一条注记;否则 ``None``);
    * 作者证词:``claimed_written_at`` / ``claimed_valid_from`` / ``claimed_valid_until`` /
      ``claimed_expires_at``(C-10)——facts 里自述的时间,键表见 :data:`MEMORY_CLAIMED_KEYS`。

    两组可以不一致,而那正是要能看见的事(P-07 / P-27)。解析不出来的自述时间落一条
    ShapeError(``memory.<字段>.unparsable``),字段留 ``None``——不拿 ``None`` 冒充"没写"。
    **不加 Block 字段**:这些都是从 facts / 事件读出来的视图。
    """

    shape: ClassVar[Shape] = Shape(name="memory", required=("name",), kind_hint="memory")

    name: str
    body: tuple[Block, ...]
    recorded_written_at: datetime | None
    recorded_invalid_at: datetime | None
    claimed_written_at: datetime | None
    claimed_valid_from: datetime | None
    claimed_valid_until: datetime | None
    claimed_expires_at: datetime | None

    @classmethod
    def _extract(
        cls, block: Block, resolve: Resolver
    ) -> tuple[dict[str, Any], list[ShapeError]]:
        children = _children(block, resolve)
        facts = _facts(block, children)
        errors: list[ShapeError] = []

        made = block.origin.made
        recorded = made.written_at if isinstance(made, Recalled) else None

        claimed: dict[str, datetime | None] = {}
        for field_name, keys in MEMORY_CLAIMED_KEYS.items():
            raw = next((facts[k] for k in keys if facts.get(k)), "")
            value: datetime | None = None
            if raw:
                try:
                    value = datetime.fromisoformat(raw)
                except ValueError:
                    errors.append(
                        ShapeError(
                            f"memory.{field_name}.unparsable",
                            f"frontmatter {keys[0]} {raw!r} is not ISO 8601",
                            subject=block.id,
                        )
                    )
            claimed[field_name] = value

        fields = {
            "name": facts.get("name") or block.title or "",
            "body": tuple(c for c in children if c.kind != KIND_FRONTMATTER),
            "recorded_written_at": recorded,
            "recorded_invalid_at": _recorded_invalid_at(block, _ledger_of(resolve)),
            **claimed,
        }
        return fields, errors

    @classmethod
    def build(
        cls,
        *,
        name: str,
        origin: Origin,
        body: Iterable[Block] = (),
        written_at: str | None = None,
        valid_from: str | None = None,
        valid_until: str | None = None,
        expires_at: str | None = None,
        annotations: Mapping[str, str] | None = None,
        title: str | None = None,
        kind: str = "memory",
        id: BlockId | None = None,
    ) -> Block:
        """造一个记忆根块(C-10)。四个时间是**作者证词**,落根块 ``annotations``
        (``written_at`` / ``valid_from`` / ``valid_until`` / ``expires_at``,ISO 8601 字符串,
        库不解析、不校验——证词原样存);机械时间在 ``origin``(``Recalled.written_at``)上。
        """
        facts: dict[str, str] = dict(annotations or {})
        facts["name"] = name
        for key, value in (
            ("written_at", written_at),
            ("valid_from", valid_from),
            ("valid_until", valid_until),
            ("expires_at", expires_at),
        ):
            if value is not None:
                facts[key] = value
        return Block.create(
            None,
            kind=kind,
            title=title if title is not None else name,
            origin=origin,
            children=tuple(ChildLink(child=b.id) for b in body),
            annotations=facts,
            id=id,
        )


def _recorded_invalid_at(block: Block, ledger: Any) -> datetime | None:
    """C-10 的机械半边:账本上最近一条"这块作废了"的事件的 ``written_at``。

    "最近"按账本序(``seq``)取,不按 ``written_at`` 比大小——机械时钟可回拨,seq 不会。
    C-25(2026-09-06 签):``Removed`` / ``Pruned``(``block == 本块``)与 ``Revoked`` /
    ``Annotated(status)`` 同列——四种事件里 seq 最大的那条说了算。``Restored`` 不清零:
    "曾经失效过"是事实,读者要"此刻在不在场"走 ``ledger.has``。
    """
    if ledger is None:
        return None
    try:
        seq = ledger.seq_of(block.id)
    except KeyError:
        return None
    latest: datetime | None = None
    latest_seq: int | None = None
    for event in ledger.events():
        hit = (
            (isinstance(event, Revoked) and event.target_seq == seq)
            or (
                isinstance(event, Annotated)
                and event.block == block.id
                and "status" in event.block_annotations
            )
            or (isinstance(event, (Removed, Pruned)) and event.block == block.id)  # C-25
        )
        if hit and (latest_seq is None or int(event.seq) >= latest_seq):
            latest = event.written_at
            latest_seq = int(event.seq)
    return latest


# --------------------------------------------------------------------------- 工具结果


class ToolResult(Lens):
    """工具结果(v2.11 + H2 / D-CAP-2)。全部字段从 ``origin.made``(``ToolReturned``)读。

    v2.11 原表的 ``truncation: ExternalAddress`` 在 V0 换成 ``remainder``:
    D-X15-1 已裁 ``Remainder`` 是那个把手的正身(地址可为 ``None`` = 诚实的 Lost),
    裸地址表达不了"截了多少、单位是什么、还有没有下一段"。
    """

    shape: ClassVar[Shape] = Shape(name="tool_result", required=("tool",))

    tool: str
    outcome: str
    ok: bool
    attempt: int
    remainder: Remainder | None
    payload: Block

    @classmethod
    def _extract(
        cls, block: Block, resolve: Resolver
    ) -> tuple[dict[str, Any], list[ShapeError]]:
        made = block.origin.made
        errors: list[ShapeError] = []
        if not isinstance(made, ToolReturned):
            errors.append(
                ShapeError(
                    "tool_result.origin.not_tool_returned",
                    f"origin.made is {type(made).__name__}",
                    subject=block.id,
                )
            )
            return {"payload": block}, errors
        return (
            {
                "tool": made.tool,
                "outcome": made.outcome,  # C-11:四态;``ok`` 保留为派生读法
                "ok": made.ok,
                "attempt": made.attempt,
                "remainder": made.remainder,
                "payload": block,
            },
            errors,
        )


# --------------------------------------------------------------------------- N3 注册表


#: 形状名 → 透镜。``check`` 扫到 ``Ref(space="shape", target=名)`` 就查这张表。
SHAPES: dict[str, type[Lens]] = {}


def register_shape(lens: type[Lens]) -> type[Lens]:
    """登记一个透镜(调用者自有 Shape 继承即与库内建同权,C1/C3)。可作装饰器。"""
    SHAPES[lens.shape.name] = lens
    return lens


def shape_for(name: str) -> type[Lens] | None:
    return SHAPES.get(name)


for _lens in (Skill, SkillFlow, SkillChain, Memory, ToolResult):
    register_shape(_lens)


def declared_shapes(block: Block) -> tuple[str, ...]:
    """这块**自我宣称**了哪几个形状(N3 的声明半边)。"""
    return tuple(ref.target for ref in block.refs if ref.space == SHAPE_SPACE)


def check_declared(block: Block, *, resolve: Any = None) -> tuple[ShapeReport, ...]:
    """按宣称逐个跑 ``Lens.check``。未登记的形状给一条 ``shape.unknown``。

    **持有宣称是机制,永不因宣称失败拦截任何操作**(N3 定案)。
    """
    reports: list[ShapeReport] = []
    for name in declared_shapes(block):
        lens = shape_for(name)
        if lens is None:
            reports.append(
                ShapeReport(
                    shape=name,
                    block=block.id,
                    errors=(
                        ShapeError(
                            "shape.unknown",
                            f"no lens registered for shape {name!r}",
                            subject=block.id,
                        ),
                    ),
                )
            )
            continue
        reports.append(lens.check(block, resolve=resolve))
    return tuple(reports)
