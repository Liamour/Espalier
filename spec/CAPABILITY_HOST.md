# Capability hosts under Espalier

A normative companion specification for capability systems: skills, tools, and prompt rules served to a model.

| | |
|---|---|
| Version | 0.1.0-draft.1 |
| Date | 2026-08-20 |
| Author | Yu-Chi TSOU (Liamour) |
| License | CC BY 4.0 |
| Status | Working Draft |
| Parent standard | `SPEC.md`, Espalier |
| Companion documents | `AGENT_DEBUG.md` (the debug paradigm, normative), `RATIONALE.md` and `TEMPLATES.md` (informative) |

**Status of this document.** This is a Working Draft. It may be updated, replaced, or obsoleted at any time; cite it only as work in progress, by exact version. The author ratifies the transition from Working Draft to a release version; a release requires at least one implementation assessed at Level 2 against the frozen text. This document refines [ESPALIER] rule 6 for one system class and does not stand alone: a claim under this specification is meaningless without the paired [ESPALIER] claim required by 15.4.

## Abstract

A capability host is a system that holds declarations of what an agent can do and serves them to a model, to a dispatcher, and to people. Its failure mode is specific and expensive: one capability is described in a prompt, a catalog, a dispatch table, an exposure list, and a document, five memories holding one fact, and the day one of them is forgotten the model is blind to a feature the machine still executes, or routes to a feature the machine no longer has. This specification states the requirements that close that gap. It fixes the capability unit as a directory plus one static manifest with no defaults; makes composition host-mediated and its graph derived; derives qualified names from topology; makes indexing execution-free and disclosure two-stage; and restates exposure as a governed projection computed per caller from an enumerable, closed input set. It then specifies context economy: tiered narrowing, an announcement of what was withheld that is derived rather than written, and a structural reachability gate on the host's own refusal path, because the announcement was measured necessary and measured insufficient. Four mechanisms carry the machine checks: a prose-behavior lock compounded with an advisory semantic judge, a dangling-name sweep, a no-red-handoff policy, and a prompt provenance sidecar. Three conformance levels mirror the parent standard. Every requirement carries its evidence tag or is marked as design inference not yet measured, and the refutations are stated with the confirmations.

## Conformance notation

The key words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, NOT RECOMMENDED, MAY, and OPTIONAL in this document are to be interpreted as described in BCP 14 [RFC2119] [RFC8174] when, and only when, they appear in all capitals, as shown here.

This conformance-notation section, sections 1 through 15, and the normative-references list in section 17 are normative; all other content, including the abstract and the annexes, is informative. Section 2 states definitions and contains no BCP 14 keyword, so its normative status binds the vocabulary the requirements are written in without adding a requirement of its own; [ESPALIER] section 3 is normative for the same reason and governs any term the two sections share.

The capitalization discipline is load-bearing: because only all-capital keywords in normative sections carry requirements, a checker can mechanically enumerate every requirement in this document. Every requirement carries a number, and every BCP 14 keyword in a normative section sits inside a numbered requirement; a keyword in unnumbered prose is an editorial defect in this document. Three constructions are inside a numbered requirement without repeating its number: a lettered sub-clause belongs to the requirement that introduces it and is cited as such, as in 8.2(b); the level blocks of section 15 enumerate requirement numbers under the general obligation of 15.2 and add none of their own; and a field-obligation table belongs to the requirement that states the obligations its marks carry, which for the manifest table of 4.8 is 4.3.

**Evidence tags.** Every numbered requirement in this document ends with a bracketed tag. `[E ...]` cites the experiment and the result that support it. `[DI]` means design inference, not yet measured: the requirement follows from a measured result or from a convergent practice but was not itself tested. `[R ...]` marks a requirement that exists because a claim was refuted, and states the refutation. A reader may reject any `[DI]` requirement without rejecting the measured core; a reader may not silently convert one into the other. Annex A collects every tag in one table.

The experiments are those of the evidence corpus [STUDY]: exp-2, a 15-task capability-churn stream run over two behaviorally identical twin implementations, one derived and one conventionally wired, 10 streams and 150 developer sessions; exp-3, a routing experiment over a 48-capability registry in four projection arms, 240 routed requests; and the mechanism replays, which rebuild archived failure states and require each mechanism to fire on the failure and stay silent on the clean state.

## 1. Scope and applicability

