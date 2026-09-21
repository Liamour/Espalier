# Substrate invariants and the judgment boundary

| | |
|---|---|
| Parent standard | `SPEC.md`, Espalier |
| Version | 0.1.0-draft.1 |
| Date | 2026-08-27 |
| Author | Yu-Chi TSOU (Liamour) |
| License | CC BY 4.0 |
| Status | Working Draft |
| Home | https://github.com/Liamour/Espalier |

Evidence marks: **[E]** measured, with the experiment and result named.
**[DI]** design inference, not yet measured, following from a measured result
or from the shape of the mechanism. **[R]** a claim that was refuted, stated
at full strength beside what replaced it. A claim carrying none of these
marks is a defect in this document.

## 1. Scope

This instrument applies to the design or evaluation of an information
substrate: a store that holds natural-language artifacts consumed by
software — prompts, instructions, interface descriptions, policies, notes —
as declared records with identities, typed relations, and change history,
and serves queries about them to a consuming host.

Premises. The instrument is usable when three things hold:

1. The natural-language artifacts are load-bearing: software reads them and
   behaves differently because of what they say.
2. The artifacts and the things they refer to (code, tools, other
   artifacts) change on independent schedules, so staleness and drift are
   live risks rather than theoretical ones.
3. The party operating the host needs to answer, after the fact, what was
   in force, where a text came from, and what a change touches.

The substrate is a passive store. Systems in which the store itself calls
models, runs loops, or approves actions are outside this instrument's scope
by clause 4.1.

## 2. The problem this instrument addresses (informative)

Load-bearing prose drifts. A tool is modified and the paragraph describing
it is not; a description is shortened and the routing that depended on its
wording silently changes; a fact is copied into two places and one copy is
corrected. The failure is rarely that no one cared — it is that once the
system is complex, no one can enumerate what a change touches, because the
dependencies live inside sentences.

Mechanical tracking helps exactly as far as declarations reach, and no
further: a dependency expressed in prose without a marker is invisible to
every possible mechanism. A substrate that ignores this boundary ends up
lying — reporting closures as complete when they cover only what was
declared, reporting content as covered when only its bytes were checked.
The invariants below therefore come in two kinds: structural invariants
that make the mechanical part trustworthy, and a judgment-boundary contract
that makes the non-mechanical part honest. The second kind is the one more
often missing.

## 3. Terms and definitions

**information substrate** — a store of natural-language blocks, their typed
relations, identities, and change history, serving queries; never an actor.

**block** — the one record type holding a text body with its identity,
relations, and annotations.

**declared edge** — a typed relation between two identified records,
authored or mechanically extracted from markers; the only dependencies a
substrate can see.

**content identity** — a digest computed from a record's canonical bytes
and identity-bearing fields, never from names, paths, or storage location.

**origin** — a typed recovery address stating where a text came from,
sufficient to retrieve it.

**ledger** — the append-only history of typed change records; the ground
truth.

**snapshot** — a validated fold of the ledger at a point; derived, sealed,
verifiable by one self-hash.

**recorded selection** — the per-consumption record of exactly what was
served: identities, versions, forms, binding outcomes, withheld items.

**closure** — the set of records reachable from a subject over declared
edges, with evidence per hop.

**scope self-report** — a machine-produced statement attached to a query
result naming what was and was not traversed.

**mechanism gap** — a capability the substrate lacks but could build:
answerable with more structure.

**judgment gap** — a capability requiring semantic understanding of prose;
no substrate can close it, and pretending otherwise is the worst failure.

**enablement condition** — the declarations a consumer must make before a
claimed capability is actually live.

## 4. The instrument

4.1 The substrate MUST NOT be an actor: no model calls, no loops, no
approval logic, no I/O inside its engines. Behavior belongs to consumers;
governance belongs to the host. [DI: from the shape of the separation —
every capability below is a property of held information, and an acting
store couples the information's trustworthiness to the actor's choices.]

4.2 The ground truth MUST be an append-only ledger of typed change records,
each carrying an opaque actor supplied by the host. A snapshot MUST be a
fold of the ledger; a serving record MUST be a recorded selection citing
the snapshot. None of the three may be conflated. [E: a minimal
implementation of this layering was built and property-tested — fold of a
prefix plus a suffix equals incremental fold from the prefix's snapshot —
and full fold with validation measured 10.67 ms at 10^3 records and 270 ms
at 10^4, within pre-stated thresholds.]

4.3 Identity MUST be content-derived under a declared canonicalization;
display names MUST NOT be matchable or identity-bearing. One digest form
MUST serve all subjects. [DI: from the mechanism — name-keyed binding plus
renaming is a documented drift class across production systems; a
content-derived identity cannot silently re-point.]

4.4 Every record MUST carry an origin, and addresses MUST be permanent:
retirement produces a resolvable tombstone with forwarding, never a hole.
This pair is what turns compaction from loss into recoverable reduction —
dropped text remains reachable by address. [E: in the reference acceptance
run, a record served in reduced form carried its recovery address into the
serving record, and the full text was retrieved by that address; the
guarantee initially failed for reduced-but-served content and the
specification had to be repaired — the gap was found by replay, not by
review.]

4.5 There MUST be exactly one text-bearing record type. Differences of role
— instruction, description, memory entry, external anchor — MUST be carried
by relations and annotations, and role classification MUST be derived from
relation participation, never authored. [E: the reference run held
configuration sections, tool descriptors, skill bodies, matcher entries,
and instruction files — 86 units of five roles — as one record type; one
concept absent from the shipped vocabulary was added as declared data with
no change to the record model.]

