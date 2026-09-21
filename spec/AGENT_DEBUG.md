# Agent debugging under derivation

A normative specification for making agent misbehavior debuggable by lookup rather than by recollection.

| | |
|---|---|
| Version | 0.1.0-draft.1 |
| Date | 2026-08-20 |
| Author | Yu-Chi TSOU (Liamour) |
| License | CC BY 4.0 |
| Status | Working Draft |
| Home | https://github.com/Liamour/Espalier |
| Feedback | https://github.com/Liamour/Espalier/issues |
| Companion documents | `SPEC.md` (Espalier, normative), `CAPABILITY_HOST.md` (capability systems under Espalier, normative), `RATIONALE.md` and `TEMPLATES.md` (informative) |

**Status of this document.** This is a Working Draft. It may be updated, replaced, or obsoleted at any time; cite it only as work in progress, by exact version. The author ratifies the transition from Working Draft to a release version; a release requires at least one implementation assessed at Level 2 against the frozen text.

## Abstract

An agent system misbehaves when the model does something the operator did not want. The operator's first question is always the same: what did the model actually see. In current practice that question has no lookup. The served context is assembled at run time from declarations, hand-written tables, policy filters, disclosure budgets, and literals inlined in the assembler, and nothing records which of them produced which served line. The question is therefore answered by reading source and remembering what the assembler used to do, which is debugging by recollection, and recollection is the rung of the guarantee ladder that agent-era development deletes.

This specification states the condition under which the question becomes mechanical. Agent misbehavior is debuggable exactly when the influence set on the model's context is a closed, enumerable set, and derivation is what closes it. A host that derives every served surface from declarations has a finite, listable set of things that can change what the model saw. A host that hand-assembles context has an unbounded influence set: any edit anywhere in any table, prompt file, or assembler literal may or may not have moved the served bytes, and no artifact can say which did.

From that condition the specification derives three mandatory queries (forward slice, reverse slice, run diff), a normative schema for the provenance artifact that answers them, a failure taxonomy keyed to the guarantee ladder of `SPEC.md` section 4, a debug protocol that orders the lookups, and the instrument requirements without which none of it is measurable. Every requirement cites the experiment and result it rests on, or is marked as design inference not yet measured. Two results that refute parts of the surrounding paradigm are stated here with the same prominence as the confirmations, because a specification that hides its refutations cannot be used to plan.

## Conformance notation

The key words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, NOT RECOMMENDED, MAY, and OPTIONAL in this document are to be interpreted as described in BCP 14 [RFC2119] [RFC8174] when, and only when, they appear in all capitals, as shown here.

This conformance-notation section, section 3, sections 4 through 10, and the normative-references list in section 13 are normative; all other content, including the abstract, the worked example at the end of section 7, and the annexes, is informative. Section 3 states definitions and contains no BCP 14 keyword, so its normative status binds the vocabulary the requirements are written in without adding a requirement of its own; [ESPALIER] section 3 is normative for the same reason and governs any term the two sections share.

The capitalization discipline is load-bearing: because only all-capital keywords in normative sections carry requirements, a checker can mechanically enumerate every requirement in this document. Every requirement carries a number, and every BCP 14 keyword in a normative section sits inside a numbered requirement; a keyword in unnumbered prose is an editorial defect in this document. Three constructions are inside a numbered requirement without repeating its number: a lettered sub-clause belongs to the requirement that introduces it and is cited as such, as in 6.11(d); the level blocks of section 10 enumerate requirement numbers under the general obligation of 10.2 and add none of their own; and the field-obligation tables of section 6 belong to 6.1, which states the obligations their marks carry and is the number a level cites to reach them.

This document and `CAPABILITY_HOST.md` are mutually normative companions of one parent standard. Where they state incompatible requirements on one subject, [ESPALIER] 9.1.9 settles which governs: this document governs the provenance artifact, its schema, its queries, and the classification of a difference between two artifacts; `CAPABILITY_HOST.md` governs the declaration, derivation, exposure, disclosure, and service of capabilities. A conflict outside those two scopes is a defect in both documents and is resolved against [ESPALIER].

Evidence marking is also load-bearing. Every normative requirement below carries one of two marks. A parenthetical citation of the form `(exp-N: result)` names the experiment and the measured result the requirement rests on; the annex resolves each citation. The phrase **Design inference, not yet measured** marks a requirement that follows from the model of the problem and has no measurement behind it. A requirement carrying neither mark is an editorial defect in this document, with one stated exception: the requirements of section 10 govern the form of a conformance claim and rest on no measurement.

## 1. Scope

This specification applies to any system that assembles a context window for a language model from more than one declaration site, and that must be debugged after the fact by someone who was not present when the context was assembled. Typical shapes are agent hosts with layered system prompts, capability catalogs, per-caller projections, and progressive disclosure.

It governs the recording and querying of what was served: which lines reached the model, which declaration each line came from, what was withheld, and how two servings differ. It does not govern what should be served; that is the subject of `CAPABILITY_HOST.md`. It does not govern the model's reasoning, the quality of the served prose, or the correctness of the capability payloads.

It assumes the host conforms to `SPEC.md` rule 6 as amended: registration is the single declaration from which every declared surface derives, exposure is a governed projection of that declaration, and no parallel hand-maintained exposure table exists. A host that does not meet that precondition can adopt the instrument requirements of section 9 and claim Level 1 on that basis, and nothing above it, because its influence set is not closed and its artifacts would be incomplete in ways no check can bound. Level 1 is pure archiving and attributes nothing, which is why it is open to such a host; 4.1 states the bar it cannot pass.

Out of scope: federated debugging across independently versioned hosts; attribution of behavior to model weights or sampling; and any claim that instrumentation improves task success. The last is explicit because it was measured and not found (exp-2: completeness family not significant under Holm, n=5 per arm).

## 2. The problem (informative)

Three observations motivate this specification.

**The served prompt is a derived artifact that nothing records.** It is produced at run time and then discarded. When an agent misroutes, refuses, or invents, the operator reconstructs the prompt by reading the tree and reasoning about what the assembler would have produced under that mount. The reconstruction is a hypothesis, and it is tested against a memory of what the tree looked like at the time. In a controlled study this reconstruction was measurable work: answering "what did this caller see, and what was kept from it" required opening the declarations and simulating the projection by hand, and the same two questions became a single file lookup once the provenance artifact existed (exp-M4: both questions answered from the artifact with no source file opened).

**The wrong fix is cheap and plausible.** When an agent ignores an instruction, the reflex is to reword the instruction. That fix is correct only when the instruction was served and was ambiguous. It is useless when the instruction was never served, and it is worse than useless when the instruction was served, read, and overridden, because it consumes a cycle and leaves the guarantee on the same rung it already failed on. A measured case exists in which a model recited the exact withheld information the served line carried, and then refused anyway, deterministically, three times out of three on the strongest model tested (exp-3: C3 refuted on the flagship model, 9/12 against 12/12, all three failures the same task, all false refusal, all with zero searches). No amount of rewording addresses that failure. Moving the guarantee from prompt text to protocol structure did address it (exp-3: NARROW_GATED restored 12/12; the failing unit went 0/3 to 3/3).

**Recollection is the rung that agent development deletes.** `SPEC.md` section 4 ranks guarantees as structure, machine check, human memory, and observes that an agent session retains approximately nothing it was not directed to read. Debugging by recollection is a memory-tier practice applied to the one artifact that changes on every mount. It degrades exactly as the share of agent-implemented change grows, which is the environment this method was written for.

## 3. Terms and definitions

Normative as vocabulary; see the conformance notation. Terms this document shares with [ESPALIER] section 3 carry the parent standard's definition.

