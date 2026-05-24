from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

RunStatus = Literal["ok", "failed", "skipped"]


class StructureSummary(BaseModel):
    path: Path
    formula: str
    natoms: int
    charge: float | None = None
    pbc: tuple[bool, bool, bool]
    cell: list[list[float]]
    center_of_mass: list[float]


class CommandResult(BaseModel):
    command: str
    status: RunStatus
    run_dir: Path
    input_path: Path
    created_at: datetime = Field(default_factory=datetime.now)
    structure: StructureSummary | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None


class ProcessResult(BaseModel):
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
