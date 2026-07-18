"""Hub CLI: the scriptable strip over the shared Hub core (I11).

``openbart hub <sources…> --out <dir>`` is a headless path to exactly what
the UI tab (I12) exposes (DATA-SPEC §7.5): ingest the read-only sources,
re-score every pooled session from ground truth, write the reconstructed
study-wide surfaces, and print the same rendered ingestion report the
destination file carries. No Hub logic lives here — the decisions are
``ingest``'s (I8), the rows are ``rebuild``'s (I9), the destination guards
are ``write_rebuild``'s (I10). The CLI adds only argument parsing, the
``--force`` replace confirmation (``is_prior_rebuild``, the headless stand-in
for the UI's confirm dialog), and the exit-code mapping:

- **0** — clean rebuild (or clean ``--dry-run``)
- **2** — held sessions present; the rebuild proceeded on the rest
- **3** — no study identifiable in any source; nothing to rebuild
- **4** — destination refused (inside a source / non-empty non-rebuild
  folder / prior rebuild without ``--force``); nothing written
- **64** — usage error (``EX_USAGE``); argparse's stock 2 would collide
  with the reserved "held sessions present", so a typo'd invocation can
  never read as a successful-but-held rebuild to a script

``openbart`` is the command's public name; in this repo it runs as
``python -m sidecar hub …`` and ships inside the frozen sidecar binary as
the same ``hub`` subcommand.
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from sidecar.hub import NoStudyError, ingest
from sidecar.hub_writer import (
    DestinationRefused,
    is_prior_rebuild,
    render_report,
    write_rebuild,
)
from sidecar.rebuild import rebuild


class _Parser(argparse.ArgumentParser):
    """An ArgumentParser whose usage errors exit 64 (``EX_USAGE``), not
    argparse's stock 2 — §7.5 reserves 2 for "held sessions present".
    Subparsers inherit this class, so the remap covers ``hub`` too."""

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(64, f"{self.prog}: error: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="openbart",
        description="Open BART researcher tools.",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="<command>")
    hub = commands.add_parser(
        "hub",
        help="rebuild study-wide outputs from assembled station folders",
        description=(
            "Ingest one or more read-only source folders, re-score every "
            "session from its recorded events, and write the reconstructed "
            "study-wide surfaces — printing the itemized ingestion report "
            "either way. Exit codes: 0 clean, 2 held sessions present, "
            "3 no study identifiable, 4 destination refused."
        ),
    )
    hub.add_argument(
        "sources",
        nargs="+",
        metavar="<source>",
        help="read-only source folder(s) holding assembled station output",
    )
    hub.add_argument(
        "--out",
        metavar="<dir>",
        help=(
            "destination folder, wholly separate from every source "
            "(required unless --dry-run)"
        ),
    )
    hub.add_argument(
        "--mode",
        choices=("classic", "advanced"),
        help="rebuild-mode override (default: the study's configured mode)",
    )
    hub.add_argument(
        "--force",
        action="store_true",
        help="replace a prior rebuild in place",
    )
    hub.add_argument(
        "--dry-run",
        action="store_true",
        help="run ingestion and print the report; write nothing",
    )
    hub.set_defaults(parser=hub)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return _run_hub(args)


def _run_hub(args: argparse.Namespace) -> int:
    if args.out is None and not args.dry_run:
        args.parser.error("--out is required (omit it only with --dry-run)")
    if not args.dry_run and not args.force and is_prior_rebuild(args.out):
        print(
            f"openbart hub: refused: destination {args.out} holds a prior "
            f"Hub rebuild — pass --force to replace it in place",
            file=sys.stderr,
        )
        return 4
    try:
        report = ingest(args.sources)
    except NoStudyError as exc:
        print(f"openbart hub: {exc}", file=sys.stderr)
        return 3
    result = rebuild(report, args.mode)
    if args.dry_run:
        print(render_report(report, result))
        print("Dry run — nothing written.")
    else:
        try:
            receipt = write_rebuild(report, result, args.out)
        except DestinationRefused as exc:
            print(f"openbart hub: refused: {exc}", file=sys.stderr)
            return 4
        print(render_report(report, result))
        replaced = (
            " (replaced the prior rebuild in place)"
            if receipt.replaced_prior_rebuild
            else ""
        )
        print(f"Wrote {len(receipt.files)} file(s) to {receipt.destination}{replaced}")
        for name in receipt.files:
            print(f"  {name}")
    return 2 if report.held else 0
