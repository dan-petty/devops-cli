"""The path parameters of every published MCP tool are confined or are not file paths (#3300).

The audit finds a path parameter by its type and by its name (#3480). A command option that
Typer reads from a `Path` annotation needs a decision under any name. A text option whose name
holds a path keyword needs one too. A text option that holds a path under another name is named
in `_TEXT_PATH_OPTIONS`, because a type check cannot find a string.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Annotated, Any

import pytest
import typer
from fastmcp import FastMCP
from fastmcp.tools import Tool
from typer._click.types import File as TyperFile
from typer.models import TyperPath

from devops_cli.ai.mcp.generator import _create_tool_function, resolve_click_command
from devops_cli.ai.mcp.path_confinement import (
    NOT_A_FILE_PATH,
    NOT_A_PATH_VALUE,
    PATH_CONFINEMENTS,
)
from devops_cli.ai.mcp.server import mcp
from devops_cli.config.constants import CONST_EXIT_FAILURE, CONST_MCP_EXPOSURE_TABLE
from devops_cli.core.paths import _PATH_PARAM_KEYWORDS, validate_path_parameter
from devops_cli.exceptions import SandboxValidationError, SecurityError, ValidationError

_MIN_REASON = 30

# A text option that holds a path under a name with no path keyword. Its type is a string, so the
# audit finds it by neither type nor name. `devops scan sast --config` is a path or a registry id.
_TEXT_PATH_OPTIONS: Mapping[str, frozenset[str]] = {"scan_sast": frozenset({"config"})}

# The published path parameters that issue #3480 lists, and `scan_sast.config`, which is a string.
# `tf_plan.out` and `scan_injection.sarif` left the schema in #3235.
_CENSUS: tuple[tuple[str, str], ...] = (
    ("ai_harness_offload", "repo"),
    ("ai_read", "repo"),
    ("docker_sandbox", "workspace"),
    ("sandbox_deploy", "workspace"),
    ("k8s_diff_helm", "values"),
    ("review_export_feedback", "output"),
    ("tf_plan", "out"),
    ("roadmap_refine", "source"),
    ("scan_injection", "sarif"),
    ("scan_injection", "suppress"),
    ("scan_sast", "config"),
)

# Each option that this change confines: the command path, the option, and the other arguments
# that the tool needs.
_CONFINED: tuple[tuple[tuple[str, ...], str, dict[str, Any]], ...] = (
    (("ai", "harness", "offload"), "repo", {}),
    (("ai", "read"), "repo", {"target_path": "README.md"}),
    (("docker", "sandbox"), "workspace", {"command": ["id"]}),
    (("sandbox", "deploy"), "workspace", {}),
    (("k8s", "diff-helm"), "values", {"release_name": "web"}),
    (("roadmap", "refine"), "source", {}),
    (("scan", "injection"), "suppress", {}),
    (("scan", "sast"), "config", {}),
)


def _catalogue() -> dict[str, Any]:
    return {tool.name: tool for tool in asyncio.run(mcp._list_tools())}


def _properties(tool: Any) -> dict[str, Any]:
    return (tool.parameters or {}).get("properties", {})


def _is_text(spec: dict[str, Any]) -> bool:
    if spec.get("type") in {"string", "array"}:
        return True
    return any(_is_text(part) for part in spec.get("anyOf", []))


def _is_path_schema(spec: dict[str, Any]) -> bool:
    """Whether pydantic typed the property as a path, as it does for a `Path` annotation."""
    parts = [*spec.get("anyOf", []), *([spec["items"]] if "items" in spec else [])]
    return spec.get("format") == "path" or any(_is_path_schema(part) for part in parts)


def _exposed_commands() -> dict[str, Any]:
    """The Click command behind each tool of the exposure table, by tool name."""
    return {
        "_".join(path).replace("-", "_"): resolve_click_command(path)
        for path, *_ in CONST_MCP_EXPOSURE_TABLE
    }


def _typed_as_path(command: Any) -> set[str]:
    """The options of a command that Typer reads from a path.

    A `Path` annotation gives `typer.models.TyperPath`, and a `FileText` or `FileBinaryRead`
    annotation gives `typer._click.types.File`, which Typer opens from a path. Neither type is a
    `click.Path`.
    """
    return {
        param.name for param in command.params if isinstance(param.type, (TyperPath, TyperFile))
    }


def _path_parameters(tools: Sequence[Tool], commands: Mapping[str, Any]) -> dict[str, set[str]]:
    """The published parameters of `tools` that hold a path, by type or by name."""
    found: dict[str, set[str]] = {}
    for tool in tools:
        typed = _typed_as_path(commands[tool.name]) if tool.name in commands else set()
        named = _TEXT_PATH_OPTIONS.get(tool.name, frozenset())
        names = {
            parameter
            for parameter, spec in _properties(tool).items()
            if _is_path_schema(spec)
            or parameter in typed
            or parameter in named
            or (
                _is_text(spec)
                and any(keyword in parameter.lower() for keyword in _PATH_PARAM_KEYWORDS)
            )
        }
        if names:
            found[tool.name] = names
    return found


def _published_path_parameters() -> dict[str, set[str]]:
    return _path_parameters(list(_catalogue().values()), _exposed_commands())


def _is_decided(tool: str, parameter: str) -> bool:
    """Whether a table names the parameter: `PATH_CONFINEMENTS` or `NOT_A_FILE_PATH`."""
    return parameter in PATH_CONFINEMENTS.get(
        tool, frozenset()
    ) or parameter in NOT_A_FILE_PATH.get(tool, {})


def _undecided(found: Mapping[str, set[str]]) -> list[str]:
    """Each `tool.parameter` that neither table names."""
    return sorted(
        f"{tool}.{parameter}"
        for tool, parameters in found.items()
        for parameter in parameters
        if not _is_decided(tool, parameter)
    )


def _probe_with_a_path_option(thing: Annotated[Path, typer.Option("--thing")]) -> None:
    return None


def _probe_with_a_file_option(thing: Annotated[typer.FileText, typer.Option("--thing")]) -> None:
    return None


def _probe_with_a_text_option(thing: Annotated[str, typer.Option("--thing")]) -> None:
    return None


def _other_command() -> None:
    return None


def _command_with(probe: Callable[..., None]) -> Any:
    """The Click command `probe` that Typer builds from the function `probe`."""
    app = typer.Typer()
    app.command("probe")(probe)
    app.command("other")(_other_command)
    return typer.main.get_group(app).commands["probe"]


def _hand_written_probe(thing: Path) -> str:
    return "ok"


def _fixture_tools(tool_fn: Callable[..., Any]) -> Sequence[Tool]:
    """The tools of a server that holds one tool, `probe`, made from `tool_fn`."""
    server = FastMCP("path-audit-test")
    server.tool(name="probe")(tool_fn)
    return asyncio.run(server._list_tools())


def _generated_probe(probe: Callable[..., None]) -> tuple[Sequence[Tool], dict[str, Any]]:
    """The tool that the generator makes from `probe`, and the command that it reads."""
    command = _command_with(probe)
    tool_fn = _create_tool_function(("probe",), 5.0, False, "probe", command)
    return _fixture_tools(tool_fn), {"probe": command}


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


def test_the_audit_fails_on_a_path_option_with_no_keyword_and_no_decision() -> None:
    tools, commands = _generated_probe(_probe_with_a_path_option)

    found = _path_parameters(tools, commands)

    assert found == {"probe": {"thing"}}
    assert _undecided(found) == ["probe.thing"]


def test_the_audit_fails_on_a_file_option_with_no_keyword_and_no_decision() -> None:
    """Typer opens a `FileText` option from a path, so its Click type is `File`, not `Path`."""
    tools, commands = _generated_probe(_probe_with_a_file_option)

    found = _path_parameters(tools, commands)

    assert found == {"probe": {"thing"}}
    assert _undecided(found) == ["probe.thing"]


def test_the_audit_fails_on_a_path_annotation_of_a_tool_that_no_command_backs() -> None:
    found = _path_parameters(_fixture_tools(_hand_written_probe), {})

    assert found == {"probe": {"thing"}}
    assert _undecided(found) == ["probe.thing"]


def test_the_audit_finds_no_text_option_by_type() -> None:
    """A string that holds a path is named in a table, because its type is no path."""
    tools, commands = _generated_probe(_probe_with_a_text_option)

    assert _path_parameters(tools, commands) == {}


def test_every_published_path_parameter_is_confined_or_is_not_a_file() -> None:
    assert _undecided(_published_path_parameters()) == []


@pytest.mark.parametrize(("tool", "parameter"), _CENSUS, ids=[".".join(c) for c in _CENSUS])
def test_a_parameter_of_the_census_is_decided_or_is_not_published(
    tool: str, parameter: str
) -> None:
    if parameter in _properties(_catalogue()[tool]):
        assert parameter in _published_path_parameters().get(tool, set()), "the audit misses it"
        assert _is_decided(tool, parameter), "it has no decision"
    else:
        assert not _is_decided(tool, parameter), "a table names an unpublished parameter"


def test_every_text_path_option_names_a_published_parameter() -> None:
    catalogue = _catalogue()
    for tool, parameters in _TEXT_PATH_OPTIONS.items():
        for parameter in parameters:
            assert parameter in _properties(catalogue[tool]), f"stale {tool}.{parameter}"


def test_every_not_a_file_entry_names_a_published_path_parameter() -> None:
    published = _published_path_parameters()
    for tool, entries in NOT_A_FILE_PATH.items():
        for parameter in entries:
            assert parameter in published.get(tool, set()), f"stale {tool}.{parameter}"


def test_every_confinement_entry_names_a_published_path_parameter() -> None:
    published = _published_path_parameters()
    for tool, parameters in PATH_CONFINEMENTS.items():
        for parameter in parameters:
            assert parameter in published.get(tool, set()), f"stale {tool}.{parameter}"


def test_every_not_a_path_value_entry_names_a_confined_parameter() -> None:
    for tool, parameters in NOT_A_PATH_VALUE.items():
        for parameter in parameters:
            assert parameter in PATH_CONFINEMENTS.get(tool, frozenset()), (
                f"stale {tool}.{parameter}"
            )


def test_every_not_a_file_reason_is_at_least_thirty_characters() -> None:
    for tool, entries in NOT_A_FILE_PATH.items():
        for parameter, reason in entries.items():
            assert len(reason) >= _MIN_REASON, f"{tool}.{parameter} has a short reason"


@pytest.mark.parametrize("keyword", _PATH_PARAM_KEYWORDS)
def test_the_runtime_check_refuses_traversal_under_each_keyword(keyword: str) -> None:
    with pytest.raises(SecurityError, match=f"parameter 'my_{keyword}'"):
        validate_path_parameter(f"my_{keyword}", "../x")


@pytest.mark.parametrize("name", ["repo", "workspace", "values", "source", "suppress", "config"])
def test_the_runtime_check_ignores_a_name_that_holds_no_path_keyword(name: str) -> None:
    """`validate_path_parameter` reads `_PATH_PARAM_KEYWORDS` for the agent tools too, so the
    audit finds these options by type and the keyword list stays as it was (#3480)."""
    assert validate_path_parameter(name, "../x") is None


def test_a_traversal_value_is_refused_before_a_command_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _record(monkeypatch)
    tool = _tool(("gh", "pages", "verify"))

    with pytest.raises(ValidationError) as caught:
        tool(root_dir="../../etc/passwd")

    assert caught.value.details["field"] == "root_dir"
    assert calls == []


@pytest.mark.parametrize(
    ("path", "parameter", "required"),
    _CONFINED,
    ids=["_".join(c[0]) + "." + c[1] for c in _CONFINED],
)
def test_a_traversal_value_of_each_confined_option_is_refused_before_a_command_runs(
    path: tuple[str, ...],
    parameter: str,
    required: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _record(monkeypatch)
    value: Any = ["../../etc/passwd"] if parameter == "values" else "../../etc/passwd"

    with pytest.raises(ValidationError) as caught:
        _tool(path)(**required, **{parameter: value})

    assert (caught.value.error_code, caught.value.exit_code, caught.value.details["field"]) == (
        "VALIDATION_ERROR",
        CONST_EXIT_FAILURE,
        parameter,
    )
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


@pytest.mark.parametrize(
    ("path", "required"),
    [(("docker", "sandbox"), {"command": ["id"]}), (("sandbox", "deploy"), {})],
    ids=["docker_sandbox", "sandbox_deploy"],
)
def test_a_sandbox_workspace_outside_the_work_tree_is_refused(
    path: tuple[str, ...],
    required: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`validate_sandbox_workspace` allows a directory outside the work tree, so the tool
    confines the workspace first (#3480)."""
    tree = tmp_path / "tree"
    outside = tmp_path / "outside"
    tree.mkdir()
    outside.mkdir()
    monkeypatch.chdir(tree)
    calls = _record(monkeypatch)

    with pytest.raises(ValidationError) as caught:
        _tool(path)(**required, workspace=str(outside))

    assert (caught.value.error_code, caught.value.exit_code, caught.value.details["field"]) == (
        "VALIDATION_ERROR",
        CONST_EXIT_FAILURE,
        "workspace",
    )
    assert calls == []


def test_a_sandbox_workspace_in_the_work_tree_still_meets_the_sandbox_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".ssh").mkdir()
    monkeypatch.chdir(tmp_path)
    calls = _record(monkeypatch)

    with pytest.raises(SandboxValidationError) as caught:
        _tool(("docker", "sandbox"))(command=["id"], workspace=".ssh")

    assert caught.value.error_code == "SANDBOX_VALIDATION_ERROR"
    assert caught.value.details["path"] == str((tmp_path / ".ssh").resolve())
    assert calls == []


def test_a_semgrep_registry_id_is_not_a_path(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _record(monkeypatch)

    _tool(("scan", "sast"))()
    _tool(("scan", "sast"))(config="p/python")

    assert [argv[argv.index("--config") + 1] for argv in calls] == ["p/default", "p/python"]


def test_a_local_semgrep_config_resolves_under_the_work_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    calls = _record(monkeypatch)

    _tool(("scan", "sast"))(config="rules")

    argv = calls[0]
    assert argv[argv.index("--config") + 1] == str(tmp_path / "rules")


def test_a_semgrep_config_url_does_not_reach_semgrep(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    calls = _record(monkeypatch)

    _tool(("scan", "sast"))(config="https://example.com/rules.yaml")

    argv = calls[0]
    assert Path(argv[argv.index("--config") + 1]).is_relative_to(tmp_path)


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
        ("review_export_feedback", {"output"}),
    ],
)
def test_a_tool_publishes_no_unconfined_write_or_free_path_option(
    tool: str, dropped: set[str]
) -> None:
    published = set(_properties(_catalogue()[tool]))
    assert dropped.isdisjoint(published)


def test_the_export_feedback_command_keeps_its_output_option() -> None:
    """The command writes to the configured dataset unless a person names a file."""
    flags = {
        opt
        for param in resolve_click_command(("review", "export-feedback")).params
        for opt in param.opts
    }

    assert "--output" in flags
