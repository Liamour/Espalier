"""身份标识:四个 NewType 与单调 ULID 生成器(DESIGN.md v2.2)。

v2.2 原文::

    BlockId  = NewType("BlockId", str)   # ULID
    LedgerId = NewType("LedgerId", str)
    CanonId  = NewType("CanonId", str)   # "c1" = LF + 纯空白行归一
    Seq      = NewType("Seq", int)       # 账本位置;参数名统一 at_seq

ULID 形制:48 bit 毫秒时戳 + 80 bit 随机,共 128 bit,以 Crockford base32 编成
**26 个字符**。字母表 ``0123456789ABCDEFGHJKMNPQRSTVWXYZ`` 在 ASCII 上严格递增,
故 ULID 字符串的字典序 == 其整数序,"单调"在字符串层面即可见。

**单调性口径**(V0-CHOICE):同一毫秒内、或时钟回拨时,不重新取随机数,而是把上一枚的
80 bit 随机部分 +1(时戳部分沿用上一枚,不回退)。因此同一个 ``UlidFactory`` 产出的序列
在字符串上严格递增,与真实时钟是否单调无关。80 bit 在一毫秒内耗尽时抛
``RuntimeError``——A0:宁可显式失败,不静默换语义。

A0 机制完备:时钟与熵源都可注入(``UlidFactory(clock=..., entropy=...)``),测试与
确定性重放不必打补丁;``encode_ulid`` / ``decode_ulid`` / ``ulid_timestamp_ms`` 三个
纯函数把编解码两向都露在外面。
"""

from __future__ import annotations

import os
import threading
import time
from typing import Callable, Final, NewType

__all__ = [
    "BlockId",
    "LedgerId",
    "CanonId",
    "Seq",
    "CANON_RAW",
    "CANON_C1",
    "CROCKFORD_ALPHABET",
    "ULID_LENGTH",
    "UlidFactory",
    "encode_ulid",
    "decode_ulid",
    "ulid_timestamp_ms",
    "is_ulid",
    "new_ulid",
    "new_block_id",
    "new_ledger_id",
    "default_ulid_factory",
]

BlockId = NewType("BlockId", str)
LedgerId = NewType("LedgerId", str)
CanonId = NewType("CanonId", str)
Seq = NewType("Seq", int)

#: 规范形名。v2.2 只给了 "c1";"raw" 是 V0-PLAN §3.1 定的运行期默认(F-2-D1)。
CANON_RAW: Final[CanonId] = CanonId("raw")
CANON_C1: Final[CanonId] = CanonId("c1")

#: Crockford base32(去掉 I / L / O / U)。ASCII 严格递增 ⇒ 字典序 == 数值序。
CROCKFORD_ALPHABET: Final[str] = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_CROCKFORD_DECODE: Final[dict[str, int]] = {
    char: index for index, char in enumerate(CROCKFORD_ALPHABET)
}

ULID_LENGTH: Final[int] = 26
_TIMESTAMP_BITS: Final[int] = 48
_RANDOM_BITS: Final[int] = 80
_MAX_TIMESTAMP: Final[int] = (1 << _TIMESTAMP_BITS) - 1
_MAX_RANDOM: Final[int] = (1 << _RANDOM_BITS) - 1


def encode_ulid(value: int) -> str:
    """128 bit 整数 → 26 字符 Crockford base32。"""
    if not 0 <= value < (1 << 128):
        raise ValueError(f"ULID value out of range: {value}")
    out = [""] * ULID_LENGTH
    for index in range(ULID_LENGTH - 1, -1, -1):
        out[index] = CROCKFORD_ALPHABET[value & 0x1F]
        value >>= 5
    return "".join(out)


def decode_ulid(text: str) -> int:
    """26 字符 Crockford base32 → 128 bit 整数。非法字符/长度抛 ``ValueError``。

    大小写不敏感(Crockford 规范);但本库自己只发大写。
    """
    if len(text) != ULID_LENGTH:
        raise ValueError(f"ULID must be {ULID_LENGTH} characters, got {len(text)}")
    value = 0
    for char in text.upper():
        digit = _CROCKFORD_DECODE.get(char)
        if digit is None:
            raise ValueError(f"not a Crockford base32 character: {char!r}")
        value = (value << 5) | digit
    if value >= (1 << 128):
        raise ValueError("ULID overflows 128 bits")
    return value


def ulid_timestamp_ms(text: str) -> int:
    """取 ULID 的毫秒时戳部分(高 48 bit)。

    注意:时戳**不入任何身份哈希**(v2.1 纪律⑤),它只是 id 自带的排序线索。
    """
    return decode_ulid(text) >> _RANDOM_BITS


def is_ulid(text: str) -> bool:
    """纯查询:``text`` 是不是一枚合法 ULID。永不抛。"""
    try:
        decode_ulid(text)
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def _system_clock_ms() -> int:
    return time.time_ns() // 1_000_000


class UlidFactory:
    """线程安全的单调 ULID 生成器。

    A0:``clock`` 与 ``entropy`` 都可注入——库自己不假设"只有一个时钟"。
    """

    __slots__ = ("_clock", "_entropy", "_lock", "_last_ms", "_last_random")

    def __init__(
        self,
        *,
        clock: Callable[[], int] | None = None,
        entropy: Callable[[int], bytes] | None = None,
    ) -> None:
        self._clock: Callable[[], int] = clock if clock is not None else _system_clock_ms
        self._entropy: Callable[[int], bytes] = entropy if entropy is not None else os.urandom
        self._lock = threading.Lock()
        self._last_ms: int = -1
        self._last_random: int = 0

    def next(self) -> str:
        """产出下一枚 ULID。同一个 factory 的产出严格字典序递增。"""
        with self._lock:
            now_ms = int(self._clock())
            if now_ms < 0 or now_ms > _MAX_TIMESTAMP:
                raise ValueError(f"clock outside ULID timestamp range: {now_ms}")
            if now_ms > self._last_ms:
                self._last_ms = now_ms
                self._last_random = int.from_bytes(self._entropy(10), "big")
            else:
                # 同毫秒 or 时钟回拨:时戳不回退,随机部分 +1(V0-CHOICE,见模块 docstring)
                if self._last_random >= _MAX_RANDOM:
                    raise RuntimeError(
                        "ULID randomness exhausted within one millisecond; "
                        "cannot stay monotonic without lying about the timestamp"
                    )
                self._last_random += 1
            return encode_ulid((self._last_ms << _RANDOM_BITS) | self._last_random)

    def next_block_id(self) -> BlockId:
        return BlockId(self.next())

    def next_ledger_id(self) -> LedgerId:
        return LedgerId(self.next())


#: 进程级默认 factory。调用者要确定性时自己建一个 ``UlidFactory``,不要改这个。
default_ulid_factory: Final[UlidFactory] = UlidFactory()


def new_ulid() -> str:
    return default_ulid_factory.next()


def new_block_id() -> BlockId:
    return default_ulid_factory.next_block_id()


def new_ledger_id() -> LedgerId:
    return default_ulid_factory.next_ledger_id()
