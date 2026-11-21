"""Load profile-specific Markdown guidance for planners and reporters."""

from __future__ import annotations

from pathlib import Path


class SkillLoader:
    """Load bundled domain Markdown; an explicit directory supports local extensions."""

    def __init__(self, directory: str | Path | None = None) -> None:
        """Initialize the loader with bundled or user-supplied skills.

        Args:
            directory: Directory containing ``common.md`` and profile files.
        """
        self.directory = Path(directory) if directory else Path(__file__).with_name("skills")

    def load(self, profile: str, role: str = "planner") -> str:
        """Load common and profile instructions for a role.

        Args:
            profile: Alphanumeric profile name.
            role: Either ``planner`` or ``reporter``.

        Returns:
            Combined Markdown instructions, or an empty string when absent.

        Raises:
            ValueError: If the profile name or role is unsafe.
        """
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
        """Return report field names declared by a profile skill."""
        return {
            line.removeprefix("- field:").strip()
            for line in self.load(profile, "reporter").splitlines()
            if line.startswith("- field:")
        }
