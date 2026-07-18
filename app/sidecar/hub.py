"""Data Hub ingestion: read assembled station folders, decide, itemize (I8).

The importable core under the Hub's CLI and UI (DATA-SPEC §5). ``ingest``
walks researcher-chosen source folders, groups the per-session files stations
emitted, and produces the itemized ingestion report — the structure the
output writer renders and the fixture suite asserts on.

Governing rule: **the Hub never acts silently.** Every session is included
cleanly, or flagged / held / partitioned / skipped, and every departure is
named as one ``HubFinding``:

- **held** — excluded until resolved (divergent duplicate, future schema,
  missing ground truth or identity, unreadable JSON); holds block only the
  affected session, never the run.
- **attention** — pooled but itemized (ID collisions, duplicate station
  labels, config drift, older schemas); ``loud`` marks the data-integrity
  tier within the group.
- **info** — clean/informational (collapsed duplicate copies, re-runs kept,
  re-score-only sessions, foreign files skipped).

The one dataset-level failure is ``NoStudyError``: nothing in any source
identifies what study is being looked at. Ingestion only decides — rebuild
(re-scoring) is I9 and output writing is I10; both consume this report.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Any, Literal, Sequence

from pydantic import BaseModel, Field

from scoring.config import TaskConfig
from scoring.projection import MetricsMode
from scoring.schemas import SessionEnvelope
from sidecar.naming import SESSION_FILE, TIMESTAMP, slug

# The newest schema_version this Hub understands: the current model's own
# default. Anything ≤ this loads through the current pydantic models with
# defaults filling (§6.2 — default-filling *is* the migration); anything
# newer is refused per session, never guessed at.
HUB_SCHEMA_MAX = TaskConfig.model_fields["schema_version"].default

# Study-level files the live path writes beside the sessions (frozen config +
# timestamped copies, provenance record, data dictionary, the two CSVs and
# their unmerged/backup siblings). Recognized so they never count as foreign;
# their content is not ingested — sessions alone are ground truth.
_STUDY_LEVEL = (
    re.compile(rf".+_study(_{TIMESTAMP})?\.json$"),
    re.compile(r".+_provenance\.json$"),
    re.compile(r".+_data_dictionary\.md$"),
    re.compile(rf".+_(results|trials)(_(unmerged|backup)_{TIMESTAMP})?\.csv$"),
)


class NoStudyError(Exception):
    """No source folder yields a parseable frozen study config or a readable
    per-session config — the Hub cannot establish what study it is looking
    at, the only situation that aborts ingestion outright (§5.6)."""


Group = Literal["held", "attention", "info"]


class HubFinding(BaseModel):
    """One itemized line of the ingestion report — a named departure from a
    clean ingest. The fixture suite (I15) asserts on ``code`` + ``group``;
    ``message`` is the rendered line the CLI/UI/report file show."""

    code: str = Field(description="stable machine-readable hazard code")
    group: Group = Field(
        description=(
            "severity: held = excluded until resolved; attention = pooled "
            "but itemized; info = clean/informational"
        )
    )
    message: str = Field(description="the human-readable report line")
    loud: bool = Field(
        default=False,
        description="the loud data-integrity tier within the group",
    )
    session_ids: list[str] = Field(
        default_factory=list,
        description="session UUIDs this line is about, where known",
    )
    paths: list[str] = Field(
        default_factory=list,
        description="files or folders this line is about, where useful",
    )


class SessionRecord(BaseModel):
    """One session the Hub will pool: identity, provenance, and the file
    paths the rebuild (I9) re-scores from. ``timestamp_utc`` is recovered
    from the filename stem — the only place it is persisted (§9.3) — and is
    the station's local-clock capture, not synchronized global time."""

    session_id: str = Field(description="canonical key: the session UUID")
    label: str = Field(
        description="human-readable report label (station · candidate · timestamp)"
    )
    stem: str = Field(description="the shared filename stem of the four files")
    candidate_id: str
    station_id: str | None = Field(
        description="station label from the session envelope; None when unset"
    )
    machine_uuid: str | None = Field(
        description=(
            "machine UUID from the folder's provenance record; the "
            "duplicate-station-label discriminator"
        )
    )
    participant_key: str = Field(
        description=(
            "unambiguous participant column (station::candidate) — "
            "candidate_id is never rewritten (§5.3)"
        )
    )
    timestamp_utc: str = Field(
        description="local-clock session write time, recovered from the stem"
    )
    seed: int | None = Field(
        description="the RNG seed this session's own config recorded"
    )
    schema_version: str
    envelope: SessionEnvelope
    config: TaskConfig
    events_path: str
    session_path: str
    config_path: str
    metrics_path: str | None = Field(
        description="stored metrics for the verify pass; None when absent/unreadable"
    )
    events_sha256: str = Field(
        description="content hash of events.jsonl — the duplicate verifier (§5.1)"
    )


