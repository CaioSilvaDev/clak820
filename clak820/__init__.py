"""Painel de consumo do Claude Code na tela TFT do AJAZZ AK820 Pro."""

import os
from pathlib import Path

__version__ = "0.1.0"


def data_dir() -> Path:
    """Pasta onde ficam state.json, daemon.json, config.json e o log."""
    base = os.environ.get("CLAK820_HOME")
    if base:
        path = Path(base)
    else:
        path = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "clak820"
    path.mkdir(parents=True, exist_ok=True)
    return path
