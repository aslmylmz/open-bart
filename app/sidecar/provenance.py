"""Study-level provenance files: the OSF-ready output directory (issue 42).

Rather than an export button nobody clicks, the output directory itself is
permanently OSF-ready: alongside the per-session files, every study directory
carries a frozen copy of the exact study config used, a provenance record
(app/engine versions, platform, seed), and a data dictionary generated from
the scoring models — publishing is right-click → Compress.

Refresh rules follow the master-CSV writer's spirit (issue 36): nothing here
ever raises or blocks a session write — failures come back as readable
warnings. A file is rewritten only when its generated content actually changed
(a mid-study upgrade), so unchanged files keep their timestamps. The frozen
config is the exception: it is written once and never replaced — a changed
config is recorded alongside, timestamped, so the original design stays
auditable.
"""

from __future__ import annotations

import json
import platform
import re
from datetime import datetime, timezone
from pathlib import Path

import scoring
from pydantic import BaseModel
from scoring.config import ColorProfile, TaskConfig
from scoring.projection import CLASSIC_CANON, CLASSIC_FIELDS, CLASSIC_TRIALS_DROPPED
from scoring.schemas import (
    BARTMetrics,
    ColorMetrics,
    EventPayload,
    GameEvent,
    GameSession,
    TrialRecord,
)
from sidecar.station import StationIdentity


def ensure_provenance(
    out_dir: Path,
    config: TaskConfig,
    slug: str,
    station: StationIdentity | None = None,
) -> list[str]:
    """Create or refresh the study-level provenance files under ``out_dir``.

    Called on every (non-practice) session write; returns readable warnings
    when a file could not be updated — the session's own data is never
    affected. Never raises.
    """
    warnings: list[str] = []
    steps = [
        (out_dir / f"{slug}_study.json", _freeze_study_config),
        (
            out_dir / f"{slug}_provenance.json",
            lambda path, config: _refresh_provenance(path, config, station),
        ),
        (
            out_dir / f"{slug}_data_dictionary.md",
            lambda path, config: _write_if_changed(
                path, _render_dictionary(config, slug)
            ),
        ),
    ]
    for path, step in steps:
        try:
            step(path, config)
        except OSError as exc:
            reason = getattr(exc, "strerror", None) or str(exc) or type(exc).__name__
            warnings.append(
                f"Could not update {path.name} ({reason}) — the session's own "
                f"data is unaffected; the file will be refreshed on the next "
                f"session once it is writable."
            )
    return warnings


def _write_if_changed(path: Path, text: str) -> None:
    """Write ``text`` only when the file's content differs, so an unchanged
    file keeps its timestamp — sessions never churn the provenance files."""
    try:
        if path.read_text(encoding="utf-8") == text:
            return
    except OSError:
        pass
    path.write_text(text, encoding="utf-8")


def _freeze_study_config(path: Path, config: TaskConfig) -> None:
    """Freeze the exact study config on first write; never replace it.

    A config that no longer matches the frozen copy is recorded alongside as
    ``[title]_study_[timestamp].json`` — once per distinct config, however
    many sessions run under it — so a mid-study design change stays auditable
    next to the original. The timestamp is matched strictly (digits + T + Z),
    the ``_count_sessions`` rule, so a candidate literally named "study" can
    never shadow a versioned copy.
    """
    current = config.model_dump(mode="json")
    if not path.exists():
        path.write_text(config.model_dump_json(indent=2), encoding="utf-8")
        return
    copies = [
        p
        for p in path.parent.iterdir()
        if re.fullmatch(rf"{re.escape(path.stem)}_\d{{8}}T\d+Z\.json", p.name)
    ]
    if any(_records(p, current) for p in [path, *copies]):
        return
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path.with_name(f"{path.stem}_{ts}.json").write_text(
        config.model_dump_json(indent=2), encoding="utf-8"
    )


def _records(path: Path, config_dump: dict) -> bool:
    """Whether ``path`` already records exactly this config (compared parsed,
    so hand-reformatting the JSON does not count as a design change)."""
    try:
        return json.loads(path.read_text(encoding="utf-8")) == config_dump
    except (OSError, ValueError):
        return False


