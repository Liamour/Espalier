# Espalier rationale and evidence base (informative)

Companion to `SPEC.md` 1.0.0-draft.4. This document is informative throughout; nothing here can be cited to satisfy or contest a conformance claim. It records where each rule comes from, what independent evidence supports it, what the method claims as its own, and where the evidence is thin.

Citation confidence marks: **[P]** primary source fetched and read directly; **[S]** secondary-mediated (search snippets, mirrors, or paraphrase; the underlying primary was unreachable or unparseable during research). The reference list in section 6 carries the authoritative mark per source; inline marks are echoes for reading convenience, and a combined inline mark such as [P/S] means the cited set mixes both. Both marks record how a source was reached during research; neither predicts whether the source supports the claim it is cited for. Reference [11] carried the [P] mark and was still wrong about its subject until it was corrected. A citation should therefore be checked on three separate questions, because the first two can pass while the third fails: does the work exist, is it attributed correctly, and does it support the sentence that cites it. All access dates 2026-08-18 unless a publication date is given.

## 1. Origin

The method was forged in one environment: an internal company management system, built by a human owner directing AI agent sessions, in three research-and-design rounds during 2026. Two facts of that environment shaped every rule.

First, the predecessor. An earlier system by the same owner was abandoned after accumulated coupling made change unsafe; the mandate that resulted is recorded in the successor's constitution as a one-clause design law: name the module boundary and the seam before writing code. This is an owner's account, not a published postmortem, and it is presented here as motivation, not evidence.

Second, the developers are agents. Every implementation session starts with empty context and ends by discarding it. The team observed directly that any invariant held by "the previous session knew this" was violated within days, and that the only durable carriers were structure, machine checks, and the files each session is directed to read. The guarantee ladder (rule 1) is that observation stated as law.

The method's first full application produced its own best evidence: the first machine-measured import graph of the reference system contradicted the hand-drawn target architecture; the divergences were corrected while enforcement was still in design. Hand-drawn bands are hypotheses until measured (rule 4, requirement 7.4) was written from that incident. The quantitative account of the reference implementation, including its red-list composition and its self-assessed conformance level, lives in SPEC Annex A, which is the authoritative statement; this section does not restate its numbers.

## 2. Evidence by rule

### Rule 1, the guarantee ladder

The ladder is not a metaphor; it is the observed historical ordering of mechanisms aimed at the same problem. At the top, Rust rejects a struct literal missing a required field at compile time (error E0063), the mainstream instance of Minsky's "make illegal states unrepresentable" [26][30] [P]. One rung down, Python dataclasses fail at class-definition time on default-ordering violations, and Pydantic v2 refuses construction of a model missing a required field [28][29] [P]. Next, Spring Boot's validated configuration binding fails process startup naming the offending property, the pattern for facts knowable only at deployment [31] [S]. At the bottom rung that still counts as a mechanism, Meyer's design-by-contract assertions and Shore's fail-fast fire at the violated call site at runtime [23][27] [S]. King's parse-don't-validate is the connective tissue: it converts a runtime check into a compile-time fact by making the check's proof live in the return type [25] [P].

Two independent corroborations. The fitness-function taxonomy of Building Evolutionary Architectures classifies architectural assessments along explicit dimensions (atomic or holistic, triggered or continual, automated or manual); even its manual category is a defined, executed assessment with a recorded outcome. The taxonomy contains no tier for unverified standing human memory, which is the rung the ladder orders last [7] [S]. And the Cordis/DeepSeek Harness team, holding a full runtime dependency-injection machinery, still added a CI-static check that declared plugin dependencies appear in the manifest, converging on the ladder from the opposite enforcement point [49] [P, preview].

The agent-era sharpening (4.4, 4.5) is corroborated by a 2025-2026 industry convergence: practitioner guidance that architecture checks must run inside the agent's own iteration loop to be corrective rather than forensic [47] [S], a practitioner site prescribing CI-enforced fitness functions specifically against AI-driven architecture drift [45] [S], industry analysis reporting that architectural debt accelerates under AI adoption and that quality feedback belongs in the engineering process rather than in periodic review [44] [P], and a preprint-tier academic finding that agent-generated code decays architecturally as a function of scale [42] [S].

