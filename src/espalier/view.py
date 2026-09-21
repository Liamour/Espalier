"""``View``:渲染的输入(V0-PLAN §3.2 / H3 / D-CAP-3)。

v2 章从头到尾引用 ``View`` 却没给定义(``ledger.view()`` 的返回型、``render(view, …)``
的入参)——这是 H3 的一半。§3.2 给了签名,本模块照抄并补齐 A0 完备项。

四个自由度,互不重叠:

* ``leaf`` / ``at_seq``:**看哪条时间线的哪一刻**。事件树上 ``prev`` 可指非尖端(D5),
  所以"哪条线"和"哪一刻"是两个参数。
* ``roots``:``None`` = 账本顶层顺序;给了就是这几个块(次序即给定次序)。
* ``without``:**排除**,进 ``Manifest.excluded``(v2.10:排除是决策,须留痕)。
* ``include_open``:X16——渲染必须接受开态(74.2% 的轮 ≥2 次请求),所以**默认 True**。

``View`` 是 frozen dataclass:``without_()`` 返回新 View,不改原件。它持有 ``Ledger``
引用(不是快照),因此同一个 View 在账本继续写入后 ``blocks()`` 可能变——除非它带了
``at_seq``。这是刻意的:要定影就给 ``at_seq``,别让库替你猜。
"""

from __future__ import annotations

from dataclasses import dataclass, replace as dc_replace
from typing import TYPE_CHECKING, Iterable

from ._freeze import freeze_tuple
from .block import Block
from .ids import BlockId, Seq

if TYPE_CHECKING:  # pragma: no cover - 只为类型;运行期不 import,避免与 ledger 成环
    from .ledger import Ledger, OpenComposite

__all__ = ["View"]


@dataclass(frozen=True)
class View:
    """账本的一个可渲染切面。"""

    ledger: "Ledger"
    leaf: Seq | None = None
    at_seq: Seq | None = None
    roots: tuple[BlockId, ...] | None = None
    without: frozenset[BlockId] = frozenset()
    include_open: bool = True

    def __post_init__(self) -> None:
        if self.roots is not None:
            object.__setattr__(self, "roots", freeze_tuple(self.roots))
        object.__setattr__(self, "without", frozenset(self.without))

    # ----------------------------------------------------------------- 派生

    def without_(self, ids: Iterable[BlockId] | BlockId) -> "View":
        """加排除项,返回**新** View。收单个 id 或一串 id(A0:不逼调用者包 list)。"""
        more = {ids} if isinstance(ids, str) else set(ids)
        return dc_replace(self, without=frozenset(self.without | more))

    def with_(self, ids: Iterable[BlockId] | BlockId) -> "View":
        """撤掉排除项(排除的逆);不在排除集里的 id 静默忽略。"""
        fewer = {ids} if isinstance(ids, str) else set(ids)
        return dc_replace(self, without=frozenset(self.without - fewer))

    def at(self, at_seq: Seq | None) -> "View":
        """换时刻。"""
        return dc_replace(self, at_seq=at_seq)

    def rooted_at(self, roots: Iterable[BlockId] | None) -> "View":
        """换根集合;``None`` 回到账本顶层顺序。"""
        return dc_replace(self, roots=None if roots is None else tuple(roots))

    # ----------------------------------------------------------------- 取块

    def block_ids(self) -> tuple[BlockId, ...]:
        """本视图**实际**给出的 id 序列(已按 ``roots`` / ``without`` / 墓碑过滤)。"""
        return tuple(b.id for b in self.blocks())

    def blocks(self) -> tuple["Block | OpenComposite", ...]:
        """按账本顶层顺序(或 ``roots`` 给定次序)取块。

        三条过滤:``without`` 排除;墓碑块不出现(它们的证据在 ``retrieve().lost``);
        ``include_open=False`` 时开复合不出现。找不到的 ``roots`` 项静默跳过——
        那是**悬空引用**,归 ``check`` 报告,不在渲染路上抛。
        """
        ledger = self.ledger
        if self.roots is None:
            ids = ledger.top_level(at_seq=self.at_seq, leaf=self.leaf)
        else:
            ids = self.roots

        out: list[Block | OpenComposite] = []
        for block_id in ids:
            if block_id in self.without:
                continue
            item = ledger.find(block_id, at_seq=self.at_seq, leaf=self.leaf)
            if item is None:
                continue
            if not isinstance(item, Block) and not self.include_open:
                continue
            out.append(item)
        return tuple(out)

    def excluded(self) -> tuple[BlockId, ...]:
        """本视图排除掉的 id,**整份**列出(给 ``Manifest.excluded`` 用)。两段接起来:

        1. 此刻在**账本顶层**的那些,按账本顶层次序;
        2. 其余的——凡**不在顶层**的 id 都归这里——按 id 字典序。成因不止一种:嵌套在
           复合里的子块、账本上从没有过的 id、落了墓碑的、被 ``replace`` / ``merge`` 顶掉
           位置的旧块(块值还在账上,``find`` 照样给得出)、以及 ``at_seq`` 切点之后才写进
           来的。落这一段**不是**"这个 id 不存在"的断言。

        **不做在场过滤**:调用者给进 ``without`` 的那份名单原样留痕、一个不丢(A9),
        库不替他判断哪个 id "真的在账上"。排序按账本顶层次序、不按集合的哈希序——留痕
        要可复现。
        """
        ledger = self.ledger
        ordered = ledger.top_level(at_seq=self.at_seq, leaf=self.leaf)
        known = [b for b in ordered if b in self.without]
        rest = sorted(b for b in self.without if b not in set(ordered))
        return tuple(known + rest)
