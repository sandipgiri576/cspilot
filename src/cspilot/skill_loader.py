from __future__ import annotations

from pathlib import Path


class SkillLoader:
    """Load bundled domain Markdown; an explicit directory supports local extensions."""

    def __init__(self, directory: str | Path | None = None):
        self.directory = Path(directory) if directory else Path(__file__).with_name("skills")

    def load(self, profile: str, role: str = "planner") -> str:
        if not profile.replace("_", "").isalnum() or role not in {"planner", "reporter"}:
            raise ValueError("Invalid skill profile or role.")
        sections = []
        for name in dict.fromkeys(("common", profile)):
            path = self.directory / f"{name}.md"
            if not path.is_file():
                continue
            active = False
            lines = []
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("## "):
                    active = line[3:].strip().lower() == role
                elif active:
                    lines.append(line)
            if lines:
                sections.append("\n".join(lines).strip())
        return "\n\n".join(sections)

    def report_fields(self, profile: str) -> set[str]:
        return {
            line.removeprefix("- field:").strip()
            for line in self.load(profile, "reporter").splitlines()
            if line.startswith("- field:")
        }