### Rule 2, dependency versus derivation

The strongest industrial precedent is the schema-first ecosystem: one OpenAPI document mechanically produces 50+ client generators, 40+ server stubs, and documentation [19] [P]; one .proto file compiles into every target language, with compatibility rules enforced by the compiler [20] [P]; one Prisma schema derives the typed client and the SQL migrations [22] [P]; AsyncAPI does the same for event-driven seams [21] [P]. None of these ecosystems trusts a human to keep derived surfaces in sync, and the fan-out is the argument: no team can hand-sync that many surfaces.

The boundary-tool survey (section 3 below) adds a precision the first draft of this method lacked, now stated as 5.6: what is empirically derivable is the measured substrate and the declared facts (graphs, labels, catalogs); the hand-authored rule content, the intent, stays hand-written in every tool surveyed, and in this method too, by design.

### Rule 3, the five types

The survey result is blunt within its scope: every boundary-enforcement tool examined (ArchUnit, import-linter, dependency-cruiser, eslint-plugin-boundaries, Nx boundaries, Bazel visibility) enforces exactly one dependency type, code, and none generalizes to data, contract, temporal, or governance obligations [1]-[6] [P/S]. Per-type enforcers do exist in disjoint ecosystems: schema compilers enforce contract obligations [20], reconciliation engines enforce convergence over time [16]-[18], and policy-as-code engines (OPA/Gatekeeper, HashiCorp Sentinel, Kubernetes admission controllers) enforce write-gating [50] [S]. The taxonomy's contribution is not that per-type enforcement is unprecedented; it is naming all five as obligations of one map, with requirement 6.2 forbidding the conflation of one type's enforcer with another's.

Field evidence for keeping types separate: Shopify shipped one "privacy" check that did two jobs (encapsulation boundary and de facto API design), regretted the conflation, and removed it in Packwerk 3.0; the `packwerk-extensions` gem for Packwerk 3 now carries four narrower, independently togglable checkers, of which the privacy checker is the one extracted from Packwerk itself [10] [P] [11] [P]. Protobuf carrying its own evolution rules inside the schema motivated 6.4 [20] [P].

### Rule 4, the two-layer map and the red list

Terraform is the industrial prior art: hand-written configuration is intent, synchronized state plus live refresh is measurement, and `terraform plan` renders the diff as a directly actionable execution plan, the worklist itself [13] [S] [14][15] [P]. Kubernetes controllers generalize the diff into a standing loop; Flux reverts manual edits on the next reconciliation; ArgoCD exposes diff-detection and self-heal as separately named policies on one engine [16][17][18] [P]. Requirement 7.8 (computation and policy are separable; auto-correction is an optional escalation) is taken directly from that separation.

The ratchet (7.6) has a production lineage: Packwerk's `package_todo.yml` records existing violations so adoption needs no big-bang rewrite, and strict mode refuses new entries, promoting burn-down from courtesy to build gate [8][9] [P]. ArchUnit's FreezingArchRule and dependency-cruiser's known-violations baseline are the same pattern in two other ecosystems, but they differ on the ratchet discipline 7.6 requires: dependency-cruiser and Packwerk shrink the baseline only by explicit human action, while ArchUnit's default (`allowStoreUpdate=true`) shrinks it automatically as violations disappear [1] [P] [4] [P]. Requirement 7.6 follows the former; an ArchUnit adopter must set the flag to conform.

