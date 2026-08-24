# Espalier templates (informative)

Fill-in artifacts for adopting Espalier. Section and requirement numbers cite `SPEC.md`. Copy, fill, and delete the guidance lines; rows marked "(example from the reference implementation, replace)" are illustrations, not defaults. Per SPEC section 11, the reference implementation reached Level 1 in a day; expect days for larger codebases.

## T1. Layer-A map file skeleton (7.1, 7.2, 7.9)

```markdown
# System dependency map

Date: YYYY-MM-DD. Owner: <name>. Status: reviewed by owner on every change.

## 1. Layer A: system map (hand-written, small)

<ASCII or mermaid diagram, at or under 20 nodes>

Node membership (7.9; every measured layer-B component maps to exactly one node;
unassigned components go straight to the red list):

| Layer-A node | Measured components it comprises |
|---|---|
| platform-core | config, model, storage, identity |
| feature-modules | ingest, reporting |
| ...every layer-B component appears exactly once in this column... |

Arrow records (7.2; all eight fields per edge):

| # | From -> To | Type | Direction rule | Enforcer | Version (contract only) | Change discipline | Derivable? |
|---|---|---|---|---|---|---|---|
| A1 | client -> host | contract | client consumes, never the reverse | generated openapi.json | v1 | same-commit until codegen trigger | partially derived already (example from the reference implementation, replace) |
| A2 | host -> adjacent line | contract | port file implements the agreed shape | enforcer today is a version-constant anchor in the regression battery; the byte-level pin is memory-tier and sits on the register as a promotion candidate | 0.4 | version bump via cross-team agreement | no; it is the negotiated fact itself (example from the reference implementation, replace) |
| A3 | store -> engine | code | no import upward | none yet, memory-tier, register row 2 | none | owner sign-off | yes, convert via an import linter (honest day-one state; most first rows look like this) |

Explicit type absences (6.6; absence and emptiness are different facts):

- governance: <"no governance-type edges exist in this system" or the gate map>

## 2. Layer B: measured map (DERIVED <date>; regenerate with <command>, never hand-edit)

<generator output pasted or linked as CI artifact>

Overlays the import graph cannot see (hand annotations, typed):
- data: <who owns which store/table; name any second writer>
- governance: <which writes pass which gate, and the enforcing engine>
- temporal: <startup order and what checks it>
- contract: <pins and versions>

## 3. Red list (7.5; numbered; the diff between target and measurement)

| # | Finding | Type | Guarantee tier today | Destination | Tier after |
|---|---|---|---|---|---|
| R1 | ... | derivation violation | human memory | <a named, tracked change: issue/PR/work-item id, not a direction; entries with unnamed destinations are re-adjudicated at owner review> | structure |

## 4. Memory-tier register (4.3; every invariant nothing verifies)

| # | Invariant held only by memory | Promotion destination | Waiver (reason + trigger) |
|---|---|---|---|
| 1 | ... | <fill this column or the next; a row with both blank is nonconforming (4.3)> | |

## 5. Maintenance and metrics

- Layer A: hand-maintained here; every change owner-reviewed; an unrecorded system edge is a review-blocking defect (7.1).
- Layer B: regenerated per 7.7; hand edits forbidden (7.3).
- Every future design increment names which arrows it adds or converts (dependency -> derivation).
- Metric baselines (4.3, 5.5), re-recorded at each owner review:
  - memory-tier register rows: <n> (baseline <date>)
  - open derivation debt (derivation-violation red entries + unconverted derivable arrows): <n> (baseline <date>)
```

## T2. Module manifest, abstract schema (8.1 through 8.3)

Language-neutral field list, aligned with SPEC 8.2. Required fields carry no defaults; construction fails naming the module.

