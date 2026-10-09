"""Tests for collecting the `devops` argv lists built under src and resolving them statically."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.docs import app as docs_app
from devops_cli.core.command_resolver import ArgvPlaceholder, module_click_command
from devops_cli.docs.generator import DocGenerator
from devops_cli.docs.source_argv_collector import (
    ArgvChoice,
    DevopsArgvReference,
    SourceArgvToken,
    collect_devops_argv_references,
    collect_source_argv_references,
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


def auto_deploy(stack: str, args: list[str], flags: list[str]) -> None:
    run_subprocess(["devops", "k8s", "deploy-stack", "infra"])
    run_subprocess(["devops", "k8s", "deploy-stack", stack])
    run_subprocess(["devops", "k8s", "deploy-stack", "--stack", stack])
    run_subprocess(["devops", "k8s", "deploy-stack", *args])
    spread = ["devops", "k8s", "deploy-stack"]
    spread.extend(flags)
    appended = ["devops", "k8s", "deploy-stack"]
    appended.append(stack)


def config_output(as_json: bool, export: bool) -> str:
    _run(["uv", "run", "devops", "config", "output", "--json" if as_json else "--yaml"])
    return _run(
        ["devops", "config", "output", "--json" if as_json else "--export" if export else "-e"]
    )
"""

FIXTURE_REFERENCES = collect_devops_argv_references(FIXTURE_SOURCE, "fixture.py")


def _single(expression: str) -> ArgvPlaceholder:
    return ArgvPlaceholder(expression=expression, single_token=True)


def _spread(expression: str) -> ArgvPlaceholder:
    return ArgvPlaceholder(expression=expression)


def _reference(line: int, owner: str, *tokens: SourceArgvToken) -> DevopsArgvReference:
    return DevopsArgvReference(path="fixture.py", line=line, owner=owner, tokens=tokens)


@pytest.fixture(scope="module")
def command_trees() -> None:
    """Build every command module's tree once, as `devops docs check` has before it resolves.

    Importing a command module may spawn (GitPython runs `git version` on import), so the
    trees are built before any test patches `subprocess.Popen`, and outside its call phase.
    """
    for module_path, _ in _COMMAND_SPECS.values():
        module_click_command(module_path)


@pytest.fixture(scope="module")
def src_references() -> list[DevopsArgvReference]:
    """Every `devops` argv list under src, collected once for the tests that read the tree.

    Collecting parses each module that quotes `devops`, about a megabyte of source. Starting a
    process or calling the MCP runner while collecting raises, so the fixture fails loudly.
    """
    with (
        patch("devops_cli.ai.mcp.server._run_mcp_cmd", side_effect=AssertionError("no tool")),
        patch("subprocess.Popen", side_effect=AssertionError("no subprocess")),
    ):
        return collect_source_argv_references()


def test_argv_lists_and_everything_added_to_them_are_collected() -> None:
    """Verify each `devops` or `uv run devops` list keeps its literals, a placeholder per
    runtime value, and every token appended or extended onto its variable, in order.

    A computed element or append is a single token, while a starred element or a runtime
    extend stands for any number of them. A conditional between literals, nested or not,
    is a choice between them.
    """
    deploy = ("k8s", "deploy-stack")
    assert FIXTURE_REFERENCES == [
        _reference(2, "ai_architecture", "analyze", "architecture", _single("target")),
        _reference(
            6,
            "scan_complexity",
            "scan",
            "complexity",
            _single("target"),
            "--max-nesting-depth",
            _single("str(depth)"),
        ),
        _reference(
            12,
            "repos_sync",
            "repos",
            "sync",
            "--all",
            _single("branch"),
            _spread("extra_flags"),
            "list",
        ),
        _reference(23, "two_commands", "repos", "sync", "--no-pull"),
        _reference(25, "two_commands", "repos", "sync", "--dry-run"),
        _reference(35, "scan_sast", "scan", "sast", ".", "--config", _single("config")),
        _reference(42, "auto_deploy", *deploy, "infra"),
        _reference(43, "auto_deploy", *deploy, _single("stack")),
        _reference(44, "auto_deploy", *deploy, "--stack", _single("stack")),
        _reference(45, "auto_deploy", *deploy, _spread("*args")),
        _reference(46, "auto_deploy", *deploy, _spread("flags")),
        _reference(48, "auto_deploy", *deploy, _single("stack")),
        _reference(
            53, "config_output", "config", "output", ArgvChoice(alternatives=("--json", "--yaml"))
        ),
        _reference(
            55,
            "config_output",
            "config",
            "output",
            ArgvChoice(alternatives=("--json", "--export", "-e")),
        ),
    ]