**served surface.** Any text the model can read: the assembled system prompt, a catalog row, a tool declaration, a search result. The context window is itself a served surface and falls under `SPEC.md` rule 9.1.

**mount.** The declared boundary at which the projection is computed: session assembly, host construction, or process start. A mount has a state: which roots were mounted, which policy applied, which disclosure budget was in force.

**caller.** The declared principal a projection is computed for. Two callers at one mount receive two different served surfaces from one registry.

**projection.** The derived, per-caller view of the registry that becomes a served surface. Written as `exposure = projection(registry, policy, caller, entry, budget)`, which is the closed five-input set of [ESPALIER] 9.1.6.

**group.** A declared grouping of capabilities, used as the unit an announcement names when naming individual withheld capabilities would be too long. The evidence record calls them bundles.

**influence set.** The set of declaration sites whose change can change what a given caller saw at a given mount. Closed when every served line is derived from an enumerable declaration; unbounded otherwise.

**provenance artifact.** The sidecar record of one caller's served prompt at one mount: one record per non-empty served line naming the declaration it came from, plus a header recording the mount state.

**sidecar.** An artifact emitted beside the served bytes and never inserted into them.

**forward slice.** The query from a declaration to every served surface it moved.

**reverse slice.** The query from an observed served line to the declaration behind it and the mount state around it.

**run diff.** The classified difference between two provenance artifacts of the same caller.

**unattributed line.** A served line that matches no string the host declares. A finding about the host, recorded and counted, never assigned to the nearest plausible declaration.

**withholding.** A capability registered but not projected to this caller. Under `SPEC.md` 9.1 it is a declaration, never an omission.

**announcement.** A served line stating that a withholding occurred, carrying a derived count and the withheld names.

**guarantee tier.** As in `SPEC.md` section 4: structure, machine check, or human memory.

**assembly defect.** A misbehavior whose cause is that the intended line never reached the served surface.

**prompt-tier failure.** A misbehavior whose cause is that the line reached the served surface, was read, and was overridden by the model's prior.

**structure-tier failure.** A misbehavior whose cause is that the protocol itself permits the bad action.

## 4. The bounded influence set

The thesis of this specification is stated as a requirement because everything else follows from it mechanically.

- **4.1** A conforming host MUST compute every served surface as a projection of an enumerable set of declarations, and MUST be able to list that set. The list is the influence set. A host that cannot list it MUST NOT claim Level 2 or above under this specification, because attribution and the queries of section 5 have no defined answer over an open set. Level 1 is the archiving level and depends on no closed set, so it remains open to such a host, which is the case section 1 describes; a host claiming Level 1 with an open influence set MUST record the openness as a memory-tier entry under [ESPALIER] 4.3, so that the gap carries a promotion destination rather than passing as a decision. **Design inference, not yet measured** as an inability proof; the positive half is measured in that a host whose surfaces are all derived supports complete attribution of every served line (exp-M4: four frozen readings, 16/16, 14/14, 17/17 and 15/15 non-empty lines attributed, zero unattributed).

