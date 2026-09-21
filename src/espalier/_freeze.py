"""内部工具:把调用者交来的可变容器冻成不可变**值**。

不是公开名(不进 ``espalier.__all__``)。存在的两个理由:

1. 全库 dataclass 一律 ``frozen=True``,但 ``Mapping`` / ``Sequence`` 字段若原样存下,
   调用者手里的引用仍能改动块内容——那会破坏 A6(派生不改料)与身份哈希的稳定性。
2. ``types.MappingProxyType`` 不可哈希,会让含映射字段的 ``Block`` / ``Origin`` 变成
   "声称是 frozen dataclass、``hash()`` 却抛异常"的半吊子值。:class:`FrozenMapping`
   补上 ``__hash__``,于是 ``Block`` / ``Origin`` / ``OpaqueAddress`` 都是真正的值,
   能进 set、能当 dict 键。

这里做的只是**容器类型归一**(dict → FrozenMapping、list → tuple),不改任何取值,
因此不构成 A0 意义上的"默认动作"。
"""

from __future__ import annotations

from collections.abc import Mapping as AbcMapping
from typing import Iterable, Mapping, TypeVar

_K = TypeVar("_K")
_V = TypeVar("_V")
_T = TypeVar("_T")


class FrozenMapping(AbcMapping[_K, _V]):
    """不可变、可哈希的浅拷贝映射。与 ``dict`` / 任意 ``Mapping`` 按内容相等。"""

    __slots__ = ("_data", "_hash")

    def __init__(self, data: Mapping[_K, _V] | Iterable[tuple[_K, _V]] = ()) -> None:
        self._data: dict[_K, _V] = dict(data)
        self._hash: int | None = None

    def __getitem__(self, key: _K) -> _V:
        return self._data[key]

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: object) -> bool:
        return key in self._data

    def __eq__(self, other: object) -> bool:
        if isinstance(other, FrozenMapping):
            return self._data == other._data
        if isinstance(other, AbcMapping):
            return self._data == dict(other)
        return NotImplemented

    def __hash__(self) -> int:
        if self._hash is None:
            self._hash = hash(frozenset(self._data.items()))
        return self._hash

    def __repr__(self) -> str:
        return f"FrozenMapping({self._data!r})"


EMPTY_MAPPING: Mapping[str, str] = FrozenMapping()


def freeze_mapping(value: Mapping[_K, _V] | None) -> Mapping[_K, _V]:
    """返回 ``value`` 的不可变浅拷贝;``None`` → 空映射。已是 ``FrozenMapping`` 则原样返回。"""
    if value is None:
        return FrozenMapping()
    if isinstance(value, FrozenMapping):
        return value
    return FrozenMapping(value)


def freeze_tuple(value: Iterable[_T] | None) -> tuple[_T, ...]:
    """返回 ``value`` 的 tuple 拷贝;``None`` → 空 tuple。"""
    if value is None:
        return ()
    return tuple(value)