def test_unresolved_fixture_argv_are_reported_with_their_source_line(
    command_trees: None,
) -> None:
    """Verify each broken fixture line is reported once, at its line, naming what broke.

    The deploy-stack stack passed as a literal or a computed positional is an extra argument.
    The stack passed with `--stack`, a starred tail and a runtime extend resolve, as do the
    option and value appended in two calls at line 35 and each alternative of the nested
    conditional at line 55. The conditional at line 53 names its unknown alternative.
    """
    assert describe_unresolved_references(FIXTURE_REFERENCES) == [
        "fixture.py:2 ai_architecture: 'devops analyze architecture <target>': "
        "unknown command 'analyze' under 'devops'.",
        "fixture.py:6 scan_complexity: "
        "'devops scan complexity <target> --max-nesting-depth <str(depth)>': "
        "unknown option '--max-nesting-depth' for 'devops scan complexity'.",
        "fixture.py:12 repos_sync: 'devops repos sync --all <branch> <extra_flags> list': "
        "unknown option '--all' for 'devops repos sync'.",
        "fixture.py:42 auto_deploy: 'devops k8s deploy-stack infra': "
        "unexpected extra argument 'infra' for 'devops k8s deploy-stack'.",
        "fixture.py:43 auto_deploy: 'devops k8s deploy-stack <stack>': "
        "unexpected extra argument '<stack>' for 'devops k8s deploy-stack'.",
        "fixture.py:48 auto_deploy: 'devops k8s deploy-stack <stack>': "
        "unexpected extra argument '<stack>' for 'devops k8s deploy-stack'.",
        "fixture.py:53 config_output: 'devops config output --yaml': "
        "unknown option '--yaml' for 'devops config output'.",
    ]


def test_a_module_without_a_quoted_devops_is_not_parsed(tmp_path: Path) -> None:
    """Verify only modules that spell `devops` as a quoted literal are parsed.

    A module that only imports `devops_cli` is skipped unparsed; one that quotes the word
    outside an argv is parsed and yields nothing. Paths are taken from the repository root.
    """
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    package = tmp_path / "pkg"
    (package / "commands").mkdir(parents=True)
    (package / "commands" / "deploy.py").write_text(
        'run(["devops", "k8s", "deploy-stack", "infra"])\n', encoding="utf-8"
    )
    (package / "names.py").write_text("NAMESPACE = 'devops'\n", encoding="utf-8")
    (package / "imports.py").write_text("import devops_cli\n", encoding="utf-8")

    with patch.object(ast, "parse", wraps=ast.parse) as parse:
        references = collect_source_argv_references(package)

    assert ([(ref.path, ref.line, ref.tokens) for ref in references], parse.call_count) == (
        [("pkg/commands/deploy.py", 1, ("k8s", "deploy-stack", "infra"))],
        2,
    )


def test_the_collector_reads_every_module_and_both_prefixes(
    src_references: list[DevopsArgvReference],
) -> None:
    """Verify the lists outside the MCP server are collected, bare and through `uv run`.

    179 lists were in src when the collector widened past the MCP server (#868): 172 in the
    server, three in `commands/ci.py`, two in `commands/devcontainer.py`, one each in
    `commands/release.py` and `core/cli.py`. The floor of 174 catches a collector that loses
    a module or a prefix.
    """
    collected = {(reference.path, reference.tokens) for reference in src_references}
    expected = {
        ("src/devops_cli/commands/ci.py", ("docs", "check")),
        ("src/devops_cli/commands/release.py", ("ci", "run")),
        (
            "src/devops_cli/commands/devcontainer.py",
            ("k8s", "deploy-stack", "--stack", _single("stack")),
        ),
        ("src/devops_cli/core/cli.py", (_single("cmd_name"), _spread("*args"))),
        (
            "src/devops_cli/ai/mcp/server.py",
            ("config", "output", ArgvChoice(alternatives=("--json", "--export"))),
        ),
    }
    assert (len(src_references) >= 174, expected <= collected) == (True, True)


def test_every_devops_argv_in_src_resolves(
    src_references: list[DevopsArgvReference], command_trees: None
) -> None:
    """Verify every `devops` and `uv run devops` argv list under src names a real command,
    real options and no stray argument.

    The lists are resolved, not run: neither the MCP runner nor a subprocess is reached.
    """
    with (
        patch("devops_cli.ai.mcp.server._run_mcp_cmd") as mcp_runner,
        patch("subprocess.Popen", side_effect=AssertionError("no subprocess")) as popen,
    ):
        unresolved = describe_unresolved_references(src_references)

    assert (unresolved, mcp_runner.called, popen.called) == ([], False, False)


def test_docs_check_reports_an_unresolved_source_argv(tmp_path: Path, command_trees: None) -> None:
    """Verify `devops docs check` fails on a source argv and names its `path:line`."""
    broken = [FIXTURE_REFERENCES[7]]
    with (
        patch.object(DocGenerator, "generate_all_docs", return_value={}),
        patch(
            "devops_cli.docs.source_argv_collector.collect_source_argv_references",
            return_value=broken,
        ),
        patch(
            "devops_cli.docs.markdown_argv_collector.collect_knowledge_base_argv_references",
            return_value=[],
        ),
        patch(
            "devops_cli.docs.markdown_argv_collector.collect_handwritten_docs_argv_references",
            return_value=[],
        ),
    ):
        ok, errors = DocGenerator().check_docs(tmp_path, check_readme_table=False)
        result = CliRunner().invoke(
            docs_app, ["check", "--no-check-readme", "--output-dir", str(tmp_path)]
        )

    assert (ok, errors, result.exit_code, "fixture.py:43" in result.output) == (
        False,
        describe_unresolved_references(broken),
        1,
        True,
    )
