"""JOSS paper contract guards (issue 33).

The paper must describe the software as it ships: the standalone configurable
instrument, no pre-instrument leftovers, resolvable citations, JOSS word
bounds, and a figure that exists next to the manuscript.
"""

from __future__ import annotations

from pathlib import Path

PAPER_DIR = Path(__file__).resolve().parent.parent / "paper"
PAPER = (PAPER_DIR / "paper.md").read_text(encoding="utf-8")


def test_paper_describes_the_instrument_without_stale_claims():
    """The manuscript sells what ships: the offline configurable desktop
    instrument — and none of the pre-instrument repo's claims."""
    # stale: the client is a Vite SPA in a Tauri shell, and the engine is scipy-free
    assert "Next.js" not in PAPER
    assert "virtanen2020" not in PAPER  # the scipy citation
    assert "scipy" not in PAPER.lower()

    # present: the instrument story
    assert "Tauri" in PAPER
    assert "hazard famil" in PAPER.lower()
    assert "offline" in PAPER.lower()
    assert "Master CSV" in PAPER


def test_every_citation_resolves_and_every_bib_entry_is_cited():
    """A missing bib key breaks the JOSS build; an uncited entry is dead
    weight. The manuscript and bibliography must match exactly."""
    import re

    bib = (PAPER_DIR / "paper.bib").read_text(encoding="utf-8")
    bib_keys = set(re.findall(r"@\w+\{([^,]+),", bib))

    body = PAPER.split("---", 2)[2]  # skip the YAML front matter
    cited = set(re.findall(r"@([A-Za-z][\w-]*)", body))

    assert cited - bib_keys == set(), "citations missing from paper.bib"
    assert bib_keys - cited == set(), "uncited entries in paper.bib"


def test_paper_length_is_within_joss_bounds():
    """JOSS asks for 250-1000 words of main text."""
    body = PAPER.split("---", 2)[2]
    words = len(body.split())

    assert 250 <= words <= 1000, f"paper body is {words} words"


def test_paper_figures_exist_next_to_the_manuscript():
    """JOSS compiles figures relative to paper.md; a broken image path
    fails the build."""
    import re

    images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", PAPER, flags=re.DOTALL)

    assert images, "the paper should include the hazard-families figure"
    missing = [img for img in images if not (PAPER_DIR / img).exists()]
    assert missing == []


def test_paper_build_workflow_compiles_the_manuscript():
    """CI compiles paper.md to a PDF artifact with the Open Journals draft
    action whenever the paper changes."""
    import yaml

    wf_path = PAPER_DIR.parent / ".github" / "workflows" / "paper.yml"
    workflow = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
    text = wf_path.read_text(encoding="utf-8")

    steps = [s for job in workflow["jobs"].values() for s in job["steps"]]
    uses = [s.get("uses", "") for s in steps]

    assert any("openjournals" in u for u in uses), "missing draft-pdf action"
    assert any("upload-artifact" in u for u in uses), "PDF must be uploaded"
    assert "paper/paper.md" in text
    assert (PAPER_DIR / "paper.md").exists()
