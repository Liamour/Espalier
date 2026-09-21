"""内部工具:值类型 ↔ JSON 记录的双向编解码。

不是公开名(不进 ``espalier.__all__``);公开入口是 :mod:`espalier.persist` 的
``block_to_record`` / ``block_from_record`` / ``origin_to_record`` /
``origin_from_record`` 四个 re-export,以及 :meth:`espalier.Event.to_record`。

存在的理由:事件要落 JSONL,而 ``Appended`` / ``Opened`` / ``Replaced`` 三个事件
**随行携带块值**(见 :mod:`espalier.events` 的 V0-CHOICE),于是块 / 出身 / 载荷都要有
记录形。把它们放在私有模块里,是为了让 ``events`` 与 ``persist`` 都能用而不互相 import。

三条纪律:

* **判别键不叫 type**(v2.13 全库禁令)。Made 变体用 ``"made"``、地址用 ``"address"``、
  载荷用 ``"payload"`` 作判别键,取值是类名。
* **一切时戳落 ISO 8601 字符串**(``datetime.isoformat()``)。``canon_json`` 拒收
  ``datetime`` 正是为了逼这一步显式发生。
* **往返逐字段相等**:``x == from_record(to_record(x))`` 对本模块经手的每个类型成立。
  ``frozenset`` 落成排序列表、``tuple[tuple[int,int]]`` 落成嵌套列表,读回时复原容器型。

**扩展纪律**:给 ``Made`` 加变体要同时改四处——``origin.py`` 的 union / ``MADE_VARIANTS`` /
两张档表 + 本模块的 :func:`made_to_record` 与 :func:`made_from_record`。
``tests/test_events.py`` 按 ``MADE_VARIANTS`` 枚举往返,漏了就红。

**向后兼容纪律(v0.18,C-1..C-20)**:新字段读旧记录一律 ``record.get(key, 默认值)``——
旧记录缺键 ⇒ 字段默认值;写出来的新记录总是带全键。唯一的取值翻译在
``ToolReturned``:旧记录只有 ``ok`` ⇒ ``True → "ok"``、``False → "error"``(C-11)。

**C-12 口径(反驳补记)**:v0.17 的 ``Injected.configured_by`` 默认哨兵 ``"unknown"``
(语义 = 记录未说)在 v0.18 读回时**原样保留为字面串** ``"unknown"``,不翻译成 ``None``。
理由:C-12 把它改成开域字段,``"unknown"`` 从此也是一个合法的 harness 原词,读者无法从
记录本身分辨"旧写者的哨兵"与"新写者真的写了 unknown";翻译就是猜(A9:不编造)。
读到 ``"unknown"`` 的消费者若要按"未说"处理,须结合账本头的 ``format_version``(1 ⇒
v0.17 写者)自己判。同一口径对 ``blocking=False``(v0.17 默认)成立:原样读回。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

from ._freeze import freeze_mapping
from .block import Block, ChildLink, Claim, Ref
from .hashes import BytesHash, CallHash, ToolCallHash
from .ids import BlockId, CanonId, LedgerId
from .origin import (
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
    Recalled,
    Remainder,
    Templated,
    ToolReturned,
    Transformed,
    UrlAddress,
    Uttered,
    address_canon,
)
from .payload import Blob, ContentRef, Payload, Text

Record = dict[str, Any]


# --------------------------------------------------------------------------- 时间


def dt_to_iso(value: datetime) -> str:
    """``datetime`` → ISO 8601 字符串。库不替调用者选时区,原样落。"""
    return value.isoformat()


def dt_from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


# --------------------------------------------------------------------------- 载荷


def content_ref_to_record(ref: ContentRef) -> Record:
    return {"hash": str(ref.hash), "size": int(ref.size)}


def content_ref_from_record(record: Mapping[str, Any]) -> ContentRef:
    return ContentRef(hash=BytesHash(record["hash"]), size=int(record["size"]))


def payload_to_record(payload: Payload | None) -> Record | None:
    if payload is None:
        return None
    if isinstance(payload, Text):
        body = payload.body
        return {
            "payload": "Text",
            "canon": str(payload.canon),
            "inline": isinstance(body, str),
            "body": body if isinstance(body, str) else content_ref_to_record(body),
        }
    data = payload.data
    return {
        "payload": "Blob",
        "mime": payload.mime,
        # C-6:``data`` 按类型判别——ContentRef 记录有 ``hash`` 键,地址记录有 ``address`` 键。
        "data": content_ref_to_record(data) if isinstance(data, ContentRef) else address_to_record(data),
    }


def payload_from_record(record: Mapping[str, Any] | None) -> Payload | None:
    if record is None:
        return None
    kind = record["payload"]
    if kind == "Text":
        body = record["body"]
        return Text(
            canon=CanonId(record["canon"]),
            body=body if record["inline"] else content_ref_from_record(body),
        )
    if kind == "Blob":
        data = record["data"]
        if "hash" in data:
            return Blob(mime=record["mime"], data=content_ref_from_record(data))
        address = address_from_record(data)
        if address is None:
            raise ValueError("Blob record has neither a ContentRef nor an address in 'data'")
        return Blob(mime=record["mime"], data=address)
    raise ValueError(f"unknown payload record: {kind!r}")


# --------------------------------------------------------------------------- 地址


def code_site_to_record(site: CodeSite | None) -> Record | None:
    if site is None:
        return None
    return {"file": site.file, "line": site.line, "symbol": site.symbol}


def code_site_from_record(record: Mapping[str, Any] | None) -> CodeSite | None:
    if record is None:
        return None
    return CodeSite(file=record["file"], line=record["line"], symbol=record["symbol"])


def address_to_record(address: ExternalAddress | None) -> Record | None:
    """地址记录 = :func:`espalier.origin.address_canon`(身份部分)+ 时戳(``UrlAddress``)。"""
    if address is None:
        return None
    record: Record = dict(address_canon(address))
    if isinstance(address, UrlAddress):
        record["fetched_at"] = dt_to_iso(address.fetched_at)
    return record


def address_from_record(record: Mapping[str, Any] | None) -> ExternalAddress | None:
    if record is None:
        return None
    kind = record["address"]
    if kind == "FileAddress":
        return FileAddress(
            path=record["path"],
            offset=record["offset"],
            limit=record["limit"],
            cap=record["cap"],
            total=record["total"],
            version=record["version"],
            unit=record.get("unit"),  # C-26 / C-29:旧记录缺键 ⇒ None(记录未说)
            base=record.get("base"),
        )
    if kind == "UrlAddress":
        return UrlAddress(
            url=record["url"],
            fetched_at=dt_from_iso(record["fetched_at"]),
            version=record.get("version"),  # C-36:旧记录缺键 ⇒ None(记录未说)
        )
    if kind == "OpaqueAddress":
        return OpaqueAddress(scheme=record["scheme"], params=record["params"])
    raise ValueError(f"unknown address record: {kind!r}")


def remainder_to_record(remainder: Remainder | None) -> Record | None:
    if remainder is None:
        return None
    return {
        "address": address_to_record(remainder.address),
        "have": [segment.to_record() for segment in remainder.have],  # C-21:[start, stop, unit]
        "total": remainder.total,
        "unit": remainder.unit,
        "hit": sorted(remainder.hit),
        "continues": remainder.continues,
        "totals": dict(remainder.totals),
    }


def remainder_from_record(record: Mapping[str, Any] | None) -> Remainder | None:
    if record is None:
        return None
    continues = record["continues"]
    return Remainder(
        address=address_from_record(record["address"]),
        # C-21:三元 [a, b, unit];旧记录的两元 [a, b] 由 Remainder 构造器补上 ``unit``。
        have=tuple(tuple(segment) for segment in record["have"]),  # type: ignore[arg-type]
        total=record["total"],
        unit=record["unit"],
        hit=frozenset(record["hit"]),
        continues=BlockId(continues) if continues is not None else None,
        totals={str(k): int(v) for k, v in (record.get("totals") or {}).items()},  # C-1:旧记录缺键 ⇒ 空
    )


# --------------------------------------------------------------------------- Made / Origin


def claim_to_record(claim: Claim) -> Record:
    return {"address": address_to_record(claim.address), "note": claim.note}


def claim_from_record(record: Mapping[str, Any]) -> Claim:
    address = address_from_record(record["address"])
    if address is None:
        raise ValueError("Claim record has no address")
    return Claim(address=address, note=record.get("note"))


def claims_to_record(claims: Sequence[Claim]) -> list[Record]:
    return [claim_to_record(c) for c in claims]


def claims_from_record(record: Sequence[Mapping[str, Any]] | None) -> tuple[Claim, ...]:
    return tuple(claim_from_record(c) for c in (record or ()))


def _sources_to_record(sources: tuple[BlockId, ...] | None) -> list[str] | None:
    """C-4:``None``(未记录)与 ``[]``(已知为空)分别落记录。"""
    return None if sources is None else list(sources)


def _sources_from_record(value: Any) -> tuple[BlockId, ...] | None:
    """口径切换(v0.18):v0.17 写出的 ``sources: []`` 当时读作"整个 manifest",现在读成
    ``()`` = "已知为空";只有缺键 / ``null`` 才读成 ``None``。仓内没有持久化的 v0.17 账本,
    无实损;有的话需要按 ``[]`` → ``null`` 迁一遍。"""
    return None if value is None else tuple(BlockId(s) for s in value)


def made_to_record(made: Made) -> Record:
    """十变体 → 记录。判别键 ``"made"``,取值是变体类名。"""
    if isinstance(made, Uttered):
        return {
            "made": "Uttered",
            "role": made.role,
            "ledger": made.ledger,
            "site": code_site_to_record(made.site),
        }
    if isinstance(made, Authored):
        return {"made": "Authored", "by": made.by, "site": code_site_to_record(made.site)}
    if isinstance(made, Parsed):
        return {
            "made": "Parsed",
            "path": made.path,
            "codec": made.codec,
            "shape_name": made.shape_name,
            "canon": str(made.canon),
            "carried": origin_to_record(made.carried),
            "remainder": remainder_to_record(made.remainder),
            "span": address_to_record(made.span),
        }
    if isinstance(made, Templated):
        return {
            "made": "Templated",
            "template": made.template,
            "resolved": dict(made.resolved),
        }
    if isinstance(made, Transformed):
        return {
            "made": "Transformed",
            "op": made.op,
            "params_canon": made.params_canon,
            "sources": _sources_to_record(made.sources),
            "span": address_to_record(made.span),
        }
    if isinstance(made, LlmDerived):
        return {
            "made": "LlmDerived",
            "call": str(made.call),
            "ledger": made.ledger,
            "sources": _sources_to_record(made.sources),
            "instruction": made.instruction,
            "model": made.model,
            # C-35:无条件写全键(None 落 null),与同槽的 Parsed / ToolReturned / Recalled 同写法。
            "remainder": remainder_to_record(made.remainder),
        }
    if isinstance(made, ToolReturned):
        return {
            "made": "ToolReturned",
            "call": None if made.call is None else str(made.call),
            "tool": made.tool,
            "attempt": made.attempt,
            "outcome": made.outcome,
            "touched": [address_to_record(a) for a in made.touched],
            "remainder": remainder_to_record(made.remainder),
        }
    if isinstance(made, Injected):
        return {"made": "Injected"}  # V1:六个 hook 字段已退注记(``hook.*``),见 Injected docstring
    if isinstance(made, Computed):
        return {"made": "Computed", "provider": made.provider, "params_canon": made.params_canon}
    if isinstance(made, Recalled):
        return {
            "made": "Recalled",
            "memory": made.memory,
            "written_at": dt_to_iso(made.written_at),
            "carried": origin_to_record(made.carried),
            "ledger": made.ledger,
            "remainder": remainder_to_record(made.remainder),
        }
    raise TypeError(f"made_to_record has no entry for {type(made).__name__}")


def made_from_record(record: Mapping[str, Any]) -> Made:
    kind = record["made"]
    if kind == "Uttered":
        ledger = record["ledger"]
        return Uttered(
            role=record["role"],
            ledger=LedgerId(ledger) if ledger is not None else None,
            site=code_site_from_record(record["site"]),
        )
    if kind == "Authored":
        return Authored(by=record["by"], site=code_site_from_record(record["site"]))
    if kind == "Parsed":
        return Parsed(
            path=record["path"],
            codec=record["codec"],
            shape_name=record["shape_name"],
            canon=CanonId(record["canon"]),
            carried=origin_from_record(record["carried"]),
            remainder=remainder_from_record(record.get("remainder")),
            span=_file_address_from_record(record.get("span")),
        )
    if kind == "Templated":
        return Templated(
            template=BlockId(record["template"]),
            resolved={k: BlockId(v) for k, v in record["resolved"].items()},
        )
    if kind == "Transformed":
        return Transformed(
            op=record["op"],
            params_canon=record["params_canon"],
            sources=_sources_from_record(record.get("sources")),
            span=_file_address_from_record(record.get("span")),
        )
    if kind == "LlmDerived":
        ledger = record["ledger"]
        instruction = record["instruction"]
        return LlmDerived(
            call=CallHash(record["call"]),
            ledger=LedgerId(ledger) if ledger is not None else None,
            sources=_sources_from_record(record.get("sources")),
            instruction=BlockId(instruction) if instruction is not None else None,
            model=record["model"],
            remainder=remainder_from_record(record.get("remainder")),  # C-35:旧记录缺键 ⇒ None
        )
    if kind == "ToolReturned":
        call = record["call"]
        if "outcome" in record:
            outcome = record["outcome"]
        else:  # C-11:旧记录只有 ``ok``
            outcome = "ok" if record.get("ok", True) else "error"
        return ToolReturned(
            call=ToolCallHash(call) if call is not None else None,
            tool=record["tool"],
            attempt=record["attempt"],
            outcome=outcome,
            touched=tuple(address_from_record(a) for a in record["touched"]),  # type: ignore[misc]
            remainder=remainder_from_record(record["remainder"]),
        )
    if kind == "Injected":
        # 旧记录(v0.18–v0.21)的六个 hook 键不在这里读——它们由
        # :func:`legacy_hook_annotations` 搬进持有者(块 / 事件)的 ``annotations``。
        # 三条搬运路:``block_from_record``(块出身)、``event_from_record``(事件 actor)、
        # ``Opened.body_from_record``(复合出身)。**已知未覆盖**:嵌套在 ``Parsed.carried`` /
        # ``Recalled.carried`` 里的 ``Injected``(一个 carried 出身的 made 是 Injected)——
        # 这条路没有持有者能收那六键,读回只剩 ``Injected()``。没有任何夹具 / 写者写过
        # 这一形,搬进持有者要用带 ``via`` 前缀的键(如 ``Parsed.carried>hook.injector``),
        # 那是签核清单里没有的约定,留给 owner / fable 裁,不在这里自造。
        return Injected()
    if kind == "Computed":
        return Computed(provider=record["provider"], params_canon=record["params_canon"])
    if kind == "Recalled":
        ledger = record["ledger"]
        return Recalled(
            memory=record["memory"],
            written_at=dt_from_iso(record["written_at"]),
            carried=origin_from_record(record["carried"]),
            ledger=LedgerId(ledger) if ledger is not None else None,
            remainder=remainder_from_record(record.get("remainder")),
        )
    raise ValueError(f"unknown made record: {kind!r}")


def _file_address_from_record(record: Mapping[str, Any] | None) -> FileAddress | None:
    """``span`` 槽只收 ``FileAddress``(C-5);记录里是别的地址型就如实报错,不静默降级。"""
    address = address_from_record(record)
    if address is None or isinstance(address, FileAddress):
        return address
    raise ValueError(f"span must be a FileAddress record, got {record.get('address')!r}")


def actor_to_record(actor: Uttered | Authored | Injected | None) -> Record | None:
    """事件的 ``actor``(C-20):按 Made 记录形编码,``None`` 落 ``None``。"""
    return None if actor is None else made_to_record(actor)


def actor_from_record(record: Mapping[str, Any] | None) -> Uttered | Authored | Injected | None:
    if record is None:
        return None
    made = made_from_record(record)
    if not isinstance(made, (Uttered, Authored, Injected)):
        raise ValueError(f"event actor must be Uttered/Authored/Injected, got {type(made).__name__}")
    return made


def origin_to_record(origin: Origin | None) -> Record | None:
    """两轴 ``Origin`` → 记录。``arrived`` 落枚举**名**(不落序号:序号是实现细节)。"""
    if origin is None:
        return None
    return {
        "made": made_to_record(origin.made),
        "arrived": origin.arrived.name,
        "channel": origin.channel,
    }


def origin_from_record(record: Mapping[str, Any] | None) -> Origin | None:
    if record is None:
        return None
    return Origin(
        made=made_from_record(record["made"]),
        arrived=Arrived[record["arrived"]],
        channel=record["channel"],
    )


# --------------------------------------------------------------------------- 块


def refs_to_record(refs: Sequence[Ref]) -> list[list[str]]:
    return [[r.space, r.target] for r in refs]


def refs_from_record(record: Sequence[Sequence[str]]) -> tuple[Ref, ...]:
    return tuple(Ref(space=space, target=target) for space, target in record)


def children_to_record(children: Sequence[ChildLink]) -> list[list[Any]]:
    return [[link.child, link.gap] for link in children]


def children_from_record(record: Sequence[Sequence[Any]]) -> tuple[ChildLink, ...]:
    return tuple(ChildLink(child=BlockId(child), gap=int(gap)) for child, gap in record)


def block_to_record(block: Block) -> Record:
    """``Block`` → 记录。``_cache`` 不落(它是惰性 memoize 盒,不是字段)。"""
    return {
        "id": block.id,
        "kind": block.kind,
        "title": block.title,
        "payload": payload_to_record(block.payload),
        "children": children_to_record(block.children),
        "tail_gap": block.tail_gap,
        "origin": origin_to_record(block.origin),
        "refs": refs_to_record(block.refs),
        "cited_refs": refs_to_record(block.cited_refs),
        "cited_claims": claims_to_record(block.cited_claims),
        "annotations": dict(block.annotations),
    }


#: v0.18–v0.21 ``Injected`` 记录里的六个类型化键 → V1 注记键(A10,2026-09-08 签)。
HOOK_LEGACY_KEYS: tuple[tuple[str, str], ...] = (
    ("injector", "hook.injector"),
    ("configured_by", "hook.configured_by"),
    ("blocking", "hook.blocking"),
    ("decision", "hook.decision"),
    ("decision_scope", "hook.decision_scope"),
    ("decision_reason", "hook.decision_reason"),
)


def legacy_hook_annotations(made_record: Mapping[str, Any] | None) -> dict[str, str]:
    """把旧 ``Injected`` 记录里的六个键翻成 ``hook.*`` 注记(值转成字符串;``None`` 不搬)。

    只对 ``made == "Injected"`` 的记录有输出;新记录没有这些键,返回空。布尔按
    ``"true"`` / ``"false"`` 写(注记值是 ``str``);其余值 ``str()``。
    """
    if not made_record or made_record.get("made") != "Injected":
        return {}
    out: dict[str, str] = {}
    for old, new in HOOK_LEGACY_KEYS:
        value = made_record.get(old)
        if value is None:
            continue
        out[new] = ("true" if value else "false") if isinstance(value, bool) else str(value)
    return out


def merge_legacy_annotations(
    annotations: Mapping[str, Any] | None, legacy: Mapping[str, str]
) -> Mapping[str, Any]:
    """已有键不覆盖(作者写的优先),旧记录里的键补进去。"""
    if not legacy:
        return annotations or {}
    merged = dict(annotations or {})
    for key, value in legacy.items():
        merged.setdefault(key, value)
    return merged


def block_from_record(record: Mapping[str, Any]) -> Block:
    origin = origin_from_record(record["origin"])
    if origin is None:
        raise ValueError(f"block record {record.get('id')!r} has no origin; origin 是构造期必填字段")
    legacy = legacy_hook_annotations((record["origin"] or {}).get("made"))
    return Block(
        id=BlockId(record["id"]),
        kind=record["kind"],
        title=record["title"],
        payload=payload_from_record(record["payload"]),
        children=children_from_record(record["children"]),
        tail_gap=int(record["tail_gap"]),
        origin=origin,
        refs=refs_from_record(record["refs"]),
        cited_refs=refs_from_record(record["cited_refs"]),
        cited_claims=claims_from_record(record.get("cited_claims")),  # C-5:旧记录缺键 ⇒ ()
        annotations=freeze_mapping(merge_legacy_annotations(record["annotations"], legacy)),
    )
