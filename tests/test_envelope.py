"""The per-session envelope: ``SessionEnvelope`` + server-authored
``EngineStamp`` (DATA-SPEC §3/§3.1, Decision A).

Per-session identity + station + engine provenance live in one purpose-built
model, cleanly separated from the gameplay ``GameSession``, and written to
``*_session.json``. The engine stamp is a write-time fact — the sidecar
records what actually ran, ignoring anything a client claims — so every
session stays gradable at the Hub without backfilling. These tests exercise
the model's load path (old data → ``None``, "ungraded") and the stamp through
the sidecar's public ``/write-output`` surface.
"""

from __future__ import annotations

import json
import platform
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

import scoring
from scoring.schemas import SessionEnvelope

from tests.test_sidecar import client
from tests.test_station import _write_session


def test_pre_envelope_session_json_loads_as_ungraded():
    """Defaults-as-migration (DATA-SPEC §3.1): a v1.0.0 ``session.json`` —
    written before the envelope carried station or engine provenance — loads
    with ``engine``/``station_id``/``id_source`` as ``None`` ("ungraded").
    No schema_version bump: the envelope's new fields are additive/optional."""
    legacy = {
        "session_id": "sess-1",
        "game_type": "BART_RISK",
        "candidate_id": "cand-1",
        "condition": None,
        "duplicate_acknowledged": False,
        "practice": False,
    }
    envelope = SessionEnvelope.model_validate(legacy)
    assert envelope.engine is None
    assert envelope.station_id is None
    assert envelope.id_source is None
    assert envelope.session_id == "sess-1"
    assert envelope.candidate_id == "cand-1"


def test_write_output_stamps_the_engine_that_actually_ran(tmp_path):
    """Every session.json carries an ``engine`` block naming the app version,
    engine version, and platform that recorded it (DATA-SPEC §3.1) — the
    write-time fact that keeps the session gradable at the Hub and that no
    study-level record can recover per-station."""
    out = _write_session(tmp_path)
    envelope = json.loads(Path(out["session"]).read_text("utf-8"))
    assert envelope["engine"] == {
        "app_version": scoring.__version__,
        "engine_version": scoring.__version__,
        "platform": platform.platform(),
    }


def test_a_client_supplied_engine_stamp_is_overwritten(tmp_path):
    """The stamp means "what actually ran": a client claiming a bogus engine
    version gets it replaced with the sidecar's own — the field is
    server-authored, never trusted from the request."""
    out = _write_session(
        tmp_path,
        engine={
            "app_version": "0.0.0-forged",
            "engine_version": "0.0.0-forged",
            "platform": "EtchASketch",
        },
    )
    envelope = json.loads(Path(out["session"]).read_text("utf-8"))
    assert envelope["engine"]["engine_version"] == scoring.__version__
    assert envelope["engine"]["platform"] == platform.platform()


def test_the_envelope_carries_the_station_when_set(tmp_path):
    """`station_id` is the envelope's per-session attribution (DATA-SPEC §2.3):
    the recording station's label when one is configured, an explicit None in
    single-station mode — so merged folders stay attributable row by row."""
    unset = _write_session(tmp_path)
    envelope = json.loads(Path(unset["session"]).read_text("utf-8"))
    assert envelope["station_id"] is None

    client.post("/station", json={"station_id": "S1"})
    stamped = _write_session(tmp_path, candidate_id="cand-2")
    envelope = json.loads(Path(stamped["session"]).read_text("utf-8"))
    assert envelope["station_id"] == "S1"


def test_the_envelope_records_how_the_id_was_entered_under_auto_id(tmp_path):
    """`id_source` is the client's honest per-session report of which path
    produced `candidate_id` (DATA-SPEC §3.2) — it is what makes the Hub's
    generated-collision tier (§5.3) exact rather than approximate, since a
    study-level flag alone cannot tell a hand-typed ID in an auto-ID study
    from a generated one."""
    auto = {"auto_participant_id": True}
    generated = _write_session(tmp_path, auto, id_source="generated")
    assert json.loads(Path(generated["session"]).read_text("utf-8"))["id_source"] == (
        "generated"
    )

    typed = _write_session(tmp_path, auto, candidate_id="cand-2", id_source="manual")
    assert json.loads(Path(typed["session"]).read_text("utf-8"))["id_source"] == "manual"


def test_id_source_stays_absent_while_auto_id_is_off(tmp_path):
    """With the toggle off the field means nothing — every ID is hand-typed —
    so the envelope stays byte-identical to pre-auto-ID data even if a client
    sends a value (DATA-SPEC §3.2: "present only when the toggle is on")."""
    out = _write_session(tmp_path, id_source="generated")
    assert json.loads(Path(out["session"]).read_text("utf-8"))["id_source"] is None


def test_id_source_admits_only_the_two_entry_paths():
    """The field is a two-valued fact about the ID screen, not free text: a
    third value would silently weaken the Hub's generated-collision tier,
    which reads it as an exact signal (DATA-SPEC §5.3)."""
    envelope = {
        "session_id": "sess-1",
        "game_type": "BART_RISK",
        "candidate_id": "482719300",
    }
    assert SessionEnvelope.model_validate(
        {**envelope, "id_source": "generated"}
    ).id_source == "generated"
    with pytest.raises(ValidationError):
        SessionEnvelope.model_validate({**envelope, "id_source": "auto"})


def test_data_dictionary_documents_the_envelope_and_engine_fields(tmp_path):
    """The dictionary's Session envelope section is generated from
    ``SessionEnvelope`` itself, so the provenance fields — and the nested
    ``engine`` block's — are documented without being described twice."""
    _write_session(tmp_path)
    dictionary = next(tmp_path.glob("*_data_dictionary.md")).read_text("utf-8")
    section = dictionary.split("### Session envelope", 1)[1].split("\n### ", 1)[0]
    fields = set(re.findall(r"^\| `([^`]+)` \|", section, flags=re.M))
    assert {
        "session_id",
        "candidate_id",
        "condition",
        "station_id",
        "id_source",
        "engine",
        "app_version",
        "engine_version",
        "platform",
    } <= fields