4.6 There MUST be exactly one reference shape. Pinning MUST be an edge
property, not a container type; edges crossing a versioning boundary pin by
content identity; group identity MUST be a derived fold over a declared
closure, with no stored composite. [DI: from the mechanism — every
additional reference shape multiplies every query and every validation;
the reference run required no second shape for any of its five roles.]

4.7 Every closure result MUST carry a scope self-report stating that it
covers declared edges only and that a dependency expressed in prose without
a marker cannot be detected by any mechanism. Tier-style credit for honesty
attaches only to this machine-carried report, never to side documents.
[E: in the reference acceptance run, three replayed real-world failures
fell outside declared edges and were adjudicated as passes solely because
the scope self-report truthfully named the blindness; a fourth, documented
only in a human-written porting log, was adjudicated a silent miss —
the distinction is load-bearing.]

4.8 Each judgment gap MUST have a fixed contract sentence, emitted verbatim
with the query results it qualifies: at minimum, undetectable prose
dependencies; description-truthfulness after edits; same-fact duplication
and contradiction between independently admitted texts; interference
between assembled neighbors; the runtime state of external bindings.
[E: one such sentence was amended after a replayed failure showed a query
answering truthfully about bytes while a reasonable consumer would read the
answer as "capability verified" — a true statement with a false
implicature, adjudicated as the worst failure class in the run.]

4.9 Every capability gap MUST be classified as mechanism or judgment.
Mechanism gaps are built or declared unbuilt; judgment gaps are stated in
the contract and MUST NOT be approximated silently. [DI: the classification
itself is a design act; its value follows from clause 4.8's measured case.]

4.10 Impact closures MUST NOT be pruned for cost. A cost optimization that
can under-report a closure endangers the substrate's primary answer and is
forbidden; cost is recovered by precomputation and caching of derived
indices, never by narrowing the answer. [E: the reference design removed a
hash-based early-cutoff optimization on these grounds; measured full
recomputation stayed within every pre-stated threshold at target scale.]

4.11 Failure direction MUST be declared data on relation kinds, not
control flow: self-integrity violations refuse; host-binding failures
withhold the affected declarations, announce the difference, and serve the
rest. [E: in the reference run, a binding broken by a rename withheld
exactly the dependent declaration while everything else served, with the
served-versus-declared difference computable from one record.]

4.12 Every claimed host capability MUST publish its enablement conditions:
the declarations a consumer must make before the capability is live. A
capability whose preconditions are unmet MUST be visible as unlit, never
silently absent. [E: five of thirteen replayed failures in the reference
run were catchable by the shipped mechanism and caught only when the
relevant declaration existed; the pattern forced the conditions table into
the specification's contract.]

4.13 Derived facts MUST NOT have constructors or stored identities — they
are query results. One exception is sanctioned: the snapshot's self-hash,
so that a consumer can open sealed state by verifying one value without
replay. [DI: from the mechanism — a stored derived fact can certify a state
that no longer holds, and its staleness is invisible because the store
still verifies.]

4.14 One concept MUST have one home. A concept expressible through two
mechanisms is a defect even when both mechanisms work; where two authoring
surfaces legitimately express the same declaration, the parser MUST
reconcile them into one record. [E: the reference run's corpus was refused
by its own validation over an edge declared through two surfaces until
reconciliation was specified. [R: the specification's own revision then
reintroduced the same defect — two annotation kinds duplicating existing
record fields — caught only by a targeted consistency review; the norm is
stated here at full strength precisely because its violation recurred
inside the process that created it.]]

## 5. Borrowed and original

**Borrowed.** Most of the structural half has long precedent, and the debt
is broad. Content-derived identity follows content-addressed storage (git,
Nix, Unison). The append-only ledger with derived views follows the
event-sourcing tradition; point-in-time and validity queries follow
bi-temporal database practice. Typed relations as data follow RDF and
property-graph modeling. The recorded selection follows the lockfile
tradition in dependency management; pinning across versioning boundaries
follows dependency integrity checking (checksum databases, semantic
integrity checks). Refuse-at-load follows the static-checking tradition;
withhold-and-announce follows graceful-degradation practice in distributed
systems. Fixed normative sentences follow the conformance language of
standards bodies. Derived-not-stored follows database view discipline.

**Original, as far as the gap statement below reaches.** Each element has
precedent on its own, and the claim is limited to this composition, not to
any element of it. The judgment
boundary as a first-class emitted contract — fixed sentences attached to
query results, stating per gap what no mechanism can answer (4.8), with
honesty credit bound to machine-carried reports only (4.7). Enablement
conditions as a published part of the capability contract, making
undeclared preconditions a visible unlit state rather than a silent absence
(4.12). The unpruned-closure rule as a stated priority of answer integrity
over cost (4.10). Origin-plus-address-permanence as the specific pair that
converts context compaction into recoverable reduction (4.4). The
one-concept-one-home rule with parser-level reconciliation and its
self-exposed violation record (4.14).

## 6. Gap statement

Within a scope covering prompt- and configuration-management systems,
content-addressed storage literature, event-sourcing practice, temporal
databases, and agent-framework documentation reachable by keyword search in
August 2026 (searched: prompt versioning, prompt dependency tracking,
impact analysis for natural-language artifacts, prose dependency graph,
scope self-reporting, honest degradation contract, capability
preconditions declaration), no substrate contract of this shape — machine
queries over declared prose structure paired with fixed, verbatim-emitted
statements of what cannot be answered, and per-capability declaration
preconditions — was found. Search was by keyword and is not exhaustive.