def _refresh_provenance(
    path: Path, config: TaskConfig, station: StationIdentity | None = None
) -> None:
    """The provenance record a methods section needs. App and engine currently
    share one version constant (released in lockstep via the issue-35
    handshake); recorded separately so a future split stays representable.
    ``metrics_mode`` travels beside ``engine_version`` (DATA-SPEC §4.5) — the
    mode is stated explicitly in both modes, never inferred from an absence.

    With a station ID set (DATA-SPEC §2.3) the record also carries the label
    and the per-install machine UUID — folder-level machine identity, and the
    Hub's detector for two machines sharing one label. Unset, both keys are
    absent and the record stays byte-identical to single-station output."""
    record = {
        "app_version": scoring.__version__,
        "engine_version": scoring.__version__,
        "metrics_mode": config.metrics_mode,
        "platform": platform.platform(),
        "seed": config.seed,
    }
    if station is not None and station.station_id:
        record["station_id"] = station.station_id
        record["machine_uuid"] = station.machine_uuid
    _write_if_changed(path, json.dumps(record, indent=2))


def _cell(text: str | None) -> str:
    """One markdown table cell: newlines collapsed, pipes escaped."""
    return " ".join((text or "").split()).replace("|", "\\|")


def _table(columns: list[tuple[str, str | None]], key: str = "Column") -> str:
    rows = "\n".join(f"| `{name}` | {_cell(desc)} |" for name, desc in columns)
    return f"| {key} | Description |\n|--------|-------------|\n{rows}\n"


def _identity_columns(config: TaskConfig) -> list[tuple[str, str | None]]:
    """The identity columns ``write_output`` prepends to every study-wide CSV
    row. ``condition`` follows the present-only-when-configured rule
    (issue 37), exactly like the row writer."""
    columns: list[tuple[str, str | None]] = [
        (
            "timestamp_utc",
            "Session write time (UTC, filename-safe format) — shared by the "
            "session's files and its study-wide CSV rows.",
        ),
        ("session_id", "The client-generated session identifier (UUID)."),
        ("candidate_id", "The participant ID entered at the start of the run."),
    ]
    if config.conditions:
        columns.append(
            (
                "condition",
                "The condition assigned at the ID screen; one of: "
                + ", ".join(config.conditions)
                + ".",
            )
        )
    return columns


def _unflattened_fields(config: TaskConfig) -> set[str]:
    """The ``BARTMetrics`` fields ``_flatten_metrics`` keeps out of the master
    CSV: the nested narrative/per-color structures and the JSON-only dict/list
    fields (``ev_optimal_stops``, ``session_warnings`` — issue 53), plus the
    payout pair for studies that declare no payout (the conditional-column
    rule, issue 41). These stay documented in the scored-metrics JSON section."""
    skip = {
        "behavioral_profile",
        "color_metrics",
        "ev_optimal_stops",
        "session_warnings",
    }
    if config.payout is None:
        skip |= {"payout_amount", "payout_currency"}
    return skip


def _classic_described(name: str, description: str | None) -> str | None:
    """A classic column's description with its canon literature name/definition
    appended (DATA-SPEC §4.3): repo column names are kept, the literature name
    lives here in the dictionary — never as a rename."""
    canon = CLASSIC_CANON.get(name)
    if not canon:
        return description
    lead = (description or "").strip()
    if lead and not lead.endswith("."):
        lead += "."
    return f"{lead} {canon}".strip()


def _master_csv_columns(config: TaskConfig) -> list[tuple[str, str | None]]:
    """Exactly the columns ``write_output`` puts in this study's master CSV:
    identity, then the flat ``BARTMetrics`` scalars, then per-color
    ``{color}_{field}`` blocks — mirroring ``_flatten_metrics``. In classic
    metrics mode the scalars narrow to the projection's keep-set — annotated
    with their literature names — and Classic is session-level only, so the
    per-color blocks disappear (DATA-SPEC §4.3)."""
    classic = config.metrics_mode == "classic"
    skip = _unflattened_fields(config)
    if classic:
        skip |= set(BARTMetrics.model_fields) - CLASSIC_FIELDS
    columns = _identity_columns(config)
    columns += [
        (name, _classic_described(name, field.description) if classic else field.description)
        for name, field in BARTMetrics.model_fields.items()
        if name not in skip
    ]
    if classic:
        return columns
    for color in config.colors:
        columns += [
            (f"{color.name}_{name}", field.description)
            for name, field in ColorMetrics.model_fields.items()
            if name != "color"
        ]
    return columns


def _trials_csv_columns(config: TaskConfig) -> list[tuple[str, str | None]]:
    """Exactly the columns of this study's long-format trials CSV (issue 39):
    identity, then the engine's ``TrialRecord`` fields — minus the projection's
    dropped column in classic metrics mode (DATA-SPEC §4.3)."""
    dropped = (
        CLASSIC_TRIALS_DROPPED if config.metrics_mode == "classic" else frozenset()
    )
    return _identity_columns(config) + [
        (name, field.description)
        for name, field in TrialRecord.model_fields.items()
        if name not in dropped
    ]