Two honest limits. The diff can indict the intent, not only the implementation: Shopify's hand-drawn domain boundaries diverged so far from measured runtime reality that layer A itself had to be redesigned [10] [P]; 7.5 was amended to allow that resolution. And the specific asymmetry this method prescribes, a deliberately small hand-written layer A against an exhaustive derived layer B, is not attested in the reconciliation-tooling survey; Terraform's config and state share one schema at different fidelity. Adjacent precedent exists in architecture-description practice: the C4 model hand-curates small upper-level diagrams while tooling in that lineage (Structurizr) derives lower-level views from a model [51] [S]. That practice shares the small-intent-map instinct but performs no measurement diff and carries no red list; the asymmetry as an enforced reconciliation discipline remains this method's own design choice, argued on reviewability: a seven-edge map is owner-reviewable, a 25-node adjacency is not.

### Rule 5, manifests and fail-loud construction

Construction-time required fields have three independent mainstream implementations: Rust struct literals (compile time), Python dataclasses (definition time), Pydantic required fields (construction time) [30][29][28] [P]. Refusing to start half-configured has the Spring Boot startup-validation precedent [31] [S] and a fresh convergent one: Cordis validates plugin config against schemas at load, "the plugin never starts half-configured" [49] [P, preview]. The reference implementation's designed manifest schema requires `depends_on` even when empty because absence and emptiness are different facts, an act of making the undeclared state unrepresentable.

Explicit mounting with a forgotten-mount sweep (8.4), rather than auto-discovery, is an owner-ruled tradeoff in the reference implementation: keep the human decision visible, catch the human error by machine.

### Rule 6, registration is exposure

The closest existing precedent operates one boundary out: generating MCP agent-tool definitions from an OpenAPI document, so the API spec is "the single source of truth" and the agent surface cannot drift from it [48] [P]. The method generalizes that from the external HTTP boundary to internal module manifests: the same registry the governance engine dispatches on generates the agent tool catalog and the UI form descriptors. The research pass found no publication describing that generalization (an absence-of-evidence result; see section 5). The motivating failure is concrete: in the reference system, one capability was described in three parallel hand tables (engine dispatch, agent prompt text, frontend form registry), and forgetting any one left the agent blind to a live feature.

### Rule 7, name the enforcer

