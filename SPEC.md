# Espalier

The dependency map method: a structure-first engineering standard for codebases co-developed by humans and AI agents.

| | |
|---|---|
| Version | 1.0.0-draft.3 |
| Date | 2026-08-24 |
| Author | Yu-Chi TSOU (Liamour) |
| License | CC BY 4.0 |
| Status | Working Draft |
| Home | https://github.com/Liamour/Espalier |
| Feedback | https://github.com/Liamour/Espalier/issues |
| Companion documents | `RATIONALE.md` (related work and the origin account, informative; it carries none of the experimental evidence, which resolves through [STUDY-inf]), `TEMPLATES.md` (fill-in artifacts, informative), `CAPABILITY_HOST.md` and `AGENT_DEBUG.md` (normative within their scope, invoked by 9.1.9, listed in section 15) |

**Status of this document.** This is a Working Draft. It may be updated, replaced, or obsoleted at any time; cite it only as work in progress, by exact version. The author ratifies the transition from Working Draft to a release version; a release requires at least one implementation assessed at Level 2 against the frozen text.

**Status of this amendment.** Draft.3 changes no requirement. It corrects one informative sentence in `RATIONALE.md` that claimed a primary-fetched citation mark made re-verification unnecessary, a claim this document's own reference [11] falsified, and it adds the author's ORCID to the citation metadata. The draft identifier advances because section 14 advances it on any change, not only on a normative one; a Level assessment made against draft.2 stands against draft.3 without reassessment, because no requirement moved.

**Status of the previous amendment.** Draft.2 amends rule 9.1 and states it as nine numbered sub-requirements; amends 8.2, 9.4, 11.1 and 11.3; declares section 3 normative and adds the terms the amended rule turns on; adds the sub-requirements of 9.1 to the Level 3 enumeration in section 11; and adds two normative references. No section or requirement was renumbered. The Level 3 requirement list cites the same numbers it cited before, but Level 3 rises substantively: 9.1.1 and 9.1.2 bind through 9.1, so a Level 3 claim now carries a boundary-derived projection materialized as a readable artifact and, where the projection withholds, a derived announcement together with a host-side reachability gate. A Level 3 claim made against draft.1 is reassessed against draft.2 before it is restated. Section and requirement numbers are a coordinate system cited from outside this document, so an amendment adds sub-requirements under an existing number rather than renumber; extending a level's enumeration with numbers that already exist is not renumbering. The evidence base for the amendment is recorded in `CHANGELOG.md` and cited inline in 9.1.

## Abstract

Espalier is a methodology for keeping a software system's implemented structure true to its designed structure, under the specific pressure of the agent era: developers, human or AI, whose working context is ephemeral. Design documents customarily stop one level above the component; every relationship they leave unstated is improvised at implementation time, and improvised relationships are where coupling disasters begin. Espalier closes that last mile with seven rules: a guarantee ladder that ranks how invariants are held (structure over machine check over human memory), a strict separation of dependencies from derivations (declare once, derive everywhere), a five-type dependency taxonomy with per-type enforcement, a two-layer mapping discipline whose intent-versus-measured diff is the work list, a module manifest contract with fail-loud construction, a rule that registering a capability is the single act from which every surface declared for it is derived, including AI agent surfaces, while what any one caller is served is a projection computed from that single declaration rather than a second list, and a rule that every stated invariant names its machine enforcer. A three-level conformance model (Mapped, Checked, Derived) makes adoption incremental and claims testable.

## Conformance notation

The key words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, NOT RECOMMENDED, MAY, and OPTIONAL in this document are to be interpreted as described in BCP 14 [RFC2119] [RFC8174] when, and only when, they appear in all capitals, as shown here.

This conformance-notation section, section 3, sections 4 through 11, and the normative-references list in section 15 are normative; all other content, including the abstract and the annexes, is informative. Section 3 states definitions and contains no BCP 14 keyword, so its normative status binds the vocabulary the requirements are written in without adding a requirement of its own.

The capitalization discipline is load-bearing: because only all-capital keywords in normative sections carry requirements, a checker can mechanically enumerate every requirement in this document. Every requirement carries a number, and every BCP 14 keyword in a normative section sits inside a numbered requirement; a keyword in unnumbered prose is an editorial defect in this document. Two constructions are inside a numbered requirement without repeating its number: a lettered sub-clause belongs to the requirement that introduces it and is cited as such, and the level blocks of section 11 enumerate requirement numbers under the general obligation of 11.2 and add none of their own. The level-cited subset of that enumeration is the conformance checklist in `TEMPLATES.md` T4; requirements cited by no level are the conditional requirements of 11.3.

**Evidence marks.** A numbered requirement in this document may carry an evidence recitation: the experiment identifier and the result the obligation rests on. A recitation states what was measured and adds no obligation of its own; the obligation is carried by the BCP 14 keywords beside it, which is how a reader of a cited requirement tells which sentences bind. The phrase "Design inference, not yet measured" names an obligation that follows from a measured result or from the shape of a mechanism but was not itself tested. A paragraph or clause labelled informative, such as an economy note, states neither an obligation nor a measurement of one. The companion specifications draw the same distinctions with the bracketed tags `[E]`, `[DI]` and `[R]`, and a mark in either form carries the same meaning.

## 1. Scope

Espalier applies to software systems of module-level granularity: single-team monoliths, modular monoliths, and small service constellations. It is language-agnostic. It assumes nothing about runtime architecture and prescribes nothing about code style.

Espalier is written for the case where a significant share of implementation work is performed by AI agents operating with ephemeral context. It remains useful without agents; every rule predates them in some form. The agent case only removes the last excuse for the lowest rung of the ladder, because an agent that starts a fresh session retains nothing that was not written into structure, checks, or files it is directed to read.

