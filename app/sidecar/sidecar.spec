# PyInstaller spec for the full offline scoring sidecar.
#
# Freezes app/sidecar/__main__.py — the launcher that binds 127.0.0.1 on an
# ephemeral port, prints PORT=<n> to stdout, and serves the FastAPI app via uvicorn
# — into a single executable the Tauri shell bundles via `externalBin` (SPEC §10).
# This extends the hello-score freeze (issue 07) to the *full* sidecar
# (FastAPI + uvicorn + numpy), retiring the SPEC §18 risk #1 for the real binary.
#
# Build from the repo root:  pyinstaller app/sidecar/sidecar.spec
# Output:                    dist/bart-sidecar[.exe]

import os

from PyInstaller.utils.hooks import collect_submodules

# SPECPATH is injected by PyInstaller: the directory containing this spec.
script = os.path.join(SPECPATH, "__main__.py")

# Put app/ on the analysis path so the `sidecar` package resolves. The engine,
# the sidecar, and uvicorn import submodules dynamically enough that we collect
# them explicitly rather than relying on graph discovery.
pathex = [os.path.join(SPECPATH, "..")]
hiddenimports = (
    collect_submodules("scoring")
    + collect_submodules("sidecar")
    + collect_submodules("uvicorn")
)

a = Analysis(
    [script],
    pathex=pathex,
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # The engine is scipy-free (issue 05); keep these heavy libs out of the binary.
    excludes=["scipy", "matplotlib", "pandas"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="bart-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
