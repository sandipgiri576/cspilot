from __future__ import annotations

import json
from pathlib import Path

from cspilot.agents import executor
from cspilot.tools.registry import normalize_tool_args, normalize_tool_result


def test_normalize_tool_result_dict_is_json_safe(tmp_path):
    result = normalize_tool_result("tool", {"success": True, "path": tmp_path / "file.xyz"})

    assert result == {"success": True, "path": str(tmp_path / "file.xyz")}


def test_normalize_tool_result_json_string():
    result = normalize_tool_result("tool", json.dumps({"success": True, "value": 3}))

    assert result == {"success": True, "value": 3}


def test_normalize_tool_result_plain_string():
    result = normalize_tool_result("tool", "completed")

    assert result == {"success": True, "tool": "tool", "message": "completed"}


def test_normalize_tool_result_path():
    result = normalize_tool_result("tool", Path("out.xyz"))

    assert result == {"success": True, "tool": "tool", "path": "out.xyz"}


def test_normalize_tool_result_none():
    result = normalize_tool_result("tool", None)

    assert result == {"success": False, "tool": "tool", "error": "Tool returned None"}


def test_normalize_tool_result_bool_and_number():
    assert normalize_tool_result("tool", True) == {"success": True, "tool": "tool", "value": True}
    assert normalize_tool_result("tool", 2.5) == {"success": True, "tool": "tool", "value": 2.5}


def test_normalize_tool_args_input_file_alias():
    result = normalize_tool_args("run_xtb_orca_workflow", {"input_file": "benzene.xyz"})

    assert result == {"xyz_path": "benzene.xyz"}


def test_normalize_tool_args_input_xyz_alias():
    result = normalize_tool_args("run_xtb_orca_workflow", {"input_xyz": "benzene.xyz"})

    assert result == {"xyz_path": "benzene.xyz"}


def test_normalize_tool_args_output_file_alias():
    result = normalize_tool_args("stk_build_from_smiles_tool", {"output_file": "benzene.mol"})

    assert result == {"output_path": "benzene.mol"}


def test_failed_tool_does_not_crash_executor(tmp_path, monkeypatch):
    monkeypatch.setattr(executor, "get_allowed_tools", lambda: ["fake_tool"])
    monkeypatch.setattr(
        executor,
        "call_tool",
        lambda tool_name, args, workdir: {
            "success": False,
            "tool_name": tool_name,
            "tool": tool_name,
            "error": "mock failure",
        },
    )

    result = executor.execute_plan(
        {"steps": [{"tool": "fake_tool", "args": {}}]},
        str(tmp_path),
    )

    assert result["success"] is False
    assert result["failed_step_index"] == 1
    assert result["failed_tool"] == "fake_tool"
    assert result["error"] == "mock failure"
    assert (tmp_path / "step_001_result.json").exists()
    assert (tmp_path / "execution_result.json").exists()