Espalier governs structural facts: who may depend on whom, who owns what state, what shape crosses a seam, what must exist before what, and which writes pass which gate. It does not govern algorithmic correctness, testing strategy, or product design.

## 2. The problem (informative)

Two observations motivate the method.

First, the last mile. Architecture documents describe systems down to subsystems, then stop. The relationships below that line, which module imports which, which of two writers owns a table, whether a config value is read at startup or per request, are decided ad hoc by whoever implements next. Each such decision is invisible until it conflicts with another one. Systems do not usually die of a wrong grand design; they die of a thousand improvised relationships. This failure mode was the reported cause of death of the project that preceded this standard: coupling accumulated until every change broke something unrelated, and development stopped being economically viable (an owner account, not an audited postmortem; see RATIONALE section 5).

Second, the memory collapse. Traditional practice quietly leans on human memory: the senior engineer who remembers that the ledger has two writers, the convention that nobody imports upward. When developers are AI agents, that rung of the ladder drops to approximately zero retention. An invariant held only by memory is not weakened by agent development; it is deleted by it. The method's response is not to demand better memory but to move every guarantee up the ladder until memory holds nothing that matters.

## 3. Terms and definitions

**structural fact.** A statement of who depends on whom, who owns what state, what shape crosses a seam, what must exist before what, or which writes pass which gate.

**structural invariant.** A structural fact the system commits to keeping true.

**declaration.** A machine-readable statement of a structural fact, written in exactly one place.

**dependency.** Two artifacts that both exist and must be kept consistent by effort. Dependencies are where desync bugs breed.

**derivation.** An artifact generated from a declaration, with no independent existence. A derivation cannot silently drift: any divergence from its source is mechanical staleness, erased by regeneration, which 7.7 makes mandatory.

**enforcer.** The named mechanism that makes violating an invariant visible or impossible: a type system, a linter contract, a CI check, a startup self-check, a named section of a deterministic test battery.

**guarantee tier.** The rung of the ladder on which an invariant is held: structure, machine check, or human memory.

**layer-A map.** The hand-written, system-level intent map. Small, stable, owner-reviewed.

**layer-B map.** The machine-derived, component-level measured map. Regenerated, never hand-edited.

**red list.** The materialized diff between the layer-A target and the layer-B measurement: the numbered list of current violations, each with a destination.

**module.** The unit of code ownership and mapping: a package or directory subtree with a single owner and declared state.

**manifest.** The module's single static declaration of identity, dependencies, capability surfaces, owned state, emitted traces, and contract pins.

**capability surface.** Any point where a module's function is consumed: HTTP routes, UI forms, agent tool catalogs, read models, exported functions. **consumer surface** is a synonym, used where the emphasis is on the consumer rather than on the module; the two terms denote the same set and this document does not distinguish them.

**served surface.** A capability surface whose consumption is the delivery of a projection to a caller: an assembled context window, a rendered capability catalog, a rendered tool list, a per-caller read model. Every served surface is a capability surface; not every capability surface is served, because a surface consumed by code rather than by a caller carries no projection.

**capability.** One declared unit of what a module can do, addressed by name, indexed on the surfaces declared for it and dispatched by the module that declares it.

**registry.** The set of every capability declaration the system mounted, unfiltered by any caller or policy.

**caller.** The principal a projection is computed for: a role, a session identity, a human user, or an agent. Caller identity is the principal's own identifier, distinct from the policy that decides what that principal may see.

**policy.** The declared rules the host applies when it computes a projection: which registry entries a caller may be served, and the ordered rules served alongside them. Policy is a declaration set; caller identity selects which of its rules apply. Policy is compound, so its recording location names more than one field.

**entry declaration.** The declaration, made when a session or an assembly begins, of which part of the registry is served resident to that session, as distinct from the part left searchable.

**budget.** The declared quantity that bounds a projection's size: a disclosure limit, a context budget, or both. A budget is an input to the projection, never a run-time truncation.

**governed projection.** The derived, per-caller view of the registry that becomes a served surface, computed from the closed input set of 9.1.6. Exposure is the result of a projection, never a stored list.

**withholding.** The deliberate absence, from a served surface, of a capability the caller's policy permits, computed from declarations rather than produced by omission.

**group.** A declared grouping of capabilities, used as the unit an announcement names where naming individual withheld capabilities would be too long to serve.

**announcement.** The served line that states a withholding occurred, carrying a count and the withheld names or group names, both derived from the projection that withheld them.

**reachability gate.** A host-side protocol rule that makes a withheld capability reachable independently of served text, by refusing a refusal from a caller that has not searched the withheld set.

**assembly point.** The single place where the system reads manifests and constructs its modules and surfaces, whether that place is reached at process start, at host construction, or at session assembly. **session mount** is the assembly point of one served session: the boundary at which that session's projection is derived. A **declared boundary** is either, and it is the term the companion specifications call a mount.

**waiver.** A recorded, reasoned exception to a rule, carrying the reason and the trigger that ends it.

## 4. Rule 1: the guarantee ladder

Every structural invariant is held on exactly one of three tiers.

**Structure.** The violation cannot be expressed. The type system rejects it, the artifact is generated so divergence has nowhere to live, the ownership model provides no second writer.

**Machine check.** The violation can be expressed, but expressing it turns a machine signal red before it merges or before the system starts: a linter contract, a CI job, a startup self-check.

**Human memory.** A person, or an agent session, must remember. This includes documentation that nothing verifies, conventions, and review vigilance.

