"""The golden fixture, built in code from the real emission path (I13).

DATA-SPEC §9 makes a **deterministic in-code builder** the single source of
truth for the Hub's validation standard: every input the two suites assert on
is produced here at test time, so nothing can drift from production and no
input file is ever committed. Well-formed sessions go through the *live*
``write_output`` — the same call a station makes in the field, station identity
and all — with the emission path's clock seams pinned to fixed synthetic
timestamps (§9.5) and each machine impersonated by its own settings file, so
two builds yield byte-identical trees. Only defects the emission path cannot
produce are written
directly: a truncated JSON is truncated bytes, a removed file is simply not
there, corrupted metrics are edited in place.

Two studies (§9.1), because a shared slug would pollute clean byte-equality:

- **``clean-equivalence``** — one station, ``standalone=False`` (the only mode
  that live-appends the study-wide CSVs, so it is the only mode with a
  reference to compare a rebuild against), three clean sessions, no hazards.
  Feeds the byte-equality gate (I14).
- **``hazard-suite``** — one slug across four stations (two of them sharing a
  label), every hazard of the §9.2 table planted **one per session**, so each
  defect owns exactly one report line and a dropped flag cannot be masked by
  another. Feeds the report-line assertions (I15).

Both feed the committed sample snapshot (I16). Each session's config snapshot
records the output directory it was written to, so *where* a study is built is
part of its bytes: reproducibility is per location, and a snapshot meant to be
committed must be built under a **relative** base (from the repo root), never
an absolute temp path — the same path-leak discipline the screenshots follow.
"""

from __future__ import annotations

import json
import os
import shutil
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

import scoring
from scoring.config import DEFAULT_TASK_CONFIG, TaskConfig
from scoring.schemas import EventPayload, GameEvent, GameSession
from sidecar import app as app_module, provenance
from sidecar.models import WriteOutputRequest, WriteOutputResponse
from sidecar.naming import slug
from sidecar.station import StationIdentity

CLEAN_STUDY = "clean-equivalence"
HAZARD_STUDY = "hazard-suite"

# The synthetic wall clock: sessions are stamped one minute apart from here, in
# build order, so every filename stem is unique and reproducible. Nothing in
# the fixture ever reads the real clock.
_EPOCH = datetime(2026, 3, 2, 9, 0, 0, tzinfo=timezone.utc)

# The engine version the cross-version verify hazard (§9.2 row 11) claims. It
# must differ from the running engine or the row would grade as corruption
# instead of benign drift — asserted at build time rather than trusted.
_OLDER_ENGINE = "1.0.0"


@dataclass(frozen=True)
class Station:
    """One machine in the fixture: the folder it writes into (``""`` for the
    study root, the single-station case), the label the researcher gave it,
    and its per-install UUID. Two stations may share a label (§9.2 row 6) —
    the UUID is what tells them apart."""

    folder: str
    label: str
    machine_uuid: str


# α and α′ share the label 'lab-01' on two different machines — the duplicate
# station label the Hub must catch (§9.2 row 6).
ALPHA = Station("lab-01", "lab-01", "aaaaaaaa-0000-4000-8000-00000000000a")
ALPHA_PRIME = Station("lab-01-second", "lab-01", "aaaaaaaa-0000-4000-8000-00000000002a")
BETA = Station("lab-02", "lab-02", "bbbbbbbb-0000-4000-8000-00000000000b")
GAMMA = Station("lab-03", "lab-03", "cccccccc-0000-4000-8000-00000000000c")


@dataclass(frozen=True)
class Fixture:
    """A built study: where it lives, what to hand ``ingest``, and how to reach
    any planted session's files by the hazard name it was planted for."""

    root: Path
    slug: str
    sources: list[Path]
    sessions: dict[str, str] = field(default_factory=dict)
    stems: dict[str, Path] = field(default_factory=dict)

    def record(self, name: str, session_id: str, events_path: str) -> None:
        """Note where the hazard named ``name`` was planted. The stem is
        recovered from the emitted filename rather than recomposed, so the
        fixture reads the grammar back exactly as the Hub does (§9.3)."""
        self.sessions[name] = session_id
        events = Path(events_path)
        self.stems[name] = events.with_name(
            events.name.removesuffix("_events.jsonl")
        )

    def file(self, name: str, kind: str) -> Path:
        """One of a session's four files by hazard name and ``kind`` — the
        Hub's own vocabulary for the four (``events.jsonl``, ``metrics.json``,
        ``config.json``, ``session.json``; see ``sidecar.naming.SESSION_FILE``).
        Returns the path whether or not it exists: a *removed* file is itself a
        planted hazard, and the tests assert on its absence."""
        stem = self.stems[name]
        return stem.with_name(f"{stem.name}_{kind}")


