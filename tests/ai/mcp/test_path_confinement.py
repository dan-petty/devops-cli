"""The path parameters of every published MCP tool are confined or are not file paths (#3300)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.mcp.generator import _create_tool_function, resolve_click_command
from devops_cli.ai.mcp.path_confinement import NOT_A_FILE_PATH, PATH_CONFINEMENTS
from devops_cli.ai.mcp.server import mcp
from devops_cli.core.paths import _PATH_PARAM_KEYWORDS
from devops_cli.exceptions import ValidationError

_MIN_REASON = 30


def _catalogue() -> dict[str, Any]:
    return {tool.name: tool for tool in asyncio.run(mcp._list_tools())}


def _properties(tool: Any) -> dict[str, Any]:
    return (tool.parameters or {}).get("properties", {})


def _is_text(spec: dict[str, Any]) -> bool:
    if spec.get("type") in {"string", "array"}:
        return True
    return any(_is_text(part) for part in spec.get("anyOf", []))


def _path_parameters() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for name, tool in _catalogue().items():
        names = {
            parameter
            for parameter, spec in _properties(tool).items()
            if _is_text(spec)
            and any(keyword in parameter.lower() for keyword in _PATH_PARAM_KEYWORDS)
        }
        if names:
            found[name] = names
    return found


def _tool(path: tuple[str, ...]) -> Any:
    name = "_".join(path).replace("-", "_")
    return _create_tool_function(path, 5.0, False, name, resolve_click_command(path))


def _record(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], timeout: float) -> str:
        calls.append(argv)
        return "ok"

    monkeypatch.setattr("devops_cli.ai.mcp.server._run_mcp_cmd", fake_run)
    return calls


def test_every_published_path_parameter_is_confined_or_is_not_a_file() -> None:
    for tool, parameters in _path_parameters().items():
        for parameter in parameters:
            confined = parameter in PATH_CONFINEMENTS.get(tool, frozenset())
            exempt = parameter in NOT_A_FILE_PATH.get(tool, {})
            assert confined or exempt, f"{tool}.{parameter} has no path decision"


def test_every_not_a_file_entry_names_a_published_path_parameter() -> None:
    published = _path_parameters()
    for tool, entries in NOT_A_FILE_PATH.items():
        for parameter in entries:
            assert parameter in published.get(tool, set()), f"stale {tool}.{parameter}"


def test_every_confinement_entry_names_a_published_path_parameter() -> None:
    published = _path_parameters()
    for tool, parameters in PATH_CONFINEMENTS.items():
        for parameter in parameters:
            assert parameter in published.get(tool, set()), f"stale {tool}.{parameter}"


def test_every_not_a_file_reason_is_at_least_thirty_characters() -> None:
    for tool, entries in NOT_A_FILE_PATH.items():
        for parameter, reason in entries.items():
            assert len(reason) >= _MIN_REASON, f"{tool}.{parameter} has a short reason"


def test_a_traversal_value_is_refused_before_a_command_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _record(monkeypatch)
    tool = _tool(("gh", "pages", "verify"))

    with pytest.raises(ValidationError) as caught:
        tool(root_dir="../../etc/passwd")

    assert caught.value.details["field"] == "root_dir"
    assert calls == []


def test_an_absolute_path_outside_the_work_tree_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _record(monkeypatch)
    tool = _tool(("ai", "ast", "graph"))

    with pytest.raises(ValidationError) as caught:
        tool(target_dir="/etc")

    assert caught.value.details["field"] == "target_dir"
    assert calls == []


def test_a_relative_path_stays_in_the_work_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "docs").mkdir()
    monkeypatch.chdir(tmp_path)
    calls = _record(monkeypatch)
    tool = _tool(("gh", "pages", "verify"))

    assert tool(root_dir="docs") == "ok"

    assert calls == [
        ["uv", "run", "devops", "gh", "pages", "verify", "--dir", str(tmp_path / "docs")]
    ]


def test_a_relative_path_resolves_from_a_nested_directory_against_the_work_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    nested = tmp_path / "nested"
    nested.mkdir()
    monkeypatch.chdir(nested)
    calls = _record(monkeypatch)
    tool = _tool(("gh", "pages", "verify"))

    assert tool(root_dir="docs") == "ok"

    assert calls == [
        ["uv", "run", "devops", "gh", "pages", "verify", "--dir", str(tmp_path / "docs")]
    ]


def test_the_confinement_root_is_not_a_tool_argument() -> None:
    tool = _tool(("gh", "pages", "verify"))
    assert {"root", "base_dir", "work_tree"}.isdisjoint(tool.__signature__.parameters)


@pytest.mark.parametrize(
    ("tool", "dropped"),
    [
        ("ai_ingest_library", {"output_dir"}),
        ("scan_sbom", {"output_file"}),
        ("scan_aibom", {"output_file"}),
        ("ai_ast_graph", {"output_path"}),
        ("k8s_security_stream", {"output"}),
        ("k8s_create_tls_secret", {"cert_path", "key_path"}),
        ("k8s_enable_tls", {"tls_dir"}),
        ("ssh_audit", {"key_dir"}),
        ("ssh_status", {"key_dir"}),
    ],
)
def test_a_tool_publishes_no_unconfined_write_or_free_path_option(
    tool: str, dropped: set[str]
) -> None:
    published = set(_properties(_catalogue()[tool]))
    assert dropped.isdisjoint(published)