Requirements:

- **4.1** Every structural invariant stated in the layer-A map, the module manifests, the project's context files, or the memory-tier register MUST be assigned a tier, recorded where the invariant is stated. The obligation is bounded to stated invariants; the elicitation prompts of `TEMPLATES.md` T6 exist to make the stated set approach the true set.
- **4.2** Every invariant held below the structure tier MUST either be promoted to a higher tier or carry a waiver naming the reason (disproportionate cost is a valid reason, and it must be written down) and the trigger for revisiting.
- **4.3** All memory-tier invariants MUST be enumerated in a single memory-tier register. The register SHOULD be derived by mechanical extraction of the tier tags recorded under 4.1, of which the context-file tags of 10.1 are one instance, not maintained as an independent copy; a hand-maintained register is itself a hand-synchronized pair and counts against the 5.5 metric. Each entry MUST carry either a promotion destination or a 4.2 waiver. The register's row count is the project's structural risk metric; its baseline and each subsequent reading MUST be recorded at owner review.
- **4.4** Under agent development, a memory-tier invariant MUST be treated as a defect scheduled for promotion, not an accepted risk: new register entries after the baseline MUST be flagged at owner review the same way new red-list findings are. The framing is informative but exact: an agent session retains approximately nothing it was not directed to read.
- **4.5** Under agent development, machine checks SHOULD also run inside the developing agent's own iteration loop, as a locally runnable command named in the context file, not only in post-merge CI. A check the agent sees while working is a correction; a check that fires after the pull request is an autopsy.

## 5. Rule 2: dependency versus derivation

- **5.1** Every structural fact MUST have exactly one authoritative declaration site. A fact stated in two places is two facts that will diverge.
- **5.2** Reverse relations (who depends on me, who consumes this) MUST always be computed from forward declarations, never written by hand.
- **5.3** Every dependency edge recorded on the layer-A map MUST answer the question: why is this not a derivation. An edge with no answer is a conversion candidate and SHOULD be red-listed.
- **5.4** Derived artifacts MUST carry a generated-file marker and the regeneration command. Hand-editing a derived artifact is a defect, not a shortcut.
- **5.5** Design reviews SHOULD apply conversion pressure: each cycle, dependencies whose source of truth is clear are converted into derivations. The conversion metric is defined operationally: the count of open red-list entries typed as derivation violations, plus layer-A arrows whose derivable answer is yes but which are not yet converted. Its baseline and each reading MUST be recorded at owner review, and it should fall.
- **5.6** The derivation mandate applies to declared facts and measured substrates, not to intent. The layer-A map is deliberately hand-written (7.1). The declarations a boundary check enforces (bands, allowed directions, `depends_on`) are hand-written intent; the check configuration compiled from them is a derivation (8.5). The method derives consumers from declarations; it does not attempt to derive the declarations themselves.

## 6. Rule 3: the five dependency types

One picture that mixes dependency types is how maps rot. Each type has its own enforcement.

| Type | Meaning | Minimum enforcer | Canonical failure smell |
|---|---|---|---|
| code | who may import or link whom | static import linter, CI-red | upward import, sibling reach-around |
| data | who owns state, who may only read | ownership declared in the manifest state field, plus a static check that only the declared owner references the store's write path, or a runtime write guard where static analysis cannot see the access | two writers, orphan table |
| contract | promised shape across a seam, versioned | version constant plus pin; consumer generation at higher levels | silent shape drift, hand-mirrored types |
| temporal | what must exist before what | explicit assembly order plus startup self-check | works-on-my-boot ordering luck |
| governance | which writes pass which gate | engine or middleware enforcement, never convention | a write path that bypasses the gate |

- **6.1** Every edge MUST be labeled with exactly one primary type; an unlabeled or mixed-type map does not conform.
- **6.2** Each type MUST be enforced by a mechanism suited to that type; a code-type linter does not discharge a data-type obligation.
- **6.3** Governance-type edges MUST be enforced in the executing engine or middleware. Convention and documentation are non-mechanisms for governance.
- **6.4** Contract-type declarations SHOULD carry their own evolution rules: which changes are compatible and what a version bump means, enforced by the same mechanism that consumes the declaration, so compatibility is checked where the contract lives rather than promised in a changelog.
- **6.5** Consumers of a contract-type declaration SHOULD be generated from it; where they are not, the generation trigger MUST be recorded in the arrow record.
- **6.6** A system MAY have zero edges of a given type. The layer-A map MUST record that absence explicitly, because absence and emptiness are different facts (8.2); the per-type obligations of that type are then satisfied vacuously, and the recorded absence is owner-reviewed like any layer-A fact.

## 7. Rule 4: the two-layer map and the red list

