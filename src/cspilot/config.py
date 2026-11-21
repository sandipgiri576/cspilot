"""Load environment-backed CSPilot runtime settings."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Store deterministic executable paths and the default runs directory."""

    runs_dir: Path = Field(default=Path("runs"))
    xtb_command: str = Field(default="xtb")
    orca_command: str = Field(default="orca")
    nwpesse_command: str = Field(default="nwpesse")
    multiwfn_command: str = Field(default="Multiwfn_noGUI")
    orca_2mkl_command: str = Field(default="orca_2mkl")


def load_settings(env_file: Path | str = ".env.cspilot") -> Settings:
    """Load CSPilot settings from a dotenv file and environment variables.

    Args:
        env_file: Dotenv file loaded before reading process environment values.

    Returns:
        Validated runtime settings.
    """
    load_dotenv(env_file)
    return Settings(
        runs_dir=Path(os.getenv("CSPILOT_RUNS_DIR", "runs")),
        xtb_command=os.getenv("XTB_COMMAND", "xtb"),
        orca_command=os.getenv("ORCA_COMMAND", "orca"),
        nwpesse_command=os.getenv("NWPESSE_BIN", "nwpesse"),
        multiwfn_command=os.getenv("MULTIWFN_COMMAND", "Multiwfn_noGUI"),
        orca_2mkl_command=os.getenv("ORCA_2MKL_COMMAND", "orca_2mkl"),
    )
