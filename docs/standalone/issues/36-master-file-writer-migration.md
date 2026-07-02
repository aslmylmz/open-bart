# 36 — Master-file writer: header-versioned append with auto-migrate

**Prefactor (sidecar) · depends on: none**

Status: ready-for-agent

## Context

The Master CSV is appended one flat row per session by the sidecar, and the
column order is canonical from the config. Phase 7 adds columns to that
contract three separate times (condition — 37, QC flags — 40, payout — 41) and
introduces a second study-wide append file (the trials CSV — 39). Today the
append path assumes the header on disk always matches the row being written:
a lab that upgrades the app mid-study would get silently misaligned columns —
the exact "garbage data" failure pillar 2 of the client brief exists to
prevent.

Decision from the roadmap grill: **auto-migrate with a backup**. One file per
study stays the invariant; old rows get honest blanks in new columns.

## Scope

- [ ] Extract the Master CSV append into a reusable header-versioned writer
      (the trials CSV in 39 will be its second caller).
- [ ] On append, compare the existing file's header to the current schema:
      exact match → plain append, as today.
- [ ] On mismatch: copy the existing file to a timestamped backup alongside
      it, rewrite the file with the current header (rows from the old file
      keep their values by column *name*; new columns are blank), then append
      the new row.
- [ ] If the file is locked or unwritable (e.g. open in Excel on Windows):
      never lose the session — write the row to a timestamped sibling file and
      surface a readable warning in the write-output response.
- [ ] Never reorder or drop data: migration is add-columns-only; a header with
      *unknown* columns (file from a newer app) also falls back to the sibling
      file rather than rewriting.
- [ ] Document the migration/backup behavior in the data-outputs docs page.

## Acceptance

- Appending to a file with the current header is byte-for-byte the same
  behavior as before.
- Appending to a file with an older header produces: a backup copy, a migrated
  file with the new header where pre-upgrade rows have blanks in new columns,
  and the new row appended — verified by tests.
- A locked file yields a sibling file with the session row and a warning; no
  exception, no lost session.
- `pytest`, `npm test`, `tsc`, `vite build` stay green.

## Comments

**2026-07-02 — implemented (TDD).** The append lives in a new reusable module,
`app/sidecar/versioned_csv.py` (`append_row(path, row) -> AppendResult`), ready
for the trials CSV in 39. Behavior as decided: exact header → plain append;
older header → timestamped `*_backup_*` copy + auto-migrate by column name with
honest blanks; unknown columns (newer app) → untouched file + timestamped
`*_unmerged_*` sibling; locked/unwritable **or unparseable** file (e.g. Excel
re-saved as non-UTF-8 — found during review, beyond the issue's scope list but
required by "never lose the session") → same sibling fallback. All fallbacks
return a readable warning surfaced via a new `warnings` list on
`WriteOutputResponse` (the TS client ignores response bodies, so no client
change). Covered by `tests/test_versioned_csv.py` (6 writer-contract tests) +
2 endpoint tests in `tests/test_sidecar.py`; migration/backup behavior
documented in `docs/data_outputs.md`. Gates: pytest 115 ✅, npm test 76 ✅,
tsc ✅, vite build ✅.
