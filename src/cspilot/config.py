from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field


class Settings(BaseModel):
    runs_dir: Path = Field(default=Path("runs"))
    xtb_command: str = Field(default="xtb")
    orca_command: str = Field(default="orca")
    nwpesse_command: str = Field(default="nwpesse")


def load_settings(env_file: Path | str = ".env.cspilot") -> Settings:
    load_dotenv(env_file)
    return Settings(
        runs_dir=Path(os.getenv("CSPILOT_RUNS_DIR", "runs")),
        xtb_command=os.getenv("XTB_COMMAND", "xtb"),
        orca_command=os.getenv("ORCA_COMMAND", "orca"),
        nwpesse_command=os.getenv("NWPESSE_BIN", "nwpesse"),
    )
