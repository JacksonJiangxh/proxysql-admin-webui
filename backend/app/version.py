"""Project version — read dynamically from the root VERSION file.

The VERSION file at the project root is the single source of truth.
This module locates it automatically regardless of how the app is run:

- Source checkout: walks up from this file until it finds VERSION
- PyInstaller (frozen): reads from sys._MEIPASS/VERSION
- Docker: VERSION is copied alongside the backend code via Dockerfile

Usage::

    from app.version import get_version
    print(get_version())  # -> "1.0.0"
"""

import sys
from pathlib import Path


def _find_version_file() -> Path:
    """Locate the VERSION file.

    Resolution order:
    1. PyInstaller bundle (``sys._MEIPASS`` + ``VERSION``)
    2. Walk upward from this source file (max 5 levels)
    """
    # PyInstaller single-file bundle
    if getattr(sys, "frozen", False):
        candidate = Path(sys._MEIPASS) / "VERSION"
        if candidate.is_file():
            return candidate

    # Source checkout / Docker — walk up from this file
    current = Path(__file__).resolve().parent
    for _ in range(5):
        candidate = current / "VERSION"
        if candidate.is_file():
            return candidate
        current = current.parent

    raise FileNotFoundError(
        "VERSION file not found. Ensure a VERSION file exists at the project root."
    )


def get_version() -> str:
    """Return the current project version (e.g. ``"1.0.0"``)."""
    try:
        return _find_version_file().read_text().strip()
    except FileNotFoundError:
        return "0.0.0"
