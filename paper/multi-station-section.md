# Multi-station deployment

*Draft manuscript section — a claim source, not a submission file. Each claim
below is written to be lifted into the manuscript; the notes in brackets say
what backs it, so nothing is asserted here that the repository cannot
demonstrate.*

## The problem the architecture addresses

Laboratory data collection for a behavioral task rarely happens on one machine.
A study of any size runs several testing stations in parallel, and every
implementation that maintains a study-wide results file must decide what
happens when *n* copies of itself maintain *n* copies of that file.

The common answer is to leave it to the researcher: each machine accumulates
its own spreadsheet, and the files are concatenated at the end. This is not
merely tedious. Concatenation silently assumes the facts that most need
checking — that every machine ran the same design, that no participant
identifier was issued twice, that no session was copied twice during
collection, that every file scored under the same software version. None of
these assumptions is visible in the concatenated product, and each fails
quietly rather than loudly. A duplicated file appears as a genuine
observation; two stations running a mid-study configuration change appear as
one pooled sample; two participants who were both assigned `P014` become one
participant with an implausible number of trials.

The design problem, then, is not file management. It is that a multi-station
deployment generates a specific family of data-integrity failures, and the
default architecture makes every one of them silent.

## Design: detect what cannot be prevented

The instrument is offline by construction — a strict requirement of the
testing environments it targets, where machines sit on isolated networks under
institutional data-protection constraints. This rules out the obvious
remedies. No station can consult a central registry to learn that an
identifier is taken, and no station can discover that another machine is
running a different version of the study. Uniqueness cannot be *enforced* at
entry. It can only be *detected* afterwards.

The architecture therefore separates the failures it can prevent locally from
those it can only make visible later, and treats the second class as a
first-class deliverable rather than an error path.

**Prevented at the station.** A one-flag deployment switch (`standalone`)
travels inside the distributed study file rather than being a per-machine
preference — so every station of a study agrees by construction, and a machine
left un-toggled cannot silently keep writing a partial results file. When the
flag is on, stations stop maintaining the study-wide file and write only
per-session records; each station's folder remains independently complete and
archive-ready. A station label is required before a standalone session may
run, because unlabelled data is unattributable after the fact, and that is not
a recoverable error.

**Made detectable at assembly.** Each session record carries the station that
produced it, and each machine additionally persists a random installation
identifier. This is what lets two machines that a researcher accidentally
labelled identically be distinguished from one machine's legitimate data — a
distinction offline software cannot make at collection time and cannot recover
without the identifier. Similarly, each session carries a write-time stamp of
the software version and platform that scored it. Study-level provenance
records only the last software version to touch a folder, so without a
per-session stamp a study collected across machines that upgraded at different
times cannot be attributed session by session. The stamp is unbackfillable by
nature — engine version is a write-time fact — which is why it ships before
data collection rather than after.

**Reduced at the source, where that is possible without cost.** One hazard —
the same participant identifier issued independently on two stations — admits
a partial station-side remedy that does not depend on any station knowing what
the others have done. An optional per-study setting offers the operator a
generated identifier drawn uniformly from a nine-digit space, wide enough that
a collision within a pooled sample of realistic size (~0.055% at N = 1000) is
an anomaly worth investigating rather than an expected event. The design is
deliberately conservative in three respects. It is opt-in and never mandatory,
because the participant identifier is the researcher's external join key to
consent, payment, and screening records, and a forced random value would
destroy that role; the field therefore remains editable and manual entry
remains unconstrained. It is independent of the deployment flag, since
multi-station studies frequently distribute meaningful identifiers from a
central roster. And it does not replace detection: the generated value is
recorded with a per-session marker of whether the identifier was generated or
typed, which makes the assembly-time collision signal exact rather than
approximate — a collision between two *generated* identifiers is
near-impossible by chance and is reported distinctly from ordinary identifier
reuse. The same measure also defuses a reproducibility hazard: because the
balloon sequence is derived from the pair (study seed, participant
identifier), two participants sharing an identifier under a fixed seed would
otherwise receive identical sequences and would not constitute independent
observations. [Backed by: `TaskConfig.auto_participant_id`;
`app/src/run/participantId.ts`; the `id_source` field on the session envelope;
the `generated_id_collision` finding in the Hub; the seed-notice downgrade in
Study Setup. The 0.055% figure is a birthday-problem calculation over 9·10⁸
values at N = 1000, not a measured result — state it as such.]

**Non-destructive resolution.** Where a conflict is detected, the architecture
adds information rather than removing it. A participant identifier appearing
on two stations is never rewritten; an unambiguous composite key is added
alongside it, and the original is preserved as the researcher's external join
key to consent, payment, and screening records. Sessions are never dropped to
produce a tidier output.

## The ingestion report as the deliverable

Assembly is performed by a Data Hub, available both as an interface in the
application and as a command-line entry point over the identical core. It
takes the collected station folders as strictly read-only input and rebuilds
the study-wide outputs.

