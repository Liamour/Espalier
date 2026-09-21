# Espalier

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22075256.svg)](https://doi.org/10.5281/zenodo.22075256)

English | [中文](README.zh.md)

Espalier is a Python library for people who build their own agent harness. It is a substrate, not a framework: an append-only ledger that records four kinds of fact on the harness's behalf.

- Where the bytes came from. Every block carries an `Origin` with two axes: who made the bytes, and which slot they arrived through.
- Who was shown what. Every model call records a `Manifest`, the list of what was actually sent, down to byte ranges.
- What later covered it. Compaction, replacement, removal, folding and exclusion each leave an event on the ledger.
- Addresses and remainders. When a file was only half read or a tool result was truncated, `ExternalAddress` and `Remainder` record where the rest is.

All of this is recorded mechanically and can be retrieved by id. The loop, the side effects and the policy stay in your harness.

## What it does not do

- It does not call models or tools. `served` and `returned` record the two ends of a call; you make the call yourself and hand the result to the library. `touched` and `Remainder.address` only record addresses; re-reading is the harness's job.
- It reads nothing from the outside world except its own log file. It depends on the environment in two places, and you can replace both: the clock used for event timestamps (`clock=`) and the ULID factory that makes ids (`ulids=`). `Ledger.create`, `open` and `fork` all accept them.
- It does not set policy for you. How far to compact, what to keep, whether to honor a field: the library gives you the mechanism and you choose the thresholds. `prune(Retention())` with an empty policy prunes nothing.
- It does not interpret the values you put in `annotations`. Key names are a documentation convention and the library does not validate them. If you want a closed vocabulary, validate it yourself.
- `check_ledger` reports and never blocks. It returns a report, raises nothing, and stops no write.

## Install

```sh
pip install -e .            # or skip installing: PYTHONPATH=src
```

Python ≥ 3.12, no dependencies. There are three version numbers, and each moves on its own:

| Line | Current | When it moves |
|---|---|---|
| Package version | `0.1.0` | Only when a package is published; none has been yet |
| git tag | `v1.3.1` | Milestones; a tag does not always mean the library changed |
| Log format `FORMAT_VERSION` | `5` | When the key set of persisted records, or the thin record that feeds the hashes, changes |

A file in an older format loads with a `format_version_behind` diagnostic. Whether to refuse it or upgrade it is the harness's decision.

## Core objects

Six objects to know first.

| Object | What it is | Note |
|---|---|---|
| `Block` | Payload + origin + annotations + children / refs | A frozen value. To change content use `replace`: it writes a new block and an event, and the old block stays on the ledger. To change only annotations use `annotate`; the id and the TreeHash stay the same |
| `Origin` | Two axes: `made` (who made the bytes, ten variants) × `arrived` (which slot they came through, nine channels) | `arrived` has no default. If you do not know, write `Arrived.UNKNOWN` explicitly |
| `Ledger` | An append-only event stream (eighteen event kinds) | Edits and deletions are events too. Almost every query takes `at_seq` / `leaf`, so you can ask what things looked like at a given moment |
| `View` → `render` → `Rendering` | View → pure function → text + `Manifest` | `render` writes nothing to the ledger. Rendering the same view with another spec does not affect the first |
| `served` / `returned` | The two ends of one model call | The call itself is yours. Write a `Returned(outcome="error")` for failed calls as well, or you cannot tell "failed" from "not back yet" |
| `retrieve` / `check_ledger` | Fetch by id / health check | Both are pure queries. One answers "where is it", the other "what does not add up" |

One model call:

```
append ──► view ──► render ──► served ──► (you call the model) ──► returned

  append    ledger.append(block)          writes an Appended event
  view      ledger.view()                 a plain value, nothing written
  render    render(view, spec)            pure function: text + Manifest, nothing written
  served    ledger.served(rendering, …)   writes a Called event; the manifest goes on the ledger with it
  (yours)   send rendering.text to the model; the library is not involved
  returned  ledger.returned(called, …)    writes a Returned event: usage, external ids, output block
```

## Minimal example

Create a ledger, append two blocks, render once, record the call with `served`, look at what the model saw with `manifest_of`, retrieve by id, then run `check_ledger`.

```python
from datetime import datetime, timezone

from espalier import (
    Arrived, Block, BlockId, Injected, Ledger, LedgerHeader, LedgerId,
    Origin, RenderSpec, Uttered, check_ledger, is_ulid, render,
)

header = LedgerHeader(id=LedgerId("demo"), created_at=datetime(2026, 9, 8, tzinfo=timezone.utc))
with Ledger.create(None, header=header) as ledger:  # path=None keeps it in memory; a path writes a JSONL log
    user = Block.create(
        "Make the README shorter.", kind="message",
        origin=Origin(made=Uttered(role="user"), arrived=Arrived.USER_SLOT),
    )
    hook = Block.create(
        "Repository rule: run the tests before committing.", kind="attachment",
        origin=Origin(made=Injected(), arrived=Arrived.ATTACHMENT),  # Injected is a marker with no fields
        annotations={"hook.injector": "before_prompt", "hook.blocking": "false"},
    )
    ledger.append(user)
    ledger.append(hook)

    rendering = render(ledger.view(), RenderSpec())               # pure function: text + manifest
    called = ledger.served(rendering, model="demo-model")         # writes Called; the manifest goes with it
    manifest = ledger.manifest_of(called.seq)                     # what the model saw this time
    ids = [BlockId(e.source) for e in manifest.entries            # source is one of BlockId / InlayKey / Absent
           if isinstance(e.source, str) and is_ulid(e.source)]
    got = ledger.retrieve(ids)                                    # by id: present / lost / external / unknown
    assert [b.id for b in got.present] == [user.id, hook.id]
    assert got.present[1].annotations["hook.injector"] == "before_prompt"

    report = check_ledger(ledger)                                 # pure query; reports, never blocks
    assert report.ok, [f.rule for f in report]
```

## I want to do X: what do I use

| I want to | Use | Note |
|---|---|---|
| Create, persist, reopen a ledger | `Ledger.create` / `Ledger.open` / `load` | `path=None` stays in memory; with a path, each event is one JSONL line |
| Record a conversation turn | `Block.create` + `ledger.append` | What the user said, what the model replied, what a tool returned: each gets its own `Origin` |
| Record a model call | `render` → `ledger.served` → `ledger.returned` | The library records the two ends; you make the call |
| Ask what the model saw on a call | `ledger.manifest_of` / `ledger.saw` | A CallHash, a ManifestHash or a Seq all fetch the same manifest |
| Ask which calls sent a block | `ledger.calls_showing` | Returns a tuple of `Seq`; an empty tuple on no match, no exception |
| Check a reply against what was sent | `ledger.verify` | Four verdicts: `Verified` / `Stale` / `Mismatch` / `Unverifiable` |
| Control what gets sent | `RenderSpec`: `exclude` / `fold` / `absent` / `inlays` / `ids` / `fence` | You set the policy; the library renders to the spec and records those decisions in the manifest |
| Compact the context | `ledger.prepare_compact` → `ledger.commit_with_receipt` | Two steps: fix what to compact, then write to the ledger. Any amount of time may pass in between |
| Remove, edit, merge, revoke | `remove` / `replace` / `merge` / `restore` / `prune` / `revoke` | All of them are events; `supersedes` tells you which blocks a block replaced |
| Wrap a turn into one block | `ledger.open_composite` → `close` | The id is assigned on open, so an unfinished turn can already be rendered |
| Fork a ledger, checkpoint, mark a resume | `ledger.fork` / `checkpoint` / `resumed` | fork replays the parent's prefix; you record resumes yourself, `open()` does not |
| Store session-level settings | `ledger.configure` / `ledger.setting(name, at_seq=…)` | Values are plain strings, the last one wins, and you can evaluate at any point in time |
| Parse Markdown files such as skills or memories | `parse_tree` / `render_authoring` / `frontmatter_entries` | The round trip holds byte for byte on the canonical form `c1`, which may differ from the original text |
| Read skills, memories, tool results by shape | `Skill` / `Memory` / `ToolResult` / `SkillFlow` | `.of` raises when the shape does not fit, `.check` reports without raising; the two always agree |
| Keep large payloads off the ledger | `Text.of(ref)` / `Blob` / `MemoryContentStore` | Bytes go into the CAS or stay at an external address; the block keeps a reference |
| Get information back by id | `ledger.retrieve(ids)` | Four groups: present / lost / external / unknown. An id the ledger has never seen goes to unknown, not lost |
| Health-check a ledger | `check_ledger` (= `ledger.check()`) | `.ok` looks at errors only; warnings state facts and do not affect `.ok` |
| Recompute hashes for independent verification | `chain_hash` / `seal` / `state_hash` from `espalier.expert` | Replay the chain event by event and compare `.link`, without trusting what the ledger recorded |

The six recipes below are the most common ones. Each runs as is.

### Record a turn with a tool call

```python
from datetime import datetime, timezone

from espalier import (
    Arrived, Block, FileAddress, Ledger, LedgerHeader, LedgerId, Origin,
    Remainder, ToolReturned, Uttered, tool_call_hash,
)

led = Ledger.create(None, header=LedgerHeader(
    id=LedgerId("turn"), created_at=datetime(2026, 9, 5, tzinfo=timezone.utc)))
led.append(Block.create("List the files under src/.", kind="message",
                        origin=Origin(made=Uttered(role="user"), arrived=Arrived.USER_SLOT)))
# The model's reply is not recorded in this recipe. When your own loop calls the model, the reply
# block is LlmDerived(call=called.call, …), bound to that call; see the next recipe. Use
# Uttered(role="model") only when ingesting another harness's transcript and you do not have the
# manifest of what was sent: that variant means "a model on another ledger".

# A truncated tool result: the part you have is on the ledger, and an address is kept for the rest
# so the harness can re-read it later
where = FileAddress(path="src/espalier", offset=0, limit=5, total=18, unit="line", base=0)
result = Block.create(
    "block.py\ncalls.py\ncheck.py\ncodec.py\ncompact.py\n...(13 more)",
    kind="tool_result",
    origin=Origin(
        made=ToolReturned(
            call=tool_call_hash("Read", {"path": "src/espalier"}),
            tool="Read",
            touched=(where,),                       # what this tool call read or wrote outside
            remainder=Remainder(address=where, have=((0, 5),), total=18,
                                unit="line", hit=frozenset({"limit"})),
        ),
        arrived=Arrived.TOOL_RESULT_SLOT,
    ),
)
led.append(result)

got = led.retrieve([result.id])
assert [b.id for b in got.present] == [result.id]
assert got.external == ((result.id, where),)        # the address of the rest, found by id
```

`Remainder.unit` accepts only `str`; `None` raises `ValueError`. If you do not know the unit, do not build a `Remainder`: the library will not fill one in for you. `touched` (what the tool read or wrote outside) and `remainder.address` (where to re-read the truncated part) are two separate slots, and you may fill only one.

### Before and after a model call

```python
from datetime import datetime, timezone

from espalier import (
    Arrived, Block, Ledger, LedgerHeader, LedgerId, LlmDerived, Origin,
    RenderSpec, Uttered, Verified, render,
)

led = Ledger.create(None, header=LedgerHeader(
    id=LedgerId("call"), created_at=datetime(2026, 9, 5, tzinfo=timezone.utc)))
led.append(Block.create("What is 2+2?", kind="message",
                        origin=Origin(made=Uttered(role="user"), arrived=Arrived.USER_SLOT)))

rendering = render(led.view(), RenderSpec())                  # the text to send + the manifest
called = led.served(rendering, model="m1", params={"temperature": 0})

# Here the harness sends rendering.text to the model itself; the library is not involved
reply = led.append(Block.create(
    "4", kind="text",
    origin=Origin(made=LlmDerived(call=called.call, model=called.model),
                  arrived=Arrived.ASSISTANT_SLOT),   # you write this origin; the library will not
)).block_value
returned = led.returned(called, outcome="ok", output=reply.id,
                        usage={"input": 12, "output": 1},
                        external_ids={"request_id": "req-42"})

assert led.manifest_of(called.call) == rendering.manifest   # CallHash / ManifestHash / Seq fetch the same manifest
assert returned.usage == {"input": 12, "output": 1}         # usage lives on Returned: not in CallHash, but in the audit chain
assert isinstance(led.verify(reply.id), Verified)           # the reply block matches what was sent
```

For a reply block to be verifiable later, you have to write its `origin.made` as `LlmDerived(call=called.call, …)`. The library does not mark it for you.

### Asking afterwards

```python
from datetime import datetime, timezone

from espalier import (
    Arrived, Block, Ledger, LedgerHeader, LedgerId, LlmDerived, Origin,
    Stale, Unverifiable, Uttered, render,
)

USER = Origin(made=Uttered(role="user"), arrived=Arrived.USER_SLOT)
led = Ledger.create(None, header=LedgerHeader(
    id=LedgerId("audit"), created_at=datetime(2026, 9, 5, tzinfo=timezone.utc)))
first = led.append(Block.create("The release is on Thursday.", kind="text", origin=USER)).block_value
rendering = render(led.view())
called = led.served(rendering, model="m1")
reply = led.append(Block.create(
    "Noted.", kind="text",
    origin=Origin(made=LlmDerived(call=called.call, model="m1"), arrived=Arrived.ASSISTANT_SLOT),
)).block_value

# Looking back: what did the call that produced this block see
assert led.saw(reply.id) == rendering.manifest
assert led.saw(first.id) is None                       # its origin is not LlmDerived, so the question does not apply
# Looking forward: which calls sent this block
assert led.calls_showing(first.id) == (called.seq,)

# The source is edited later, so the verdict is Stale (the other three: Verified / Mismatch / Unverifiable)
led.replace(first.id, Block.create("The release moved to Friday.", kind="text", origin=USER))
verdict = led.verify(reply.id)
assert isinstance(verdict, Stale) and verdict.changed == (first.id,)
assert isinstance(led.verify(first.id), Unverifiable)
assert led.get_block(first.id).payload.body == "The release is on Thursday."   # the old block is still on the ledger
```

`Stale` means a source was replaced or removed afterwards. `Mismatch` means the records contradict each other. The two are decided by different criteria. `Unverifiable` only means the question cannot be answered here.

### Render control: exclude, fold, absent

```python
from datetime import datetime, timezone

from espalier import (
    Absent, Arrived, Block, Ledger, LedgerHeader, LedgerId, Origin,
    RenderSpec, Uttered, render,
)

USER = Origin(made=Uttered(role="user"), arrived=Arrived.USER_SLOT)
led = Ledger.create(None, header=LedgerHeader(
    id=LedgerId("render"), created_at=datetime(2026, 9, 5, tzinfo=timezone.utc)))
kept = led.append(Block.create("body text", kind="text", origin=USER)).block_value
secret = led.append(Block.create("inner monologue", kind="thinking", origin=USER)).block_value
long_leaf = led.append(Block.create("a long passage\nsecond line", kind="text", origin=USER)).block_value
comp = led.open_composite(kind="turn", origin=USER)
comp.append(Block.create("turn content", kind="text", origin=USER))
comp.close()

spec = RenderSpec(
    exclude_why={secret.id: "thinking block, not sent to the model"},   # exclude, and record why
    fold=frozenset({long_leaf.id, comp.id}),                             # fold into a one-line summary
    absent=((kept.id, Absent(reason="attachment missing from the transcript")),),  # sent, but not on the ledger
)
rendering = render(led.view(), spec)

assert "inner monologue" not in rendering.text
assert rendering.manifest.excluded_why == {secret.id: "thinking block, not sent to the model"}
assert long_leaf.id in rendering.manifest.expandable()         # only blocks that did fold are in this set
# To find folds that were requested but did not happen, take the difference. fold applies only to
# leaf blocks in the runtime realm; composites and authoring-realm blocks are not folded, and no error is raised.
assert frozenset(spec.fold) - rendering.manifest.expandable() == {comp.id}
assert any(isinstance(e.source, Absent) for e in rendering.manifest.entries)
```

There are two ways to exclude: `View.without_` on the view, and `RenderSpec.exclude` / `exclude_why` on the spec. `render` merges them into one set before rendering, so a block the manifest lists as excluded never has its bytes sent.

### Two-step compaction

```python
from datetime import datetime, timezone

from espalier import (
    Arrived, Block, Ledger, LedgerHeader, LedgerId, LlmDerived, Origin, RenderSpec, Uttered,
    render,
)

USER = Origin(made=Uttered(role="user"), arrived=Arrived.USER_SLOT)
led = Ledger.create(None, header=LedgerHeader(
    id=LedgerId("compact"), created_at=datetime(2026, 9, 5, tzinfo=timezone.utc)))
first = led.append(Block.create("the first long message", kind="text", origin=USER)).block_value
second = led.append(Block.create("the second long message", kind="text", origin=USER)).block_value

# Step one: read only, no events. It fixes which blocks to compact and the prompt to send;
# you can commit minutes later.
req = led.prepare_compact([first.id, second.id])
assert req.targets == (first.id, second.id) and isinstance(req.prompt, str)

# Here the harness sends req.prompt to the model and gets the summary text back
# Step two: four events in one write (Called / Appended / Returned / Compacted).
receipt = led.commit_with_receipt(
    req, "The user sent two long messages, both about scheduling.", model="m1",
    usage={"input_tokens": 120, "output_tokens": 12},
)
assert receipt.targets_match and receipt.conflicts == ()      # nothing was written between the two steps
assert receipt.summary.origin.made == LlmDerived(
    call=receipt.called.call, model="m1", sources=(first.id, second.id))
assert dict(receipt.returned.usage) == {"input_tokens": 120, "output_tokens": 12}
assert led.get_block(first.id).payload.body == "the first long message"   # compacted blocks stay on the ledger

# Compaction does not replace the originals: the default view still has them, with the summary last.
# Exclude the compacted blocks yourself on the next render.
assert led.view().block_ids() == (first.id, second.id, receipt.summary.id)
spec = RenderSpec(exclude_why={block_id: "compacted" for block_id in req.targets})
text = render(led.view(), spec).text
assert "the first long message" not in text and "both about scheduling" in text
```

The ledger stays writable between `prepare_compact` and `commit`. Blocks written in that window are outside the covered range, and `CommitReceipt.conflicts` lists them. `ledger.commit()` is the same implementation without the receipt.

Three things to know before using compaction:

1. Compaction does not replace the original blocks (see the last lines of the code above). After reopening a ledger, read `ledger.compactions()` to find out what a compaction covered.
2. When you pass `instruction=`, the instruction block must be appended first. Otherwise the summary block's lineage edge points to a block that is not on the ledger, and `check` reports an error.
3. With a composite block as the target, `targets_match` is always `False`. This is expected: the equation is a set difference over ids, and the nested children all count. In that case the library records the targets explicitly in `Compacted.targets`. When `Compacted.targets` is `None` the equation holds, and you recompute what was covered by definition: blocks present at `base_seq` whose seq falls inside `covers`, minus `kept`.

### Persist and reopen

```python
from datetime import datetime, timezone
from pathlib import Path

from espalier import (
    Arrived, Block, Ledger, LedgerHeader, LedgerId, Origin, Uttered, load,
)

USER = Origin(made=Uttered(role="user"), arrived=Arrived.USER_SLOT)
path = Path("session.jsonl")

led = Ledger.create(path, header=LedgerHeader(         # with a path it persists: one JSONL line per event
    id=LedgerId("sess"), created_at=datetime(2026, 9, 5, tzinfo=timezone.utc)), fsync=False)
note = led.append(Block.create("Picking up where we left off.", kind="message", origin=USER)).block_value
led.close()

report = load(path)                                    # format problems do not raise; they are in the report
assert report.ok and report.errors == ()

again = Ledger.open(path)                              # strict=True by default: a fatal diagnostic raises LoadError
assert again.block_ids() == (note.id,)
assert again.get_block(note.id).payload.body == "Picking up where we left off."
resumed = again.resumed()                              # you record "the session resumes here"; the library does not
assert resumed.tip_before == again.tip - 1
again.close()
```

In-memory and persisted ledgers share one API and behave the same over the same records. Pass `None` during development and a path in production; the code does not change. `Ledger.create` does not overwrite an existing non-empty ledger; it raises `FileExistsError`.

`load` does not raise on format problems; they all go into the `LoadReport`: bad JSON, a wrong version, a torn last line (including one cut in the middle of a multi-byte character by a crash). IO errors such as a missing file are raised as usual and are the caller's to handle.

## Where information goes: typed fields or `annotations`

The rule: a field exists only for information the library itself interprets; everything else goes into `annotations`. Annotation keys are a documentation convention. The library stores and carries the values and does not interpret them. If you want a closed vocabulary, validate it yourself.

For example, a vendor's usage report has some integer items and some that are not. Flatten the integer items into `Returned.usage` (its type is `Mapping[str, int]`) and put the rest into the `annotations` of that response. Nothing is lost, and the library does not need a field for every vendor's record shape.

The six hook facts work the same way. `Injected` is a marker variant with no fields (its type still decides the trust class, THIRD_PARTY). The six facts go on the `annotations` of whatever holds them, a block or an event:

| Key | Value |
|---|---|
| `hook.injector` | Which hook or event name injected it |
| `hook.configured_by` | Who configured it (user / project / plugin / …; the harness's own words, open vocabulary) |
| `hook.blocking` | `"true"` / `"false"`; a missing key means the record did not say |
| `hook.decision` | The harness's own word (deny / block / ask / allow / continue:false / …) |
| `hook.decision_scope` | call / turn / task / session … |
| `hook.decision_reason` | The reason, verbatim |

Older records (v0.18–v0.21) stored these six facts as typed fields on `Injected`. On load the library moves them into `annotations` (an existing key of the same name is not overwritten), and no byte is lost.

### Reading `None`

The library records "the record did not say" and "known to be empty" separately. `Transformed.sources` has three values: `None` means this record did not state its sources; `()` means it did, and there are none; a non-empty tuple is the actual relation. `origin_sources` yields no edges for the first two, so to tell them apart you have to look at the field itself; the absence of edges does not tell you.

For `Remainder`, what `None` means depends on the variant that holds it. On `ToolReturned` / `Parsed` / `Recalled` it reads "not truncated". On `LlmDerived` it reads "no testimony", because on the model side a stop_reason is usually available, and not having recorded it does not mean nothing was truncated. Generic code that walks the `remainder` slot across variants has to handle the two readings separately.

## What the library promises

1. **Nothing lost, nothing made up** (A9). Old records load without losing a byte. What a record did not say stays `None` or a missing key; the library fills in no defaults. An id it has never seen goes to unknown, not lost.
2. **Mechanism, not policy** (A0). Default values are allowed, default actions are not: `check_ledger` reports and never blocks, `render` is a pure function, and an empty retention policy prunes nothing.
3. **The library calls no model and no tool** (A8). It prepares what to send before a call and records afterwards; every side effect is yours to perform.
4. **Fields only for what the library interprets** (A10). A field that some library function reads is never demoted to an annotation. Everything else goes into `annotations`, which the library stores and carries without interpreting.
5. **Lossless fallback by construction** (A5). Structure the parser does not recognize is wrapped as an opaque block as is; this does not depend on how much the parser recognizes.

Where the library's docstrings mention A0 / A5 / A8 / A9 / A10, they mean these five.

## Three import layers

The public surface has three layers:

| Layer | Import | Names | For whom |
|---|---|---|---|
| lite | `from espalier import Ledger, Block, render, …` | 175 | Everyday use: ledger, blocks, origins, events, rendering, manifests, retrieval, checks |
| expert | `from espalier.expert import Lens, Shape, chain_hash, seal, …` | 29 | Lens extension points; hash and log functions for people writing verifiers or retrieval tools |
| internal | `espalier.hashes.BYTES_HASH_PREFIX`, `espalier.persist.event_line`, … | 41 | Reachable only by module path: prefix constants, line-level codecs, ULID internals |

Nine more public APIs are methods of `Ledger`: `served` / `returned` / `manifest_of` / `saw` / `verify` / `calls_showing` / `prepare_compact` / `commit` / `commit_with_receipt`. They are not importable names, so they are not in `__all__`; you call them as `ledger.served(…)`.

## Specification, license and author

- `spec/` holds the specification text of the method (rules, evidence, templates); this library is its implementation for agent context ledgers.
- License: this library (`src/`, both READMEs, `pyproject.toml`) is released under the MIT license, see `LICENSE-CODE`; the documents under `spec/` are released under CC BY 4.0, see `LICENSE`.
- Citation: DOI [10.5281/zenodo.22075256](https://doi.org/10.5281/zenodo.22075256) (see `CITATION.cff`).
- Author: Yu-Chi TSOU (Liamour).