class Partition(BaseModel):
    """One comparable output set: sessions sharing a config fingerprint over
    the pooling-breaking fields (§5.4). The first partition is the main one
    (most sessions); each also carries the field values that define it."""

    fingerprint: str = Field(description="hash of the pooling-breaking fields")
    breaking: dict[str, Any] = Field(
        description="the pooling-breaking field values shared by these sessions"
    )
    sessions: list[SessionRecord] = Field(
        description="pooled sessions, sorted (station_id, timestamp_utc, session_id)"
    )


class IngestionReport(BaseModel):
    """The Hub's primary deliverable: every pooled session by partition, and
    every departure as an itemized finding. I9 slots its verify-grading rows
    into the same findings list; I10/I11/I12 render it."""

    title: str = Field(description="the identified study's title")
    slug: str = Field(description="the study's filename namespace")
    sources: list[str] = Field(description="the source folders as given")
    configured_mode: MetricsMode = Field(
        description=(
            "the study's configured metrics mode (§6.3) — the rebuild default, "
            "so the reconstructed master matches the live one"
        )
    )
    partitions: list[Partition]
    findings: list[HubFinding]

    @property
    def held(self) -> list[HubFinding]:
        return [f for f in self.findings if f.group == "held"]

    @property
    def attention(self) -> list[HubFinding]:
        return [f for f in self.findings if f.group == "attention"]

    @property
    def info(self) -> list[HubFinding]:
        return [f for f in self.findings if f.group == "info"]

    @property
    def will_rebuild(self) -> int:
        return sum(len(p.sessions) for p in self.partitions)


# ── Scan: walk sources, glob our own patterns ────────────────────────────────


@dataclass
class _FileSet:
    """The files sharing one per-session stem in one directory. Two copies of
    a session in two folders are two sets — dedupe needs both."""

    directory: Path
    stem: str
    ts: str
    files: dict[str, Path] = field(default_factory=dict)  # kind → path


@dataclass
class _FolderStation:
    """The station identity a folder's provenance record claims for it —
    label + machine UUID, either possibly absent on pre-station data."""

    station_id: str | None
    machine_uuid: str | None


@dataclass
class _Scan:
    sets: list[_FileSet] = field(default_factory=list)
    frozen: list[Path] = field(default_factory=list)  # {slug}_study.json files
    stations: dict[str, _FolderStation] = field(default_factory=dict)  # by dir
    foreign: int = 0
    practice_dirs: int = 0