- **7.1** The layer-A map MUST be hand-written, SHOULD stay at or under twenty nodes, and MUST be reviewed by the system owner on every change. Adding a system edge without recording it is a review-blocking defect.
- **7.2** Every layer-A arrow MUST carry the arrow record: from, to, type, direction rule, enforcer, contract version where the type is contract, change discipline (the rule for how the edge may change: same-commit, version bump, owner sign-off), and the derivable-or-not answer of 5.3.
- **7.3** The layer-B map MUST be derived by tooling from code and declarations. Hand edits to layer B MUST NOT occur; a hand-maintained component map goes stale and is worse than none, because it is trusted.
- **7.4** Target structure (bands, layers, allowed directions) is hand-set as an architecture fact, but MUST be validated against the measured layer-B graph before enforcement lands. Hand-drawn bands are hypotheses until measured.
- **7.5** The diff between target and measurement MUST be materialized as a numbered red list. Each entry records the finding, its type, and its current guarantee tier; each entry MUST be given a destination (a named, tracked change, not a direction) and the tier it will land on. The diff adjudicates in both directions: an entry MAY resolve by amending layer A instead, when measurement proves the intent was drawn wrong, and that amendment is owner-reviewed like any layer-A change.
- **7.6** The red list MUST operate as a ratchet: the existing stock is enumerated at adoption and MUST NOT grow silently; a new violation MUST turn a machine signal red immediately. Stock is debt, flow is zero.
- **7.7** Layer B MUST be regenerated before any change to the layer-A map or the red list, and after any change to a module's imports, manifest, or mount list. It SHOULD be produced as a CI artifact so staleness is impossible.
- **7.8** Diff computation and enforcement policy are separable. The minimum conforming policy is diff-as-worklist; a system MAY escalate specific edge classes to automatic correction where the corrective action is itself derived and safe, keeping the diff engine unchanged.
- **7.9** Each layer-A node MUST declare its membership: the set of measured layer-B components it comprises. Every measured component MUST map to exactly one layer-A node; an unassigned component MUST be recorded as a red-list finding. Membership is what makes the 7.5 diff mechanical and the 7.4 validation a procedure, and it closes the trivial conformance of a map too coarse to say anything.

## 8. Rule 5: module manifests and fail-loud construction

- **8.1** Every module MUST export exactly one manifest. The manifest is static data interpreted by the assembly point, not executable registration code.
- **8.2** The manifest MUST declare: identity; dependencies on other modules (REQUIRED even when empty, because absence and emptiness are different facts); capability surfaces; and owned state (REQUIRED even when empty). The capability-surface declaration MUST name, per declared capability, the set of consumer surfaces that capability is exposed on, REQUIRED even when that set is empty; an empty set is a declared withholding from every surface and an absent set is an incomplete manifest (8.3). This per-capability set is the declaration the derivation check of 9.1 consumes. It SHOULD declare emitted traces or events and contract pins, and it MAY declare waivers.
- **8.3** Required manifest fields MUST have no defaults. An incomplete manifest MUST fail no later than construction or startup, naming the module; a compile-time or definition-time rejection satisfies this requirement at the structure tier. Half-configured modules do not start.
- **8.4** Assembly MUST be explicit: a mount list, not magic discovery. A machine sweep MUST detect modules present on disk but absent from the mount list, so that forgetting is caught by a check, not by a user.
- **8.5** From the manifests, the following MUST be derived: the reverse dependency graph, the boundary-check configuration for code-type enforcement, and the mount-order self-check. The following SHOULD be derived as the system grows into them: agent tool catalogs, UI form descriptors, state persistence composition, trace catalogs.

## 9. Rule 6: registration is the single declaration, exposure is a projection

