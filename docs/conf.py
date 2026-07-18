"""Sphinx configuration for the Dynamic Hazard Rate BART documentation."""

from __future__ import annotations

import os
import sys

# Make the project package importable for autodoc (resolve relative to this
# file, not the current working directory, so the build works from anywhere).
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _REPO_ROOT)

# ── Project information ──────────────────────────────────────────────────────

project = "Dynamic Hazard Rate BART"
author = "Ahmet Selim Yılmaz"
copyright = "2026, Ahmet Selim Yılmaz"  # noqa: A001

# The full version, including alpha/beta/rc tags.
release = "1.1.0"
version = "1.1"

# ── General configuration ────────────────────────────────────────────────────

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.mathjax",
    "myst_parser",
    "sphinx_copybutton",
]

# Heavy scientific libraries are imported lazily inside functions, so we mock
# them for autodoc. pydantic is installed for real so the schema models can be
# introspected.
autodoc_mock_imports = ["numpy", "scipy", "pandas", "matplotlib"]
autodoc_member_order = "bysource"
autodoc_typehints = "description"

napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_use_rtype = False

myst_enable_extensions = [
    "deflist",
    "colon_fence",
    "dollarmath",
    "amsmath",
    "tasklist",
]
myst_heading_anchors = 3

source_suffix = {
    ".md": "markdown",
    ".rst": "restructuredtext",
}

exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    # Gitignored maintainer notes (issue 70 removed them from tracking, but
    # they persist in local working trees): absent on CI/Read the Docs, where
    # these patterns are no-ops, yet without them a local build drowns in
    # toc.not_included warnings and the 0-warning docs gate fails.
    "adr/**",
    "agents/**",
    # The committed sample dataset (DATA-SPEC §9.5) is *data*, not prose: its
    # generated data dictionaries and ingestion report are artifacts a reader
    # opens in the repo, not pages in the manual — and without this the
    # 0-warning docs gate drowns in toc.not_included for every one of them.
    "samples/**",
    "standalone/issues/**",
    "standalone/QUALITY-KAIZEN.md",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "pydantic": ("https://docs.pydantic.dev/latest/", None),
}

# ── HTML output ──────────────────────────────────────────────────────────────

html_theme = "furo"
html_title = "Dynamic Hazard Rate BART"
html_show_sourcelink = True

html_theme_options = {
    "source_repository": "https://github.com/aslmylmz/open-bart/",
    "source_branch": "main",
    "source_directory": "docs/",
}

# ── LaTeX / PDF output (xelatex handles the Turkish characters safely) ───────

latex_engine = "xelatex"
