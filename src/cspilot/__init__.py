"""cspilot package."""

from __future__ import annotations

from importlib.metadata import version

try:
    __version__ = version("cspilot")
except Exception:
    __version__ = "0.0.0"