- **9.1** Registering a capability MUST be the single act from which every surface declared for it is derived. Requirements 9.1.1 through 9.1.9 state that obligation in detail, chiefly for the case where a surface is served to a caller. Each of them is a requirement of 9.1: a claim that cites 9.1, including the Level 3 claim of section 11, MUST satisfy each of them wherever its subject exists, and section 11 enumerates them at Level 3 for the benefit of a mechanical checker. The sub-numbers run in the order the sub-requirements were adopted rather than in logical order, because numbers here are a coordinate system and are never reassigned; 9.1.3 states the base obligation that 9.1.1 and 9.1.2 qualify.

  Evidence for 9.1, refutation first. Deriving every served surface from one declaration did not produce a measured completeness advantage. In the method's controlled twin trial (exp-2: a derived capability host against a hand-wired twin of identical observable behavior, five streams per arm, fifteen sequential add, remove, and change tasks per stream, one developer model), the completeness family was not significant: state incompleteness p = 0.270, Cliff's d = 0.48; tasks fully complete p = 0.270; nothing in that family survived correction for multiplicity. Nor did the arms separate on whether a change failed loudly: loud task counts were 6, 0, 0, 0, 0 in the derived arm against 0, 0, 1, 0, 0 in the hand-wired arm, p = 1.000, Cliff's d = 0.04, and the derived arm's entire loud-task count belongs to the single stream the study's own audit excluded from confirmatory readings after finding that its session billed zero tokens and never ran. Read after that correction, the derived arm holds no surviving loud failure and the hand-wired arm holds the only one. What separated was propagation cost and what a failure left behind. Turns and edit sites were lower in the derived arm in every stream (complete separation, d = -1.00, on the order of one hundred fewer turns and fifty fewer edit sites per fifteen-task stream; p = 0.0079 each with all five derived streams, and p = 0.0159 each on the four streams that remain when the flagged stream is excluded, with complete separation and d = -1.00 holding under both), and streams that ended carrying a silently stale served surface were one of five in the derived arm against five of five in the hand-wired arm (Fisher exact p = 0.048, exploratory, constructed after seeing the data, and computed under the corrected reading of the run's instrument defect 8, in which the composed state expectation had frozen a served sentence that a later task falsified; under the instrument's original scoring the shape of the completeness family reverses, and neither reading reaches significance at five streams per arm). This rule rests on those two results, and on neither a completeness gain nor a difference in failure rate.

  - **9.1.1 Derive once, at a declared boundary.** The projection MUST be derived at a declared boundary as section 3 defines that term, and MUST NOT be recomputed per turn inside a served session. The boundary MUST be named where the projection is declared. The projection derived at the boundary MUST be materialized as an artifact a machine check can read, recording at least the boundary, the caller, and a hash of the served text; `AGENT_DEBUG.md` specifies that artifact and the queries it answers, and binds by normative reference under 9.1.9. The acceptance test for the prohibition is stated so that it is observable: every turn of one served session MUST attribute to a projection carrying the same recorded hash. A session whose turns attribute to two hashes has recomputed its projection between them and does not conform; a host that materializes no artifact has no hash to attribute to and does not conform either. A per-turn projection is not a contract: no artifact exists for a check to read, no two turns are guaranteed to have served the same set, and an observed behavior cannot be traced back to what the caller was shown. Evidence: a mount-scoped, caller-scoped provenance artifact attributed every served line on four frozen readings (16 of 16, 14 of 14, 17 of 17, and 15 of 15 non-empty lines) and classified seven single-edit differences into exactly their own classes with two silence controls holding, which is the checkability this requirement exists to preserve; a literal inlined at render time instead of declared was reported as unattributed and failed emission rather than being attributed to the nearest plausible declaration, which is what an undeclared input costs. The same mechanism reports a benign renderer format change as a block of unattributed rows and fails emission identically, so a nonzero emission is a finding to be triaged against the renderer before it is read as an undeclared input ([AGENT-DEBUG] 6.11). Design inference, not yet measured: that a per-turn projection degrades routing accuracy or run-to-run stability, and the same-hash acceptance test itself, which follows from the artifact's shape and was not run as an arm. The measured result is that a boundary-derived projection is completely attributable and diffable, on four frozen readings and seven diff classes; that a per-turn projection is not checkable follows from the definition of the artifact, and the per-turn alternative was not run as an arm.

  - **9.1.2 Withholding is a declaration, and reachability is a protocol guarantee.** Where a projection withholds a capability the caller's policy permits, two obligations hold. First, the withholding MUST be announced inside the served surface itself, as a derived count together with the withheld names or group names, derived from the same projection that withheld them and never hand-written. Second, the reachability of a withheld capability MUST be guaranteed by the host at the protocol layer, and MUST NOT rest on the served announcement alone. That obligation states a predicate rather than an aspiration, and the predicate is the measured one: the host MUST NOT accept a refusal from a caller that has not searched the withheld set on that request, and on declining a refusal it MUST return one observation and continue rather than terminate. [CAPABILITY-HOST] 9.7 states this predicate for the model-facing case and binds here by normative reference through 9.1.9. Every firing of the gate MUST be recorded with its request, its position in the exchange, and its outcome ([CAPABILITY-HOST] 9.11), and that firing record is the conformance evidence for this obligation; a host that asserts the guarantee and records no firings has produced no evidence either way. The announcement is necessary and insufficient, and necessity and insufficiency are the two halves that were measured; that the announcement be derived rather than hand-written was never manipulated in that experiment, and it rests on the twin trial's staleness result, in which hand-maintained served text is the arm that carried silent staleness, and otherwise on design inference, not yet measured. Necessity: removing the announcement from an otherwise byte-identical narrowed projection, with the search capability still rendered, dropped routing success on requests whose answer sat in a withheld group from 21 of 24 to 9 of 24, and added 8 confidently wrong routes on top of 4 additional false refusals (exp-3); that line measured 48 to 70 tokens and was the highest-yield text in the experiment. Insufficiency, which is a refutation and is stated as one: that a capability narrowed out stays reachable because the withholding is announced and search is available was a refutation condition declared before the run, and it was refuted on the flagship model. With the announcement served and read, that model false-refused one such request 3 times out of 3, deterministically, with zero searches, after reciting the withheld group names including the group that held the answer, scoring 9 of 12 against the full projection's 12 of 12 on that class (exp-3, condition C3 refuted). The generalization limit belongs with the refutation: the smaller of the two models tested never exhibited the failure, and the prediction that narrowing protects weaker models more was refuted with its direction reversed, on a design with no headroom on that model. The announcement is prompt text, which is the lowest rung of the guarantee ladder (section 4), and a model prior overrode it. The protocol fix: a fourth arm served a prompt byte-identical to the narrowed arm, verified by hash, differing only in that the host refused a refusal from a caller that had not searched, returning one observation and continuing; out-of-scope routing returned to 12 of 12, the gate fired 3 times in 72 requests and every firing ended on the correct capability, and it fired zero times on the 24 in-scope and 24 distractor requests, with average steps unchanged at 1.00 on both classes (exp-3). Known limits of the validated gate, which are part of this requirement and not footnotes: the predicate checks that a search occurred, not that it was relevant, so a perfunctory search followed by a refusal is uncovered; a zero false-refusal count in the gated arm is partly definitional, because an unsearched first-step refusal is unreachable by construction, and the non-definitional evidence is that the forced continuation produced the correct capability 3 times of 3; and the sample is one failing task unit and three firings, which is evidence that the arm stops false-refusing on this fixture, not an effect-size estimate. A conforming host therefore SHOULD strengthen the predicate so that a refusal is admissible only after a search that returned rows, and only when the refusal names what the search found and why it does not apply; the strengthened predicate is a design inference, not yet measured, and [CAPABILITY-HOST] 9.9 states it at the same strength. This requirement binds only where a projection withholds: a projection that withholds nothing satisfies it vacuously, and the fact that nothing is withheld is itself recorded, because absence and emptiness are different facts (6.6, 8.2). Economy note (informative): narrowing measured at the projection layer cut the served catalog to 30 to 33 percent of the full rendering on both models tested, while per-request billed tokens rose in the same harness, because the extra step re-paid a fixed context of which the served catalog was about 9 percent; the two halves are cited together or not at all.

  - **9.1.3 Registration is not exposure.** The registry holds every declaration. What any one caller is served MUST be a governed projection computed for that caller. A second list of what a caller may see, kept beside the registry, is the parallel exposure table 9.2 forbids; the prohibition is stated at 9.2 and is not restated here, because two statements of one rule are two facts that will diverge (5.1). Where a system serves one caller class rather than distinguishable callers, that fact MUST be recorded and the projection is the identity over the registry, which is how this requirement binds a documentation index or a form descriptor derived from manifests; absence and emptiness are different facts (6.6).

  - **9.1.4 The manifest carries the surface set the check reads.** For each declared capability, the manifest MUST declare the set of consumer surfaces that capability is exposed on (8.2), and every one of those surfaces MUST be derived from that declaration. Where the system possesses an agent tool catalog, a UI descriptor, or a documentation index, each is such a surface.

  - **9.1.5 The context window is a served surface.** An assembled system prompt, an injected capability catalog, and a rendered tool list MUST be treated as projections under this rule and carry every obligation it states. A host that treats its assembled context as authored text rather than as a projection has left its largest served surface outside every check it owns.

  - **9.1.6 The projection input set is closed and enumerable.** The inputs to a projection MUST be an enumerable closed set, declared where the projection is declared, and that set is exactly five: the registry, the policy, the caller identity, the entry declaration, and the budget. Each input MUST have exactly one declared recording location in the artifact of 9.1.1, so that an assessor reads each input in one place. A recording location MAY name more than one field where the input is itself compound, and no field may serve two inputs; a field an assessor must apportion between two inputs is not a recording location. Anything else that can change what a caller is served MUST be promoted into one of the five or recorded as a defect. The enumeration of five is fixed by this standard and is not extended by a host; closure is the per-host property that its concrete inputs all map onto the five, and Level 3 requires that closure be demonstrated mechanically rather than asserted. A projection that reads an undeclared input cannot be reproduced, and 9.1.1 cannot be checked against it. [CAPABILITY-HOST] 8.2 states the same five inputs for the model-facing case and states the checks that demonstrate closure.

  - **9.1.7 A withheld surface is withheld by declaration.** A surface deliberately not derived for a capability MUST be recorded as an empty or narrowed surface set on that capability's declaration, never as an omission; absence and emptiness are different facts (8.2).

  - **9.1.8 Honest citation of this rule's evidence.** A conformance claim MUST NOT cite the evidence recorded under 9.1 as a measured completeness gain, and MUST NOT cite it as a measured difference in how often a change fails. The measured results are the propagation-cost separation and the failure-mode split, and a claim MUST cite them as those.

  - **9.1.9 Companion specifications.** Where a system possesses a model-facing capability surface, a claim under 9.1 MUST be assessed against [CAPABILITY-HOST] for the capability unit, composition, namespacing, catalog and disclosure, the exposure projection, and context economy, and against [AGENT-DEBUG] for the provenance artifact of 9.1.1 and the three queries a host answers mechanically about a projection it served. Both are normative within their scope. Where a companion states a requirement on the same subject as this section, the companion is the specific statement and this rule the general one, and a companion never weakens a requirement of this section. Where the two companions state incompatible requirements on one subject, the governing document is the one whose scope owns that subject: [AGENT-DEBUG] governs the provenance artifact, its schema, its queries, and the classification of a difference between two artifacts; [CAPABILITY-HOST] governs the declaration, derivation, exposure, disclosure, and service of capabilities. A conflict outside those two scopes is a defect in both companions and is resolved against this section.

