# Failure-replay acceptance

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

This instrument applies to the acceptance testing of an architecture whose
job is to hold declared structure — records, typed relations, identities,
change history — and answer queries about it. It replaces designer-authored
test scenarios with the replayed, documented failures of a real third-party
system.

Premises. The instrument is usable when four things exist:

1. A subject specification written precisely enough that a minimal
   implementation can be built from it without further design decisions
   being made silently.
2. A third-party system whose declaration surface is publicly documented,
   and whose failures are publicly recorded with citable sources
   (postmortems, issue trackers, changelogs, published defect analyses).
3. A minimal runnable implementation of the subject specification —
   throwaway by discipline, built only to make the specification
   executable.
4. Three separated roles: a porter, an examiner, and an adjudicator. The
   roles may be filled by people or by model agents; what matters is the
   isolation stated in clause 4.3.

## 2. The problem this instrument addresses (informative)

An architecture validated only against scenarios its own designer wrote has
been examined by the mind that produced it. The scenarios inherit the
design's blind spots: what the designer did not think to model, the designer
also did not think to test. Success-rate summaries deepen the problem — a
system can score well while failing dishonestly, reporting coverage it does
not have, and no self-authored scenario is likely to probe for that.

Real systems accumulate the opposite kind of evidence for free. Their
postmortems and defect records are failure descriptions written with no
knowledge of the architecture under test, dated, cited, and paid for in
production. Replaying them against a candidate architecture asks the only
question that matters at acceptance time: would the information this design
holds have made these recorded failures visible — and where it would not,
does the design say so honestly?

The instrument's verdict scale is built around that last clause. An
architecture that cannot detect a class of failure and says so truthfully
passes; an architecture that presents undetected territory as covered fails
at the highest severity, above silence.

## 3. Terms and definitions

**subject specification** — the architecture document under acceptance.

**declaration surface** — the set of authored, load-bearing artifacts a
system reads to configure its own behavior: configuration entries, prompt or
template text, interface descriptions, binding tables.

**ported surface** — the third-party system's declaration surface
transcribed into the subject specification's declaration format.

**porter** — the role that produces the ported surface by mechanical
transcription from the third-party system's public documentation.

**judgment item** — a porter's logged record of any mapping decision that
was not mechanical: a concept with no home, information flattened or
dropped, a choice between two plausible encodings.

**replay case** — one documented failure of the third-party system,
reconstructed as events against the ported surface.

**scenario fixture** — declaration material added by the examiner to make a
replay case concrete where the ported surface lacks an instance; fixtures
extend the ported surface and never modify it.

**scope self-report** — a machine-produced statement attached to a query
result naming what the query did and did not traverse.

**silent miss** — a replayed failure that enters the system and is surfaced
by no query, with no self-report naming the blindness.

**false pass** — a replayed failure over which a query presents an
affirmative claim of coverage or health that a reasonable consumer would
read as "verified", while the failure is present.

## 4. The instrument

4.1 The third-party system MUST be selected for the quality of its public
failure record, not for its resemblance to the subject specification. Every
replay case MUST carry a citation to a dated public source. [E: run once
against an external system meeting the premises of section 1; 13 replay
cases assembled, each cited in the acceptance record — 6 from the subject
system's own published records, 7 from a second system's recorded
incidents.]

4.2 The porter MUST transcribe the declaration surface mechanically from the
third-party system's public documentation, MUST log every non-mechanical
decision as a judgment item, and MUST list surface that was not ported with
the reason. An honest gap list is worth more than forced coverage. [E: 86
declaration units ported; 13 judgment items; one concept absent from the
subject vocabulary was expressible as declared data with no change to the
subject specification — itself an acceptance datum for the specification's
extension mechanism.]

4.3 The porter MUST NOT be told which failures will be replayed. The
examiner MUST NOT amend the ported surface; a defect found in it during
examination is a finding about the porting or the specification, never a
thing to fix in place. This isolation exists so the corpus cannot be shaped,
consciously or not, toward catching the known failures. [DI: the isolation
is argued from the shape of the incentive; no controlled comparison of
isolated versus non-isolated porting has been run.]

4.4 Each replay case MUST be reconstructed as events against the ported
surface, and the queries the subject specification claims as its capability
surface MUST be run and transcribed verbatim into the examination record.
[E: all 13 cases in the reference run were reconstructed as events and
their query outputs transcribed verbatim into the examination record.]

4.5 Every replay case MUST receive exactly one verdict from this scale:

| Tier | Meaning | Verdict |
|---|---|---|
| 1 | the failure cannot enter: refused at admission or validation | pass |
| 2 | surfaced by a query, with machine-carried evidence | pass |
| 3 | honest degradation: affected capability withheld and announced, the rest serves | pass |
| 4 | not caught, and the scope self-report truthfully says this class is out of reach | pass |
| 5a | silent miss | fail |
| 5b | false pass | fail, ranked worse than 5a |