The governing constraint is that **the Hub never acts silently**: every
session is either included cleanly or its departure from that is itemized by
name in a report, graded into sessions held back pending resolution, sessions
pooled but flagged, and sessions ingested cleanly. The report is written
beside the data, always visible in the interface, and never a modal dialog to
be dismissed — it is the primary output of assembly, not a diagnostic
side-effect.

The behaviors it reports are graded by what is actually at stake. Two copies
of the same session collapse to one and are counted. Two *different* versions
of the same session are held back, because no rule for choosing between them
is defensible. A station running a genuinely different task — different hazard
curves, reward structure, conditions, or instruction language — is partitioned
into a separate output set rather than pooled, since pooling incomparable
tasks is the one failure worse than stopping; a station differing only in
seed, currency label, or file-format version is flagged and pooled. An
identifier reused across stations is pooled with a disambiguating key, and is
escalated to a loud warning when both sessions also ran under the same fixed
seed, because the two participants then saw *identical* balloon sequences and
the sessions are not independent observations. Files that are unreadable,
missing their raw event log, or missing their identity record are held back
individually; one damaged file never invalidates a run of two hundred good
ones. Assembly aborts for exactly one reason — the Hub cannot establish what
study it is looking at at all.

Rather than trusting stored scores, the Hub re-derives every session's metrics
from its raw event log. This is what makes the pooled dataset uniform in the
presence of version skew: the reconstruction is scored by one engine, and its
provenance truthfully names that engine. Stored scores are retained as a
verification signal, compared against the re-derivation and graded by the
per-session version stamp — a discrepancy under an *identical* engine version
is reported loudly as possible corruption, since identical software on
identical events must reproduce, while a discrepancy across versions is
expected drift and is noted quietly. Sessions predating the stamp are reported
as ungraded rather than assumed benign. This grading never changes what is
written; the re-derived value is always the value that lands.

## Validation: a verifiable claim and an illustrative artifact

The fidelity claim is stated in two tiers, and the distinction is deliberate.

**The verifiable claim is byte-identity.** In the clean single-station case,
reconstructing the study-wide outputs from per-session records alone reproduces
the file the live path wrote, byte for byte. This holds by construction rather
than by inspection: the Hub re-runs the live path's own scoring and row-building
code rather than a parallel implementation, so there is no second code path
available to drift. It is enforced as a continuous-integration gate. The test
generates both sides from the current code — the reference is produced by the
live write path at test time, never read from a stored file — so the gate
cannot silently degrade into a comparison against a stale expectation.

[Backed by: `tests/hub/test_hub_equivalence.py`, run on every CI build.]

**The illustrative artifact is the hazard suite.** The repository additionally
commits a small four-station study with one integrity problem planted in each
session — a duplicated session, two machines sharing a label, an identifier
reused across stations, a station left on a different currency, a station
administering the task in a different language, stored scores that disagree
with the events, files that never made it back from the field — together with
the reconstruction the Hub produced from it and the report it wrote. Each planted problem corresponds to exactly one asserted line in that
report, so a flag that stopped firing cannot be masked by another.

This artifact demonstrates rather than proves. Its role is that a reader can
open the committed report and see the never-silent property exercised against
a realistic set of failures, without installing anything. Both sample studies
are generated by a deterministic builder that reuses the production emission
path, and a drift test regenerates and byte-compares them, so what is committed
is always what the current code emits.

[Backed by: `tests/hub/test_hub_ingestion.py`, `docs/samples/`. State this as
illustrative; the byte-identity gate is the claim that carries evidential
weight.]

## Roadmap: scoring data from other BART implementations

A survey of deployed BART implementations found that several — including
Inquisit raw output, PsyToolkit, PEBL, and the community jsPsych plugin —
emit fixed schemas that collapse without loss onto a minimal per-balloon
record: participant identifier, balloon index, pump count, and an explosion
flag, with earnings and reaction times where available. That record is already
what the scoring engine consumes, and per-balloon pumps plus an explosion flag
is precisely the discriminator between formats that can be scored exactly and
formats that can only be passed through.

Because the reconstruction path was built to re-derive metrics from a minimal
ground-truth record and to emit through shared code, ingesting foreign data is
an adapter problem rather than an architectural one: foreign files map to the
interchange record, scoring and emission are unchanged, and station identity
is replaced by import provenance naming the source tool, format, and adapter
version. Fidelity is reported per field in three tiers — recomputed from raw
data, passed through as reported by the source tool, or recomputed with a
methodological caveat where a task variant makes the canonical dependent
variable inappropriate — so an imported dataset never claims more fidelity
than its source supports, and imported sessions never masquerade as natively
collected ones.

```{admonition} Framing constraint
This is an **architectural** claim, not an empirical one. No adapters ship in
this version, and the manuscript must not imply otherwise. The claim is that
the reconstruction architecture generalizes to foreign input via a stated
interchange contract, with adapters as a fast-follow. Unlike the per-session
version stamp — which cannot be added retroactively and therefore had to ship
before data collection — legacy data already sits on disk and will score
identically whenever an adapter arrives, so deferring costs nothing.
```

[Backed by: the format survey in
`.scratch/multi-station-data/assets/foreign-bart-formats.md`. Do not cite
adapter behavior; none exists.]