- **9.2** Parallel hand-maintained exposure tables MUST NOT exist. Where the same capability is described in an engine dispatch table, an agent prompt, and a frontend form registry, three memories hold one fact, and the agent goes blind the day one of them is forgotten.
- **9.3** The catalog an AI agent reads MUST be generated from the same declaration the engine executes. What the model believes and what the machine enforces share a source, so they cannot disagree.
- **9.4** Agent-facing surfaces are first-rank derivation targets, not documentation afterthoughts. A capability declared for a surface but unreachable on that surface MUST be recorded as a red-list finding where no declaration accounts for the absence. A withholding declared under 9.1.2 or 9.1.7, and reachable under the protocol guarantee of 9.1.2, accounts for the absence and MUST NOT be recorded as a finding; that is the difference between an omission and a declaration, and it is what keeps a conforming per-caller projection from red-listing itself at Level 3 (11.3). An absence with no declaration behind it remains a finding whether or not a caller's policy would have permitted the capability.

## 10. Rule 7: name the enforcer

- **10.1** Every rule stated in a context or constitution file (the file an agent or a new engineer reads first) MUST name its machine enforcer: the check id, the linter contract, the regression-suite section id. A rule that has none MUST be explicitly tagged as memory-tier, which by 4.3 places it on the register.
- **10.2** The project MUST maintain an enforcer inventory: which mechanism guards which invariant, and where it runs. The inventory SHOULD be validated against the live check set and MAY itself be derived.
- **10.3** A stated rule whose named enforcer does not exist or does not run MUST be treated as a defect of the same severity as the violation it fails to catch.
- **10.4** The enforcer inventory SHOULD record each enforcer's known blind spots: the class of violation it cannot see, and the scope it was never pointed at. Zero violations closes the named risk, not all risk; a clean check is a floor, not a ceiling.
- **10.5** A machine check MUST verify that every check id cited in context files and in the enforcer inventory resolves to a live, executed check. The rule about rules needing enforcers has this as its own enforcer.

## 11. Conformance levels

