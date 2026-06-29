"""Offline scoring sidecar for the standalone BART instrument.

A localhost-only FastAPI app that wraps the installed ``scoring`` package (SPEC
§9). It is not pip-installed; PyInstaller freezes it from source and it imports
``scoring`` at runtime, so there is no code duplication.
"""