- **4.2** The projection MUST be derived once at a declared mount, not per turn. A per-turn projection is not a contract, nothing can validate it, and no artifact can describe a served surface that is rebuilt between the observation and the lookup. **Design inference, not yet measured** for the prohibition, at the same strength `CAPABILITY_HOST.md` 7.2 states it: the per-turn alternative was not run as an arm. The supporting observation is an arm-construction fact between two boundary-derived arms (exp-3: the NARROW and NARROW_GATED arms are byte-identical by sha256 because both render through one projection path, which is what isolated the host's refusal gate as the only difference between them), and that a per-turn projection would have made the isolation unavailable is the inference, not the measurement.

- **4.3** Every projection input MUST be recorded in the provenance artifact, and each MUST have exactly one declared recording location, so that an assessor reads each input in one place. A location MAY name more than one field where the input is itself compound, as policy is, and no field may serve two inputs. The input set is the closed five of [ESPALIER] 9.1.6, restated verbatim by `CAPABILITY_HOST.md` 8.2 and tabulated here with the recording location of each: the registry, the policy, the caller identity, the entry declaration, and the budget. The table below is the validated recording (exp-M4: registry, policy, caller identity and budget are recorded explicitly in every emitted artifact, across four frozen readings in both rendering modes). At schema version 1 this requirement binds on four of the five, the registry, the policy, the caller identity, and the budget, each of which the table locates in a named field. The entry declaration has no field of its own in that version and is recorded only implicitly, through the visible set and the group rows, and the gap is carried in the requirement rather than only in prose: a host emitting schema version 1 MUST record the entry declaration's missing recording location as a memory-tier entry under [ESPALIER] 4.3, and a claim at Level 2 over schema version 1 is not defeated by that one gap. A host that needs the queries of section 5 to be complete over the entry input declares a field of its own, bumps the schema integer, and declares the addition (6.8, 6.10); from a schema version that carries such a field, a declared recording location for the entry declaration is REQUIRED as it is for the other four. The gap is not repaired here by inventing a field the validation did not cover:

| Projection input | What it is | Where it is recorded |
|---|---|---|
| registry | every declared capability and tool | `capabilities`, keyed by qualified name |
| policy | the declared exposure rules and the ordered rules served alongside them; compound | `capabilities[*].expose_to` and `capabilities[*].visible` for the exposure half, `records` of kind `rules-table` for the ordered half |
| caller identity | the principal this projection was computed for | `caller`. The `records` entry of kind `caller-declaration` is the served line derived from this input, not a second recording of it |
| entry declaration | the mounted roots and entry set for this session | no field of its own at schema version 1; recorded implicitly, through the visible set and the group rows, and carried as a memory-tier entry; see 6.10 |
| budget | the disclosure limit and the rendering it forced | `disclosure_limit`, `disclosure_mode` |

- **4.4** A served line that is not derived from a declaration MUST be recorded as unattributed and counted, and emission MUST exit nonzero. The host MUST NOT be given the benefit of the doubt by attaching the line to the nearest plausible declaration. (exp-M4: a literal inlined in the assembler and a renderer format change were both planted, and both surfaced as unattributed with a nonzero exit naming the line; neither was silently attributed.)

- **4.5** A host MUST NOT maintain any served surface as a hand-edited table parallel to the registry (this restates `SPEC.md` 9.2 and is repeated here because it is the precondition for a closed influence set). A hand table has no anchor: no mechanism can tell whether its text still corresponds to any declaration. (exp-2: streams carrying a silently stale served surface split 1/5 for the derived arm against 5/5 for the hand-wired arm, Fisher exact p = 0.048, exploratory and constructed after seeing the data; and the hand-wired arm's catalog is outside the reach of the prose-lock mechanism by nature, because hand tables have no anchor to lock against.)

- **4.6** A conformance claim under this specification MUST NOT be stated as a claim that derivation improves task completeness. The measured effect of derivation in the one controlled comparison available is on propagation cost, not on completeness. (exp-2: turns and edit sites separate completely, Cliff's d = -1.00, exact Mann-Whitney p = 0.0079 on both with all five derived streams and p = 0.0159 on both without the audit-flagged stream, and billed tokens p = 0.032 with d = -0.84; the completeness family is not significant under Holm, state incompleteness p = 0.270, tasks fully complete p = 0.270, n = 5 per arm.)

## 5. The three mandatory queries

A conforming host answers three questions mechanically, from artifacts, with no source file opened. The three are exhaustive over the influence set: a declaration changed (forward), a behavior was observed (reverse), or two runs differ (diff).

- **5.1** A conforming host MUST answer all three queries of 5.2, 5.3 and 5.4 without requiring the operator to read source or re-derive a past mount by hand. (exp-M4: the reverse slice and the run diff were exercised, the two reverse-slice questions of the debugging case being answered from the artifact alone and the diff classifying seven single-edit differences with two silence controls. The forward slice was not exercised by the validated implementation; 5.2 carries that mark.)

- **5.2 Forward slice.** Given a declaration identifier and two mount states that differ only in that declaration, the host MUST return, for every declared caller, the classified set of served-surface changes attributable to it: the run diff of 5.4 over the two mounts for that caller, restricted to changes whose subject or record source identifier is the named declaration. The precondition is part of the query: over two mounts that differ in more than the named declaration the same procedure answers what changed between two mounts, not what one declaration moved, and a host that cannot hold the other declarations fixed MUST state that it is answering the two-mount question instead. A caller whose served bytes did not move MUST be reported as identical, explicitly, and MUST NOT be omitted from the answer: an unmoved caller is a fact, and absence and emptiness are different facts (`SPEC.md` 8.2). **Design inference, not yet measured** for the query as a whole: no validated implementation performs it. Its per-caller mechanics rest on the diff (exp-M4: an exposure edit reported `exposure-changed` on the affected caller and `identical` on the caller whose served prompt did not move; an identity edit reported the mirror image).

- **5.3 Reverse slice.** Given a caller, a mount, and a served line number, the host MUST return that line's full record and the mount state on the same answer: the layer, the served text, the source kind, the source identifier, the file holding that declaration, the content hash, the capabilities the line names, and the header's disclosure mode and limit, registered, visible and withheld counts, the withheld names, and whether the withholding was announced in the served text with the announcing line numbers. The mount state is REQUIRED in the same answer because the tier decision of section 7 needs both halves. The declaration facts behind each withholding SHOULD be returned per withheld name in the same answer; the artifact records them per capability (6.13), and the validated implementation prints them only for capabilities the served line itself names, which is why this half is RECOMMENDED and the list above is REQUIRED. (exp-M4: `explain` on the line the model refuses from returns the rules-table entry and its file together with the withheld set and the not-announced verdict on the same screen.)

- **5.4 Run diff.** Given two provenance artifacts of the same caller, the host MUST classify every difference into exactly one of seven classes, MUST print one line per change naming its subject, and MUST exit nonzero when any difference exists. The classes are `line-added`, `line-removed`, `description-changed`, `exposure-changed`, `disclosure-state-changed`, `rules-changed`, `identity-changed`. This class set is stated here and nowhere else; `CAPABILITY_HOST.md` 14.8 binds it by reference rather than restating it, because two statements of one class set are two facts that will diverge (`SPEC.md` 5.1). (exp-M4: one real edit per class on a temporary copy, each reporting exactly its own class naming its own subject and nothing else, seven for seven, plus two silence controls.)

- **5.5** The class set MUST be closed by a residual sweep, and the residual behavior is this: a difference in served text that no other named class accounts for MUST be reported under `line-added` or `line-removed`, naming the record's own source as the subject, and the change MUST be marked in its detail as a residual so that no reader takes the class as a statement of cause. A served line MUST NOT be able to differ in silence, and a clean exit MUST mean the served text is the same text, not merely that no class matched. The residual classes are the two that assert nothing about why a line moved, which is why the sweep lands there rather than in a class that names a cause. (exp-M4: the validated implementation sweeps every remaining differing record into a line pair keyed on the record's own subject, and the sweep is what makes exit 0 mean the served text is the same text. **Design inference, not yet measured**: the residual marking in the detail field, which the validated implementation does not carry and which this specification adds so that a residual line pair is distinguishable from a directly classified one.)

- **5.6** The queries MUST operate on emitted artifacts, not on live re-derivation of a past mount. A mount that no longer exists cannot be re-derived, and a mount that still exists may have changed since the observation. **Design inference, not yet measured.**

- **5.7** The per-caller loop of 5.2 SHOULD be built on the run diff of 5.4 rather than on a second attribution path, because two attribution paths are two facts that will diverge (`SPEC.md` 5.1). **Design inference, not yet measured**: the validated implementation exposes the diff and leaves the per-caller loop to the operator.

### Interface declarations

Language-neutral sketch. Types are shapes, not a language binding.

```
Artifact  := the section 6 schema
Change    := { class, subject, detail }
LineAnswer:= { record: LineRecord, mount: MountState }

emit(tree, caller)                       -> Artifact          # exit 1 if unattributed lines exist
run_diff(artifact_before, artifact_after)-> list[Change]      # exit 1 if any change
reverse_slice(artifact, line_number)     -> LineAnswer | none # none only for a blank line; exit 1
forward_slice(declaration_id, mount_before, mount_after)
                                         -> map[caller -> list[Change] | IDENTICAL]
                                         # specified, not validated: see 5.2
```

Python reference signatures. `build_artifact`, `diff_artifacts` and `explain_line` match the validated implementation; `forward_slice` has no validated implementation and is specified by 5.2 as the diff applied over every declared caller.

```python
def build_artifact(tree: str | Path, caller_name: str) -> dict:
    """Assemble one caller's prompt through the host's own code and record
    where every served line came from. Read only against the tree, which
    is the same value the schema's `tree` field records."""

def diff_artifacts(before: dict, after: dict) -> list[Change]:
    """Every difference between two artifacts of one caller, one class each,
    with a residual sweep so no served line differs in silence."""

def explain_line(artifact: dict, number: int) -> list[tuple[str, str]] | None:
    """One served line's full record plus the mount state. None for a blank
    line, which carries no record; out of range raises."""
```

Command surface, with the exit codes of 6.9:

```
emit    --tree DIR --caller NAME [--out FILE]
diff    --a FILE --b FILE
explain --artifact FILE --line N
```

## 6. The provenance artifact

The artifact is the mechanism that makes the section 5 queries lookups. It is a recorder, not a detector: it never fires on anything (exp-M4 ruling: validated as a recorder; it makes two questions a lookup that were a source read before, at a cost of one JSON file per caller per mount, no model, about one second to emit).

### Emission requirements

- **6.1** A conforming host MUST emit one artifact per caller per mount, in the schema stated later in this section, with that artifact kind constant, those field names, and those value shapes. Every field of that schema is REQUIRED and carries no default (`SPEC.md` 8.3); the field-obligation tables below are that schema's detail. This section is the single statement of the artifact contract for this standard and its companions: `CAPABILITY_HOST.md` 14.14 binds it by reference and states no second schema, and where a reader finds two schemas for this artifact, this one governs (`SPEC.md` 9.1.9). (exp-M4: the artifact is per caller, and so is the diff; the schema below is the one the validated emitter produced.)

- **6.2** The artifact MUST be a sidecar and MUST NOT be inlined into any served surface. Provenance added to the text the model reads changes the context, and therefore changes the behavior the artifact exists to explain; an inlined recorder measures a system that only exists while it is being measured. (exp-M4: byte identity of the served prompt with and without emission is pinned as a test, asserted independently of the emitter's own hash, together with a check that no provenance text reaches the prompt.)

- **6.3** The conformance check for 6.2 MUST be byte identity: the served surface assembled with emission enabled MUST be byte-identical to the served surface assembled with emission disabled, compared as bytes and not through the artifact's own recorded hash. An implementation that verifies 6.2 using the value the emitter itself computed has verified nothing. (exp-M4: the byte-identity test is written to be independent of the emitter's hash for this reason.)

- **6.4** Emission MUST be read-only with respect to the source being described: it MUST NOT write into the source tree, and it MUST NOT leave incidental artifacts such as compiled bytecode caches. A frozen subject must gain nothing from being observed. (exp-M4: bytecode writing is disabled for the duration of the mount and the frozen readings were emitted against unmodified trees.)

- **6.5** The emitter MUST cross-check the host's actually served surface against the surface the declarations derive, for every declared caller, and MUST fail loud rather than report on a host whose serving diverges from its declarations. A recorder that quietly describes a divergent host is worse than no recorder, because its output is trusted. (exp-M4: the mounted view raises a tree error naming both sets when the served catalog and the derived catalog disagree.)

- **6.6** The emitter MUST fail loud when the assembled surface no longer has the shape it reads, specifically when a declared layer header is absent from the assembled text, rather than attributing lines to the wrong layer. (exp-M4: the layer split raises naming the missing header and the declared header set.)

- **6.7** Serialization MUST be deterministic: sorted keys, fixed indentation, UTF-8 without escaping, trailing newline, so that two emissions of the same mount are byte-identical and artifacts are comparable as files. (exp-M4: emission is pinned as repeatable and deterministic.)

- **6.8** The artifact MUST declare its kind and version, and a reader MUST refuse an artifact whose version it does not read, naming the version found and the version it reads. Two readers of an undeclared artifact contract derive two different contracts. (exp-2 instrument incident: two implementations built in parallel against an unwritten shared contract diverged on entry point, capability set, callers, error names, loop API, and disclosure; both were internally coherent and green, and neither could run the other's tests. The rule adopted from it: the shared contract is written before any implementation that must satisfy it, and parallel builders are given the artifact, never the intent.)

- **6.9** Exit codes MUST be: 0 clean, 1 findings, 2 usage, tree, or artifact error. The findings exit covers unattributed lines on emit, any difference on diff, and a reverse slice on a blank line, which carries no record and is a finding about the request rather than an error. A findings exit and an error exit MUST be distinguishable, because a findings exit is data and an error exit is not. (exp-M4: these codes are the validated implementation's, exercised by the unmountable-tree and version-mismatch cases, by the blank-line explain, and by the clean and differing runs.)

### The schema

The schema below is normative, is the schema that was validated, and is the schema 6.1 requires. Two properties of it are load-bearing for the companions and are stated here rather than left to be inferred. Its artifact kind constant is `m4-prompt-provenance`. Its header carries no separate boundary identifier: a projection's boundary is identified by `tree` and `caller` together, which is the pair `CAPABILITY_HOST.md` 8.6 reads, and a host whose boundaries are not distinguished by that pair adds an identifier of its own under 8.6 and declares the addition.

```json
{
  "artifact": "m4-prompt-provenance",
  "version": 1,
  "tree": "subjects/order-desk",
  "caller": "auditor",
  "disclosure_limit": 10,
  "disclosure_mode": "full",
  "prompt_sha256": "9f2c...",
  "prompt_lines": 16,
  "attributed_lines": 14,
  "unattributed_lines": [],
  "counts": { "registered": 7, "visible": 5, "withheld": 2 },
  "withholding": {
    "count": 2,
    "names": ["finance:refund_check", "ledger_write"],
    "announced_in_prompt": false,
    "announcing_lines": []
  },
  "capabilities": {
    "ops:triage_backlog": {
      "kind": "skill",
      "source_file": "skills/ops/triage_backlog/manifest.toml",
      "description": "Triage the open backlog. Use when a queue review is requested.",
      "description_sha256": "1b7e...",
      "behavior_sha256": "c04a...",
      "visible": true,
      "expose_to": null,
      "uses": ["ops:fetch_orders", "ops:score_risk"],
      "required_tools": ["orders_query", "risk_score"],
      "tools_withheld_from_caller": [],
      "children_withheld_from_caller": [],
      "named_in_prompt": true
    },
    "ledger_write": {
      "kind": "tool",
      "source_file": "toolset/declarations.py",
      "description": "Write one ledger entry. Use when a refund is approved.",
      "description_sha256": "88d1...",
      "behavior_sha256": "",
      "visible": false,
      "expose_to": ["operator"],
      "uses": [],
      "required_tools": [],
      "tools_withheld_from_caller": [],
      "children_withheld_from_caller": [],
      "named_in_prompt": false
    }
  },
  "records": [
    {
      "line": 4,
      "layer": "rules",
      "text": "4. Refuse work outside the desk's declared scope.",
      "source_kind": "rules-table",
      "source_id": "4",
      "source_file": "prompt/layers.py",
      "content_sha256": "5ac9...",
      "capabilities": []
    },
    {
      "line": 9,
      "layer": "skills",
      "text": "- ops:score_risk: Score one order's risk. Use before escalation.",
      "source_kind": "capability-declaration",
      "source_id": "ops:score_risk",
      "source_file": "skills/ops/score_risk/manifest.toml",
      "content_sha256": "3e70...",
      "capabilities": ["ops:score_risk"]
    }
  ]
}
```

Field obligations:

| Field | Obligation | Meaning |
|---|---|---|
| `artifact` | REQUIRED | artifact kind constant, `m4-prompt-provenance` |
| `version` | REQUIRED | integer schema version; a reader refuses versions it does not read (6.8) |
| `tree` | REQUIRED | the source root the surface was assembled from |
| `caller` | REQUIRED | the declared caller this projection was computed for |
| `disclosure_limit` | REQUIRED | the budget in force at this mount |
| `disclosure_mode` | REQUIRED | the rendering the budget forced: `full` or `deferred`, read off the served text, never re-derived |
| `prompt_sha256` | REQUIRED | sha256 of the served bytes |
| `prompt_lines` | REQUIRED | total served lines, blank lines included |
| `attributed_lines` | REQUIRED | count of records whose source kind is not `unattributed` |
| `unattributed_lines` | REQUIRED, `[]` is a declaration | line numbers matching no declaration (4.4) |
| `counts.registered` | REQUIRED | capabilities and tools in the registry at this mount |
| `counts.visible` | REQUIRED | of those, projected to this caller |
| `counts.withheld` | REQUIRED | of those, withheld from this caller |
| `withholding.count` | REQUIRED | withheld total |
| `withholding.names` | REQUIRED, `[]` is a declaration | sorted qualified names withheld from this caller |
| `withholding.announced_in_prompt` | REQUIRED | whether any served line names a withheld capability or one of the withheld set's declared groups; see the matching rule and its limit in 6.11(d) |
| `withholding.announcing_lines` | REQUIRED | the line numbers that do |
| `capabilities` | REQUIRED | one entry per registered capability and tool, keyed by qualified name |
| `records` | REQUIRED | one record per non-empty served line, in served order |

Capability entry fields: `kind` (`skill` or `tool`), `source_file`, `description`, `description_sha256`, `behavior_sha256`, `visible`, `expose_to` (declared exposure list, or `null` where no exposure was declared, which is a different fact from an empty list), `uses`, `required_tools`, `tools_withheld_from_caller`, `children_withheld_from_caller`, `named_in_prompt`. All are required by 6.1.

Record fields: `line`, `layer`, `text`, `source_kind`, `source_id`, `source_file`, `content_sha256`, `capabilities`. All are required by 6.1. `source_kind` is exactly one of `caller-declaration`, `rules-table`, `capability-declaration`, `tool-declaration`, `derived-note`, `unattributed`.

- **6.10** `layer` MUST carry the host's own declared layer name, derived from its declared layer headers, and the layer set is therefore the host's, not this specification's. The validated instance carried `identity`, `rules`, `skills` (exp-M4: every record in the four frozen readings sits in one of the three declared layers, and a declared header absent from the assembled text fails the emission loudly rather than shifting the lines into a neighbouring layer). Blank served lines carry no record; a reverse slice on a blank line MUST report that the line is blank rather than return an empty record. The entry input of 4.3 is recorded implicitly in this schema version, through the visible set and the group rows, and an explicit entry field is a candidate for a later version; it is named here as a known gap rather than added, because this schema is the one that was validated. 4.3 states how a host carries that gap at schema version 1 and what a schema version carrying such a field owes.

### Attribution discipline and known false-positive classes

Attribution is matching, never re-derivation: each served line is compared against the strings the host itself declares (the caller identity, the ordered rules, the catalog descriptions, the rendered rows, the layer note constants). The mechanism never pins a line on the nearest plausible declaration.

- **6.11** An implementation MUST document the following classes in its own operator documentation, because each is a case where the artifact's record is correct as a mechanism and misleading as a conclusion. These are normative content, not footnotes.

  (a) **Inlined literal.** A string written into the assembler instead of declared in a layer module has no declaration to match and is recorded as `unattributed`, with a nonzero exit naming the line. This is the correct behavior of the recorder and is a finding about the host: the host has a served line outside its influence set. (exp-M4: planted and surfaced.)

  (b) **Renderer format change.** A change to how rows are rendered, for example a row separator, makes every affected row unattributed at once, because the matcher compares rendered text against declared text. A block of unattributed rows is more often a renderer change than a block of undeclared lines, so the renderer is the first hypothesis to test where the unattributed rows are contiguous inside one layer. That is guidance for reading the record and places no obligation on any party; the record is correct either way, and the finding it raises is the same finding as (a). (exp-M4: planted and surfaced, in the same shape as (a).)

  (c) **Duplicate declared strings.** Two declared constants holding the same string are reported under the first name in sorted order. The ambiguity is in the host, not in the recorder, and the record MUST NOT be read as evidence that the other constant is unused. **Design inference from the matching rule, not measured.**

  (d) **Announcement matching is a substring test over declared names.** In the validated emitter `announced_in_prompt` is true when any served line contains a withheld capability's qualified name as a substring. That rule carries a false negative on a conforming host: an announcement of the measured form carries a derived count and the withheld group names (`CAPABILITY_HOST.md` 9.4) and names no capability, so it records as not announced, which inverts the tier decision 7.2 rests on. An implementation MUST therefore match the declared group names of the withheld set as well as the withheld qualified names. The match set is a computation and not a field shape, so widening it does not bump the schema integer (6.8). **Design inference, not yet measured**: the validated emitter matches qualified names only, and the narrowing experiment's announcement was never emitted through the recorder, so the field's true case is untested. The field stays evidence about the served text rather than a verdict about whether the withholding was communicated: a line that mentions a withheld name for an unrelated reason counts as announcing, and an announcement that describes a withholding without naming it or its groups counts as not announcing. (The same tradeoff class as the qualified-name sweep of `CAPABILITY_HOST.md`, whose declared grammar can false-positive on capability-shaped tokens that are not references.)

  (e) **Empty behavior hash.** `behavior_sha256` is the empty string for tools and for any capability whose declaration cannot be parsed. An empty hash is a missing measurement, not a stable value, and MUST NOT be compared as though it were a hash. Two capabilities both carrying `""` are not thereby equal. **Design inference from the empty-hash convention, not measured.**

- **6.12** A capability line's `content_sha256` MUST be computed by the same hash function the prose lock of `CAPABILITY_HOST.md` uses for description hashing, so that an artifact and a lock compare without a second rule. (exp-M4: pinned as a test, the hash is the one the lock records.)

### Honest scope of the recorder

- **6.13** An implementation MUST NOT present the artifact as a detector. It does not fire, it has no verdict, and a clean emission is not evidence that anything is correct. Specifically, the artifact does not judge whether the served prose is true, does not know what the user asked, and does not re-derive the host's exposure decision: for a withheld capability it reports the declaration facts that bear on the decision (declared exposure, required tools this caller may not see, used children this caller may not see) and leaves the reading to a human. (exp-M4 ruling: validated as a recorder.)

- **6.14** Prose truth MUST NOT be assigned to this mechanism, and an implementation MUST NOT claim that a co-change lock detects stale prose. A lock forces prose and behavior to be re-confirmed together; it does not detect staleness. (exp-M1 audit: as a staleness detector the lock fires on 89 of 150 archived states at equal lock age, approximately 8 percent precision, and three constructions serve false prose while the lock reads clean; the mechanism is admitted only as a compound of the lock as a co-change forcing function plus a semantic judge as detector, with the judge on the advisory seat, emitting a warning that quotes the contradicted claim, never failing a build. Judge recall 6/6 in each of two rounds; specificity 5/6, with the single false positive moving between rounds on byte-identical material; in-flow negatives 4/4.)

## 7. Failure taxonomy by guarantee tier

Every agent misbehavior lands on exactly one of three tiers, and the tier determines the fix. The tiers are the guarantee ladder of `SPEC.md` section 4 applied to the served surface.

| Tier | What happened | Where the fix goes | Distinguishing evidence in the artifact |
|---|---|---|---|
| (a) assembly defect | the intended line never reached the served surface | the renderer or the declaration | no record for the expected text; or the capability entry shows `named_in_prompt: false` and `visible: false` |
| (b) prompt-tier failure | the line was served, attributed, and overridden by the model's prior | promotion to the protocol; not wording | a record exists, the served text is present and correct, and the mount state shows the information was carried |
| (c) structure-tier failure | the protocol itself permits the bad action | the protocol | the artifact is clean and the served text is correct; the host's own refusal or dispatch path accepted the action |

- **7.1** Every reported misbehavior MUST be classified into exactly one tier before any fix is written. The tiers partition by what the artifact shows, so the classification is decidable rather than a judgement about the model. **Design inference, not yet measured** as a partition of all misbehaviors; the individual tier evidence is cited in 7.2 through 7.4.

- **7.2** The tier decision between (a) and (b) MUST be answerable by one reverse slice, with no source file opened. (exp-M4: the debugging case answers both halves of the question, whether the withholding was announced in what the model saw and which capability was withheld, from the artifact alone.)

- **7.3** A tier-(b) failure MUST NOT be fixed by rewording the served text alone. The fix MUST move the guarantee up the ladder, to a machine check or to protocol structure, or MUST record a waiver naming the reason and the revisiting trigger (`SPEC.md` 4.2). Served text is the weakest rung, and a failure at that rung is evidence about the rung, not about the sentence. (exp-3: the announcement is necessary and insufficient. Necessary: removing it while leaving the search row rendered drops out-of-scope success from 21/24 to 9/24 and adds 8 confident wrong routes on top of 4 extra false refusals. Insufficient: with the announcement present, the flagship model read it, recited the withheld group names including the one holding the answer, and refused, 3/3 deterministic, zero searches. Promotion to protocol restored 12/12.)

- **7.4** A tier-(b) promotion MUST be validated against the failure it claims to fix, on the same fixture, with the served bytes held constant where possible, and the validation MUST report both the repair and the spurious-firing rate on the classes the mechanism was not aimed at. (exp-3: the gated arm's served prompt is byte-identical to the ungated arm by sha256; the gate fired 3 times in 72 requests, all on the failing unit, every firing ending correct, with zero spurious firings on the in-scope class 0/24 and the distractor class 0/24, and average steps unchanged at 1.00 on both.)

- **7.5** A tier-(b) fix that changes served bytes MUST be accompanied by the run diff of 5.4 showing exactly what moved. A fix whose diff reports classes the author did not intend is a second change riding along. **Design inference, not yet measured** as a practice; the diff's sharpness under one-edit-per-class conditions is measured (exp-M4: seven for seven, each reporting exactly its own class).

- **7.6** The tier classification MUST be recorded with the fix, so that a class of misbehavior repeatedly landing on tier (b) becomes visible as a standing structural finding rather than a recurring wording task. **Design inference, not yet measured.**

- **7.7** Where an implementation carries a validated repair whose success is partly definitional, the definitional part MUST be stated in the same place as the result. (exp-3 caveat, kept: in the gated arm a first-step refusal without a search is unreachable by construction, so a false-refusal count of zero is partly definitional; the non-definitional evidence is that the forced continuation produced the correct capability 3/3 rather than a repeated refusal or a wrong call. Two further caveats kept with it: n is one task unit and three firings, which is evidence that the arm no longer false-refuses on this fixture and not an effect-size estimate; and the gate checks that a search happened, not that it was relevant, so a perfunctory search followed by a refusal remains open and a rollout needs a stronger predicate.)

### Worked example (informative)

An order-desk host serves a narrowed projection to a caller named `operator`: an entry set of capabilities, a search capability that queries the full permitted registry, and one announcement line carrying a derived count of withheld capabilities and the withheld group names. A request arrives whose answer sits in a withheld group. The model answers that no capability covers the request, without searching. Three repetitions, three identical refusals.

**Debugging by recollection.** The operator asks whether the announcement rendered at all, whether the search row rendered, whether the count was right, whether the description of the search capability was clear enough. Each question is answered by reading the assembler and simulating the mount. The team rewrites the announcement to be more emphatic and ships it.

**Debugging by lookup.** The operator runs a reverse slice on the line the model refused from. The answer returns the record (`rules-table`, entry 4, the file that declares the rules tuple, the content hash) and, on the same screen, the mount state: disclosure mode and limit, registered, visible and withheld counts, `withholding.names` listing the withheld set including the group that holds the answer, `withholding.announced_in_prompt: true`, and `announcing_lines` naming the line that carried the announcement. One lookup, and tier (a) is excluded: the line was served, it was attributed to a declaration, and it named the group the answer sits in. The true verdict here presumes the matching rule of 6.11(d), which reads group names as well as qualified names; the narrowing host of that experiment was never emitted through the recorder, and under the validated emitter's qualified-name-only rule an announcement naming groups alone would have read false.

The archived model output closes the case. The model recited the withheld group names, including the one holding the answer, and refused rather than spend one step searching. It read the text. The text was correct. The model's persona prior, a desk copilot for which the withheld domain is not its own, overrode it. This is tier (b), and the served sentence was never the problem.

The fix is at the protocol, not in the text: the host refuses a refusal from a caller that has not searched, returns one observation, and continues. The served prompt is unchanged, verified byte-identical by sha256, so the change is isolated to the host's refusal path. The failing class went from 9/12 to 12/12, the failing unit from 0/3 to 3/3, and the gate fired three times in seventy-two requests with every firing ending correct and no spurious firing on either of the two classes it was not aimed at.

**The contrast case, same symptom, opposite tier.** A second host, differently assembled, produces the identical symptom: a caller refuses a request whose answer exists. The reverse slice on that host returns `withholding.announced_in_prompt: false`, `announcing_lines: []`, and no served line naming the capability. The withholding was real and the model was never told. That is tier (a): the assembler has no announcement path at all, so every prompt it serves that withholds anything is structurally the silent condition. The measured cost of that condition on the same fixture is 9/24 against 21/24 on out-of-scope requests, with 8 confident wrong routes added.

Two hosts, one symptom, opposite fixes, distinguished by one boolean in one artifact. Without provenance both look like a wording problem, and rewording is the fix that is wrong in both directions: in tier (b) it rewrites a sentence the model already read and recited, and in tier (a) it rewrites a sentence that was never served. The standing finding this example generalizes to is that a host with no announcement path cannot be debugged into having one by editing prose, and that a host with one cannot be repaired by editing prose either. The announcement is necessary and insufficient; the reachability of a withheld capability belongs at the protocol.

## 8. The debug protocol

The protocol orders the lookups so that the cheapest disqualifying answer comes first. Source reading is last, not first.

- **8.1** Step 0, existence. A session that billed zero tokens MUST be classified as an infrastructure failure, retried, and never scored or read as behavior. A missing session is not a quiet agent. (exp-2 audit: a stream's session read exit 1, one turn, zero billed tokens, and the task's committed diff contained only the injected acceptance test; the published narrative of a loud refusal for that stream was wrong and was corrected, and the stream was flagged for exclusion from confirmatory readings.)

- **8.2** Step 1, mount. Determine whether the host mounted. A loud mount failure names the capability and ends the investigation; that is what fail-loud construction is for (`SPEC.md` 8.3). An implementation MUST check this before any prompt-level analysis, because an unmounted host serves nothing to attribute. (exp-2: mount-time sweep failures exist only in the derived arm, which is the arm asymmetry this step exploits. The arms did not separate on whether a change failed loudly: loud task counts were 6, 0, 0, 0, 0 against 0, 0, 1, 0, 0, p = 1.000, Cliff's d = 0.04, and the derived arm's entire count belongs to the one stream the study's audit excluded after finding its session billed zero tokens and never ran, which leaves the derived arm with no surviving loud failure. What the arms did separate on is what a failed change left behind: a silently stale served surface, 1/5 against 5/5, Fisher exact p = 0.048, exploratory. Whether a mount sweep converts a silent failure into a loud one is this specification's expectation from the arm asymmetry and is **design inference, not yet measured**.)

- **8.3** Step 2, full-state probe. Probe the live system against its declared expected live state, not against the delta of the most recent change. A delta probe cannot see a stale surviving surface, which is the failure class that survives longest. (exp-2: both persistent-drift findings in the run were invisible to the per-task delta probe and visible only to the state probe; in one stream a removed capability's reference survived six further tasks to the end of the stream with the suite green throughout.)

- **8.4** Step 3, reverse slice. Run the reverse slice on the implicated served lines. The tier decision of section 7 between (a) and (b) MUST be taken here. (exp-M4: the debugging case is answered at this step from the artifact alone, with no source file opened.)

- **8.5** Step 4, run diff. Diff the current artifact against the last known-good artifact for the same caller. A classified change names the subject; an identical result excludes the served surface as the cause and moves the investigation to the protocol, which is tier (c). (exp-M4: the diff names the subject of each of seven change classes and reports identical on the callers whose served bytes did not move.)

- **8.6** Step 5, source. Only now read source. An implementation MUST NOT skip to this step; the first four steps are cheap, bounded, and exclude the majority of hypotheses, and reading source first is the practice this specification exists to replace. **Design inference, not yet measured** as an ordering optimum; the individual steps carry their own citations above.

- **8.7** The step that produced the answer SHOULD be recorded with the fix, so that the protocol's own cost is measurable and steps that never produce answers can be retired. **Design inference, not yet measured.**

## 9. Instrument requirements

None of the above is available after the fact unless the instrument was in place before the fact. These requirements bind the operating environment, not the host's application code.

- **9.1** The assembled served surface MUST be archived per session, byte-exact, with its caller and mount state. The archive is what makes a diagnosis about what the model read rather than about what the operator believes it read. (exp-3: the archived prompts are what showed the model reciting the withheld group names before refusing; that diagnosis is unavailable without them.)

- **9.2** The system MUST carry a declared expected live state that a probe can be run against: the full set of capabilities and served surfaces that should exist after each change, not only the surfaces the change touched. (exp-2 amendment, adopted after the gold-standard pass: accumulated prior delta probes are not a usable stability statistic when the change stream legitimately removes, renames, and moves earlier capabilities, and a delta-only probe cannot see a stale surviving surface.)

- **9.3** Probe output and archived artifacts MUST be written outside any working tree the agent can edit. (exp-2: in two streams a subject session deleted the experimenter's probe dumps from the trial directory, with the signature of a clean operation, tracked files surviving and excluded files vanishing; measurement rows written outside the tree at the time were unaffected.)

- **9.4** The environment MUST isolate resolution paths per subject so that changes made inside a session cannot hijack what the next session resolves. (exp-2 oracle discipline, carried from the pilot where the agent-modifies-environment threat class was first found.)

- **9.5** A state expectation MUST pin behavior, and MUST pin served prose only where the change that produced it stated the replacement string. An instrument that freezes a sentence a later change falsifies will score truth-telling as failure. (exp-2 defect 8: three subjects corrected a served description that a behavior change had falsified; the frozen expectation charged each of them ten incompleteness points across four tasks, while every stream that kept serving the false sentence scored clean. Under the corrected reading the arm shapes invert.)

- **9.6** The last known-good archived served surface MUST be retained across every mount change, and from the level at which artifacts exist (6.1) the last known-good artifact MUST be retained with it, because the artifact is the second operand of the run diff. At Level 1 the retained operand is the archive of 9.1, compared by hand; an implementation that retains only the current state has the recorder without the query. **Design inference, not yet measured**, following directly from the two-operand shape of 5.4.

- **9.7** A change to the measurement instrument that redefines a metric SHOULD be checked for arm bias before adoption, by re-running the comparison under both definitions. (exp-2 ruling: the redefinition of the stability metric was adopted only after the cross-arm matrix was found byte-identical at every cell, so the change biased neither arm.)

- **9.8** Where two implementations must be comparable, the shared observable contract MUST be written before either implementation, and parallel builders MUST be given the artifact rather than the intent. Two consumers of an undeclared contract derive two different contracts. (exp-2 instrument incident, as cited in 6.8.)

## 10. Conformance levels

- **10.1** A conformance claim MUST name the claimed level, the version of this specification it was assessed against (section 12), the assessor, and the assessment date, and MUST be supported by evidence: at Level 1, the session archive and the expected-state declaration; at Level 2 and above, emitted artifacts for every declared caller at the assessed mount.

- **10.2** A claim at a level MUST satisfy every requirement enumerated for that level and for all lower levels.

- **10.3** Requirements not enumerated by any level are conditional and bind at every level wherever their subject exists.

- **10.4** A conformance claim MUST NOT be accompanied by a claim that this instrumentation improves agent task success or integration completeness (4.6). It MAY be accompanied by the propagation-cost result, provided both halves of any economy claim are cited together (see 11).

**Level 1, Archived.** MUST satisfy 8.1, 8.2, 8.3, 9.1, 9.2, 9.3, 9.6. In prose: sessions and served surfaces are archived byte-exact outside the agent's reach, an expected live state exists and is probeable, zero-token sessions are never scored, and the last known-good archive is retained.

**Level 2, Attributed.** MUST additionally satisfy 4.3, 4.4, 6.1 through 6.9, 6.11, 6.12, 6.13. In prose: one artifact per caller per mount, emitted as a sidecar with byte identity pinned, in the schema of section 6, with unattributed lines reported and the known classes documented.

**Level 3, Queryable.** MUST additionally satisfy 4.1, 4.2, 4.5, 5.1 through 5.6, 7.1, 7.2, 7.3, 7.5. In prose: all three queries answer mechanically over a closed influence set derived at one mount, and the tier of every misbehavior is decided by lookup before a fix is written.

The table below is informative. It summarizes the level lists above by question; where it and a level list disagree, the level list governs and the table is a defect of this document.

| Capability | Level 1 | Level 2 | Level 3 |
|---|---|---|---|
| what was served | archived bytes (9.1) | attributed per line, emitted as a sidecar (4.4, 6.2) | reverse slice answers with mount state (5.3) |
| what changed | two archives to compare by hand (9.6) | two artifacts (6.1) | classified run diff, residual swept (5.4, 5.5) |
| what a declaration moved | not answerable | answerable per caller by hand | forward slice over every caller (5.2) |
| why it misbehaved | recollection | one artifact lookup for tier (a) versus (b) (7.2) | tier recorded before the fix, promotion required for tier (b) (7.1, 7.3) |

## 11. Limits and non-goals (informative)

**A recorder, not a detector.** Nothing in this specification fires. A clean emission means every served line matched a declaration, not that the declarations are right, the prose is true, or the behavior is desirable.

**No request-side knowledge.** The artifact does not know what the user asked. It can say that a capability was withheld and whether the withholding was announced; it cannot say whether the withheld capability was the right one for the request.

**No intent.** The artifact reports the declaration behind a withholding, never the reason the author declared it.

**Per caller, per mount.** A declaration edit that does not move one caller's served surface is silent in that caller's diff by design, and appears in another caller's. Cross-host or federated attribution is out of scope.

**Served text is not billed cost.** The artifact measures the projection, not the invoice. Where an economy claim is made about narrowing, both halves must be cited together (exp-3 C1: the served projection falls to 30 to 33 percent of the full catalog on both models tested, and per-request billed tokens nevertheless rise in the narrow arm, because the extra step re-pays that harness's fixed context, of which the served catalog is about 9 percent; the claim is true at the projection layer and false at the invoice layer of that harness).

**Evidence base is narrow.** The measured results behind this document come from one synthetic fixture family, a small number of models, and small samples: five streams per arm in the change-stream comparison, and single-task units behind the strongest protocol result. One further stated hypothesis was refuted with its direction reversed and is recorded as underpowered rather than settled (exp-3 C5: the weaker model ceilinged at 12/12 on the full-catalog arm in every class, so the measured effect was larger on the stronger model, and the design has no headroom to say more).

**Not a substitute for structure.** The queries make the tier decision cheap. They do not promote anything. A system whose invariants sit on prompt text will be diagnosed faster and will keep failing until the invariant moves.

## 12. Versioning of this document

This document versions under Semantic Versioning 2.0.0 [SEMVER-inf], in step with `SPEC.md`. Changes to normative requirements bump major or minor; editorial changes bump patch. Pre-release drafts increment the draft identifier on any change and promise nothing about compatibility. The artifact schema of section 6 carries its own integer `version` field, independent of this document's version; a schema change bumps that integer and readers refuse versions they do not read (6.8).

## 13. References

Normative (this list is normative; see Conformance notation):

- [RFC2119] Bradner, S., "Key words for use in RFCs to Indicate Requirement Levels", BCP 14, RFC 2119, March 1997.
- [RFC8174] Leiba, B., "Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words", BCP 14, RFC 8174, May 2017.
- [ESPALIER] "Espalier", `SPEC.md`, this repository, version 1.0.0-draft.4. Cited for sections 3 (terms), 4 (guarantee ladder), 5 (dependency versus derivation), 8 (manifests and fail-loud construction), 9 (registration is the single declaration and exposure is a governed projection, including the closed input set of 9.1.6 and the companion precedence rule of 9.1.9).
- [CAPABILITY-HOST] "Capability hosts under Espalier", `CAPABILITY_HOST.md`, this repository, version 0.1.0-draft.1. Cited for the projection, disclosure, reachability gate, and prose-lock mechanisms this document records rather than defines; 8.6 there reads the boundary from this document's `tree` and `caller` fields, and 14.8 and 14.14 there bind this document's diff class set and artifact schema by reference.

Informative:

- [SEMVER-inf] Preston-Werner, T., "Semantic Versioning 2.0.0", https://semver.org/spec/v2.0.0.html.

## Annex A (informative): evidence

Citation keys used in the normative text resolve as follows. All results come from a controlled study of the method, run on synthetic fixtures with archived per-request rows.

**Locator.** Repository `dmm-study` (`github.com/Liamour/dmm-study`), snapshot commit `a98fa852647a79f7b61a132c9bf86094e225905a`, dated 2026-08-20. exp-2 resolves to `data/main/ANALYSIS.md` (analysis of record), `docs/EXPERIMENT2_DESIGN.md` (design), `docs/TWIN_CONTRACT.md` (the shared observable contract and the incident cited in 6.8 and 9.8), and `data/streams.jsonl` (per-session rows). exp-3 resolves to `docs/EXPERIMENT3_NARROWING.md`, with per-cell rows at `narrowing/report.txt` and `narrowing/results.jsonl`. exp-M4 and exp-M1 resolve to `docs/MECHANISMS.md`, with the emitter and its tests at `mechanism/prompt_provenance.py` and `mechanism/test_provenance.py`. Where the record is not reachable by an assessor, every figure quoted in this document is author-held and is not independently checkable; the requirement text stands on its own and is what a claim is assessed against.

**exp-2**, change-stream comparison. Two behaviorally equivalent implementations of one small agent host, one wired by derivation and one by hand tables, under an identical 15-task stream of capability additions, removals and changes. Five streams per arm, 150 subject sessions, one developer model, zero aborts.

- Cost family: turns and edit sites separate completely, Cliff's d = -1.00, exact two-sided Mann-Whitney p = 0.0079 on both with all five derived streams, and p = 0.0159 on both over the four streams that remain when the audit-flagged stream below is excluded; complete separation and d = -1.00 hold under both readings. Billed tokens p = 0.032, d = -0.84. The derived arm needed fewer turns and fewer edit sites in every stream.
- Completeness family: not significant under Holm. State incompleteness p = 0.270, d = 0.48; tasks fully complete p = 0.270, d = -0.48. **This is a refutation and is cited as one in 4.6 and 10.4.** The honest reading is that derivation moved propagation cost and did not move measured completeness at this sample size.
- Loud-failure rate: **not separated**. Loud tasks 6, 0, 0, 0, 0 derived against 0, 0, 1, 0, 0 hand-wired, p = 1.000, Cliff's d = 0.04. The derived arm's entire loud-task count sits in the one stream the audit correction below excludes, so after correction the derived arm holds no surviving loud failure and the hand-wired arm holds the only one. Any statement that the derived arm's failures were refused or loud is not supported by this run and is not made in this document.
- Failure-mode split, exploratory and constructed after seeing the data: streams carrying any silently stale served surface, 1/5 derived against 5/5 hand-wired, Fisher exact p = 0.048. This, with the cost family, is the whole of what separated the arms.
- Instrument defect 8: the composed state expectation froze a served sentence that a later behavior change falsified; three subjects that corrected the sentence were each charged ten incompleteness points, while every stream that kept serving the false sentence scored clean. Cited in 9.5.
- Audit correction: one stream's session billed zero tokens and never ran; the published narrative for it was corrected and the stream flagged for exclusion. Cited in 8.1.
- Environment findings: subject sessions deleted experimenter probe dumps from the trial directory in two streams (9.3); per-subject path isolation was adopted after an earlier agent-modifies-environment finding (9.4).
- Instrument incident: two implementations built in parallel against an unwritten shared contract diverged on entry point, capability set, callers, error names, loop API and disclosure, each internally coherent and green, neither able to run the other's tests. Cited in 6.8 and 9.8.

**exp-3**, narrowing confirmation. One capability registry of 48 units in 8 declared groups (the record calls them bundles) served through one host under four projections, 12 requests each answerable by exactly one capability, three classes of four, three repetitions per cell, two models. 168 preregistered requests plus 72 for the fourth arm, zero exclusions, zero parse failures across all 240. Zero hallucinated routes is recorded for the 168 preregistered requests; the fourth arm's 72 were added after the preregistration and the analysis of record does not restate that check for them.

- Economy: the served projection falls to 30 to 33 percent of the full catalog; per-request billed tokens rise, because the extra step re-pays fixed context of which the catalog is about 9 percent. Both halves are required in any citation (section 11).
- In-scope routing: 24/24 against 24/24, not refuted.
- Out-of-scope reachability on the flagship model: **refuted**, 9/12 for the narrowed arm against 12/12 for the full arm. All three failures were the same task, all false refusals, all with zero searches, 3/3 deterministic. The archived prompts show the model reciting the withheld group names, including the one holding the answer, before refusing. Cited in section 2, in 7.3, and in the worked example.
- The announcement law: removing the announcement while leaving the search row rendered drops out-of-scope success from 21/24 to 9/24 and adds 8 confident wrong routes on top of 4 extra false refusals. The announcement is necessary. Cited in 7.3 and in the worked example.
- Focus: narrowing improved routing where the withheld capability was the plausible-but-wrong one, 7/12 to 11/12, distractor hits 5 to 0.
- Model-strength hypothesis: **refuted as stated, direction reversed**; the weaker model ceilinged at 12/12 on the full arm in every class. Recorded as underpowered (section 11).
- Protocol repair: a fourth arm whose served prompt is byte-identical by sha256, differing only in that the host refuses a refusal from a caller that has not searched, restored out-of-scope success to 12/12; the gate fired 3 times in 72 requests, all on the failing unit, every firing ending correct, zero spurious firings on the in-scope class (0/24) and the distractor class (0/24), average steps unchanged at 1.00 on both. Three caveats kept, reproduced in 7.7.

**exp-M4**, provenance validation. The recorder emitted against frozen readings and against planted faults.

- Attribution: four artifacts across two source trees and two callers, non-empty lines 16, 14, 17 and 15, all attributed, zero unattributed. Both rendering modes exercised, full and deferred.
- Diff sharpness: seven real edits, one per class, each reporting exactly its own class naming its own subject and nothing else, plus two silence controls in which the unaffected caller is reported identical.
- The debugging case: with one capability made visible to a single caller, both questions (was the withholding announced in what the model saw; which capability was withheld) are answered from the artifact with no source file opened, and the reverse slice returns the rules-table entry, its file, the withheld set and the not-announced verdict on one screen.
- Attribution holes, found by planting rather than by argument: an assembler-inlined literal and a renderer format change both surface as unattributed with a nonzero exit naming the line, and neither is silently attributed to the nearest declaration. Cited in 6.11.
- Standing finding: neither implementation's assembler has any withholding announcement, so every prompt either implementation serves that withholds anything is structurally the silent condition of exp-3. Cited in the worked example.
- Ruling: recorder, not detector; it does not fire; cost is one JSON file per caller per mount, no model, about one second to emit.

**exp-M1**, prose-lock validation, cited only for what it refutes. As a stale-prose detector the co-change lock is **refuted**: at equal lock age it fires on 89 of 150 archived states regardless of prose truth, approximately 8 percent precision, and three constructions serve false prose while it reads clean. It is admitted only as a compound, lock as co-change forcing function plus a semantic judge as detector, with the judge on the advisory seat: it emits a warning quoting the contradicted claim, a human rules, it never fails a build. Judge recall 6/6 in each of two rounds; specificity 5/6, the single false positive moving between rounds on byte-identical material, its signature being cross-capability invariants judged from single-capability scope plus single-shot variance; in-flow negatives 4/4. Cited in 6.14.

## Annex B (informative): adoption order

For an existing agent host, in this order, because each step makes the next one cheap:

1. Archive the assembled served surface per session, byte-exact, outside the agent's reach. This is Level 1 and requires no change to the host.
2. Declare the expected live state and probe against it, not against the delta of the last change.
3. Adopt the zero-token rule and the probe-location rule before believing any behavioral reading.
4. Emit the artifact for every declared caller at every mount, as a sidecar, and pin byte identity of the served surface with and without emission as a test. Unattributed lines are the first finding list: each one is a served line outside the influence set, usually an assembler literal.
5. Retain the last known-good artifact and wire the run diff into the change gate. From here the tier decision is a lookup.
6. Convert the remaining hand tables. Until they are gone, the influence set is not closed and the artifact is describing part of a system.