Two converging sources. The DeepSeek Harness contributor law states rules with their enforcing script named inline, which the method's research round adjudicated as the one immediately copyable practice [49] [P, preview]. Independently, the standards-craft survey showed the same principle at document scale: WCAG's conformance is a numbered testable list, not prose [34] [P]; the OpenSSF Best Practices badge derives its level from an enumerated per-criterion checklist, partially tool-verified and mostly self-asserted with recorded justifications, an example of enumerable criteria rather than machine adjudication [37] [P]; and the negative example, the Twelve-Factor App, ships no conformance procedure: nothing in the document adjudicates a compliance claim, though individual factors are mechanically checkable [38] [P]. Requirement 10.4 (record each enforcer's blind spots) is the distilled Packwerk retrospective: a package with zero violations "may actually crash with name errors when its code is executed"; the check is a floor, not a ceiling [10] [P].

## 3. Related work positioning

| Neighbor | What it has | What it does not |
|---|---|---|
| Boundary linters (ArchUnit, import-linter, dependency-cruiser, eslint-boundaries, Nx, Bazel) [1]-[6] | code-type enforcement at CI/build; ratchet baselines; in Bazel's case structure-tier (unbuildable) | one dependency type only; rule content single-consumer; no agent surface; no governance |
| Packwerk and modular monolith practice [8]-[12] | production ratchet with todo file; strict mode; candid limits retrospective | code-type only; blind to non-static loading; no derivation beyond the check |
| Terraform / Kubernetes / GitOps [13]-[18] | two-map reconciliation at scale; diff-as-plan; policy separation; auto-correction | infrastructure domain; no module manifests; no agent consumers |
| Schema-first IDLs (OpenAPI, protobuf, AsyncAPI, Prisma) [19]-[22] | declare-once massive fan-out; evolution rules in the declaration | seam-local (one contract), not system-wide topology |
| Design-by-contract lineage (Meyer, King, Minsky, Shore, Pydantic, Rust) [23]-[31] | the ladder as historical fact; construction-time refusal | object/value granularity, not system structure |
| Policy-as-code (OPA/Gatekeeper, Sentinel, admission controllers) [50] | engine-enforced write gates, deny-by-default | no tie to module topology; no dependency-map integration; no agent surface |
| Architecture description (C4 model, Structurizr) [51] | small hand-curated upper diagrams; model-derived lower views | no measurement diff; no red list; no enforcement |
| Cordis / DeepSeek Harness [49] | runtime mirror of this method (inject/PENDING, Context registry, fail-loud config); convergent CI static check | derives nothing from its composition file beyond loading; no permission or governance boundary between plugins (inference from documented absence); five days old at review time |
| AGENTS.md convention [39] | industry-standard single hand-written context file per repo, 60k+ adopters, Linux Foundation stewardship | schema-free prose; nothing fails when it lies; no derivation |
| GitHub Spec Kit / spec-driven development [40] | declare-once at feature level (spec, then plan, then tasks) | feature altitude, not codebase topology; no dependency taxonomy |
| Context engineering guidance [41] | minimal high-signal context, progressive disclosure | treats context as scarce resource to manage, not as the lowest rung to evacuate |
| Standards craft (BCP 14, W3C, WCAG, SemVer, OpenSSF) [32]-[38] | the document shape this standard follows | not about software structure |
| Agentic fitness functions proposal [46] | AI-judged advisory tier for judgment-heavy rules | complementary to, not a substitute for, deterministic enforcers; acknowledged in SPEC 13 |

## 4. What this method claims as its own

Stated precisely, against the survey. All four claims are survey-scoped; see the blanket caveat in section 5.

1. **The five-type taxonomy unified on one map.** Surveyed boundary tooling solves only the code type; per-type enforcers for the others exist in disjoint ecosystems (section 2, rule 3). The claim is the unification: five typed obligations of a single map with non-interchangeable enforcers. Governance specifically is claimed as an edge type on the module dependency map; governance enforcement per se is well precedented in policy-as-code [50].
2. **The A-small/B-derived asymmetry as an enforced reconciliation discipline.** Not attested in the survey; nearest neighbor is C4/Structurizr diagramming practice, which lacks the diff, the red list, and enforcement [51]. Defended on reviewability, not on precedent.
3. **Registration-is-exposure generalized inward.** An extension of the OpenAPI-to-MCP pattern [48] from the external API boundary to internal module manifests and their agent tool catalogs. Positioned as an extension of an established pattern, not an invention.
4. **The synthesis itself.** Ladder, derivation discipline, taxonomy, two-layer map, fail-loud manifests, enforcer-naming, and a testable conformance model in one normative document. Each element has ancestors; the survey found no existing standard that composes them, and none written for the agent-developer case as its primary condition.

## 5. Threats to validity

- **Single reference implementation, small scale.** One Python modular monolith, one small team. Nothing here is demonstrated at 100-module or multi-team scale; the static-first stance (SPEC 13) is explicitly a scale-conditional judgment.
- **The origin story is testimony.** The predecessor project's death-by-coupling is an owner mandate, not an audited postmortem.
- **Conformance levels measure mechanism presence, not outcomes.** No metric links a level to reduced coupling or change-failure rate; the levels are construct-valid only as adoption milestones, not as health scores.
- **No inter-rater protocol exists.** The scope of "structural invariant" (4.1), "proportionate cost" (4.2), and the twenty-node bound (7.1) involve assessor judgment; conformance claims are self-assessed, and the reference implementation's claim is assessed by its own author. SPEC 11.1 mitigates only by making assessor and date part of the claim.
- **Preprint-tier academic backing.** The agent-era erosion finding [42] is an arXiv preprint; no peer-reviewed venue publication on agent-coding architecture erosion *specifically* was found as of 2026-08. [43] is peer-reviewed (TOSEM 2026) but is about technical debt broadly, not architecture erosion under agent coding, and is not cited for the erosion finding.
- **Secondary-sourced citations.** Items marked [S] were not read from their primary: the Meyer and Shore PDFs resisted machine extraction, and several domains blocked fetching during the research sessions (archunit.org, engineering.gusto.com, arxiv.org, github.blog among them; blocks were per-session and inconsistent, so some github.com documents were fetched successfully and retain [P]). A post-draft spot-check re-fetched the eight highest-load [P] citations directly ([10], [25], [30], [32], [34], [36], [39], [48]) and confirmed each supports the claim made from it.
- **Cordis/dsh shelf life.** The comparison repo was five days old at review time and reserves the right to repackage freely; every mechanism detail decays fast. Principles were borrowed, never code shapes or identifiers.
- **Novelty claims are absence-of-evidence.** All four claims in section 4 rest on structured search coverage, not a systematic literature review or an exhaustive tool census; each is falsifiable by a single counterexample and will be amended, not defended, when one surfaces.
- **Sample bias toward survivors.** The survey examined tools and practices that succeeded enough to document themselves; failed structure-first methodologies leave no searchable trace.

## 6. References

Informative; the confidence mark after each entry is authoritative for that source.

1. ArchUnit user guide, Freezing Arch Rules. https://www.archunit.org/userguide/html/000_Index.html [P] (default `allowStoreUpdate=true`; the store shrinks automatically unless the flag is set)
2. Import Linter contract types, v2.9 docs. https://import-linter.readthedocs.io/en/v2.9/contract_types/ [S]
3. dependency-cruiser CLI documentation (dot reporter, baseline). https://github.com/sverweij/dependency-cruiser/blob/main/doc/cli.md [P]
4. dependency-cruiser known-violations baseline. Same source as [3]. [P]
5. eslint-plugin-boundaries. https://github.com/javierbrea/eslint-plugin-boundaries [S]
6. Nx, Enforce module boundaries; Bazel, Visibility. https://nx.dev/docs/features/enforce-module-boundaries ; https://bazel.build/concepts/visibility [S]
7. Ford, Parsons, Kua. Building Evolutionary Architectures, O'Reilly 2017; fitness-function taxonomy per https://continuous-architecture.org/practices/fitness-functions/ [S]
8. Shopify Engineering, Enforcing Modularity in Rails Apps with Packwerk, 2020-09-23. https://shopify.engineering/enforcing-modularity-rails-apps-packwerk [P]
9. Packwerk USAGE.md (strict mode; "worked off over time"). https://github.com/Shopify/packwerk/blob/main/USAGE.md [P]
10. Shopify Engineering, A Packwerk Retrospective, 2024-01-26. https://shopify.engineering/a-packwerk-retrospective [P]
11. rubyatscale, packwerk-extensions: an extension gem for Packwerk 3, not a fork. https://github.com/rubyatscale/packwerk-extensions [P]
12. Babbel Engineering, Modularizing our Rails monolith with Packwerk, 2023-08-22. https://www.babbel.com/en/magazine/modularizing-our-rails-monolith-with-packwerk [P]
13. Terraform CLI, plan. https://developer.hashicorp.com/terraform/cli/commands/plan [S]
14. Terraform language, Purpose of State. https://developer.hashicorp.com/terraform/language/state/purpose [P]
15. Terraform tutorial, Manage resource drift. https://developer.hashicorp.com/terraform/tutorials/state/resource-drift [P]
16. Kubernetes documentation, Controllers. https://kubernetes.io/docs/concepts/architecture/controller/ [P]
17. Flux, Core Concepts. https://fluxcd.io/flux/concepts/ [P]
18. Argo CD, Automated Sync Policy. https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/ [P]
19. OpenAPI Generator. https://openapi-generator.tech/ [P]
20. Protocol Buffers, Overview. https://protobuf.dev/overview/ [P]
21. AsyncAPI Specification 3.0.0. https://www.asyncapi.com/docs/reference/specification/v3.0.0 [P]
22. Prisma, Prisma Schema Overview. https://www.prisma.io/docs/orm/prisma-schema/overview [P]
23. Meyer, B. Applying "Design by Contract". IEEE Computer 25(10), Oct 1992. https://se.inf.ethz.ch/~meyer/publications/computer/contract.pdf [S]
24. Design by contract, background synthesis. https://en.wikipedia.org/wiki/Design_by_contract [S]
25. King, A. Parse, Don't Validate, 2019-11-05. https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/ [P]
26. Minsky, Y. Effective ML Revisited (make illegal states unrepresentable, 2010 lecture). https://blog.janestreet.com/effective-ml-revisited/ [P]
27. Shore, J. Fail Fast. IEEE Software 21(5), Sept 2004. https://martinfowler.com/ieeeSoftware/failFast.pdf [S]
28. Pydantic v2, Fields (required, no default). https://docs.pydantic.dev/latest/concepts/fields/ [P]
29. Python documentation, dataclasses. https://docs.python.org/3/library/dataclasses.html [P]
30. Rust error code E0063. https://doc.rust-lang.org/error_codes/E0063.html [P]
31. Reflectoring, Validate Spring Boot Configuration Parameters at Startup, 2020-05-28. https://reflectoring.io/validate-spring-boot-configuration-parameters-at-startup/ [S]
32. RFC 2119 (1997); RFC 8174 (2017), BCP 14. https://www.rfc-editor.org/rfc/rfc2119.txt ; https://www.rfc-editor.org/rfc/rfc8174.html [P]
33. W3C Manual of Style (normative/informative sectioning); W3C normative-references policy. https://www.w3.org/2001/06/manual/ ; https://www.w3.org/2013/02/stdref [P]
34. WCAG 2.2, Conformance. https://www.w3.org/TR/WCAG22/#conformance-reqs [P]
35. Understanding WCAG (techniques are informative). https://www.w3.org/WAI/WCAG22/Understanding/intro [P]
36. Semantic Versioning 2.0.0. https://semver.org/spec/v2.0.0.html [P]
37. OpenSSF Best Practices badge criteria. https://www.bestpractices.dev/en/criteria [P]
38. The Twelve-Factor App. https://12factor.net/ [P]
39. AGENTS.md. https://agents.md/ [P]
40. GitHub Spec Kit, 2025-09-02. https://github.github.com/spec-kit/ [S]
41. Anthropic, Effective context engineering for AI agents, 2025-09-29. https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents [P]
42. arXiv 2605.02741, audit of LLM/agent-generated code architecture (2026-05). https://arxiv.org/abs/2605.02741 [S]
43. Multivocal review of LLM-assisted technical debt. ACM TOSEM (2026), DOI 10.1145/3820165; preprint arXiv:2606.14796. https://arxiv.org/abs/2606.14796 [S]
44. Werner Heijstek, Software Improvement Group, on architectural debt under AI adoption, 2026-05-21. https://www.softwareimprovementgroup.com/blog/architectural-debt-ai/ [P] (cited for the debt-acceleration premise only; the article makes no fitness-function prescription)
45. techdebt.guru, AI architecture drift, updated 2026-07-26. https://techdebt.guru/ai-architecture-drift/ [S]
46. InfoQ, Agentic Fitness Functions, 2026-08-17. https://www.infoq.com/articles/agentic-fitness-functions-evolutionary-architecture/ [S]
47. Factory.ai, Using linters to direct agents. https://factory.ai/news/using-linters-to-direct-agents [S]
48. Speakeasy, Generate MCP tools from OpenAPI. https://www.speakeasy.com/mcp/tool-design/generate-mcp-tools-from-openapi/ [P]
49. deepseek-ai/deepseek-harness (vendored Cordis), repo created 2026-08-13; mechanism review conducted 2026-08-18 against repo docs as primary sources. https://github.com/deepseek-ai/deepseek-harness [P, shelf-life caveat: developer preview, breaking changes reserved]
50. Open Policy Agent / Gatekeeper; HashiCorp Sentinel; Kubernetes admission controllers (policy-as-code category; named as related work, not individually surveyed this round). https://www.openpolicyagent.org/ [S]
51. Brown, S. The C4 model for visualising software architecture; Structurizr (category named as related work, not individually surveyed this round). https://c4model.com/ [S]
