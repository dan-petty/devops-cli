"""Tests for collecting the MCP server's `devops` argv lists and resolving them statically."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from devops_cli.commands.docs import app as docs_app
from devops_cli.docs.command_resolver import ArgvPlaceholder, module_click_command
from devops_cli.docs.generator import DocGenerator
from devops_cli.docs.mcp_argv_collector import (
    DevopsArgvReference,
    collect_devops_argv_references,
    collect_mcp_server_argv_references,
    describe_unresolved_references,
)
from devops_cli.main import _COMMAND_SPECS

FIXTURE_SOURCE = """\
def ai_architecture(target: str = "src") -> str:
    return _run(["uv", "run", "devops", "analyze", "architecture", target])


def scan_complexity(target: str = "src", depth: int = 5) -> str:
    cmd = ["uv", "run", "devops", "scan", "complexity", target]
    cmd.extend(["--max-nesting-depth", str(depth)])
    return _run(cmd)


def repos_sync(all_repos: bool = False, branch: str = "") -> str:
    cmd = ["uv", "run", "devops", "repos", "sync"]
    if all_repos:
        cmd.append("--all")
    if branch:
        cmd.append(branch)
    cmd.extend(extra_flags)
    cmd.append("list")
    return _run(cmd)


def two_commands() -> str:
    cmd = ["uv", "run", "devops", "repos", "sync"]
    cmd.append("--no-pull")
    cmd = ["uv", "run", "devops", "repos", "sync"]
    cmd.append("--dry-run")
    return _run(cmd)


def not_devops() -> str:
    return _run(["uv", "run", "pytest", "-q"])


def scan_sast(config: str) -> str:
    cmd = ["uv", "run", "devops", "scan", "sast", "."]
    cmd.append("--config")
    cmd.append(config)
    return _run(cmd)
"""

FIXTURE_REFERENCES = collect_devops_argv_references(FIXTURE_SOURCE, "fixture.py")


def _reference(line: int, owner: str, *tokens: str | ArgvPlaceholder) -> DevopsArgvReference:
    return DevopsArgvReference(path="fixture.py", line=line, owner=owner, tokens=tokens)


def test_argv_lists_and_everything_added_to_them_are_collected() -> None:
    """Verify each `uv run devops` list keeps its literals, a placeholder per runtime value,
    and every token appended or extended onto the variable it is assigned to, in order.

    A non-literal append or extend becomes a placeholder like a non-literal element, so an
    option and its value appended in two calls stay together.
    """
    assert FIXTURE_REFERENCES == [
        _reference(
            2, "ai_architecture", "analyze", "architecture", ArgvPlaceholder(expression="target")
        ),
        _reference(
            6,
            "scan_complexity",
            "scan",
            "complexity",
            ArgvPlaceholder(expression="target"),
            "--max-nesting-depth",
            ArgvPlaceholder(expression="str(depth)"),
        ),
        _reference(
            12,
            "repos_sync",
            "repos",
            "sync",
            "--all",
            ArgvPlaceholder(expression="branch"),
            ArgvPlaceholder(expression="extra_flags"),
            "list",
        ),
        _reference(23, "two_commands", "repos", "sync", "--no-pull"),
        _reference(25, "two_commands", "repos", "sync", "--dry-run"),
        _reference(
            35,
            "scan_sast",
            "scan",
            "sast",
            ".",
            "--config",
            ArgvPlaceholder(expression="config"),
        ),
    ]


def test_unresolved_fixture_argv_are_reported_with_their_source_line() -> None:
    """Verify an unknown command names `analyze` and an unknown option names its line.

    The option and value appended in two calls, at line 35, resolve.
    """
    assert describe_unresolved_references(FIXTURE_REFERENCES) == [
        "fixture.py:2 ai_architecture: 'devops analyze architecture <target>': "
        "unknown command 'analyze' under 'devops'.",
        "fixture.py:6 scan_complexity: "
        "'devops scan complexity <target> --max-nesting-depth <str(depth)>': "
        "unknown option '--max-nesting-depth' for 'devops scan complexity'.",
        "fixture.py:12 repos_sync: 'devops repos sync --all <branch> <extra_flags> list': "
        "unknown option '--all' for 'devops repos sync'.",
    ]


def test_every_mcp_server_argv_resolves() -> None:
    """Verify every literal argv list in the MCP server names a real command and options.

    The lists are resolved, not run: neither the MCP runner nor a subprocess is reached.
    166 is every list once `ai_architecture` was deleted, the four roadmap-sync tools went and
    `roadmap_render` and `roadmap_migrate` came (#739). Importing a command
    module may spawn (GitPython runs `git version` on import), and `devops docs check` has
    imported every module to generate the docs before it resolves, so each module's command
    tree is built before the guard and only collecting and resolving run inside it.
    """
    for module_path, _ in _COMMAND_SPECS.values():
        module_click_command(module_path)
    with (
        patch("devops_cli.ai.mcp.server._run_mcp_cmd") as mcp_runner,
        patch("subprocess.Popen", side_effect=AssertionError("no subprocess")) as popen,
    ):
        references = collect_mcp_server_argv_references()
        unresolved = describe_unresolved_references(references)

    assert (
        len(references) >= 166,
        {reference.path for reference in references},
        unresolved,
        mcp_runner.called,
        popen.called,
    ) == (True, {"src/devops_cli/ai/mcp/server.py"}, [], False, False)


def test_docs_check_reports_an_unresolved_mcp_argv(tmp_path: Path) -> None:
    """Verify `devops docs check` fails on an MCP argv that names no real command."""
    with (
        patch.object(DocGenerator, "generate_all_docs", return_value={}),
        patch(
            "devops_cli.docs.mcp_argv_collector.collect_mcp_server_argv_references",
            return_value=FIXTURE_REFERENCES[:1],
        ),
    ):
        ok, errors = DocGenerator().check_docs(tmp_path, check_readme_table=False)
        result = CliRunner().invoke(
            docs_app, ["check", "--no-check-readme", "--output-dir", str(tmp_path)]
        )

    assert (ok, errors, result.exit_code, "fixture.py:2" in result.output) == (
        False,
        describe_unresolved_references(FIXTURE_REFERENCES[:1]),
        1,
        True,
    )