# ── Deterministic session content ────────────────────────────────────────────


_PUMP_PLAN: dict[str, list[int]] = {
    "purple": [9, 11, 10, 13, 12, 14, 11, 12, 13, 15],
    "teal": [4, 5, 6, 5, 7, 6, 5, 6, 4, 5],
    "orange": [1, 2, 3, 2, 2, 3, 1, 2, 2, 3],
}


def _events(ordinal: int) -> list[GameEvent]:
    """One participant's session: the shared pump plan shifted by ``ordinal``
    so no two sessions score alike, paced like a real participant (300 ms
    between actions) so nothing trips the QC latency rules. Every third
    balloon pops — a fixture without explosions would not exercise the
    collected-only metrics. Pure arithmetic, so it never varies between runs.
    """
    events: list[GameEvent] = []
    t = 0.0
    balloon = 0
    for color, plan in _PUMP_PLAN.items():
        for index, base in enumerate(plan):
            balloon += 1
            pumps = max(1, base + (ordinal + index) % 3 - 1)
            for _ in range(pumps):
                t += 300.0
                events.append(
                    GameEvent(
                        timestamp=t, type="pump", payload=EventPayload(color=color)
                    )
                )
            t += 300.0
            outcome = "explode" if balloon % 3 == 0 else "collect"
            events.append(
                GameEvent(timestamp=t, type=outcome, payload=EventPayload(color=color))
            )
    return events


# ── Driving the real emission path ───────────────────────────────────────────


@contextmanager
def _pinned_clock(stamp: datetime) -> Iterator[None]:
    """Pin the emission path's clock seams (I6, §9.5) to one synthetic instant.

    Two files carry a live timestamp: the session's filename stem — the only
    place its ``timestamp_utc`` is persisted (§9.3) — and the superseded-config
    copy the provenance step records when a folder's sessions ran under more
    than one design, which this fixture plants on purpose.
    """
    def pinned() -> datetime:
        return stamp

    originals = {module: module._utc_now for module in (app_module, provenance)}
    for module in originals:
        module._utc_now = pinned
    try:
        yield
    finally:
        for module, original in originals.items():
            module._utc_now = original