- **11.1** A conformance claim MUST name the claimed level, the version of this standard it was assessed against (section 14), the assessor, and the assessment date, and MUST be supported by evidence: at Level 1, the arrow-record enforcer fields (7.2) and the memory-tier register; at Level 2 and above, the enforcer inventory (10.2). A claim at a level that cites 9.1, covering a system that possesses a model-facing capability surface, MUST additionally be assessed against [CAPABILITY-HOST] at the mirrored level and against [AGENT-DEBUG] at the mirrored level, and MUST name the version and the claimed level of each; 9.1.9 binds the assessment, not the citation, so naming a companion version without assessing against it is not a claim under that companion. Below a level that cites 9.1 the companion assessment is not owed, and a claim MUST NOT name a companion version it was not assessed against.
- **11.2** A claim at a level MUST satisfy every requirement enumerated for that level and for all lower levels.
- **11.3** Requirements not enumerated by any level are conditional: each binds, at every level, wherever its subject exists (a derived artifact for 5.4, a governance edge for 6.3, an invariant below the structure tier for 4.2). A sub-requirement of a requirement a level enumerates counts as enumerated by that level and is not conditional: enumerating 9.1 at Level 3 enumerates 9.1.1 through 9.1.9 there, and enumerating no level for a parent leaves its sub-requirements conditional with it. A violation of a conditional requirement that is recorded on the red list or the memory-tier register with a destination does not defeat a claim at Level 1 or Level 2; an unrecorded violation does. At Level 3 the red list MUST NOT contain entries typed as derivation violations.

**Level 1, Mapped.** A Level 1 claim MUST satisfy: 4.1, 4.3, 6.1, 7.1, 7.2, 7.3, 7.5, 7.9. In prose: the layer-A map exists with complete arrow records and node membership, the layer-B generator runs, every edge is typed, the red list is materialized with destinations, and the memory-tier register exists. The reference implementation reached Level 1 in a day (Annex A); expect days for larger codebases. Level 1 is a mapping exercise, not a refactor.

**Level 2, Checked.** A Level 2 claim MUST additionally satisfy: 6.2, 7.6, 8.1, 8.2, 8.3, 8.4, 10.1, 10.2, 10.5. In prose: every type present is machine-enforced by a mechanism suited to it, manifests exist and fail loud, the forgotten-mount sweep and the live-check meta-check run, context files name enforcers, and the ratchet is active.

**Level 3, Derived.** A Level 3 claim MUST additionally satisfy: 5.2, 6.5, 9.1, 9.1.1, 9.1.2, 9.1.3, 9.1.4, 9.1.5, 9.1.6, 9.1.7, 9.1.8, 9.1.9, 9.2, 9.3, and the MUST-derivations of 8.5. In prose: reverse graphs are computed everywhere, registration is the single declaration from which every declared surface derives, agent surfaces included, what any one caller is served is a projection of that declaration, every served projection is derived once at a named boundary into an artifact a check can read, its input set is the closed five of 9.1.6 and is demonstrated closed, every withholding is declared and announced and reachable at the protocol, and contract consumers are generated or carry a recorded trigger. The sub-requirements of 9.1 are listed here so that the T4 checklist can be derived by enumeration; they would bind at Level 3 in any case under 11.3.

| Type | Level 1 | Level 2 | Level 3 |
|---|---|---|---|
| code | mapped and labeled (6.1) | import linter CI-red (6.2) | linter config derived from manifests (8.5) |
| data | owners recorded (7.2) | single-writer machine-checked (6.2) | persistence composed from state declarations, where adopted (8.5 SHOULD) |
| contract | pins recorded (7.2) | version-bump check (6.2) | consumers generated, or trigger recorded (6.5) |
| temporal | order documented (7.2) | startup self-check (6.2) | order derived from dependency declarations (8.5) |
| governance | gates mapped (7.2) | engine-enforced (6.3) | gate dispatch derived from the capability declarations the engine executes (9.3) |

A type with zero edges satisfies its row vacuously once the absence is recorded (6.6).

## 12. Adoption path (informative)

For an existing codebase: measure layer B first; write layer A against the measurement, not from recollection; assign every measured component to a layer-A node; label types; materialize the red list; turn on the ratchet; introduce manifests module by module; convert dependencies to derivations as truth sources become clear. The refactors fall out of the red list in priority order.

For a greenfield system: manifests and the layer-A map precede code. Every design increment names its module boundary and its seam before implementation, and names which arrows it adds or converts.

## 13. Limits and non-goals (informative)

**Not full automation.** The method mandates machine checking of human declarations, not machine discovery of intent. Full auto-discovery is rejected deliberately: explicit assembly with a forgotten-mount sweep keeps the human decision visible while catching the human error.

**Enforcement point is a scale decision.** At small scale, static CI enforcement dominates: it is debuggable, free at runtime, and sufficient when the module set is fixed per release. Runtime dependency injection, service registries, and event buses solve problems that appear with unknown third-party modules and hot reload, and buy nothing before that. The method is enforcement-point-agnostic in principle and static-first in practice.

**Deterministic enforcers are not exhaustive.** Judgment-heavy architectural concerns, boundary fidelity in meaning rather than imports, stale design assumptions, resist fixed rules. Advisory AI-judged checks are a recognized complementary tier; they remain advisory and outside conformance claims.

**Not a style guide.** Espalier governs structural facts. It has no opinion on naming, formatting, or paradigm.

**Single-repo focus.** Cross-repo seams are handled by contract-type edges under version custody discipline; the method does not attempt federated mapping.

## 14. Versioning of this standard