[E: applied across the reference run's 13 cases, each receiving exactly one
adjudicated verdict — five passes (two tier 1, three tier 4), one
unreplayable case recorded as a finding per 4.7, seven fails (one 5b, six
5a), five of the fails closable by consumer declarations per 4.8.]

4.6 Tier 4 credit MUST attach only to machine-produced self-reports. A
side document written by a person — however diligent — is not a scope
self-report; from the system's own query surface the case is a silent miss.
[E: three replay cases in the reference run turned on exactly this
distinction and were adjudicated tier 4 only where the disclaimer was a
property of the query result.]

4.7 A documented failure that cannot be reconstructed as events at all MUST
be recorded as a modeling finding against the subject specification
("unreplayable"), not dropped. [E: one of thirteen cases; adjudication
traced it to machinery deliberately outside the specification's scope,
which the specification was then required to state.]

4.8 A replay case MAY be run in two variants — as ported, and with a
scenario fixture representing declarations a consumer could plausibly add.
Both verdicts MUST be reported; the fixture variant MUST NOT replace the
as-ported verdict. [E: five of thirteen cases failed as ported and passed
with a declared fixture; the pattern — mechanism present, declaration
absent — became the run's headline finding and forced a contractual
statement of each capability's declaration preconditions.]

4.9 An adjudicator distinct from the examiner MUST assign final tiers,
record reasoning for every borderline case, and MUST be bound by the
verdict scale's definitions rather than by sympathy for the design. [E: the
reference run's examiner marked five cases as borderline with candidate
tiers; the adjudicator ruled each with recorded reasoning, twice against
the more design-favorable candidate.]

4.10 Every specification change forced by the examination MUST be recorded
as an explicit delta list, and the delta list MUST enter the acceptance
record. An acceptance run that forces no changes should raise suspicion of
the run, not confidence in the design. [E: the reference run forced
thirteen deltas, including two specification defects in capabilities the
design had claimed and one amended contract sentence.]

4.11 After the deltas are applied, the full case suite MUST be re-run with
expected outcomes stated in advance, and an expectation that fails MUST be
reported plainly rather than bent to fit. [E: the reference regression
confirmed every fix but one; the one honest red exposed a real expressive
limit of the specification's constraint mechanism, which was then recorded
with a named re-open trigger instead of being patched around.]

4.12 Cost MUST be measured on the ported surface and on synthetic corpora
at the specification's target scale, with thresholds and their consequences
stated before measurement. [E: reference run — sub-millisecond on the
ported surface; 10.67 ms at 10^3 synthetic units, 270 ms at 10^4; neither
crossed its pre-stated threshold.]

4.13 The ported surface MUST NOT be redistributed unless the third-party
system's license permits it. Attribution resolves authorship; it does not
grant redistribution rights. The method loses nothing: describing the
porting process with source citations is sufficient for the acceptance
record, and readers can retrieve the public sources themselves. [DI:
follows from the shape of copyright licensing — a transcription is a
derivative of its source and inherits the source's terms; not itself a
measured result.]

## 5. Borrowed and original

**Borrowed.** Regression tests grown from recorded bug reports are standard
practice; this instrument generalizes the habit from code defects to
architecture acceptance. Role isolation between evidence-preparer and
evaluator follows the blind-analysis tradition in experimental science.
Grading refusal at load time as the strongest pass follows the long
static-checking tradition of preferring rejection to runtime discovery.
The three-way separation of pass kinds (caught / degraded / honestly
declared out of reach) is a restatement of fail-loud and
declared-boundary norms present in many engineering cultures.

**Original, as far as the gap statement below reaches.** Each element has
precedent on its own, and the claim is limited to this composition, not to
any element of it. The five-tier scale's
honesty ordering — a truthful "cannot see this" passes, an untruthful
"covered" fails above silence (5b worse than 5a). The porter-isolation rule
applied to corpus construction for architecture acceptance. The
"unreplayable is a finding" rule (4.7). The delta-list-as-evidence
requirement (4.10) with its inverted suspicion: an acceptance run that
changes nothing is evidence against the run.

## 6. Gap statement

Within a scope covering software-architecture evaluation and
agent-evaluation literature reachable by keyword search in August 2026
(searched: acceptance testing of architectures, failure injection,
postmortem-driven testing, replay testing, blind analysis in software
evaluation), no acceptance protocol of this shape — a third-party system's
declaration surface ported under porter isolation, its documented failures
replayed as events, verdicts graded on an honesty-ordered scale in which
truthful non-coverage passes and false coverage is the worst failure — was
found. Search was by keyword and is not exhaustive.
