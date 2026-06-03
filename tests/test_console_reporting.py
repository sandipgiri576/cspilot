from __future__ import annotations

from rich.console import Console

from cspilot.agents.reporter import generate_report
from cspilot.ui.console import (
    print_banner,
    print_execution_summary,
    print_final_message,
    print_generated_files,
    print_plan_summary,
    print_verification_summary,
)


def test_rich_console_helpers_render(tmp_path):
    console = Console(record=True, width=100)
    workdir = tmp_path
    (workdir / "plan.json").write_text("{}", encoding="utf-8")
    (workdir / "execution_result.json").write_text("{}", encoding="utf-8")
    xyz = workdir / "optimized.xyz"
    xyz.write_text("1\noptimized\nH 0 0 0\n", encoding="utf-8")
    plan = {"steps": [{"tool": "inspect_structure", "args": {"xyz_path": "input.xyz"}}]}
    execution = {
        "success": True,
        "workdir": str(workdir),
        "steps": [{"tool_name": "inspect_structure", "success": True, "optimized_xyz": str(xyz)}],
    }
    verification = {"verified": True, "issues": []}

    print_banner(console)
    print_plan_summary(console, plan)
    print_execution_summary(console, execution)
    print_verification_summary(console, verification)
    print_generated_files(console, workdir, execution)
    print_final_message(console, "# Report\nDone")

    output = console.export_text()
    assert "CSPilot" in output
    assert "Created by Sandip Giri" in output
    assert "Your optimized geometry is available at:" in output


def test_generate_report_sections_and_html_fragment(tmp_path):
    execution = {"success": True, "workdir": str(tmp_path), "steps": []}
    verification = {"verified": True, "issues": []}

    markdown = generate_report("calculate water", {"steps": []}, execution, verification)
    html = generate_report("calculate water", {"steps": []}, execution, verification, html=True)

    for section in ("Welcome", "Task", "Workflow", "Results", "Generated Files", "Verification", "Notes"):
        assert f"## {section}" in markdown
    assert "Gibbs free energy: not found in parsed results." in markdown
    assert "HOMO-LUMO gap: not found in parsed results." in markdown
    assert html.startswith('<section class="cspilot-report">')
    assert "<h3>Workflow</h3>" in html
    assert "<table>" in html
    assert "```" not in html