def _read_json(path: Path) -> Any | None:
    """Parsed JSON, or None when the file is unreadable or truncated — each
    caller grades what that loss actually means (§5.6)."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _scan(roots: list[Path], findings: list[HubFinding]) -> _Scan:
    scan = _Scan()
    sets: dict[tuple[str, str], _FileSet] = {}
    for root in roots:
        recognized = 0
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames.sort()
            if "practice" in dirnames:
                # Test Runs (issue 43) are never assembled into official data.
                dirnames.remove("practice")
                scan.practice_dirs += 1
            for name in sorted(filenames):
                path = Path(dirpath) / name
                match = SESSION_FILE.match(name)
                if match:
                    key = (dirpath, match["stem"])
                    if key not in sets:
                        sets[key] = _FileSet(Path(dirpath), match["stem"], match["ts"])
                    sets[key].files[match["kind"]] = path
                    recognized += 1
                elif any(pattern.match(name) for pattern in _STUDY_LEVEL):
                    recognized += 1
                    if name.endswith("_study.json"):
                        scan.frozen.append(path)
                    elif name.endswith("_provenance.json"):
                        _read_station(path, dirpath, scan, findings)
                else:
                    scan.foreign += 1
        if not recognized:
            findings.append(
                HubFinding(
                    code="empty_source",
                    group="info",
                    message=f"no recognizable study data in source: {root}",
                    paths=[str(root)],
                )
            )
    scan.sets = [sets[key] for key in sorted(sets)]
    return scan


def _read_station(
    path: Path, dirpath: str, scan: _Scan, findings: list[HubFinding]
) -> None:
    """A folder's provenance record carries the (station label, machine UUID)
    pair — the duplicate-station-label discriminator (§5.3). Unreadable is
    only degraded attribution, named but never blocking."""
    record = _read_json(path)
    if not isinstance(record, dict):
        findings.append(
            HubFinding(
                code="study_file_unreadable",
                group="info",
                message=(
                    f"provenance record unreadable — machine attribution "
                    f"degraded: {path}"
                ),
                paths=[str(path)],
            )
        )
        return
    scan.stations[dirpath] = _FolderStation(
        record.get("station_id"), record.get("machine_uuid")
    )


def _identify(
    roots: list[Path], scan: _Scan, findings: list[HubFinding]
) -> tuple[str, str, list[TaskConfig]]:
    """What study is this? Prefer a frozen study config (its filename is the
    authoritative slug); fall back to any session's own config snapshot.
    Nothing parseable anywhere is the one true abort (§5.6). Every parseable
    frozen config is returned so drift against the folders' design records
    can be flagged (§5.4)."""
    frozen_configs: list[TaskConfig] = []
    identity: tuple[str, str] | None = None
    for path in sorted(scan.frozen):
        try:
            config = TaskConfig.model_validate(_read_json(path))
        except ValueError:
            findings.append(
                HubFinding(
                    code="study_file_unreadable",
                    group="info",
                    message=f"frozen study config unreadable or invalid: {path}",
                    paths=[str(path)],
                )
            )
            continue
        frozen_configs.append(config)
        if identity is None:
            identity = (config.title, path.name.removesuffix("_study.json"))
    if identity is not None:
        return (*identity, frozen_configs)
    for file_set in scan.sets:
        config_path = file_set.files.get("config.json")
        if config_path is None:
            continue
        try:
            config = TaskConfig.model_validate(_read_json(config_path))
        except ValueError:
            continue
        return config.title, slug(config.title), frozen_configs
    raise NoStudyError(
        "no study identifiable in "
        + ", ".join(str(r) for r in roots)
        + " — no parseable frozen study.json and no readable session "
        "config.json anywhere"
    )


# ── Load + dedupe: identity first, then the three-way key (§5.1–§5.2) ────────


@dataclass
class _Loaded:
    """A session with identity established: envelope readable, ground truth
    present, content hash computed — the dedupe unit."""

    file_set: _FileSet
    envelope: SessionEnvelope
    events_sha256: str
    label: str


def _load(scan: _Scan, findings: list[HubFinding]) -> list[_Loaded]:
    loaded: list[_Loaded] = []
    for file_set in scan.sets:
        session_path = file_set.files.get("session.json")
        if session_path is None:
            findings.append(
                HubFinding(
                    code="missing_session",
                    group="held",
                    message=(
                        f"held: session envelope missing — the filename yields "
                        f"only station/candidate/timestamp, not session_id or "
                        f"condition: {file_set.stem}"
                    ),
                    paths=[str(file_set.directory)],
                )
            )
            continue
        try:
            envelope = SessionEnvelope.model_validate(_read_json(session_path))
        except ValueError:
            findings.append(
                HubFinding(
                    code="unreadable_json",
                    group="held",
                    message=f"held: unreadable JSON — {session_path.name}",
                    paths=[str(session_path)],
                )
            )
            continue
        label = " · ".join(
            part
            for part in (envelope.station_id, envelope.candidate_id, file_set.ts)
            if part
        )
        events_path = file_set.files.get("events.jsonl")
        if events_path is None:
            findings.append(
                HubFinding(
                    code="missing_events",
                    group="held",
                    message=f"held: no events, cannot re-score — {label}",
                    session_ids=[envelope.session_id],
                    paths=[str(file_set.directory)],
                )
            )
            continue
        try:
            digest = hashlib.sha256(events_path.read_bytes()).hexdigest()
        except OSError:
            # Ground truth present but inaccessible: the same loss as missing
            # events, held per session — one bad file never sinks the rest.
            findings.append(
                HubFinding(
                    code="unreadable_events",
                    group="held",
                    message=f"held: events unreadable, cannot re-score — {label}",
                    session_ids=[envelope.session_id],
                    paths=[str(events_path)],
                )
            )
            continue
        loaded.append(_Loaded(file_set, envelope, digest, label))
    return loaded


def _dedupe(loaded: list[_Loaded], findings: list[HubFinding]) -> list[_Loaded]:
    """Three-way dedupe keyed on (session_id, events hash): identical copies
    collapse, divergent copies are held — the Hub never guesses which copy is
    authoritative — and distinct UUIDs are distinct sessions (§5.2)."""
    by_id: dict[str, list[_Loaded]] = {}
    for item in loaded:
        by_id.setdefault(item.envelope.session_id, []).append(item)
    unique: list[_Loaded] = []
    collapsed_sets = 0
    collapsed_copies = 0
    for session_id, copies in by_id.items():
        if len(copies) == 1:
            unique.append(copies[0])
        elif len({c.events_sha256 for c in copies}) == 1:
            unique.append(copies[0])
            collapsed_sets += 1
            collapsed_copies += len(copies) - 1
        else:
            folders = ", ".join(str(c.file_set.directory) for c in copies)
            findings.append(
                HubFinding(
                    code="divergent_duplicate",
                    group="held",
                    message=(
                        f"held: divergent duplicate — session {session_id} "
                        f"differs across folders ({folders}); resolve before "
                        f"assembly"
                    ),
                    session_ids=[session_id],
                    paths=[str(c.file_set.directory) for c in copies],
                )
            )
    if collapsed_sets:
        findings.append(
            HubFinding(
                code="identical_duplicates_collapsed",
                group="info",
                message=(
                    f"collapsed {collapsed_sets} identical duplicate "
                    f"file-set(s) ({collapsed_copies} extra file copies)"
                ),
            )
        )
    return unique


# ── Admit: config, schema, practice, verify availability (§5.6, §6.2) ────────


def _schema_key(version: str) -> tuple[int, ...] | None:
    try:
        return tuple(int(part) for part in version.strip().split("."))
    except ValueError:
        return None


def _admit(
    unique: list[_Loaded], scan: _Scan, findings: list[HubFinding]
) -> tuple[list[SessionRecord], list[str]]:
    kept: list[SessionRecord] = []
    practice_labels: list[str] = []
    max_key = _schema_key(HUB_SCHEMA_MAX)
    for item in unique:
        if item.envelope.practice:
            # Belt to the practice/-folder pruning: files moved out of the
            # subfolder still carry the envelope flag.
            practice_labels.append(item.label)
            continue
        config_path = item.file_set.files.get("config.json")
        if config_path is None:
            findings.append(
                HubFinding(
                    code="missing_config",
                    group="held",
                    message=(
                        f"held: study config missing — cannot re-score "
                        f"{item.label} faithfully"
                    ),
                    session_ids=[item.envelope.session_id],
                )
            )
            continue
        raw = _read_json(config_path)
        if not isinstance(raw, dict):
            findings.append(
                HubFinding(
                    code="unreadable_json",
                    group="held",
                    message=f"held: unreadable JSON — {config_path.name}",
                    session_ids=[item.envelope.session_id],
                    paths=[str(config_path)],
                )
            )
            continue
        version = str(raw.get("schema_version", HUB_SCHEMA_MAX))
        version_key = _schema_key(version)
        if version_key is None or version_key > max_key:
            findings.append(
                HubFinding(
                    code="future_schema",
                    group="held",
                    message=(
                        f"held: future schema {version} — this Hub supports "
                        f"≤ {HUB_SCHEMA_MAX}; upgrade the Hub and re-run "
                        f"({item.label})"
                    ),
                    session_ids=[item.envelope.session_id],
                )
            )
            continue
        try:
            config = TaskConfig.model_validate(raw)
        except ValueError:
            findings.append(
                HubFinding(
                    code="unreadable_json",
                    group="held",
                    message=(
                        f"held: {config_path.name} does not validate as a "
                        f"study config"
                    ),
                    session_ids=[item.envelope.session_id],
                    paths=[str(config_path)],
                )
            )
            continue
        if version_key < max_key:
            findings.append(
                HubFinding(
                    code="older_schema",
                    group="attention",
                    message=(
                        f"older schema {version} pooled — current-model "
                        f"defaults fill the missing fields ({item.label})"
                    ),
                    session_ids=[item.envelope.session_id],
                )
            )
        metrics_path = item.file_set.files.get("metrics.json")
        metrics_state = None
        if metrics_path is None:
            metrics_state = "absent"
        elif _read_json(metrics_path) is None:
            metrics_state = "unreadable"
            metrics_path = None
        if metrics_state:
            findings.append(
                HubFinding(
                    code="missing_metrics",
                    group="info",
                    message=(
                        f"stored metrics {metrics_state}; re-scored, no "
                        f"verify — {item.label}"
                    ),
                    session_ids=[item.envelope.session_id],
                )
            )
        station = item.envelope.station_id
        candidate = item.envelope.candidate_id
        kept.append(
            SessionRecord(
                session_id=item.envelope.session_id,
                label=item.label,
                stem=item.file_set.stem,
                candidate_id=candidate,
                station_id=station,
                machine_uuid=_machine_uuid_for(item.file_set.directory, scan),
                participant_key=f"{station}::{candidate}" if station else candidate,
                timestamp_utc=item.file_set.ts,
                seed=config.seed,
                schema_version=version,
                envelope=item.envelope,
                config=config,
                events_path=str(item.file_set.files["events.jsonl"]),
                session_path=str(item.file_set.files["session.json"]),
                config_path=str(config_path),
                metrics_path=str(metrics_path) if metrics_path else None,
                events_sha256=item.events_sha256,
            )
        )
    return kept, practice_labels


def _machine_uuid_for(directory: Path, scan: _Scan) -> str | None:
    """The machine UUID attributed to a session's folder: its own provenance
    record, or the nearest ancestor's (a source root may hold one station
    folder per subdirectory)."""
    for candidate in (directory, *directory.parents):
        record = scan.stations.get(str(candidate))
        if record is not None:
            return record.machine_uuid
    return None


# ── Flags: stations, collisions, re-runs (§5.3, §5.2) ────────────────────────


def _flag_duplicate_labels(scan: _Scan, findings: list[HubFinding]) -> None:
    label_uuids: dict[str, set[str]] = {}
    for station in scan.stations.values():
        if station.station_id and station.machine_uuid:
            label_uuids.setdefault(station.station_id, set()).add(
                station.machine_uuid
            )
    for label in sorted(label_uuids):
        uuids = label_uuids[label]
        if len(uuids) > 1:
            findings.append(
                HubFinding(
                    code="duplicate_station_label",
                    group="attention",
                    message=(
                        f"duplicate station label: '{label}' is used by "
                        f"{len(uuids)} different machines — their data cannot "
                        f"be told apart by label; participant_key stays "
                        f"ambiguous until stations are re-labeled"
                    ),
                )
            )


def _distinct_stations(a: SessionRecord, b: SessionRecord) -> bool:
    """Whether two sessions provably ran on different stations. A station is
    keyed on its label *plus* machine UUID (§5.3), so two machines both
    labeled S1 still count as two stations; a session without a machine UUID
    is conservatively folded into its label — the Hub never invents a
    collision it cannot prove."""
    if a.station_id != b.station_id:
        return True
    return bool(
        a.machine_uuid and b.machine_uuid and a.machine_uuid != b.machine_uuid
    )


def _flag_collisions(kept: list[SessionRecord], findings: list[HubFinding]) -> None:
    """A candidate_id spanning >1 station. Non-destructive and non-blocking:
    candidate_id is never rewritten and everything pools — participant_key
    disambiguates, and the warning is tiered by each session's own recorded
    seed, with a distinct louder line for two auto-generated IDs (§5.3)."""
    by_candidate: dict[str, list[SessionRecord]] = {}
    for record in kept:
        by_candidate.setdefault(record.candidate_id, []).append(record)
    for candidate in sorted(by_candidate):
        records = by_candidate[candidate]
        if not any(
            _distinct_stations(a, b) for a, b in combinations(records, 2)
        ):
            continue
        labels = sorted({str(record.station_id) for record in records})
        if len(labels) > 1:
            where = f"stations {', '.join(labels)}"
        else:
            machines = {r.machine_uuid for r in records if r.machine_uuid}
            where = f"{len(machines)} machines all labeled '{labels[0]}'"
        session_ids = [record.session_id for record in records]
        shared_seed = any(
            a.seed is not None
            and a.seed == b.seed
            and _distinct_stations(a, b)
            for a, b in combinations(records, 2)
        )
        if shared_seed:
            message = (
                f"ID collision: '{candidate}' ran on {where} with "
                f"the same fixed seed → identical balloon sequences; these "
                f"sessions are NOT independent (participant_key added)"
            )
        else:
            message = (
                f"ID collision: '{candidate}' appears on {where} "
                f"(participant_key added)"
            )
        findings.append(
            HubFinding(
                code="id_collision",
                group="attention",
                message=message,
                loud=shared_seed,
                session_ids=session_ids,
            )
        )
        generated = [r for r in records if r.envelope.id_source == "generated"]
        if any(_distinct_stations(a, b) for a, b in combinations(generated, 2)):
            findings.append(
                HubFinding(
                    code="generated_id_collision",
                    group="attention",
                    message=(
                        f"ID collision between auto-generated IDs "
                        f"('{candidate}') — near-impossible by chance; likely "
                        f"duplicated data or a broken generator. Investigate "
                        f"before pooling."
                    ),
                    loud=True,
                    session_ids=session_ids,
                )
            )


def _flag_reruns(kept: list[SessionRecord], findings: list[HubFinding]) -> None:
    groups: dict[tuple[str, str, str], list[SessionRecord]] = {}
    for record in kept:
        # Keyed like a station is (label + machine UUID), so two same-label
        # machines' sessions read as a collision, not a re-run.
        groups.setdefault(
            (record.candidate_id, record.station_id or "", record.machine_uuid or ""),
            [],
        ).append(record)
    for candidate, station, _machine in sorted(groups):
        records = groups[(candidate, station, _machine)]
        if len(records) > 1:
            findings.append(
                HubFinding(
                    code="rerun",
                    group="info",
                    message=(
                        f"re-run kept: '{candidate}' has {len(records)} "
                        f"sessions on station {station or '(unset)'} — "
                        f"test-retest is real data"
                    ),
                    session_ids=[record.session_id for record in records],
                )
            )


# ── Partition + study-wide drift (§5.4, §5.5) ────────────────────────────────


def _breaking_fields(config: TaskConfig) -> dict[str, Any]:
    """The pooling-breaking tier of the config: fields that change the task
    itself, so sessions differing here are not one comparable dataset (§5.4).
    Everything else (metrics_mode, output_dir, qc, …) never splits."""
    dump = config.model_dump(mode="json")
    return {
        "colors": dump["colors"],
        "reward_per_pump": dump["reward_per_pump"],
        "conditions": sorted(dump["conditions"]),
        "payout": dump["payout"],
        "language": dump["language"],
    }


def _fingerprint(breaking: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(breaking, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]


def _partition(
    kept: list[SessionRecord], findings: list[HubFinding]
) -> list[Partition]:
    ordered = sorted(
        kept, key=lambda r: (r.station_id or "", r.timestamp_utc, r.session_id)
    )
    partitions: dict[str, Partition] = {}
    for record in ordered:
        breaking = _breaking_fields(record.config)
        fingerprint = _fingerprint(breaking)
        if fingerprint not in partitions:
            partitions[fingerprint] = Partition(
                fingerprint=fingerprint, breaking=breaking, sessions=[]
            )
        partitions[fingerprint].sessions.append(record)
    # Main partition first: most sessions, first-seen breaking ties.
    order = list(partitions)
    result = sorted(
        partitions.values(),
        key=lambda p: (-len(p.sessions), order.index(p.fingerprint)),
    )
    for extra in result[1:]:
        fields = [
            name
            for name in extra.breaking
            if extra.breaking[name] != result[0].breaking[name]
        ]
        findings.append(
            HubFinding(
                code="config_drift_partition",
                group="attention",
                message=(
                    f"config drift: {', '.join(fields)} → partition "
                    f"({len(extra.sessions)} session(s) split from the main "
                    f"set)"
                ),
                session_ids=[s.session_id for s in extra.sessions],
            )
        )
    return result


def _flag_study_drift(
    kept: list[SessionRecord],
    frozen_configs: list[TaskConfig],
    partitions: list[Partition],
    findings: list[HubFinding],
) -> None:
    """Notable drift pools with a flag (§5.4); schema_version's own tier is
    handled per session in ``_admit``. The folders' frozen design records
    join the comparison: a frozen config matching no ingested session means
    the folder's design record and its sessions disagree. A title mismatch —
    across sessions or against a frozen record — is the loudest question of
    all: are these even the same study?"""
    for name in ("seed", "currency"):
        values = sorted({repr(getattr(r.config, name)) for r in kept})
        if len(values) > 1:
            findings.append(
                HubFinding(
                    code="config_drift_notable",
                    group="attention",
                    message=(
                        f"config drift: {name} ({' vs '.join(values)}) — "
                        f"sessions pooled"
                    ),
                )
            )
    partition_prints = {p.fingerprint for p in partitions}
    for config in frozen_configs:
        if partitions and _fingerprint(_breaking_fields(config)) not in partition_prints:
            findings.append(
                HubFinding(
                    code="frozen_config_drift",
                    group="attention",
                    message=(
                        f"config drift: the frozen study config for "
                        f"{config.title!r} matches no ingested session's "
                        f"config — the folder's design record and its "
                        f"sessions disagree"
                    ),
                )
            )
    titles = {r.config.title for r in kept}
    if kept:
        titles |= {c.title for c in frozen_configs}
    titles = sorted(titles)
    if len(titles) > 1:
        findings.append(
            HubFinding(
                code="title_mismatch",
                group="attention",
                loud=True,
                message=(
                    "study titles differ across this ingest: "
                    + " vs ".join(repr(t) for t in titles)
                    + " — are these even the same study?"
                ),
            )
        )


def _configured_mode(
    kept: list[SessionRecord], frozen_configs: list[TaskConfig]
) -> MetricsMode:
    """The study's configured metrics mode (§6.3) — the rebuild default. The
    frozen design record wins when one parsed (the same first-sorted file the
    study identity comes from); else the sessions' own unanimous setting.
    When neither pins a mode — no design record and the sessions disagree, or
    nothing was kept — advanced: the lossless superset, chosen over inferring
    a "latest" from cross-machine clocks (§5.5); the explicit rebuild-time
    override remains for a researcher who wants classic."""
    if frozen_configs:
        return frozen_configs[0].metrics_mode
    modes = {record.config.metrics_mode for record in kept}
    if len(modes) == 1:
        return modes.pop()
    return "advanced"


# ── Entry point ──────────────────────────────────────────────────────────────


def ingest(sources: Sequence[str | Path]) -> IngestionReport:
    """Ingest assembled station folders into one itemized report (§5).

    Walks every source, groups per-session files by stem, establishes each
    session's identity, dedupes on (session_id, events hash), admits sessions
    through the graded-tolerance rules, flags stations/collisions/drift, and
    partitions by config fingerprint. Raises ``NoStudyError`` only when no
    study is identifiable at all; every lesser defect becomes a finding.
    """
    roots = [Path(source) for source in sources]
    findings: list[HubFinding] = []
    scan = _scan(roots, findings)
    title, study_slug, frozen_configs = _identify(roots, scan, findings)
    loaded = _load(scan, findings)
    unique = _dedupe(loaded, findings)
    kept, practice_labels = _admit(unique, scan, findings)
    _flag_duplicate_labels(scan, findings)
    _flag_collisions(kept, findings)
    _flag_reruns(kept, findings)
    partitions = _partition(kept, findings)
    _flag_study_drift(kept, frozen_configs, partitions, findings)
    if scan.foreign:
        findings.append(
            HubFinding(
                code="foreign_files",
                group="info",
                message=f"skipped {scan.foreign} unrecognized file(s)",
            )
        )
    if scan.practice_dirs or practice_labels:
        skipped = []
        if scan.practice_dirs:
            skipped.append(f"{scan.practice_dirs} practice folder(s)")
        if practice_labels:
            skipped.append(f"{len(practice_labels)} practice session(s)")
        findings.append(
            HubFinding(
                code="practice_excluded",
                group="info",
                message=(
                    f"skipped {' and '.join(skipped)} — test runs are never "
                    f"assembled"
                ),
            )
        )
    return IngestionReport(
        title=title,
        slug=study_slug,
        sources=[str(root) for root in roots],
        configured_mode=_configured_mode(kept, frozen_configs),
        partitions=partitions,
        findings=findings,
    )
