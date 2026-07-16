"""The per-machine station identity setting (DATA-SPEC §2.3).

Multi-station studies need every output attributable to the machine that
produced it. Two facts make that possible, both persisted here as a small
per-machine settings file — outside ``study.json``, which is distributed
identically to every station and so can never carry a per-machine value:

- **``station_id``** — the researcher's label for this machine (``S1``,
  ``lab-A-03``), entered once at machine setup and stamped into the output
  filename stem, the session envelope, and the provenance record.
- **``machine_uuid``** — a random per-install UUID generated on first run.
  Offline, no machine can know another's label, so duplicate labels cannot be
  prevented at entry; the UUID lets the Hub tell two machines both labeled
  ``S1`` (different UUIDs → flag) apart from one machine's legitimate data.

The sidecar owns all file I/O, so the settings file lives here rather than in
the webview: a JSON file under the platform's per-user app-data directory,
overridable via ``BART_STATION_FILE`` (tests point it at a scratch path so
they never touch the machine's real identity).
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

from pydantic import BaseModel


class StationIdentity(BaseModel):
    """What this machine knows about itself: the researcher-entered station
    label (``None`` until machine setup) and the per-install UUID."""

    station_id: str | None = None
    machine_uuid: str


def settings_path() -> Path:
    """Where this machine's station settings live.

    ``BART_STATION_FILE`` overrides; otherwise the platform's conventional
    per-user app-data directory, namespaced ``open-bart``.
    """
    override = os.environ.get("BART_STATION_FILE")
    if override:
        return Path(override)
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "open-bart" / "station.json"


def load_station() -> StationIdentity:
    """Read the persisted identity, minting the machine UUID on first run.

    Never raises: an unreadable file reads as a fresh install, and if the
    minted UUID cannot be persisted it is still returned so the session can
    proceed — attribution degrades, data collection never blocks.
    """
    path = settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    identity = StationIdentity(
        station_id=str(data.get("station_id") or "") or None,
        machine_uuid=str(data.get("machine_uuid") or ""),
    )
    if not identity.machine_uuid:
        identity.machine_uuid = str(uuid.uuid4())
        try:
            _persist(path, identity)
        except OSError:
            pass
    return identity


def store_station_id(station_id: str | None) -> StationIdentity:
    """Persist a new station label (``None`` clears it) beside the machine
    UUID and return the resulting identity. Validation is the caller's job —
    this module only owns storage. Raises ``OSError`` when the setting cannot
    be written: a label that silently vanishes on restart is worse than an
    error the researcher sees at setup time."""
    identity = load_station()
    identity.station_id = station_id
    _persist(settings_path(), identity)
    return identity


def _persist(path: Path, identity: StationIdentity) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(identity.model_dump_json(indent=2), encoding="utf-8")
