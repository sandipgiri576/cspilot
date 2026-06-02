from __future__ import annotations

from pathlib import Path
from typing import Any

REQUIRED_DOCS = {
    "docs/installation.md",
    "docs/configuration.md",
    "docs/cli_usage.md",
    "docs/agent_usage.md",
    "docs/workflows.md",
    "docs/tools.md",
    "docs/agapi.md",
    "docs/development.md",
    "docs/roadmap.md",
    "docs/safety.md",
    "docs/examples.md",
    "docs/updating_docs.md",
}
CLI_COMMAND_MARKERS = {
    "agent",
    "plan",
    "execute",
    "run",
    "inspect",
    "xtb-opt",
    "orca-sp",
    "mace-opt",
    "workflow xtb-orca-sp",
    "workflow mace-orca",
    "workflow xtb-orca-freq",
    "docs-check",
    "stk",
    "stk-build-smiles",
    "stk-polymer",
    "stk-xtb",
    "stk building-block-smiles",
    "stk building-block-file",
    "stk linear-polymer",
    "stk replace-smiles",
    "stk export-xyz",
    "nwpesse-search",
    "greencatai",
    "greencatai design-mbh",
    "search",
}
FORBIDDEN_TEMPLATE_MARKERS = {
    "example_docs",
    "This is the cspilot package!",
    "YourName",
}


def check_documentation_consistency(root: str | Path = ".") -> dict[str, Any]:
    """Run lightweight documentation consistency checks."""
    root_path = Path(root)
    issues: list[str] = []

    for relative in sorted(REQUIRED_DOCS):
        if not (root_path / relative).exists():
            issues.append(f"Missing documentation file: {relative}")

    cli_usage = root_path / "docs" / "cli_usage.md"
    if cli_usage.exists():
        text = cli_usage.read_text(encoding="utf-8")
        for marker in sorted(CLI_COMMAND_MARKERS):
            if marker not in text:
                issues.append(f"docs/cli_usage.md does not mention: {marker}")

    scan_paths = [
        root_path / "README.md",
        root_path / "docs",
        root_path / "mkdocs.yml",
        root_path / "_zensical.toml",
    ]
    for path in _iter_text_files(scan_paths):
        text = path.read_text(encoding="utf-8", errors="replace")
        for marker in FORBIDDEN_TEMPLATE_MARKERS:
            if marker in text:
                issues.append(f"Template marker '{marker}' remains in {path.relative_to(root_path)}")

    return {
        "success": not issues,
        "checked_root": str(root_path),
        "issues": issues,
        "required_docs": sorted(REQUIRED_DOCS),
        "cli_markers": sorted(CLI_COMMAND_MARKERS),
    }


def _iter_text_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(path.rglob("*.md")))
    return files