| Field | Obligation | Meaning |
|---|---|---|
| name | REQUIRED | stable module identity |
| depends_on | REQUIRED, even when empty | modules this one may use; feeds derived reverse graph and boundary-check config |
| surfaces | REQUIRED | capabilities exposed, each naming the set of consumer surfaces it is declared for, REQUIRED even when that set is empty (8.2, 9.1.4); feeds derived catalogs |
| state | REQUIRED, even when empty | stores/tables this module solely owns; feeds persistence composition |
| traces | RECOMMENDED | events/trace points emitted, named |
| contracts | RECOMMENDED | cross-seam pins: {name, version, custody} |
| waivers | OPTIONAL | recorded exceptions: {rule, reason, trigger} |

Python sketch (frozen dataclass; required fields have no defaults):

```python
@dataclass(frozen=True)
class ModuleManifest:
    name: str
    depends_on: tuple[str, ...]      # () is a declaration; omission is a TypeError
    surfaces: tuple[Surface, ...]    # each Surface names its declared consumer surfaces
    state: tuple[str, ...]
    traces: tuple[str, ...] = ()     # RECOMMENDED, not required (8.2)
    contracts: tuple[ContractPin, ...] = ()
    waivers: tuple[Waiver, ...] = ()
```

TypeScript sketch:

```ts
interface ModuleManifest {
  readonly name: string;
  readonly dependsOn: readonly string[];   // required; [] is a fact, undefined is a compile error
  readonly surfaces: readonly Surface[];
  readonly state: readonly string[];
  readonly traces?: readonly string[];     // recommended, not required (8.2)
  readonly contracts?: readonly ContractPin[];
  readonly waivers?: readonly Waiver[];
}
```

Assembly stays explicit (8.4):

```python
MOUNTS = [ingest.MANIFEST, reporting.MANIFEST]   # hand list
# CI sweep: every package under modules/ appears in MOUNTS, else red naming the module
```

## T3. Enforcer inventory (10.2, 10.4)

| Check id | Guards | Runs at | Source of the rule | Known blind spots (10.4) |
|---|---|---|---|---|
| importlinter:layers | code-type band direction | CI | layer-A map bands | dynamic imports invisible (example from the reference implementation, replace) |
| verify §NN | forgotten-mount sweep | CI | SPEC 8.4 | (example from the reference implementation, replace) |
| depcruise:boundaries | code-type bands | CI | layer-A map bands | require()-time tricks invisible (TS/JS parallel example, replace) |
| mounts.test.ts | forgotten-mount sweep | CI | SPEC 8.4 | (TS/JS parallel example, replace) |
| startup:manifest | required manifest fields | process start | SPEC 8.3 | prose quality of filled fields |
| engine:approval-gate | governance edges | runtime, always | SPEC 6.3 | (example from the reference implementation, replace) |
| meta:check-ids-live | every cited check id resolves to a live check | CI | SPEC 10.5 | none |

Rule 7 check: every rule in the project context file cites one of these ids or carries the tag `memory-tier` (10.1); the meta:check-ids-live row is what keeps this table honest (10.5).

## T4. Conformance checklist (SPEC section 11)

This checklist enumerates the requirements each level cites; SPEC section 11 is authoritative and this list must be regenerated when it changes. Regenerated for SPEC 1.0.0-draft.2, whose Level 3 list gained the sub-requirements of 9.1; draft.3 changed no requirement, so this list is unchanged and carries forward. A model-facing capability system is additionally assessed against `CAPABILITY_HOST.md` and `AGENT_DEBUG.md`, which carry their own level lists; this checklist covers the parent standard only.

Level 1, Mapped (MUST satisfy 4.1, 4.3, 6.1, 7.1, 7.2, 7.3, 7.5, 7.9):
- [ ] layer-A map exists, at or under 20 nodes, owner-reviewed (7.1)
- [ ] every arrow carries all eight arrow-record fields (7.2)
- [ ] every layer-B component assigned to exactly one layer-A node; unassigned = red-listed (7.9)
- [ ] layer-B generator runs; output marked derived, never hand-edited (7.3)
- [ ] every edge labeled with exactly one of the five types; absent types recorded explicitly (6.1, 6.6)
- [ ] red list materialized, numbered, every entry has a named tracked destination and target tier (7.5)
- [ ] every stated invariant has a recorded tier (4.1)
- [ ] memory-tier register exists; every row carries a promotion destination or a waiver (4.3)

