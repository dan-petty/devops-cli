"""Every published path-like parameter is removed, confined, or recorded with a reason (#3300)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import devops_cli.ai.mcp.path_confinement as path_confinement
from devops_cli.ai.mcp.generator import _create_tool_function, resolve_click_command
from devops_cli.ai.mcp.path_confinement import audit_path_parameters
from devops_cli.ai.mcp.roles import ROLE_OPS, tools_for_role
from devops_cli.ai.mcp.server import mcp
from devops_cli.config.constants import CONST_MCP_EXPOSURE_TABLE
from devops_cli.core.paths import _PATH_PARAM_KEYWORDS
from devops_cli.core.repo import find_worktree_root
from devops_cli.exceptions import ValidationError


def _catalogue() -> list[Any]:
    return asyncio.run(mcp._list_tools())


def _tool_fn(path: tuple[str, ...]) -> Any:
    _, timeout, _read_only, format_json = next(
        entry for entry in CONST_MCP_EXPOSURE_TABLE if entry[0] == path
    )
    tool_name = "_".join(path).replace("-", "_")
    return _create_tool_function(path, timeout, format_json, tool_name, resolve_click_command(path))


def _path_like_parameters() -> set[str]:
    names: set[str] = set()
    for tool in tools_for_role(ROLE_OPS, _catalogue()):
        for name in tool.parameters.get("properties", {}):
            if any(keyword in name.lower() for keyword in _PATH_PARAM_KEYWORDS):
                names.add(f"{tool.name}.{name}")
    return names


def test_every_path_like_parameter_is_confined_or_explained() -> None:
    problems = audit_path_parameters(tools_for_role(ROLE_OPS, _catalogue()))
    assert problems == []


def test_the_audit_covers_a_tool_outside_the_job_roles() -> None:
    queued = {
        f"{tool.name}.{name}"
        for tool in tools_for_role(ROLE_OPS, _catalogue())
        for name in tool.parameters.get("properties", {})
        if any(keyword in name.lower() for keyword in _PATH_PARAM_KEYWORDS)
    }
    assert {"scan_aibom.output_file", "ai_ingest_library.output_dir"} <= queued


def test_a_synthetic_unconfined_path_fails_the_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(path_confinement, "PATH_CONFINEMENTS", {})
    monkeypatch.setattr(path_confinement, "NOT_A_FILE_PATH", {})
    tool = SimpleNamespace(
        name="synthetic_tool",
        parameters={"properties": {"output_path": {"type": "string"}}},
    )
    problems = audit_path_parameters([tool])
    assert len(problems) == 1
    assert "synthetic_tool.output_path" in problems[0]


def test_a_short_reason_fails_the_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(path_confinement, "PATH_CONFINEMENTS", {})
    monkeypatch.setattr(
        path_confinement, "NOT_A_FILE_PATH", {"synthetic_tool": {"target": "a host"}}
    )
    tool = SimpleNamespace(
        name="synthetic_tool",
        parameters={"properties": {"target": {"type": "string"}}},
    )
    problems = audit_path_parameters([tool])
    assert len(problems) == 1
    assert "synthetic_tool.target" in problems[0]


def test_a_stale_entry_fails_the_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        path_confinement, "PATH_CONFINEMENTS", {"gone_tool": frozenset({"file_path"})}
    )
    monkeypatch.setattr(path_confinement, "NOT_A_FILE_PATH", {})
    problems = audit_path_parameters([])
    assert len(problems) == 1
    assert "gone_tool.file_path" in problems[0]


def test_a_path_outside_the_work_tree_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[list[str]] = []
    monkeypatch.setattr(
        "devops_cli.ai.mcp.server._run_mcp_cmd",
        lambda cmd, timeout: started.append(cmd) or "ok",
    )
    tool = _tool_fn(("ai", "ast", "parse"))
    with pytest.raises(ValidationError, match="file_path"):
        tool(file_path="/etc/passwd")
    assert started == []


def test_a_traversal_value_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[list[str]] = []
    monkeypatch.setattr(
        "devops_cli.ai.mcp.server._run_mcp_cmd",
        lambda cmd, timeout: started.append(cmd) or "ok",
    )
    tool = _tool_fn(("gh", "pages", "verify"))
    with pytest.raises(ValidationError, match="root_dir"):
        tool(root_dir="../../etc/passwd")
    assert started == []


def test_a_relative_path_resolves_under_the_work_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    root = find_worktree_root(Path.cwd())
    started: list[list[str]] = []
    monkeypatch.setattr(
        "devops_cli.ai.mcp.server._run_mcp_cmd",
        lambda cmd, timeout: started.append(cmd) or "ok",
    )
    tool = _tool_fn(("ai", "ast", "parse"))
    assert tool(file_path="README.md") == "ok"
    assert str(root / "README.md") in started[0]