- **1.1** A system MUST be treated as in scope for this specification when one capability declaration must reach three or more served surfaces. This is the fan-out boundary. Below it, the hand-maintained forms this specification forbids are cheap enough that the specification's cost is not justified. [E exp-2: the conventional arm carried five served surfaces per capability and paid roughly 50 more edit sites and 100 more turns per 15-task stream than the derived arm, complete separation in every stream, turns p = 0.0079 d = -1.00, edit sites p = 0.0079 d = -1.00 with all five derived streams and p = 0.0159 each on the four that remain when the audit-flagged stream is excluded, complete separation and d = -1.00 holding under both; the boundary constant of three is interpolated from that measurement and from the two-surface case being untested]
- **1.2** Any host that asserts an answer to 1.1 MUST maintain a served-surface inventory: the enumerated list of surfaces on which a capability declaration is consumed. The obligation binds on the assertion, not on the answer, so that out-of-scope status is evidenced rather than claimed: a host asserting that this specification does not apply to it MUST record the enumerated list that shows fewer than three such surfaces, and a host that records no list has not decided 1.1 and MUST NOT assert either answer. Without the inventory, 1.1 is not decidable and no requirement below it is checkable. The inventory MUST name at least, where each exists: the assembled context served to a model, the machine-readable catalog served to a model, the dispatch path the executing engine takes, the per-caller exposure projection, the composition graph, and every human-facing index. [E exp-2: the conventional twin's five surfaces were prompt text, dispatch branch, catalog document, exposure allowlist, and sibling import; each was a separate hand edit and nothing swept them] [DI for binding the inventory on a host that asserts out-of-scope status: the alternative leaves 1.1 self-certifying]
- **1.3** A system below the fan-out boundary MAY apply this specification and MUST NOT be assessed as nonconforming for not applying it. Out of scope by design is a decision, not an omission. [DI]
- **1.4** The assembled context served to a model MUST be inventoried as a served surface under 1.2, and the requirements this document states for a derived artifact MUST bind it: 4.6, one authoritative declaration and no second table; 7.2, derived at a declared boundary and not per turn; 8.2, the closed input set and the three checks that demonstrate closure; 9.5, an announcement derived rather than written; and 14.1, an emitted provenance artifact. Each of those carries a check, which a blanket instruction to treat the context as derived does not. A host that treats its prompt as authored text rather than as a projection has left its largest surface outside every check it owns. [E M4 validation: four readings over two derived trees, the pristine derived twin and the grown gold tree, every non-empty served line attributed and zero unattributed; the two planted holes, a literal inlined in the renderer and a renderer format change, surfaced as unattributed with a nonzero exit. The hand-wired twin was not mountable by the recorder, which is the standing finding of 14.12]
- **1.5** This specification governs the declaration, derivation, exposure, and service of capabilities. It does not govern what a capability does, whether its payload is correct, which model consumes the surfaces, the literary quality of any served text, or the training of retrieval components. A conformance claim under this document MUST NOT be presented as a claim about any of those. [DI]

## 2. Terms and definitions

Normative as vocabulary; see the conformance notation. Terms this document shares with [ESPALIER] section 3 carry the parent standard's definition.

**capability.** One declared unit of what the system can do, of any kind the host serves: a skill with a payload, a tool with a schema and a handler, or any other unit the host both indexes and dispatches.

**capability unit.** The directory plus the one manifest that constitute a capability's single authoritative declaration.

**payload.** The body of a capability: instruction text, code, or both. Loaded on activation, never served in a catalog row.

**description.** The served sentence that states what a capability does and when to use it. It is the model's routing basis and is therefore a served surface, not documentation.

**registry.** Every declaration the host mounted, unfiltered.

**catalog.** The derived index of the registry: names, descriptions, composition graph, and per-surface exposure map, queryable without loading payloads.

**projection.** The derived, per-caller view of the registry computed from policy and context. Exposure is the result of a projection, never a stored list.

**caller.** The principal a projection is computed for: a role, a session identity, or an agent.

**entry.** The declaration, made at session assembly, of which part of the registry is served resident.

**served surface.** Any point where a capability declaration is consumed, including the assembled context served to a model.

**disclosure.** The staged service of a capability: description first, payload on activation.

**withholding.** The deliberate absence of a permitted capability from a served surface, computed from declarations.

**announcement.** The served line stating that capabilities were withheld, carrying a derived count and the withheld group names.

**reachability gate.** A host-side protocol rule that refuses a refusal from a caller that has not searched the withheld set.

**lock.** The recorded pair of hashes, behavior and description, last jointly confirmed for one capability.

**judge.** An advisory model-run check that reads a capability's prose against its declared behavior and flags contradictions.

**provenance artifact.** The sidecar recording, per served line, where that line came from, and recording what the mount withheld.

**mount.** The declared boundary at which the host reads declarations and derives its surfaces.

## 3. Relationship to the parent standard

- **3.1** This specification refines [ESPALIER] 9.1 and the sub-requirements recorded under it, among them that the projection is derived once at a declared boundary and that withholding is a declaration rather than an omission. It MUST NOT be read as relaxing any [ESPALIER] requirement. Where the two documents appear to conflict, [ESPALIER] governs and the conflict is a defect of this document. Where this document and [AGENT-DEBUG] appear to conflict, the governing document is the one whose scope owns the subject, as [ESPALIER] 9.1.9 states: [AGENT-DEBUG] governs the provenance artifact, its schema, its queries, and the classification of a difference between two artifacts; this document governs the declaration, derivation, exposure, disclosure, and service of capabilities. A conflict outside those two scopes is a defect in both documents and is resolved against [ESPALIER]. [DI]
- **3.2** A host in scope inherits, without restatement, [ESPALIER] 4.1 and 4.3 (tiers and the memory-tier register), 5.1 and 5.2 (single declaration site, computed reverse relations), 8.3 and 8.4 (fail-loud construction, explicit assembly with a sweep), 9.2 and 9.3 (no parallel exposure tables, one source for catalog and engine), and 10.1 (name the enforcer). Every requirement in this document that repeats one of those does so to bind it to a specific capability-host surface, not to create a second source. [DI]
- **3.3** Where more than one implementation must satisfy the same capability surface, the observable contract MUST be written as an artifact before any implementation begins, and implementers MUST be given the artifact rather than the intent. The contract covers names, signatures, return shapes, projections, served text, and the error types raised at call time; it MUST NOT cover how a surface is produced. [E contract-first incident: two implementations built in parallel from a shared intent with no contract artifact diverged on entry point, capability set, caller set, error names, loop API, and disclosure; both were internally coherent and green, and neither could run the other's tests; the divergence was resolved only by writing the artifact that had been missing]

## 4. The capability unit

- **4.1** Every capability MUST be a unit consisting of one addressable container and exactly one manifest of static data. The manifest MUST be interpretable, and the catalog derivable from it, without importing or executing any capability code. [E exp-2 and the six-ecosystem survey behind the design of record: execution-free indexing is the invariant every surveyed plugin host converged on, and it is what lets a host serve a catalog of capabilities whose code is not loaded]
- **4.2** Required manifest fields MUST have no defaults. An incomplete manifest MUST fail no later than mount, naming the capability and the missing field. [E exp-2 RQ-C for the arm construction, with a null outcome: the derived twin's mount raises a named error per fault class (missing field, unknown child, unknown tool, duplicate name, unmounted capability) and the conventional twin has no mount-time check, which is a design asymmetry rather than a measured outcome. The run's outcome metric for that asymmetry, whether a change failed loudly, did not separate the arms: loud tasks 6, 0, 0, 0, 0 against 0, 0, 1, 0, 0, p = 1.000, Cliff's d = 0.04, and the derived arm's entire count sits in the one stream the audit excluded for a session that billed zero tokens and never ran]
- **4.3** The manifest MUST declare: the local name; the description; the children it composes; the tools it requires; its exposure intent; and the location of its payload. Children, tools, and exposure intent are REQUIRED even when empty, because absence and emptiness are different facts ([ESPALIER] 8.2). The manifest SHOULD declare a version (10.1). [E exp-2: the derived twin's required set is name and description with no defaults, and its list fields are declarations whose empty value is meaningful; the exposure field distinguishes null, meaning no declared narrowing, from empty, meaning withheld from every caller]
- **4.4** The description MUST state both what the capability does and when to use it. It is the routing trigger and the search index's material, not prose about the capability. [E exp-3: routing across four arms was performed on descriptions alone, in-scope accuracy 24/24 against 24/24, and zero of the 168 preregistered requests called a name that was not in that arm's prompt or in that request's own search result; the fourth arm's 72 requests were added after the preregistration and the analysis of record does not restate that check for them]
- **4.5** Unknown manifest fields MUST be rejected at mount, naming the capability and the field. A tolerated unknown field is a declaration that no surface derives from and no check sees. [DI]
- **4.6** The manifest MUST be the single authoritative declaration of the capability ([ESPALIER] 5.1). No second table describing the same capability may exist, in any format, on any surface. [E exp-2: the conventional arm's parallel tables produced 124 to 154 edit sites per stream against the derived arm's 84 to 106, and produced the run's only class of silently-served staleness]
- **4.7** Mount MUST record the payload's location and MUST NOT read its contents for indexing purposes. The payload is read again, from its declared location, when a caller activates the capability. [E exp-2 twin contract: descriptions are served from the record and bodies are read on activation, which is what makes disclosure two-stage and keeps mount execution-free]

### 4.8 Interface sketch: the capability manifest

Language-neutral field list. What binds is 4.3: the concepts the manifest declares, and the obligation that a required field carry no default and fail mount by name. The field spellings below are one conforming vocabulary, not a conformance requirement, and a host declaring the same facts under other names conforms. The obligations the table's marks carry are 4.3's; the table states no second requirement.

| Field | Obligation | Meaning |
|---|---|---|
| name | REQUIRED | local name; the qualified name is derived from topology (6.1) |
| description | REQUIRED | routing trigger: what it does and when to use it (4.4) |
| uses | REQUIRED, even when empty | children invoked through the host (5.1) |
| tools | REQUIRED, even when empty | tool declarations this capability requires |
| expose_to | REQUIRED, null-or-list | declared withholding; null means no declared narrowing, empty means withheld from every caller (8.3) |
| payload | REQUIRED | location of the body; never served in a catalog row (7.3) |
| version | RECOMMENDED | declared identity; absent falls back to content hash (10.1) |

Python reference signature:

```python
@dataclass(frozen=True)
class CapabilityManifest:
    name: str                             # local; qualified name is derived (6.1)
    description: str                      # what it does and when to use it (4.4)
    uses: tuple[str, ...]                 # () is a declaration; omission is a TypeError
    tools: tuple[str, ...]                # () is a declaration
    expose_to: tuple[str, ...] | None     # None: no narrowing declared; (): withheld from all
    payload: str                          # location, not contents (4.7)
    version: str | None = None            # RECOMMENDED (10.1)

def parse_manifest(text: str, source: str) -> CapabilityManifest:
    """Every failure raises naming source and the offending field (4.2, 4.5)."""
```

## 5. Composition

- **5.1** A composite capability MUST name its children in its manifest and MUST invoke them through the host. Importing or linking another capability's code directly MUST NOT occur. [E exp-2: the conventional twin composes by importing the sibling payload module, which is what makes its composition graph unavailable to any machine; both twins return identical results, and only one of them can answer what composes what]
- **5.2** The composition graph MUST be derived from the child declarations and MUST NOT be hand-written ([ESPALIER] 5.2). [E exp-2: the derived twin's graph, dispatch table, catalog, and exposure map all derive from the same declarations, and the derived arm needed roughly 50 fewer edit sites per stream to keep them agreeing]
- **5.3** Mount MUST fail, naming both the referencing capability and the unresolved reference, when a declared child or a declared tool does not resolve in the registry. [E exp-2: the removal fault class is exactly this, a tool removed while a nested capability still declares it, and the sweep naming the dangling reference is the derived arm's treatment for it, an arm asymmetry whose loud-failure outcome did not separate the arms (4.2)]
- **5.4** A cycle in the composition graph MUST fail at mount, naming the cycle. [DI]
- **5.5** A machine check MUST enforce 5.1. Convention does not enforce a code-type boundary ([ESPALIER] 6.2). [E exp-2: the derived twin ships the illegal-import sweep as a mount-time check; the conventional twin's identical behavior with no check is the control arm]

## 6. Namespacing

- **6.1** Qualified names MUST be derived from topology and MUST NOT be hand-written. [E exp-2: one task in every stream moves a capability between groups, which changes its qualified name; in the derived arm the name follows by derivation, and the one conventional stream that failed the task outright failed on this task, landing the move almost nowhere and turning the suite red on the spot]
- **6.2** A name collision MUST fail assembly loudly, naming both claimants. [E exp-2: duplicate-name detection is one of the four mount sweeps present in the derived arm only, the arm asymmetry recorded at 4.2]
- **6.3** A host that aggregates capabilities from another host MUST prefix the aggregated names with its own identity. [DI, convergent practice: the surveyed aggregating hosts prescribe the same rule for proxied capabilities]
- **6.4** A rename MUST propagate to every declared surface by derivation. A surface that requires a second edit after a rename is a parallel table and violates 4.6. [E exp-2: renaming is one task per stream, and the arm difference is entirely in propagation cost, not in behavior]
- **6.5** After any rename or removal, the sweep of section 12 MUST run before the change crosses a handoff boundary. Derivation moves the declared references; it does not move a name written into prose. [E M2 corpus run: over 150 archived states the sweep fires on exactly the 6 that carry a real residual reference, tracking one residue through two subsequent renames, and is silent on the other 144]
- **6.6** A host MUST declare the grammar its qualified names take, as the token shape a text scan can match: the validated instance is one group segment, a colon, and a local name, matched as a standalone token. The declaration is what makes the sweep of 12.3 reproducible between two implementations and what fixes the false-positive class of 12.6, because a scan with no declared grammar scans a different token set in every host. [DI: the grammar was fixed by construction in the measured subject, and no host declaring a different grammar was run]

## 7. Catalog and disclosure

- **7.1** Indexing MUST be execution-free (4.1). The catalog MUST be buildable from manifests alone. [E exp-2 and the survey: the derived twin's mount imports no capability code, and every surveyed mature plugin host converged on the same invariant]
- **7.2** The catalog MUST be derived at a declared boundary, mount or session assembly, and emitted as an inspectable artifact. It MUST NOT be re-derived per turn. A per-turn projection is not a contract: nothing can validate it, no artifact can record it, and no two turns can be compared. [E M4 validation: the provenance artifact is defined per caller per mount and its diff classes are only meaningful between two boundary-derived states; four frozen readings emitted with every non-empty line attributed] [DI for the prohibition itself: the per-turn alternative was not run as an arm]
- **7.3** Disclosure MUST be two-stage: catalog rows carry the description only, and the payload is loaded on activation. A payload MUST NOT be served in an assembled context. [E exp-2 twin contract, pinned in both arms: bodies never reach a prompt; and the M1 audit found that once a body is served on activation it is served prose, which is why 10.3 puts it inside the identity]
- **7.4** The disclosure limit MUST be a declared quantity, not a constant embedded in a renderer. [E exp-2 gold-standard pass, defect 1: at the original limit one task's stated end state was unsatisfiable, because the seventh visible capability pushed the renderer into deferred mode while the task demanded descriptions; the limit was raised to a value that binds only where a later task lowers it deliberately]
- **7.5** When the rendered set exceeds the disclosure limit, the deferred rendering MUST still name every capability the caller may see, withholding descriptions rather than names. Deferred is a disclosure state, not a withholding. [E exp-2 twin contract: above the limit the layer renders one row per group listing the visible names, with descriptions withheld until activation]
- **7.6** The rendering mode in force MUST be recorded in the served-state record of 14.3. [E M4 diff sharpness: a limit change from 10 to 3 is reported as disclosure-state-changed, full to deferred, and as nothing else]
- **7.7** Beyond a declared scale threshold, the catalog MUST be served through search with deferred definitions rather than inlined. The threshold MUST be declared together with the projection-layer measurement that justifies it, MUST be re-measured when the registry crosses it, and MUST NOT be declared at a value the registry is not expected to reach, which would satisfy this requirement vacuously. Absent such a measurement, the evidence-backed ceiling is a registry of 48 capabilities, the size at which the measured benefit below was obtained; a host declaring a higher threshold MUST record the argument for it. [E exp-3: the served projection over a 48-capability registry falls to 30 to 33 percent of the full rendering, measured on the assembled text for both models tested, with the invoice-layer caveat of 9.15] [DI for the 48-capability ceiling as a threshold rule: it is the tested registry size, not a measured breakpoint, and no smaller or larger registry was run]
- **7.8** The catalog served to a model and the table the engine dispatches on MUST derive from the same declaration ([ESPALIER] 9.3). What the model believes and what the machine executes MUST NOT have two sources. [E exp-2: the conventional arm's catalog document and dispatch branch are separate hand edits, and its only persistent failures were served surfaces disagreeing with executed behavior]

## 8. Exposure as governed projection

- **8.1** Registration MUST NOT be exposure. What a caller is served MUST be computed per caller from the registry plus policy, and MUST NOT be read from a second maintained list. [E exp-2: both twins answer identically at the shipped set, one by deriving the projection from the tool exposure rows and one from a hand-written allowlist that happens to agree; the arms diverge as soon as the set churns]
- **8.2** The set of inputs to the projection MUST be enumerable and closed, and it is exactly five: the registry, the policy, the caller identity, the entry declaration, and the budget. This is the enumeration of [ESPALIER] 9.1.6, restated here verbatim; it is fixed by the parent standard and is not extended by a host. Anything else that can change what a caller is served MUST be promoted into one of the five or recorded as a defect. Closure is a per-host property, demonstrated against the fixed five rather than declared: a host demonstrates it by the three checks below, and Level 3 requires the demonstration rather than the assertion.

  (a) Line attribution, the enforcer of 14.4: every served line attributes to a declaration reachable from those five inputs, and a line that attributes to none fails emission. [E M4 validation: on four frozen readings every non-empty served line attributed to a declared string, zero unattributed; a literal planted in the renderer instead of the declaration surfaced as unattributed with a nonzero exit naming the line]

  (b) Reproducibility: two projections computed at one boundary from identical declared inputs MUST produce byte-identical served text. Attribution alone does not close the set, because a projection filtered by an undeclared input, a feature flag, a clock, or a sampled ordering, can still emit only declared strings and pass 14.4 with zero unattributed lines. [E exp-3: two arms rendering through one projection path produced assembled prompts byte-identical by sha256, which is what isolated the host's refusal gate as the only difference between them]

  (c) Sensitivity: mutating each declared input in turn MUST move the served text, or the host MUST record which input its projection is insensitive to and why. An input that never moves the output is either dead or is not the input the host thinks it is. [DI: the per-input mutation sweep follows from (b) and was not run as an experiment; the diff mechanism's one-edit-per-class validation exercises the same shape for four of the five inputs but was not framed as a closure test]

  Each of the five inputs MUST have exactly one declared recording location in the artifact of 14.1, as [AGENT-DEBUG] 4.3 tabulates them, so that an assessor reads each input in one place. A recording location MAY name more than one field where the input is itself compound, and no field may serve two inputs. [E M4 validation: four of the five inputs are recorded in named header or entry fields across four frozen readings; the entry declaration is recorded only implicitly and is carried as a known gap in [AGENT-DEBUG] 4.3 and 6.10]
- **8.3** Withholding MUST be by declaration, never by omission. Every capability withheld from a caller MUST have declaration facts that account for the withholding: a declared exposure narrowing, a required tool the caller may not see, or a withheld child. [E M4 validation: for every withheld capability the artifact reports the ground, a declared exposure list for the directly withheld one and a withheld-child list for the one withheld derivatively; the reading is left to a human and the ground is always present]
- **8.4** A projection requested for an undeclared caller MUST raise, naming the caller. An empty projection is not a conforming answer to an unknown caller. [E exp-2 twin contract, pinned in both arms and asserted by the equivalence gate: silently serving nothing and correctly serving nothing are indistinguishable to the caller and must not be]
- **8.5** Parallel hand-maintained exposure tables MUST NOT exist ([ESPALIER] 9.2). [E exp-2: under the corrected reading of the run, all five conventional streams served a false description from one task to the end of the stream, and nothing in that arm can surface a stale hand table; streams with any silently-stale served surface, 1 of 5 derived against 5 of 5 conventional, Fisher exact p = 0.048, exploratory and constructed after seeing the data]
- **8.6** The projection MUST be derived once at a declared boundary, and the boundary MUST be identifiable from the served-state record. In the validated artifact the boundary is identified by the header fields that name the source root and the caller the projection was computed for, together with the budget fields in force at that boundary; the artifact carries no separate boundary identifier and this requirement does not invent one. A host whose boundaries are not distinguished by those fields MUST add a boundary identifier to its own record and MUST declare the addition, because a projection whose boundary cannot be named cannot be compared with another. [E M4 validation: every emitted artifact carries the source root and the caller in its header, and the four frozen readings are distinguished by that pair] [DI for the once-only constraint, as in 7.2, and for the added-identifier case, which no validated host exercised]
- **8.7** A capability whose required tools or declared children are withheld from a caller MUST itself be withheld from that caller, and the withholding MUST be derived rather than declared a second time. [E exp-2 twin contract: the capability requiring the operator-only tool is invisible to the auditor, 4 catalog rows against 3 and 3 tool rows against 2; in the derived twin that is computed from the tool exposure rows, in the conventional twin it is a hand-written list that happens to agree]
- **8.8** Policy filtering MUST be upstream of narrowing. A context-economy tier (section 9) MUST NOT widen the permitted set, and search MUST NOT return a capability the policy withholds. [E exp-3: search queries the caller's permitted rows only, so the narrow arms could reach every permitted capability and no other; zero of the 168 preregistered requests routed to a name outside that set, which is the scope at which the analysis of record states the check]
- **8.9** The projection MUST be a value: inspectable, comparable, and hashable. It MUST NOT exist only as a side effect of rendering. [E M4: the artifact hashes the served prompt and every served line, which is possible only where the projection is a value the renderer consumes] [DI for the general form]

### 8.10 Interface sketch: the projection

```python
Row = Mapping[str, object]    # served keys: "name" and "description" (9.12).
                              # A search row may also carry implementation-
                              # private keys, a ranking score in the validated
                              # host, which the render boundary drops.

@dataclass(frozen=True)
class Projection:
    caller: str                         # caller identity, one of the five inputs
    boundary: str                       # the declared boundary, named by source root (8.6)
    resident: tuple[Row, ...]           # tier 0 (9.1)
    entry: tuple[Row, ...]              # tier 1 (9.1)
    withheld: tuple[str, ...]           # names, derived by difference (9.4)
    announcement: str                   # derived; "" only when withheld is empty (9.4)
    disclosure_mode: str                # "full" or "deferred" (7.5)
    disclosure_limit: int               # declared (7.4)
    budget_used: int                    # against the declared budget (9.14)

def project(
    registry: Registry,     # input 1: every declaration, unfiltered
    policy: Policy,         # input 2: the declared rules for who may see what
    caller: str,            # input 3: caller identity, the served principal
    entry: Entry,           # input 4: the tier-1 declaration for this session
    budget: Budget,         # input 5: declared context quantity, checked here
) -> Projection:
    """The five inputs of 8.2 and no others.

    The signature is the closure statement: a projection that reads a
    module-level flag, a clock, or an ambient ordering has an input this
    signature does not carry, and 8.2(b) will catch it as a second call
    that differs from the first.

    Raises UnknownCaller for an undeclared caller (8.4).
    Raises BudgetExceeded at assembly rather than truncating (9.14).
    """
```

## 9. Context economy

- **9.1** A host that narrows MUST declare its tiers: a resident tier served on every assembly, an entry tier declared per session, and a searchable remainder. Each capability's tier MUST be derived from the entry declaration and the registry, never hand-assigned per capability. [E exp-3: the narrow arm is resident tier of search plus two universals, entry tier of one group of six, and a searchable remainder of 40; the served projection is 30 to 33 percent of the full rendering]
- **9.2** The entry declaration MUST be made at session assembly and MUST be recorded in the served-state record. [E M4: the artifact records visible against withheld counts per caller per mount, which is the entry declaration's observable form] [DI for the requirement that entry be declared per session rather than per host]
- **9.3** A host MUST NOT narrow without both the announcement of 9.4 and the reachability gate of 9.7. Narrowing with neither is a system that lies: it answers that nothing covers a request the registry can serve. [E exp-3: removing only the announcement drops out-of-scope success from 21/24 to 9/24 and adds 8 confident wrong routes on top of 4 additional false refusals; keeping the announcement and adding no gate leaves a deterministic 3/3 false refusal on the flagship model]
- **9.4** The announcement MUST be served in the same assembled context as the narrowed set, and MUST carry a count and the withheld group names, both derived by difference from the registry. [E exp-3: the announcement is the single highest-yield text in the experiment, 48 to 70 tokens carrying a 21/24 against 9/24 difference on the out-of-scope class]
- **9.5** The announcement MUST NOT be hand-written. A hand-written count is a second declaration of the projection ([ESPALIER] 5.1) and goes stale on the first registry change. [E exp-2, the contrast stated once at 8.5 and carried here at that same strength: streams with any silently-stale served surface, 1 of 5 derived against 5 of 5 conventional, under the corrected reading of the run, Fisher exact p = 0.048, exploratory and constructed after seeing the data; and exp-3's announcement is computed by difference at assembly, never stored]
- **9.6** A host MUST NOT rely on the announcement alone. **[R exp-3, C3 refuted]** On the flagship model, out-of-scope routing fell from 12/12 with the full catalog to 9/12 with the announced narrowing. All three failures were the same request, all were false refusals, all were reached with zero searches, and the failure was deterministic at 3 of 3 repetitions. The archived prompts show the model read the announcement and recited the withheld group names, including the group holding the answer, and then refused rather than spend one step searching. Merged across the two models tested the cell reads 87.5 against 100, and a merged average does not rescue a deterministic failure on the flagship model. The announcement is prompt text, which is the weakest rung of the guarantee ladder ([ESPALIER] rule 1); the announcement is necessary and it is not sufficient.
- **9.7** A host that narrows MUST refuse to accept a refusal from a caller that has not searched the withheld set on that request. On refusal, the host MUST return one observation and continue rather than terminate. A host MAY cap the gate at one firing per request, accepting a later unsearched refusal on the same request; the measured host carried that cap, and it is what bounds the gate's cost to one extra step. [E exp-3, gated arm, 72 requests: out-of-scope routing on the flagship model rises from 9/12 to 12/12; the deterministically failing request unit goes from 0/3 to 3/3, each time refusal, then search, then the correct capability; the gate fired 3 times in 72 requests, all on that unit, and every firing ended correct; spurious firings 0/24 on in-scope and 0/24 on the distractor class, with average steps unchanged at 1.00 on both]
- **9.8** The gate MUST be enforced in the host's protocol, at the call boundary, and MUST NOT be implemented as an instruction in served text. [E exp-3 diagnosis: the announcement failed precisely because it was text and a persona prior overrode it; the fix that worked changed no text at all]
- **9.9** The gate predicate SHOULD be strengthened beyond the measured one of 9.7, so that a refusal is admissible only after a search that returned at least one row, and only when the refusal addresses what the search found. **[DI, strengthened]** The measured gate checks only that a search occurred; the experiment recorded as an open caveat that a perfunctory search followed by a refusal is still available, and that a rollout needs a stronger predicate. The strengthened predicate is this document's inference from that caveat and has not been measured, which is why it is RECOMMENDED here and in [ESPALIER] 9.1.2 rather than required; the measured predicate of 9.7 is the MUST. A host that adopts the strengthened predicate MUST define its mechanical test rather than leave it to judgement; the test this document offers is that the refusal text contains at least one qualified name drawn from the rows the search returned, and a host adopting a different test MUST state it. A host implementing only the measured predicate MUST record the gap as a memory-tier entry ([ESPALIER] 4.3).
- **9.10** Enabling the gate MUST NOT change the served bytes before the gate fires. The gate is a protocol rule, not a prompt variant, and a host that also edits its text has changed two things. [E exp-3: the gated arm renders through the narrow arm's own path, and byte identity of the assembled prompt and of every task's first-step prompt is reported by hash rather than assumed]
- **9.11** Every gate firing MUST be recorded with its request, its position in the exchange, and its outcome. The extra step a firing costs is the honest price of the gate and MUST NOT be hidden. [E exp-3: a gated request costs 3 steps against the narrow arm's 1, and that 1 step produced a wrong answer; cost is confined to firings because non-firing requests are unchanged at 1.00 steps]
- **9.12** Search MUST query the caller's full permitted set rather than the served set, MUST be deterministic including its tie-breaking, and MUST itself be served in the resident tier. The rows it serves MUST carry the name and the description, and MUST NOT carry ranking data; a row may hold ranking data internally, which the render boundary drops. [E exp-3: search over the permitted rows with deterministic scoring and name tie-breaks, each row holding a score that the rendered result does not carry; zero parse failures across all 240 requests, and zero hallucinated routes across the 168 preregistered requests, which is the scope at which the analysis of record states that check; every task's answer was verified reachable in every arm by a canary before the run]
- **9.13** A trained retrieval component SHOULD NOT be introduced below a declared scale threshold. The declared taxonomy plus a deterministic search is the index. The threshold is declared under the discipline of 7.7: it carries the projection-layer measurement that justifies it, is re-measured when the registry crosses it, and is not set at a value the registry will not reach. Absent such a measurement, the evidence-backed floor is the 48-capability registry below, at which a deterministic index routed in scope without loss. [E exp-3: a 48-capability registry routed at 24/24 in scope with a deterministic lexical search; and the retrieval literature surveyed in the design of record records a 52-point pass-rate drop attributable to a poor retriever, which is a silent cap on every capability behind it]
- **9.14** The context budget MUST be a declared quantity checked at assembly. Exceeding it MUST fail at assembly, naming the budget and the overrun. A host MUST NOT silently truncate, drop rows, or switch rendering to fit. [E exp-2 gold-standard pass, defect 1: an undeclared limit silently forced a rendering change that the task text never mentioned and that made the task's stated end state unsatisfiable; the defect was found only because a gold implementation was run before any data was collected] [DI for the fail-at-assembly form]
- **9.15** Any claim of context economy MUST cite both the projection-layer measurement and the billed measurement. **[R exp-3, C1 holds with a hard footnote]** The served projection falls to 30 to 33 percent of the full rendering, and per-request billed tokens rise in the narrow arm, because the additional step re-pays the harness's fixed context, of which the served catalog was about 9 percent. The claim is true at the projection layer and false at the invoice layer of that harness. A host citing one half of that result and not the other is misreporting.
- **9.16** A host MUST verify in-scope routing before adopting narrowing, and MUST record the result. [E exp-3, C2 not refuted: in-scope routing 24/24 against 24/24; the check is cheap and the failure it guards against would be silent]
- **9.17** A host MUST NOT justify narrowing as insurance for weaker models. **[R exp-3, C5 refuted, direction reversed]** The smaller model tested ceilinged at 12/12 on the full catalog in every class, so the measured effect was larger on the stronger model. The result is recorded as underpowered rather than settled: the design had no headroom on the smaller model. The defensible justifications for narrowing are the projection-layer economy of 9.15 and the focus result, which is itself measured on one of the two models and MUST be cited with the model it holds on: on the flagship model, narrowing improved routing where the withheld capability was a plausible-but-wrong distractor, 7/12 to 11/12 with distractor hits falling from 5 to 0; on the smaller model the same contrast reverses, 12/12 to 11/12 with distractor pull rising from 0/12 to 1/12. The focus benefit is therefore measured, model-dependent, and not a property of narrowing as such.

### 9.18 Interface sketch: the gate protocol and the search contract

```python
@dataclass(frozen=True)
class SearchCall:
    query: str
    rows: tuple[Row, ...]
    row_count: int

@dataclass(frozen=True)
class SessionState:
    searches: tuple[SearchCall, ...]     # this request only
    gate_firings: int

@dataclass(frozen=True)
class GateVerdict:
    accepted: bool
    observation: str | None              # served on refusal; None when accepted

def accepts_refusal(session: SessionState, refusal: Refusal) -> GateVerdict:
    """The measured predicate of 9.7: a search occurred on this request.

    Row count does not enter it. The validated host marks the request
    searched when a search directive parses, before any row is scored,
    and that is the predicate the gated arm was measured under. It also
    fires at most once per request: a refusal that follows a firing is
    accepted, which bounds the cost of the gate to one extra step.
    """
    if session.searches or session.gate_firings:
        return GateVerdict(True, None)
    return GateVerdict(False, OBSERVATION_UNSEARCHED)

def accepts_refusal_strengthened(
    session: SessionState, refusal: Refusal
) -> GateVerdict:
    """The strengthened predicate of 9.9. Design inference, not measured.

    A host adopting it declares its own mechanical test for addresses();
    a host implementing only the measured predicate above records the
    gap as a memory-tier entry (9.9).
    """
    productive = [s for s in session.searches if s.row_count > 0]
    if not productive:
        return GateVerdict(False, OBSERVATION_UNSEARCHED)
    found = {row["name"] for s in productive for row in s.rows}
    if not refusal.addresses(found):
        return GateVerdict(False, OBSERVATION_UNADDRESSED)
    return GateVerdict(True, None)

def search(query: str, *, caller: str, limit: int) -> tuple[Row, ...]:
    """The caller's full permitted set, not the served set (8.8, 9.12).

    Deterministic, including tie-breaking on qualified name. Rows carry
    the name and the description that are served, and may carry private
    ranking data that the render boundary drops (9.12). Row count is
    recorded for the strengthened predicate.
    """
```

- **9.19** The observation served on a refused refusal MUST state only that the withheld set has not been searched and that a refusal is not available until it has been, and MUST NOT tell the caller what to search for. The gate's measured value is that it declines the refusal, not that it steers the retry; an observation that names a capability or a query has changed the served content of the exchange and is no longer the intervention that was measured. [E exp-3: the gated arm's only difference from the ungated arm is the host declining the refusal, with the served prompt byte-identical by sha256; every firing ended on the correct capability without the observation naming it]

## 10. Version identity

- **10.1** Every capability MUST carry a machine-computable identity: the declared version where one is declared, otherwise the content hash of its payload. [E exp-2 twin contract: identity is the declared version when present and the payload hash otherwise, which is what makes a body changed without a version bump detectable]
- **10.2** A payload changed without a declared version bump MUST be machine-detectable. [E exp-2: the fallback hash exists for exactly this case, and the mechanism replays depend on it to reconstruct archived states]
- **10.3** The identity MUST cover every byte the host serves for that capability: the description, the behavior-determining declaration fields, and the payload body served on activation. [E M1 adversarial audit: a falsified activation body was served silently because the body sat outside both hashes; the behavior hash was extended to cover the served body as a direct result]
- **10.4** The identity MUST appear in the derived catalog artifact, so that two mounts can be compared without reading either tree. [DI]

## 11. Mechanism M1: the prose-behavior compound

**Verdict.** The lock is required as a co-change forcing function (11.1). The lock as a staleness detector is **REFUTED** (11.6). The judge is recommended on the advisory seat only (11.7).

**What it answers.** Six of ten streams in the main run served a description that a later behavior change had falsified, and nothing in either arm could see it. The served description is the model's routing basis, so stale prose misroutes the agent and misstates side effects.

**The refutation, stated with the requirement.** At equal lock age the lock fires on every capability edit regardless of whether the prose is true: 89 of 150 archived states fire, and its precision as a stale-prose detector is approximately 8 percent. Three constructions serve false prose with the lock silent: refreshing the lock while the prose is already stale; falsifying an activation body, which sat outside both hashes until 10.3; and falsifying a hand-maintained table, which has no anchor to lock against and is out of the mechanism's reach by nature. The lock guarantees that prose is put in front of an editor once per behavior change. It does not guarantee that the prose is true.

- **11.1** Each capability MUST carry a lock recording the last jointly confirmed pair of behavior hash and description hash. A missing or unreadable lock MUST fire: the lock is required and has no default, and an unreadable lock is not a weaker state than a missing one. [E M1 replay: the lock fires on the archived state that kept a description falsified by a later behavior change, and is silent on the state where the subject corrected it and refreshed]
- **11.2** The behavior hash MUST cover the behavior-determining declaration fields and the payload bytes, including any body served on activation, and MUST NOT cover identity-only fields. [E M1 audit and 10.3: the falsified-body construction was silent until the body entered the hash]
- **11.3** The description hash MUST be computed by the same function the provenance artifact uses for a served line's content hash (14.6), so that a lock and an artifact compare without a second rule. [E M4: the artifact's content hash for a capability line is the lock's description hash for that capability, which is what makes a served line and a locked pair comparable]
- **11.4** When the current pair differs from the locked pair, the check MUST name the capability, MUST state which side drifted, and MUST print the served description. Printing the prose is the mechanism: the confirm gate puts the sentence in front of the decider. [E M1 replay: the firing output names the capability and the drifted side and prints the served description]
- **11.5** Refreshing a lock MUST be a deliberate act performed with the drifted prose in view. Automatic refresh MUST NOT exist. A lock that refreshes itself records nothing. [E M1 audit: refresh-at-the-stale-state is one of the three silent-false constructions, and it is the one an automatic refresh would produce on every edit]
- **11.6** A host MUST NOT claim that the lock detects stale prose. Its stated guarantee is co-change forcing, and its stated precision as a detector is approximately 8 percent. [R M1 audit, as above]
- **11.7** A semantic judge SHOULD run below the deterministic checks in the guarantee ladder. It MUST run only on capabilities whose lock reports drift, MUST emit a warning rather than a failure, and MUST NOT fail a build. Runtime correctness MUST NOT depend on it. [E judge validation, two rounds: recall 6/6 in both rounds, every real falsification caught single-shot; specificity 5/6 in each round; read at deployment scope, where the lock gates which capabilities reach the judge, positives are 6/6 and the in-flow negative class, a capability whose behavior and prose changed together correctly, passes 4/4 across both rounds, with both false positives sitting in the out-of-flow class the gating excludes]
- **11.8** The judge's material MUST be the capability's served prose, its declared fields, its payload sources, and its declared children's descriptions and payloads to depth one. [E judge validation: the round-1 false positive was a parent's cross-child invariant judged without child sources; adding child material fixed it and the re-run passed with the judge citing the child's threshold by value; a guard case confirmed that child material does not launder a missing-tool claim]
- **11.9** The judge's output MUST quote the contradicted claim exactly. A judge that reports a verdict without the quotation cannot be adjudicated by the human who holds the decision. [E judge validation: every one of the 6 recalled falsifications was reported with the contradicted claim quoted]
- **11.10** The known false-positive class MUST be documented wherever the judge's output is consumed: cross-capability invariants judged from single-capability scope, and single-shot variance. The measured rate is approximately 1 in 6 on out-of-flow pristine material, and the false positive moved between rounds on byte-identical material, so one sample cannot separate scope error from sampling variance. The recorded improvement path is a callers-of section derived from the inverse composition edge; it is not built. [E judge validation, both rounds]
- **11.11** A served-prose surface that no declaration anchors MUST be eliminated by derivation (8.5), not covered by a lock. The lock has nothing to hash on a hand-maintained table. [R M1 audit: the falsified hand table is the third silent-false construction and is out of the mechanism's reach by nature]

**Cost.** The lock costs one hash pair per capability and no model. The judge costs approximately 0.09 United States dollars and 11 seconds per judged capability; at the churn density of the main run, one or two capabilities are judged per task.

### 11.12 Interface sketch: the lock

```json
{
  "lock_version": 1,
  "capability": "ops:fetch_orders",
  "behavior_sha256": "<hex>",
  "description_sha256": "<hex>"
}
```

- **11.13** The lock body MUST carry no timestamp and no other value that varies between two reconstructions of one state: a lock reconstructed at an archived state MUST be byte-reproducible. Byte reproducibility is what makes the mechanism replayable against history, and a replay is how a lock's precision was measured at all. [E M1 replay: locks do not exist in the archives and were reconstructed at the last point the prose was authored or confirmed, which is possible only because the lock body is a function of the state and of nothing else]

```python
def behavior_hash(directory: Path, fields: Mapping[str, str]) -> str:
    """sha256 over behavior fields and payload bytes, length-prefixed and
    domain-separated per item so that field and file cannot collide (11.2)."""

def description_hash(description: str) -> str:
    """sha256 of the served description string. Shared with 14.6."""

def check_tree(tree: Path) -> list[Violation]:
    """Fires per capability: missing lock, behavior drift, description drift.
    Every violation names the capability, the drifted side, and the served
    description (11.4)."""
```

## 12. Mechanism M2: the dangling-name sweep

**Verdict.** VALIDATED. Required wherever prose surfaces exist (12.1).

**What it answers.** Removals and renames leave name references behind in payload text and in served prose. Structural sweeps see declared references only; a mention inside text is invisible to them. One conventional stream carried such a residue through six tasks to the end of the stream with the suite green throughout.

- **12.1** A dangling-name sweep MUST run wherever a capability name can appear in text: payload bodies, served prose, and any prompt-layer source. [E M2 corpus run: over all 150 archived states the sweep fires on exactly the 6 carrying the real residue, tracking it through two subsequent renames, and is silent on the other 144; zero corpus false positives, and it discriminates a planted resolvable name from a planted unresolvable one]
- **12.2** The scan surface MUST be a declaration that enumerates every served-prose source, and that declaration MUST be reviewed whenever a new served-prose source appears. [E M2 audit: the conventional twin's served catalog file sat outside the scan surface, and a dangling name planted there went unseen until the file was added to the scan table; a sweep is exactly as complete as its declared surface]
- **12.3** The sweep MUST resolve tokens matching the qualified-name grammar declared under 6.6 as standalone tokens against the registry, and MUST fire naming the file, the line, and the token. [E M2 replay: both error rows fire naming file and token; the mechanism reports locations, never verdicts]
- **12.4** A host MUST NOT silence the sweep by narrowing its scan surface. The conforming response to noise is to document the false-positive class. [DI, following from 12.2: narrowing the surface is the failure the audit found, arrived at by omission rather than by intent]
- **12.5** The sweep MUST run before a rename or removal crosses a handoff boundary (6.5). [E exp-2: the residue that survived six tasks was created by a removal and was invisible to every per-task check that ran after it]
- **12.6** The known false-positive class MUST be documented: tokens shaped like the grammar declared under 6.6 that are not capability references. The documented instance is slice syntax with named bounds, which is indistinguishable from a qualified name under a substring rule. The tradeoff is the same class as a static import sweep's and is accepted, not solved. [E M2 audit, documented as a real class rather than argued away]

**Cost.** One text scan of the declared surface. No model, no runtime component.

```python
def scan_targets(tree: Path) -> tuple[list[Path], list[Path]]:
    """Capability directories and every declared prose source (12.2).
    Raises when no capability directory exists: an empty scan is a defect,
    not a pass."""

def check_tree(tree: Path) -> list[Violation]:
    """One violation per unresolved token: path, line, token, and the
    registered set it failed against (12.3)."""
```

## 13. Mechanism M3: no red across a handoff

**Verdict.** VALIDATED. Required at handoff boundaries (13.1, 13.2).

**What it answers.** Loudness guarantees coherence, not repair. In the motivating stream a red state stood for six tasks, and the two sessions that followed burned 59 and 61 turns against a 60-turn cap without clearing it. Standing debt taxes every later change.

- **13.1** A work session that ends with the gate red MUST be reverted in full to the last green boundary, and the task MUST be recorded as failed-reverted. [E M3 replay: the revert restores the prior tree byte-exactly, the suite returns green, and a live session on the reverted tree completed the next task cleanly at half the turns and half the cost of the archived session that fought the inherited debt]
- **13.2** The policy MUST be applied at handoff boundaries, where a handoff is any point at which work passes to a session that did not create the state. [E exp-2: the cost of standing debt was paid entirely by sessions that inherited it]
- **13.3** The reverted task's own delta MUST be recorded as outstanding work. The policy converts many tasks of standing red into one recorded failed task; it transfers exactly one task's worth of debt, which was nine incompleteness points in the replay. [E M3 replay, stated as the mechanism's mandatory caveat]
- **13.4** A host MUST NOT claim that the policy repairs the failed task. It bounds the blast radius of a failure; it does not perform the work. [R M3 replay: the debt transfer above is the measured limit of the mechanism]
- **13.5** A session that performed no work MUST be classified as an infrastructure failure and retried, never scored and never reverted as a subject failure. The operational signal is a session that consumed no model tokens. [E audit finding against the main-run narrative: the session originally reported as a loud refusal never ran, at 1 turn and zero billed tokens with a committed diff containing only the injected acceptance test; the narrative was corrected and the stream excluded from confirmatory readings]

**Cost.** One revert to a recorded boundary. The mechanism generalizes from a harness policy to a commit or continuous-integration hook.

## 14. Mechanism M4: the prompt provenance sidecar

**Verdict.** VALIDATED as a recorder, not a detector. Required for debuggability (14.1).

**What it answers.** The served context is a derived artifact and nothing records where each served line came from, or what the mount withheld. Answering what a model actually saw, and what was kept from it, otherwise means reading the tree and reconstructing the projection by hand.

- **14.1** The host MUST be able to emit a provenance artifact per caller per mount. [E M4 validation: four frozen readings across two trees and two callers, each emitted from the tree's own host]
- **14.2** The artifact MUST record, per served line: the layer it sits in, the line index, the line text, the source kind, the source identifier, the file that holds that declaration, the content hash, and the capabilities the line names. The source kinds MUST be an enumerated set covering caller declaration, rules table, capability declaration, tool declaration, derived note, and unattributed. [E M4 validation: 16, 14, 17, and 15 non-empty lines attributed across the four readings, with zero unattributed]
- **14.3** The artifact MUST record, outside its per-line records: the disclosure limit and the rendering mode in force, the registered against visible against withheld counts, the withheld names, the declaration facts behind each withholding, and the hash of the served text itself. Where those values sit is the schema's business, not this document's: in the validated schema the counts, the limit, the mode, the hash and the withheld names sit in the header and the grounds sit on the capability entries ([AGENT-DEBUG] section 6, which governs the artifact under 3.1). [E M4 validation: the four readings report 7/7/0, 7/5/2, 8/8/0, and 8/6/2, in full and deferred modes, with the ground of every withholding present]
- **14.4** Attribution MUST be matching against the strings the system itself declares, never re-derivation and never assignment to the nearest plausible declaration. A line that matches nothing MUST be recorded as unattributed, counted, and MUST cause the emission to exit nonzero naming the line. [E M4 attribution holes, found by planting them: a literal inlined in the renderer instead of declared in the layer module has no declaration to match and is recorded as unattributed with a nonzero exit; a renderer format change makes the affected rows unattributed in the same way; neither is silently attributed]
- **14.5** The artifact MUST NOT be inlined into the served text. Emission MUST read the tree only, MUST write nothing into it, and the served bytes MUST be identical with and without emission. Provenance added to the text a model reads changes the context and therefore changes the behavior the artifact exists to explain. [E M4 validation: emission imports the tree read-only and the served prompt hash is unchanged by emission]
- **14.6** A served line's content hash MUST be the same function the lock uses for a description hash (11.3). [E M4: the shared hash is what lets an artifact and a lock be compared without a second rule]
- **14.7** Three operations MUST exist: emit, which writes the artifact for one caller at one mount; diff, which classifies every difference between two artifacts; and explain, which prints the full record of one served line. Explain is the debugging lookup, and it is the operation that converts a source read into a question. [E M4 debugging case: both questions, whether the withholding was announced and which capability was withheld, are answered from the artifact with no source file opened]
- **14.8** The diff MUST classify every difference into exactly one named class from the enumerated set of [AGENT-DEBUG] 5.4, and each reported change MUST name its subject. The class set and the treatment of a difference that no named class accounts for are stated once, in [AGENT-DEBUG] 5.4 and 5.5, and bind here by normative reference; this document does not restate them, because two statements of one class set are two facts that will diverge ([ESPALIER] 5.1). [E M4 diff sharpness: seven single-edit cases, each reporting exactly its own class naming its own subject and reporting nothing else, plus a residual sweep so that a clean exit means the served text is the same text]
- **14.9** The artifact is per caller and so is the diff. A declaration edit that does not move a given caller's served surface MUST be silent in that caller's diff and MUST appear in the diff of a caller it does move. Silence there is correctness, not a miss. [E M4 silence controls: an exposure edit reports identical on the caller whose served text did not move, and an identity edit reports identical on the other caller]
- **14.10** A host MUST NOT claim the artifact detects anything. It does not judge prose true, which is 11.7's seat; it does not know what the caller asked; and it does not re-derive the host's exposure decision, reporting the declaration facts that bear on a withholding and leaving the reading to a human. [E M4 ruling: the mechanism fires on nothing and makes two questions a lookup that were a source read before]
- **14.11** Attribution holes MUST surface as unattributed lines rather than be special-cased. A host that adds a matching rule to absorb a renderer literal has deleted the signal that a literal was authored outside the declarations. [E M4: both planted holes surfaced, and the ruling records reporting them rather than special-casing them as the mechanism's discipline]
- **14.12 Standing finding, and the requirement that follows.** A host that derives its projection correctly and serves no withholding announcement is structurally the worst-scoring arm of the routing experiment. Emitting the artifact over the two derived trees showed that their assembler carries no withholding announcement, so every context they serve that withholds anything is structurally the silent-narrowing arm, the arm measured at 9/24 against 21/24 on the out-of-scope class with 8 confident wrong routes added. On the derived twin, the auditor is served a context that withholds two capabilities and says nothing about either. The hand-wired twin holds the same gap, established by reading its assembler rather than by emission, because the recorder cannot mount that twin: it imports the derived twin's layer, registry, and tool-declaration modules, and the hand-wired twin holds a flat prompt module and a hand-maintained catalog table instead. That a host cannot be recorded at all is itself the finding this requirement generalizes. Correct derivation therefore MUST NOT be treated as discharging the announcement obligation of 9.4: derivation quality is invisible in the served text, and a perfectly derived silent projection and a hand-maintained silent projection are the same arm from the model's side. [E M4 validation on the two derived trees, read against exp-3's silent arm, with the hand-wired twin's missing announcement path established by source inspection]

**Cost.** One structured file per caller per mount. No model, approximately one second to emit.

### 14.13 The artifact contract, and where it is stated

- **14.14** The artifact's schema is the schema of [AGENT-DEBUG] section 6, and an implementation MUST emit that schema, with that artifact kind constant and those field names and value shapes. This document states no second schema. A single artifact specified in two places is the parallel-table failure this specification exists to forbid ([ESPALIER] 5.1, 9.2, and 4.6 here), and the schema of [AGENT-DEBUG] section 6 is the one that was validated against emitted output. Where an implementation follows this document and [AGENT-DEBUG] both, [AGENT-DEBUG] governs the artifact (3.1). [E M4 validation: the validated emitter's artifact kind and header shape are the ones the companion's section 6 records]

The three operations of 14.7 have the following reference signatures. The shapes they carry are the schema of [AGENT-DEBUG] section 6 and the class set of [AGENT-DEBUG] 5.4.

```python
def emit(tree: Path, caller: str) -> dict:
    """Assemble through the tree's own host, then record where every served
    line came from. Read-only over the tree (14.5). Exits nonzero when any
    line is unattributed (14.4)."""

def diff(before: dict, after: dict) -> list[Change]:
    """One classified change per difference, each naming its subject (14.8).
    Nonzero exit when any change is reported."""

def explain(artifact: dict, line: int) -> list[tuple[str, str]]:
    """One served line's full record, plus the withheld set and the
    announcement verdict on the same screen (14.7)."""
```

## 15. Conformance levels

The three levels mirror the parent standard's Mapped, Checked, and Derived.

- **15.1** A conformance claim MUST name the claimed level, the version of this specification it was assessed against, the assessor, and the assessment date, and MUST be supported by evidence: at Level 1, the served-surface inventory (1.2) and the capability manifests; at Level 2 and above, the enforcer inventory required by [ESPALIER] 10.2, with a row for each mechanism of sections 11 through 14 that the level cites. [DI]
- **15.2** A claim at a level MUST satisfy every requirement enumerated for that level and for all lower levels. [DI]
- **15.3** Requirements not enumerated by any level are conditional: each binds, at every level, wherever its subject exists. A violation recorded on the red list or the memory-tier register with a destination ([ESPALIER] 4.3, 7.5) does not defeat a claim at Level 1 or Level 2; an unrecorded violation does. [DI]
- **15.4** A claim under this specification MUST be paired with a [ESPALIER] claim at the mirrored level: Level 1 with Mapped, Level 2 with Checked, Level 3 with Derived. A capability host conforming here while its surrounding system holds its structure by memory has moved the failure, not removed it. [DI]
- **15.5** A host that narrows its served capability set MUST claim Level 2 or above, and MUST additionally satisfy 9.1 and 9.12 at that level. Narrowing depends on the gate of 9.7, and a gate is a machine check; a Level 1 claim cannot carry it. The two additions are what the gate presupposes: 9.1 declares the tiers that fix what is withheld, and 9.12 is the search surface the gate's predicate refers to, and both are otherwise enumerated only at Level 3, so a Level 2 narrowing host would have been required to gate on a surface it was not required to possess. [E exp-3: the announcement alone, which is all a declaration-only level can offer, is the refuted configuration of 9.6]
- **15.6** A requirement a host deliberately does not meet MUST carry a waiver under [ESPALIER] 4.2, naming the reason and the trigger that ends it, and MUST appear on the memory-tier register. A requirement marked `[DI]` in this document MAY be waived on the ground that it is not yet measured, and that ground MUST be written down rather than assumed. [DI]

**Level 1, Declared.** MUST satisfy 1.1, 1.2, 1.4, 3.3, 4.1, 4.2, 4.3, 4.4, 4.6, 5.1, 6.1, 8.1, 8.3, 8.4, 10.1. In prose: the served-surface inventory exists, every capability is a directory plus one static manifest with required fields and no defaults, descriptions state what and when, composition is declared rather than imported, qualified names come from topology, exposure is computed rather than listed, withholding is declared, and every capability has a machine-computable identity.

**Level 2, Checked.** MUST additionally satisfy 4.5, 4.7, 5.3, 5.5, 6.2, 6.5, 7.1, 7.3, 7.4, 8.5, 9.3, 9.4, 9.5, 9.7, 9.8, 9.10, 9.11, 9.14, 9.16, 9.19, 10.2, 10.3, 11.1, 11.2, 11.4, 11.5, 11.6, 11.13, 12.1, 12.2, 12.3, 12.5, 12.6, 13.1, 13.2, 13.3, 13.5, 14.1, 14.2, 14.3, 14.4, 14.5, 14.7, 14.8, 14.10, 14.14. In prose: mount sweeps fail loud and name the capability, the disclosure limit and the context budget are declared and checked, narrowing ships with its announcement and its gate, the gate's observation steers nothing, the lock and the sweep run and the lock is byte-reproducible, no red crosses a handoff, and the provenance artifact can be emitted in the schema of [AGENT-DEBUG] section 6, diffed, and explained.

**Level 3, Derived.** MUST additionally satisfy 5.2, 6.3, 6.4, 7.2, 7.5, 7.6, 7.7, 7.8, 8.2, 8.6, 8.7, 8.8, 8.9, 9.1, 9.2, 9.12, 9.13, 10.4, 11.3, 11.8, 14.6, 14.9, 14.12. In prose: every surface including the composition graph and the tier assignment is derived at a declared boundary, the projection's input set is the closed five of 8.2 and is mechanically demonstrated closed by attribution, reproducibility, and sensitivity, search and the catalog serve the same registry the engine dispatches on, judged material carries declared children to depth one, and the lock and the artifact share one hash so that a served line and a locked capability compare directly.

The table below is informative. It summarizes the level lists above by surface; where it and a level list disagree, the level list governs and the table is a defect of this document.

| Served surface | Level 1 | Level 2 | Level 3 |
|---|---|---|---|
| assembled context | inventoried as a surface (1.4) | announcement and gate present where narrowing is used (9.3, 9.7) | every served line attributes to one of the five projection inputs, and closure is demonstrated (8.2, 14.4) |
| catalog served to a model | derived from manifests (4.1) | execution-free, two-stage disclosure enforced (7.1, 7.3) | one source with the dispatch path (7.8), search-served above a justified threshold (7.7) |
| dispatch | declared, not improvised (4.6) | unresolved references fail mount (5.3) | derived from the same declarations as the catalog (7.8) |
| exposure | computed per caller (8.1), withholding declared (8.3) | no parallel exposure table (8.5) | closure over tools and children derived (8.7), boundary identifiable (8.6) |
| composition | declared, host-mediated (5.1) | sibling imports machine-checked (5.5) | graph derived from declarations (5.2) |
| served prose | descriptions state what and when (4.4) | lock and dangling-name sweep run, lock byte-reproducible (11.1, 11.13, 12.1) | judged material includes children at depth one (11.8); the judge itself stays advisory at every level, running only on locked drift, warning rather than failing, and never failing a build (11.7, RECOMMENDED, cited by no level) |

## 16. Versioning of this specification

This specification versions under Semantic Versioning 2.0.0, independently of the parent standard, and records the parent version it refines in its header table. Changes to normative requirements bump major or minor; editorial changes bump patch. Pre-release drafts increment the draft identifier on any change and promise nothing about compatibility. A conformance claim cites the exact version it was assessed against, and the paired parent claim cites its own.

## 17. References

Normative (this list is normative; see Conformance notation):

- [RFC2119] Bradner, S., "Key words for use in RFCs to Indicate Requirement Levels", BCP 14, RFC 2119, March 1997.
- [RFC8174] Leiba, B., "Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words", BCP 14, RFC 8174, May 2017.
- [ESPALIER] "Espalier", `SPEC.md`, this repository, version 1.0.0-draft.4, cited by exact version in any conformance claim.
- [AGENT-DEBUG] "Agent debugging under derivation", `AGENT_DEBUG.md`, this repository, version 0.1.0-draft.1. Invoked normatively by 3.1, 8.2, 14.8 and 14.14: it states the provenance artifact's schema, the class set of a difference between two artifacts, and the recording location of each of the five projection inputs. Where this document and [AGENT-DEBUG] conflict, 3.1 states which governs.

Informative:

- [STUDY] The evidence corpus behind this document: repository `dmm-study` (`github.com/Liamour/dmm-study`), snapshot commit `a98fa852647a79f7b61a132c9bf86094e225905a`, dated 2026-08-20. exp-2, the capability-churn experiment, has its analysis of record at `data/main/ANALYSIS.md`, its design at `docs/EXPERIMENT2_DESIGN.md`, its shared observable contract at `docs/TWIN_CONTRACT.md`, and its per-session rows at `data/streams.jsonl`. exp-3, the narrowing experiment and its fourth arm, is at `docs/EXPERIMENT3_NARROWING.md`, with per-cell rows at `narrowing/report.txt` and `narrowing/results.jsonl`. The mechanism replay and the M1 through M4 verdicts are at `docs/MECHANISMS.md`, with the checkers and their tests under `mechanism/`. The composite capability design of record, the D1 through D6 decisions, is at `docs/CAPABILITY_DESIGN.md`. Where the record is not reachable by an assessor, every inline figure in this document is author-held and is not independently checkable; the requirement text stands on its own and is what a claim is assessed against.
- `RATIONALE.md` and `TEMPLATES.md` of the parent standard. Neither carries the evidence cited here; [STUDY] is the only locator for it.

## Annex A (informative): evidence annex

Every normative requirement, its evidence class, and the result it rests on. The inline tags in sections 1 through 15 are authoritative; this table collects them. Classes: **E** measured, **R** measured refutation, **DI** design inference not yet measured.

| Req | Class | Experiment | Result |
|---|---|---|---|
| 1.1 | E | exp-2 | five served surfaces per capability; turns 466-508 against 530-623, p = 0.0079, d = -1.00; edit sites 84-106 against 124-154, p = 0.0079, d = -1.00; p = 0.0159 each on the four derived streams remaining when the audit-flagged stream is excluded, complete separation and d = -1.00 under both; boundary constant of three interpolated |
| 1.2 | E / DI | exp-2 | the conventional arm's five surfaces, each a separate hand edit, nothing swept; the obligation on a host asserting out-of-scope status is inferred, so that 1.1 is evidenced rather than asserted |
| 1.3 | DI | none | out-of-scope-by-design is a decision; the two-surface case was not run |
| 1.4 | E | M4 | four readings over the derived twin and the gold tree, every non-empty served line attributed, zero unattributed; the hand-wired twin was not mountable by the recorder |
| 1.5 | DI | none | scope statement |
| 3.1 | DI | none | refinement relation to the parent standard |
| 3.2 | DI | none | inheritance statement |
| 3.3 | E | contract-first incident | two parallel implementations of one intent diverged on entry point, capability set, callers, error names, loop API, disclosure; both green; neither could run the other's tests |
| 4.1 | E | exp-2 plus six-ecosystem survey | execution-free indexing is the convergent invariant |
| 4.2 | E / null outcome | exp-2 RQ-C | four named mount sweeps in the derived arm against no mount check in the conventional arm, a design asymmetry; the loud-task outcome did not separate the arms, p = 1.000, d = 0.04, the derived arm's whole count in the excluded stream |
| 4.3 | E | exp-2 | required set with no defaults; null against empty exposure carries different meaning |
| 4.4 | E | exp-3 | in-scope routing 24/24 against 24/24 on descriptions alone; zero hallucinated routes across the 168 preregistered requests, the scope at which the analysis of record states the check |
| 4.5 | DI | none | unknown-field rejection was not exercised by a task |
| 4.6 | E | exp-2 | 124-154 edit sites against 84-106; the only class of silently-served staleness |
| 4.7 | E | exp-2 | descriptions from the record, bodies from disk on activation |
| 5.1 | E | exp-2 | the conventional twin's sibling import makes its composition graph unavailable to any machine |
| 5.2 | E | exp-2 | derived graph, dispatch, catalog, exposure from one declaration set |
| 5.3 | E | exp-2 | the dangling-child removal fault class, named by the sweep |
| 5.4 | DI | none | cycle detection exists in the subject; no task exercised it |
| 5.5 | E | exp-2 | illegal-import sweep present in one arm only, by design |
| 6.1 | E | exp-2 | the move task; the one conventional stream failure landed the move almost nowhere and turned the suite red |
| 6.2 | E | exp-2 | duplicate-name sweep, one of the four mount checks present in the derived arm only |
| 6.3 | DI | survey | aggregation prefix is convergent practice across surveyed hosts |
| 6.4 | E | exp-2 | rename propagation is the arm difference |
| 6.5 | E | M2 | fires on exactly 6 of 150 states, tracking one residue through two renames |
| 6.6 | DI | none | the measured subject's grammar was fixed by construction; no host declaring a different grammar was run |
| 7.1 | E | exp-2 plus survey | mount imports no capability code |
| 7.2 | E / DI | M4 | artifact defined per caller per mount; the per-turn alternative was not run |
| 7.3 | E | exp-2, M1 audit | bodies never reach a prompt; a served body is served prose |
| 7.4 | E | exp-2 gold pass defect 1 | an implicit limit made a task's stated end state unsatisfiable |
| 7.5 | E | exp-2 | deferred rendering names every visible capability, withholding descriptions |
| 7.6 | E | M4 | disclosure-state-changed reported for a limit change, and nothing else |
| 7.7 | E / DI | exp-3 | served projection 30-33 percent of full over 48 capabilities; the 48-capability ceiling is the tested registry size, not a measured breakpoint, and the declaration discipline on the threshold is inferred |
| 7.8 | E | exp-2 | the conventional arm's persistent failures were served surfaces disagreeing with executed behavior |
| 8.1 | E | exp-2 | identical answers, two guarantee rungs; they diverge under churn |
| 8.2 | E / DI | M4, exp-3 | (a) zero unattributed lines on four readings, a planted renderer literal surfacing with a nonzero exit; (b) two arms rendering through one projection path produced assembled prompts byte-identical by sha256; (c) the per-input mutation sweep is inferred and was not run |
| 8.3 | E | M4 | the ground of every withholding present in the artifact |
| 8.4 | E | exp-2 twin contract | an empty projection is not a conforming answer to an unknown caller |
| 8.5 | E | exp-2 | silently-stale served surface in 1 of 5 derived against 5 of 5 conventional streams, Fisher p = 0.048, exploratory |
| 8.6 | E / DI | M4 | the header records the source root and the caller, and the four frozen readings are distinguished by that pair; the once-only constraint and the added-identifier case are inferred |
| 8.7 | E | exp-2 twin contract | 4 rows against 3, 3 tool rows against 2, derived from tool exposure |
| 8.8 | E | exp-3 | search over permitted rows only; zero routes outside the permitted set |
| 8.9 | E / DI | M4 | hashing a served projection presupposes it is a value |
| 9.1 | E | exp-3 | tier structure of the narrow arm; 30-33 percent of full |
| 9.2 | E / DI | M4 | visible against withheld counts recorded per caller per mount |
| 9.3 | E | exp-3 | silent narrowing 9/24 against 21/24 with 8 wrong routes added; announced-only leaves a 3/3 deterministic false refusal |
| 9.4 | E | exp-3 | the announcement carries a 21/24 against 9/24 difference in 48-70 tokens |
| 9.5 | E | exp-2, exp-3 | the 8.5 contrast at 8.5's strength, 1 of 5 against 5 of 5 under the corrected reading, Fisher p = 0.048, exploratory; the announcement is computed by difference |
| 9.6 | **R** | exp-3 C3 | 12/12 full against 9/12 announced-narrow on the flagship model; 3/3 deterministic false refusal, zero searches; the model recited the withheld group holding the answer and refused |
| 9.7 | E | exp-3 gated arm | 9/12 to 12/12; failing unit 0/3 to 3/3; 3 firings in 72, all correct; 0/24 and 0/24 spurious; steps unchanged at 1.00 |
| 9.8 | E | exp-3 diagnosis | the text failed to a persona prior; the fix that worked changed no text |
| 9.9 | **DI** | exp-3 caveat (c) | the measured gate checks that a search happened, not that it was relevant; the strengthened predicate is inferred, not measured, and is recommended rather than required, matching [ESPALIER] 9.1.2 |
| 9.10 | E | exp-3 | byte identity of assembled and first-step prompts reported by hash |
| 9.11 | E | exp-3 | gated request costs 3 steps against 1; cost confined to firings |
| 9.12 | E | exp-3 | deterministic search; zero parse failures across 240 requests; zero hallucinated routes across the 168 preregistered requests; per-task reachability canary; served rows carry name and description, the ranking score dropped at the render boundary |
| 9.13 | E | exp-3 plus survey | 24/24 in-scope with a deterministic index over 48 capabilities; surveyed retrieval literature records a 52-point drop from a poor retriever; the threshold-declaration discipline is 7.7's |
| 9.19 | E | exp-3 | the gated arm differs from the ungated arm only by the host declining the refusal, prompts byte-identical by sha256; every firing ended correct without the observation naming a capability |
| 9.14 | E / DI | exp-2 gold pass defect 1 | an implicit limit silently forced a rendering change; fail-at-assembly is inferred |
| 9.15 | **R** | exp-3 C1 | 30-33 percent at the projection layer; per-request billed tokens rise; the catalog was about 9 percent of fixed context |
| 9.16 | E | exp-3 C2 | 24/24 against 24/24 in scope |
| 9.17 | **R** | exp-3 C5 | the smaller model ceilinged at 12/12 on full; effect larger on the stronger model; recorded underpowered; focus result is model-dependent, flagship 7/12 to 11/12 with distractor hits 5 to 0, smaller model 12/12 to 11/12 with distractor pull 0/12 to 1/12 |
| 10.1 | E | exp-2 twin contract | declared version else payload hash |
| 10.2 | E | exp-2 | the fallback hash exists for the undeclared-bump case |
| 10.3 | E | M1 audit | a falsified activation body served silently until the body entered the hash |
| 10.4 | DI | none | cross-mount comparison without reading either tree |
| 11.1 | E | M1 replay | fires on the stale-prose state, silent on the corrected state |
| 11.2 | E | M1 audit | the falsified-body construction was silent until the body entered the hash |
| 11.3 | E | M4 | the artifact's content hash for a capability line is the lock's description hash |
| 11.4 | E | M1 replay | firing names the capability and the drifted side and prints the served description |
| 11.5 | E | M1 audit | refresh-at-the-stale-state is one of three silent-false constructions |
| 11.6 | **R** | M1 audit | fires on 89 of 150 states at equal lock age; approximately 8 percent precision as a stale-prose detector |
| 11.7 | E | judge validation | recall 6/6 both rounds; specificity 5/6 each round; at deployment scope 6/6 positives and 4/4 in-flow negatives |
| 11.8 | E | judge validation | the round-1 false positive was fixed by adding child material to depth one; the guard case held |
| 11.9 | E | judge validation | every recalled falsification reported with the contradicted claim quoted |
| 11.10 | E | judge validation | approximately 1 in 6 on out-of-flow pristine material; the false positive moved between rounds on byte-identical material |
| 11.11 | **R** | M1 audit | a hand table has no anchor and is out of the mechanism's reach by nature |
| 11.13 | E | M1 replay | locks absent from the archives were reconstructed at the archived states, which requires the lock body to be a function of the state and of nothing else |
| 12.1 | E | M2 corpus run | fires on exactly 6 of 150 states, silent on 144, zero corpus false positives |
| 12.2 | E | M2 audit | a served catalog file outside the scan surface hid a planted dangling name |
| 12.3 | E | M2 replay | both error rows fire naming file and token |
| 12.4 | DI | none | follows from 12.2; the audit's hole arose by omission |
| 12.5 | E | exp-2 | the residue that survived six tasks was created by a removal |
| 12.6 | E | M2 audit | slice syntax with named bounds is a real false-positive class, documented |
| 13.1 | E | M3 replay | byte-exact revert; the next task completed clean at half the turns and cost of the archived debt-fighting session |
| 13.2 | E | exp-2 | the cost of standing debt was paid by inheriting sessions, 59 and 61 turns against a 60-turn cap |
| 13.3 | E | M3 replay | exactly one task's worth of debt transfers, nine points in the replay |
| 13.4 | **R** | M3 replay | the mechanism bounds the blast radius; it does not repair the task |
| 13.5 | E | main-run audit | the session reported as a loud refusal never ran: 1 turn, zero billed tokens, diff containing only the injected test |
| 14.1 | E | M4 validation | four frozen readings, two trees, two callers |
| 14.2 | E | M4 validation | 16, 14, 17, 15 non-empty lines attributed, zero unattributed |
| 14.3 | E | M4 validation | 7/7/0, 7/5/2, 8/8/0, 8/6/2 in full and deferred modes with grounds present |
| 14.4 | E | M4 attribution holes | planted renderer literal and format change both surfaced as unattributed with a nonzero exit |
| 14.5 | E | M4 | read-only emission; served bytes unchanged |
| 14.6 | E | M4 | shared hash with the lock |
| 14.7 | E | M4 debugging case | both debugging questions answered from the artifact with no source file opened |
| 14.8 | E | M4 diff sharpness | seven single-edit cases, each reporting exactly its own class and subject, plus the residual sweep; the class set itself is stated in [AGENT-DEBUG] 5.4 |
| 14.9 | E | M4 silence controls | identical reported on the caller whose served text did not move, in both directions |
| 14.10 | E | M4 ruling | a recorder, validated as one; it fires on nothing |
| 14.11 | E | M4 | holes reported rather than special-cased |
| 14.12 | E | M4 on the frozen twins, read against exp-3 | neither assembler announces withholding, so every withholding context is structurally the silent arm measured at 9/24 against 21/24 |
| 14.14 | E | M4 validation | the validated emitter's artifact kind and header shape are the ones recorded in [AGENT-DEBUG] section 6; this document states no second schema |
| 15.1 | DI | none | claim evidence requirements |
| 15.2 | DI | none | level cumulation |
| 15.3 | DI | none | conditional requirements |
| 15.4 | DI | none | pairing with the parent claim |
| 15.5 | E | exp-3 | the announcement alone is the refuted configuration of 9.6 |
| 15.6 | DI | none | waivers under the parent standard |

## Annex B (informative): the refutations, collected

Three results in this document are refutations, and they are as load-bearing as the confirmations. A reader who takes only the confirmations from this specification will build the systems these results rule out.

**Integration completeness did not separate the arms.** The primary preregistered measure of the capability-churn experiment, whether a derived codebase reaches integration completeness more often than a conventionally wired twin, returned no significant difference: state incompleteness 0.270 and tasks fully complete 0.270, at n = 5 per arm, and nothing in that family survives correction for multiple comparisons. What separated the arms decisively was cost, in the same direction in every single stream: turns and edit sites at p = 0.0079 with complete separation, and billed tokens in four of five pairings. The honest claim is that derivation did the propagation work by machine that the other arm's developers did by hand, roughly 50 edit sites and 100 turns per 15-task stream. The claim that derivation makes agents finish the job more often is not supported by this experiment. A secondary, exploratory contrast found that the arms differed in what a failure leaves behind rather than in how often they failed: streams carrying a silently-stale served surface, 1 of 5 against 5 of 5, Fisher exact p = 0.048, constructed after seeing the data. How often a change failed loudly did not separate either, at p = 1.000 and Cliff's d = 0.04, and the derived arm's whole loud-task count sits in the one stream the run's audit excluded for a session that billed zero tokens and never ran. Any claim that derivation makes failures loud rather than silent is therefore an expectation from the mount-sweep asymmetry, not a result of this run.

**The announcement alone is insufficient.** Stated in full at 9.6. The configuration that most implementers will reach for, narrow the catalog and tell the model that there is more, produced a deterministic false refusal on the flagship model, 3 of 3 repetitions on the same request, with zero searches, after the model had recited the name of the withheld group that held the answer.

**The lock does not detect stale prose.** Stated in full at 11.6. The mechanism that appears to catch drift between behavior and description catches co-change, not truth, at approximately 8 percent precision as a detector, and three separate constructions serve false prose with it silent.

Two further results are recorded as refuted in their preregistered form. Context economy holds at the projection layer and reverses at the invoice layer of the harness tested (9.15). The prediction that narrowing helps weaker models more was reversed by the measurement, on an underpowered design (9.17).

## Annex C (informative): the shape of a conforming host

The order-desk fixture, used throughout the evidence corpus, illustrates the shape at Level 3. Two groups of capabilities, `ops` and `finance`; three tools, of which one is exposed to the operator caller only; two callers, `operator` and `auditor`. One composite capability, `ops:triage_backlog`, declares two children and reaches them through the host. `finance:refund_check` requires the operator-only tool, so the projection withholds it from the auditor by derivation (8.7), and the auditor's context therefore carries an announcement naming one withheld group and a count of two (9.4). The auditor's provenance artifact records that withholding with its ground, `expose_to` on one entry and `children_withheld_from_caller` on the other (14.3). A request the auditor cannot serve from the entry tier reaches a refusal; the host declines the refusal because no search has run, returns one observation, and the next step searches the auditor's full permitted set and finds nothing, at which point the refusal is accepted and is true (9.7, 9.9). Nothing in that sequence was written in the served text except the announcement, and the announcement was derived by difference.