Level 2, Checked (additionally MUST satisfy 6.2, 7.6, 8.1, 8.2, 8.3, 8.4, 10.1, 10.2, 10.5):
- [ ] code-type edges enforced by a static linter in CI (6.2)
- [ ] data-type: single-writer machine-checked for every owned store (6.2)
- [ ] temporal-type: startup self-check validates assembly order (6.2)
- [ ] governance-type: every mapped gate enforced in engine/middleware, never convention (6.3, conditional)
- [ ] contract-type: version-bump check on every pinned seam (6.2)
- [ ] ratchet active: new violations turn CI red; stock burns down; baseline shrinks only by explicit action (7.6)
- [ ] every module exports one manifest of static data (8.1) declaring the 8.2 field set (8.2)
- [ ] required manifest fields have no defaults; incomplete manifests fail naming the module (8.3)
- [ ] forgotten-mount sweep runs in CI (8.4)
- [ ] context file: every rule names its enforcer or is tagged memory-tier (10.1)
- [ ] enforcer inventory exists and is validated against the live check set (10.2)
- [ ] meta-check verifies every cited check id resolves to a live check (10.5)

Level 3, Derived (additionally MUST satisfy 5.2, 6.5, 9.1, 9.1.1 through 9.1.9, 9.2, 9.3, and the 8.5 MUST-derivations):
- [ ] reverse dependency graph computed from depends_on, never hand-written (5.2, 8.5)
- [ ] boundary-check config and mount-order self-check generated from manifests (8.5)
- [ ] every capability's declared surfaces derived from its single registration (9.1)
- [ ] the projection is derived at a named boundary, never per turn; the boundary is named where the projection is declared (9.1.1)
- [ ] the boundary-derived projection is materialized as an artifact a machine check can read, carrying the boundary, the caller, and a hash of the served text (9.1.1)
- [ ] acceptance test run: every turn of one served session attributes to a projection carrying the same recorded hash (9.1.1)
- [ ] every withholding is announced inside the served surface, as a derived count plus the withheld names or group names, never hand-written (9.1.2)
- [ ] the reachability of a withheld capability is guaranteed at the protocol: the host declines a refusal from a caller that has not searched, returns one observation, and continues (9.1.2)
- [ ] gate firings are recorded with request, position, and outcome, and that record is the conformance evidence (9.1.2)
- [ ] what a caller is served is computed per caller, not read from a second list (9.1.3, 9.2); where one caller class is served rather than distinguishable callers, that fact is recorded (9.1.3)
- [ ] each capability declares the set of consumer surfaces it is exposed on, and each of those surfaces is derived from that declaration (9.1.4, 8.2)
- [ ] the assembled context, the injected capability catalog, and the rendered tool list are treated as projections under this rule (9.1.5)
- [ ] the projection's inputs are the closed five (registry, policy, caller identity, entry declaration, budget), declared where the projection is declared, each with exactly one recording location (9.1.6)
- [ ] closure is demonstrated mechanically, not asserted (9.1.6)
- [ ] a surface deliberately not derived is recorded as an empty or narrowed surface set, never as an omission (9.1.7)
- [ ] no claim cites the 9.1 evidence as a completeness gain or as a difference in failure rate (9.1.8)
- [ ] where a model-facing capability surface exists, the claim is assessed against both companions at the mirrored level and names the version and level of each (9.1.9, 11.1)
- [ ] no parallel hand-maintained exposure tables (9.2)
- [ ] agent tool catalog generated from the same declaration the engine executes (9.3)
- [ ] contract-type consumers generated, or the generation trigger recorded in the arrow record (6.5)
- [ ] red list contains no derivation-violation entries (11.3); a declared, reachable withholding is not such an entry (9.4)

