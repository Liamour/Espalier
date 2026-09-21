"""espalier.expert —— 公开面第二层:透镜扩展点 + 验证器 / 工具作者用的哈希与流水函数。

V1 三层公开面(``docs/experiments/V1-SURFACE.md`` §2,owner 2026-09-08 签)的 expert 层,
29 名。它们在 v0.21 都是顶层公开名;瘦身后只被加分线(E-1..E-7)、论文案例与 LLM 跑器
引用,不是及格线 52 项参考实现所需,于是从 ``espalier`` 顶层退到这里。代码一行不搬:
本模块只是**再导出**,实现仍在各自模块。

两组:

* **透镜扩展点**(:mod:`espalier.lens`):``Lens`` / ``Shape`` / ``ShapeError`` /
  ``ShapeReport`` / ``Resolver`` / ``Step`` / ``SkillChain`` / ``SHAPES`` / ``SHAPE_SPACE`` /
  ``MEMORY_CLAIMED_KEYS`` / ``register_shape`` / ``shape_for`` / ``declared_shapes`` /
  ``check_declared``——要自定义 ``Shape``、或在 ``check`` 之外自己跑形状声明校验的人用。
  ``Skill`` / ``Memory`` / ``ToolResult`` / ``SkillFlow`` 这四个现成透镜留在 lite。
* **哈希与流水函数**:``sha256_hex`` / ``digest`` / ``hash_prefix`` / ``hash_body`` /
  ``is_hash``(:mod:`espalier.hashes`)、``is_canonical`` / ``payload_canon``
  (:mod:`espalier.payload`)、``chain_hash`` / ``state_hash`` / ``seal`` /
  ``event_from_record`` / ``UnknownEventKind``(:mod:`espalier.events`)、``spec_digest`` /
  ``manifest_bytes``(:mod:`espalier.manifest`)、``escape_text``(:mod:`espalier.render`)
  ——写独立验证器(重算链哈希、重验 manifest 指纹)或取回工具(逐行读流水)的作者用。

用法::

    from espalier.expert import Lens, Shape, register_shape, chain_hash, seal

第三层 internal(41 名:前缀常量、域常量、行级编解码、ULID 内部工具)不在这里,
只经模块路径可达,见 ``V1-SURFACE.md`` §3。
"""

from __future__ import annotations

from .events import UnknownEventKind, chain_hash, event_from_record, seal, state_hash
from .hashes import digest, hash_body, hash_prefix, is_hash, sha256_hex
from .lens import (
    MEMORY_CLAIMED_KEYS,
    SHAPE_SPACE,
    SHAPES,
    Lens,
    Resolver,
    Shape,
    ShapeError,
    ShapeReport,
    SkillChain,
    Step,
    check_declared,
    declared_shapes,
    register_shape,
    shape_for,
)
from .manifest import manifest_bytes, spec_digest
from .payload import is_canonical, payload_canon
from .render import escape_text

__all__ = [
    # ---- hashes
    "sha256_hex",
    "digest",
    "hash_prefix",
    "hash_body",
    "is_hash",
    # ---- payload
    "is_canonical",
    "payload_canon",
    # ---- events(链 / 状态哈希与流水)
    "UnknownEventKind",
    "chain_hash",
    "state_hash",
    "seal",
    "event_from_record",
    # ---- manifest
    "spec_digest",
    "manifest_bytes",
    # ---- render
    "escape_text",
    # ---- lens(扩展点)
    "Shape",
    "ShapeError",
    "ShapeReport",
    "Resolver",
    "Lens",
    "Step",
    "SkillChain",
    "SHAPES",
    "SHAPE_SPACE",
    "MEMORY_CLAIMED_KEYS",
    "register_shape",
    "shape_for",
    "declared_shapes",
    "check_declared",
]