This standard versions under Semantic Versioning 2.0.0 [SEMVER-inf]. Changes to normative requirements bump major or minor; editorial changes bump patch. Pre-release drafts increment the draft identifier on any change and promise nothing about compatibility. Within a pre-release series the draft rule takes precedence: a normative change increments only the draft identifier, the release-number bump it would otherwise carry accumulates, and the accumulated bump is applied once at release. A claim therefore reads a normative change off the draft identifier and off the changelog entry for that draft, never off the release number, which is why a claim cites the exact version including its draft identifier. The changelog is `CHANGELOG.md`. A conformance claim cites the exact version it was assessed against.

The normative references of section 15 to [CAPABILITY-HOST] and [AGENT-DEBUG] are pinned to exact versions, and the pin advances by amendment of this document, never silently. A new version of a companion does not enter this standard until section 15 names it; until then a host assessed against the newer companion is assessed against a document this standard does not cite. When the pin advances, this standard bumps its own version by the same rule it applies to any normative change, and a claim already made stays valid against the version pair it named under 11.1. A claimant that wishes its claim to stand against the new pair reassesses and restates the claim; there is no automatic carry-forward, because a companion at Working Draft status promises nothing about compatibility.

## 15. References

Normative (this list is normative; see Conformance notation):

- [RFC2119] Bradner, S., "Key words for use in RFCs to Indicate Requirement Levels", BCP 14, RFC 2119, March 1997.
- [RFC8174] Leiba, B., "Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words", BCP 14, RFC 8174, May 2017.
- [CAPABILITY-HOST] "Capability hosts under Espalier", `CAPABILITY_HOST.md`, version 0.1.0-draft.1. Invoked by 9.1.6, 9.1.2 and 9.1.9. Normative for systems that possess model-facing capability surfaces; it specifies rule 9.1 for that case (capability unit, composition, namespacing, catalog and disclosure, exposure projection, context economy, mechanisms, conformance levels mirroring section 11). The version pin advances only by amendment of this document (section 14).
- [AGENT-DEBUG] "Agent debugging under derivation", `AGENT_DEBUG.md`, version 0.1.0-draft.1. Invoked by 9.1.1 and 9.1.9. Normative for systems that claim a served projection is debuggable; it specifies the provenance artifact required by 9.1.1, the classification of a difference between two artifacts, and the forward-slice, reverse-slice, and run-diff queries a conforming host answers mechanically. The version pin advances only by amendment of this document (section 14).

Informative:

- [SEMVER-inf] Preston-Werner, T., "Semantic Versioning 2.0.0", https://semver.org/spec/v2.0.0.html.
- Related-work references are collected in `RATIONALE.md`, which carries that citation list with per-source confidence marks. `RATIONALE.md` predates draft.2 and carries none of the experimental evidence cited in section 9; that evidence resolves through [STUDY-inf] and nowhere else.
- [STUDY-inf] The controlled study record behind every experiment identifier cited in section 9. Repository `dmm-study` (`github.com/Liamour/dmm-study`), snapshot commit `a98fa852647a79f7b61a132c9bf86094e225905a`, dated 2026-08-20. exp-2 is the two-arm twin trial of a derived host against a hand-wired twin, 10 streams and 150 subject sessions, 2026-08-19; its analysis of record is `data/main/ANALYSIS.md` and its per-session rows are `data/streams.jsonl`. exp-3 is the projection-narrowing test with its four arms, 240 routed requests, 2026-08-20; its analysis of record is `docs/EXPERIMENT3_NARROWING.md` and its per-cell rows are `narrowing/report.txt` and `narrowing/results.jsonl`. The mechanism validations, including the provenance artifact cited by 9.1.1, are `docs/MECHANISMS.md`, with the emitter and its tests at `mechanism/prompt_provenance.py` and `mechanism/test_provenance.py`. The design of record for the twins is `docs/EXPERIMENT2_DESIGN.md` and their shared observable contract is `docs/TWIN_CONTRACT.md`. Where the record is not reachable by an assessor, the figures quoted inline in section 9 are author-held and are not independently checkable; an assessor in that position treats them as the author's assertion and assesses conformance against the requirement text, which stands on its own.

## Annex A (informative): reference implementation

The first implementation is an internal company management system, built by a human owner directing AI agent sessions, which is the environment the method was forged in. Its shape today: a Python backend of about twenty-five flat modules around a graph single-source-of-truth, an approval governance engine, and an embedded agent, with the split into a module package designed and red-listed, not yet landed. Its layer-A map holds seven system edges; its layer-B generator is thirty lines of import scanning; the first measured map caught two banding errors in the hand-drawn target the same day it was written. Layer A, node membership, typed edges, and the red list were produced in one working day. Its red list held eight findings, two of them derivation violations, one being a single capability described in three parallel hand tables; all eight carry destinations. Its boundary-cut design derives the agent tool catalog and the UI form descriptors from the same registry the governance engine dispatches on, which is requirement 9.3 in designed shape. At this draft the reference implementation conforms at Level 1 (Mapped), self-assessed by its own author, with Level 2 and Level 3 mechanisms designed and red-listed rather than landed. The numbers in this annex are the authoritative statement of the origin story; RATIONALE section 1 cites them rather than restating them.

## Annex B (informative): why the ladder tightens in the agent era

An agent session ends and takes its context with it. What survives is what was written: into types, into checks, into files the next session is directed to read. The three rungs of the ladder are therefore not equal citizens that trade off against convenience; they are, respectively, permanent, permanent, and volatile. Practices that lean on the volatile rung, tribal knowledge, review vigilance, the senior engineer who remembers, degrade quietly as the share of agent-implemented change grows. The method's seven rules are each a way of moving a class of knowledge off the volatile rung. Rule 7 is the terminal case: the context file itself, the one artifact written specifically for the next session to read, must point at mechanisms rather than make promises, because a promise in a file nobody verifies is memory wearing a uniform.