## T5. Layer-B generator (7.3)

Use the ecosystem tool first: `dependency-cruiser` (JS/TS), `pydeps` or `import-linter`'s graph (Python), `jdeps` or ArchUnit (Java), `go list -deps` (Go). The sketch below is a zero-dependency fallback for Python packages; verify its output against a handful of files you know before trusting it, and adapt it to your import idiom (assumption: one package, module granularity = top-level name under the scanned root).

```python
# Layer-B generator: the measured module import graph.
# Reverse edges are computed below, never written by hand (rule 4).
import ast, io, os
ROOT = "src/yourpackage"   # package directory to scan
PKG = "yourpackage"        # the package's own import prefix, for absolute imports
mods = {}
for dirpath, _dirs, files in os.walk(ROOT):
    for f in sorted(files):
        if not f.endswith(".py") or f == "__init__.py":
            continue
        path = os.path.join(dirpath, f)
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")[:-3].split("/")[0]
        tree = ast.parse(io.open(path, encoding="utf-8").read())
        deps = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level >= 1:                      # from . import a, b / from ..x import y
                    if node.module:
                        deps.add(node.module.split(".")[0])
                    else:
                        deps.update(a.name for a in node.names)
                elif (node.module or "").split(".")[0] == PKG:   # from yourpackage.store import x
                    parts = node.module.split(".")
                    if len(parts) > 1:
                        deps.add(parts[1])
            elif isinstance(node, ast.Import):           # import yourpackage.store
                for a in node.names:
                    parts = a.name.split(".")
                    if parts[0] == PKG and len(parts) > 1:
                        deps.add(parts[1])
        mods.setdefault(rel, set()).update(d for d in deps if d != rel)
for k in sorted(mods):
    print(k, "->", ", ".join(sorted(mods[k])) or "-")
rev = {}
for k, v in mods.items():
    for d in v:
        rev.setdefault(d, []).append(k)
for k in sorted(rev, key=lambda x: -len(rev[x])):
    print(k, "<-", ", ".join(sorted(rev[k])))
```

The tool does not matter; the discipline (derived, never hand-edited, regenerated per 7.7) does. Note that the reverse edges in the second block are computed from the forward scan rather than maintained separately: a hand-written reverse list is a second home for one fact, which rule 2 forbids and rule 4 exists to prevent.

## T6. Adoption runbook (SPEC section 12)

First pass, existing codebase:

1. Measure layer B with the ecosystem tool or the T5 fallback. Verify the output against files you know. Do not fix anything yet.
2. Write layer A from T1 against the measurement, not from recollection. Keep it at or under 20 nodes.
3. Declare membership (7.9): assign every measured component to exactly one layer-A node. Components you cannot place are your first red-list findings.
4. Label every edge with one of the five types; add the data/governance/temporal overlays the import graph cannot see; record explicit absences for types with no edges (6.6).
5. Diff intent against measurement. Number the violations; give each a named, tracked destination. That is the red list, and it is the backlog in priority order.
6. Build the memory-tier register by asking, for each module, the five type questions: who may import this; who else writes its state; what shape does it promise across each seam; what must exist before it starts; which of its writes pass which gate. Every answer nothing currently checks is a register row; fill its promotion destination or waiver (4.3). This bounds the register: modules times five questions, not an open-ended enumeration.
7. Record the two metric baselines (register rows; open derivation debt) in the map file (4.3, 5.5).

You are now at Level 1 (the reference implementation did this pass in a day; larger codebases take days). Level 2 is wiring the checks (linter, manifests, sweep, inventory, meta-check); take it module by module along the red list. Level 3 arrives derivation by derivation, each one deleting a hand table.