@contextmanager
def _as_station(machines: Path, station: Station) -> Iterator[None]:
    """Impersonate one machine: its own station settings file, pre-seeded with
    a fixed UUID so nothing calls ``uuid4``. ``BART_STATION_FILE`` is what the
    sidecar reads, so this is the same identity path production takes. The
    settings file is keyed by machine UUID — the one thing that is unique per
    machine even when two of them share a label."""
    machines.mkdir(parents=True, exist_ok=True)
    path = machines / f"{station.machine_uuid}.json"
    path.write_text(
        StationIdentity(
            station_id=station.label, machine_uuid=station.machine_uuid
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )
    previous = os.environ.get("BART_STATION_FILE")
    os.environ["BART_STATION_FILE"] = str(path)
    try:
        yield
    finally:
        if previous is None:
            del os.environ["BART_STATION_FILE"]
        else:
            os.environ["BART_STATION_FILE"] = previous


class _Emitter:
    """Writes the fixture's sessions through the live path, one synthetic
    minute apart, recording where each landed so hazards can be planted on the
    files afterwards."""

    def __init__(self, root: Path, machines: Path, title: str, standalone: bool):
        self.root = root
        self.machines = machines
        self.title = title
        self.standalone = standalone
        self.ordinal = 0
        self.fixture = Fixture(root=root, slug=slug(title), sources=[])

    def write(
        self,
        station: Station,
        name: str,
        *,
        candidate_id: str | None = None,
        **config_over: object,
    ) -> WriteOutputResponse:
        """One session, exactly as that station's sidecar would have written
        it: the study config it ran under, its own station identity, its own
        timestamp. ``config_over`` is the study *design* this station ran (a
        different currency, language, metrics mode, schema version) — never a
        defect; defects are planted on the files afterwards."""
        out_dir = self.root / station.folder if station.folder else self.root
        config = {
            **DEFAULT_TASK_CONFIG.model_dump(mode="json"),
            "title": self.title,
            "output_dir": str(out_dir),
            "standalone": self.standalone,
            **config_over,
        }
        self.ordinal += 1
        session_id = f"sess-{name}"
        with _as_station(self.machines, station), _pinned_clock(
            _EPOCH + timedelta(minutes=self.ordinal)
        ):
            written = app_module.write_output(
                WriteOutputRequest(
                    session=GameSession(
                        session_id=session_id,
                        game_type="BART_RISK",
                        candidate_id=candidate_id or f"P-{name}",
                        events=_events(self.ordinal),
                    ),
                    config=TaskConfig.model_validate(config),
                )
            )
        self.fixture.record(name, session_id, written.events)
        return written


# ── Planting hazards on the written files ────────────────────────────────────


def _rewrite_json(path: Path, data: dict[str, object]) -> None:
    """Put a file back after damaging it — the shape the emission path writes
    its JSON in, so only the planted change distinguishes the file."""
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _strip_engine_stamp(path: Path) -> None:
    """Age a session envelope to before the engine stamp existed (§9.2 row 12):
    the key is *absent*, as it is in real pre-stamp data — not present-and-null,
    which is a file this instrument has never written."""
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("engine", None)
    _rewrite_json(path, data)


def _restamp_engine(path: Path, version: str) -> None:
    """Claim a session was scored by a different engine version — the fact the
    verify pass grades a metrics divergence on (§6.6)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    data["engine"] = {
        "app_version": version,
        "engine_version": version,
        "platform": "fixture-platform",
    }
    _rewrite_json(path, data)


def _corrupt_metrics(path: Path) -> None:
    """Make the stored metrics disagree with what the events re-score to —
    the divergence the verify pass grades on the engine stamp (§6.6). One
    scalar is enough; the grading is about *whether* they differ."""
    stored = json.loads(path.read_text(encoding="utf-8"))
    _rewrite_json(path, {**stored, "total_pumps": stored["total_pumps"] + 1})


def _copy_session(written: WriteOutputResponse, dest: Path) -> Path:
    """Byte-copy one session's four files into another folder — a sneakernet
    copy, the shape both duplicate hazards (§9.2 rows 2–3) take."""
    dest.mkdir(parents=True, exist_ok=True)
    for source in (written.events, written.metrics, written.config, written.session):
        shutil.copy(source, dest)
    return dest / Path(written.events).name


# ── The two studies ──────────────────────────────────────────────────────────


def build_clean_equivalence(base: Path) -> Fixture:
    """The equivalence study (§9.1): one station, ``standalone=False``, three
    clean sessions and no hazards. The live study-wide CSVs the emission path
    appends here are the gate's reference — they cannot be committed, because
    [T05] §5f requires the *current* ``write_output`` to produce both sides."""
    root = base / CLEAN_STUDY
    emitter = _Emitter(root, base / "machines", CLEAN_STUDY, standalone=False)
    bench = Station("", "bench-1", "dddddddd-0000-4000-8000-00000000000d")
    for name in ("clean-1", "clean-2", "clean-3"):
        emitter.write(bench, name)
    fixture = emitter.fixture
    fixture.sources.append(root)
    return fixture


def build_hazard_suite(base: Path) -> Fixture:
    """The hazard study (§9.1–§9.2): one slug, four stations, every row of the
    hazard table planted on its own session so each defect owns exactly one
    report line. Stations run Standalone Mode — the multi-station deployment
    the Hub exists for — so no station holds a study-wide CSV.

    Two report lines are *derived* rather than planted: rows 4 and 5 need one
    colliding pair to share a fixed seed and another to share none, so the
    study necessarily also drifts on ``seed`` — and that drift is itself a
    finding. The census test owns that arithmetic.

    Write order carries one invariant: the first session written into a folder
    freezes that folder's design record, and a frozen record whose *pooling*
    fields match no pooled session is itself a finding (§5.4). Every folder
    here therefore opens with a session whose design is pooling-compatible;
    the language drift (row 13) is planted after γ's first session, never as
    it.
    """
    assert _OLDER_ENGINE != scoring.__version__, (
        f"the cross-version verify hazard needs an engine version other than "
        f"the running {scoring.__version__}"
    )
    root = base / HAZARD_STUDY
    emitter = _Emitter(root, base / "machines", HAZARD_STUDY, standalone=True)
    write = emitter.write

    # ── α (lab-01) ───────────────────────────────────────────────────────────
    write(ALPHA, "clean-1")  # row 1: the untouched control

    # row 2: an identical sneakernet copy — collapses silently, as one line.
    identical = write(ALPHA, "dup-identical")
    _copy_session(identical, root / ALPHA_PRIME.folder)

    # row 3: the same session with different ground truth in the other copy —
    # the Hub must never guess which copy is authoritative.
    divergent = write(ALPHA, "dup-divergent")
    twin_events = _copy_session(divergent, root / ALPHA_PRIME.folder)
    with twin_events.open("a", encoding="utf-8") as fh:
        fh.write(
            GameEvent(
                timestamp=99999.0, type="pump", payload=EventPayload(color="teal")
            ).model_dump_json()
            + "\n"
        )

    # rows 4–5: one participant ID on two stations, twice — once with a shared
    # fixed seed (identical balloon sequences → not independent), once without.
    write(ALPHA, "collide-seed-a", candidate_id="P-COLLIDE-SEED", seed=777)
    write(ALPHA, "collide-free-a", candidate_id="P-COLLIDE-FREE")

    # row 10: stored metrics disagree under the *running* engine — the loud
    # tier, since an identical engine on identical events must reproduce.
    corrupt = write(ALPHA, "verify-corrupt")
    _corrupt_metrics(Path(corrupt.metrics))

    # rows 15, 18: ground truth gone, and a config that cannot be read at all.
    removed_events = write(ALPHA, "missing-events")
    Path(removed_events.events).unlink()
    truncated = write(ALPHA, "truncated-json")
    Path(truncated.config).write_text('{"incomplete":', encoding="utf-8")

    # ── α′ (a second machine also labeled lab-01) ────────────────────────────
    # row 6: its own session gives the folder a provenance record claiming the
    # shared label — the machine UUID is what exposes the collision.
    write(ALPHA_PRIME, "dup-label")

    # ── β (lab-02) ───────────────────────────────────────────────────────────
    write(BETA, "drift-currency", currency="TRY")  # row 7: notable, pools
    write(BETA, "mode-classic", metrics_mode="classic")  # row 8: unifies
    write(BETA, "collide-seed-b", candidate_id="P-COLLIDE-SEED", seed=777)

    # row 11: stored metrics disagree, but under an older engine — benign
    # drift, and the stamp is what makes that gradable.
    drifted = write(BETA, "verify-drift")
    _corrupt_metrics(Path(drifted.metrics))
    _restamp_engine(Path(drifted.session), _OLDER_ENGINE)

    write(BETA, "future-schema", schema_version="2.0")  # row 14: held

    # row 16: the data is intact, only the stored scores are gone — re-scored
    # with nothing to verify against, which is a clean outcome, not a hold.
    removed_metrics = write(BETA, "missing-metrics")
    Path(removed_metrics.metrics).unlink()

    # ── γ (lab-03) ───────────────────────────────────────────────────────────
    write(GAMMA, "schema-old", schema_version="1.0")  # row 9: pooled, flagged
    write(GAMMA, "collide-free-c", candidate_id="P-COLLIDE-FREE")

    # row 12: metrics disagree on data written before the stamp existed — the
    # Hub cannot tell drift from corruption, and says so.
    ungraded = write(GAMMA, "verify-ungraded")
    _corrupt_metrics(Path(ungraded.metrics))
    _strip_engine_stamp(Path(ungraded.session))

    write(GAMMA, "drift-lang", language="tr")  # row 13: forces a partition

    # row 17: identity gone — the filename alone cannot say which session this
    # is, or what condition it ran under.
    removed_session = write(GAMMA, "missing-session")
    Path(removed_session.session).unlink()

    # The loose foreign export: the Hub must resist parsing it and simply say
    # it skipped it, proving the §10 boundary.
    (root / GAMMA.folder / "bart_export.csv").write_text(
        "subjID,trial,pumps,exploded\n1001,1,12,0\n1001,2,8,1\n", encoding="utf-8"
    )

    fixture = emitter.fixture
    fixture.sources.extend(
        root / station.folder
        for station in (ALPHA, ALPHA_PRIME, BETA, GAMMA)
    )
    return fixture