def _model_table(model: type[BaseModel], skip: set[str] = frozenset()) -> str:
    """One table of a pydantic model's fields — name and declared description
    — so every field of the per-session files is documented straight from the
    model that defines it."""
    return _table(
        [
            (name, field.description)
            for name, field in model.model_fields.items()
            if name not in skip
        ],
        key="Field",
    )


def _render_dictionary(config: TaskConfig, slug: str) -> str:
    """The study's data dictionary, generated from the scoring models so a
    column added in code appears here without being documented twice. The
    header states the study's metrics mode in both modes (DATA-SPEC §4.5);
    in classic mode every section documents only what the projection emits."""
    classic = config.metrics_mode == "classic"
    if classic:
        mode_note = (
            "Metrics mode: `classic` — every output surface (master CSV, "
            "trials CSV, scored metrics JSON) is projected down to the "
            "classic BART canon (Lejuez et al., 2002/2003); the raw event "
            "log records the complete session either way.\n"
        )
        metrics_intro = (
            "The scored output in classic metrics mode: every Master CSV "
            "metric column above, un-flattened, plus:"
        )
        # In classic, the JSON-only extras narrow to the classic fields the
        # flattener keeps out of the CSV (session_warnings, and the null
        # payout pair for payout-less studies).
        json_extras = _unflattened_fields(config) & CLASSIC_FIELDS
        color_entries = ""
    else:
        mode_note = (
            "Metrics mode: `advanced` — the full metrics surface "
            "(the v1.0.0 default).\n"
        )
        metrics_intro = (
            "The full scored output: every Master CSV metric column above, "
            "un-flattened, plus:"
        )
        json_extras = _unflattened_fields(config)
        color_entries = (
            "\nEach `color_metrics` entry:\n\n" + _model_table(ColorMetrics)
        )
    return (
        f"# Data Dictionary — {config.title}\n"
        f"\n"
        f"Generated by the instrument (version {scoring.__version__}) from its "
        f"scoring models — regenerated automatically whenever the schema "
        f"changes; do not edit by hand. Together with the frozen study config "
        f"(`{slug}_study.json`) and the provenance record "
        f"(`{slug}_provenance.json`), this makes the output directory "
        f"self-describing and ready to archive or upload (e.g. to OSF) as-is.\n"
        f"\n"
        f"{mode_note}"
        f"\n"
        f"## Master CSV columns (`{slug}_results.csv`)\n"
        f"\n"
        f"One row per completed session.\n"
        f"\n"
        f"{_table(_master_csv_columns(config))}"
        f"\n"
        f"## Trials CSV columns (`{slug}_trials.csv`)\n"
        f"\n"
        f"One row per trial (balloon), in long format.\n"
        f"\n"
        f"{_table(_trials_csv_columns(config))}"
        f"\n"
        f"## Per-session files\n"
        f"\n"
        f"Each completed session also writes four files of its own, namespaced "
        f"by study title, candidate ID, and a UTC timestamp.\n"
        f"\n"
        f"### Raw event telemetry (`*_events.jsonl`)\n"
        f"\n"
        f"One JSON object per game event:\n"
        f"\n"
        f"{_model_table(GameEvent)}"
        f"\n"
        f"`payload` fields:\n"
        f"\n"
        f"{_model_table(EventPayload)}"
        f"\n"
        f"### Scored metrics (`*_metrics.json`)\n"
        f"\n"
        f"{metrics_intro}\n"
        f"\n"
        f"{_model_table(BARTMetrics, skip=set(BARTMetrics.model_fields) - json_extras)}"
        f"{color_entries}"
        f"\n"
        f"### Session envelope (`*_session.json`)\n"
        f"\n"
        f"The session's identity and design assignment (the raw telemetry "
        f"stays in `*_events.jsonl`):\n"
        f"\n"
        f"{_model_table(GameSession, skip={'events'})}"
        f"\n"
        f"### Study config snapshot (`*_config.json`)\n"
        f"\n"
        f"The exact study configuration this session ran under — the same "
        f"shape as the frozen `{slug}_study.json`:\n"
        f"\n"
        f"{_model_table(TaskConfig)}"
        f"\n"
        f"Each `colors` entry:\n"
        f"\n"
        f"{_model_table(ColorProfile)}"
        f"\n"
        f"Hazard-family parameters (`colors[].hazard`) are documented in the "
        f"instrument's hazard-families reference.\n"
    )
