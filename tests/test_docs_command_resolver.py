"""Tests for resolving `devops` command lines against the real Typer command tree."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from devops_cli.docs.command_resolver import (
    ArgvPlaceholder,
    ArgvToken,
    CommandReferenceDefect,
    CommandReferenceFinding,
    resolve_devops_argv,
)


def _finding(defect: CommandReferenceDefect, path: str, token: str) -> CommandReferenceFinding:
    return CommandReferenceFinding(defect=defect, command_path=path, token=token)


TARGET = ArgvPlaceholder(expression="target")
NUMBER = ArgvPlaceholder(expression="str(max_complexity)")


# The negative controls below fail if a Typer upgrade changes how the walk descends: each
# defect sits at a different depth, so a walk that stops early, or a parse that stops
# raising, turns a finding into None.
@pytest.mark.parametrize(
    ("tokens", "expected"),
    [
        (
            ["analyze", "architecture", TARGET],
            _finding(CommandReferenceDefect.UNKNOWN_COMMAND, "devops", "analyze"),
        ),
        (
            ["scan", "gitleaks", TARGET],
            _finding(CommandReferenceDefect.UNKNOWN_COMMAND, "devops scan", "gitleaks"),
        ),
        (
            ["scan", "complexity", TARGET, "--max-nesting-depth", NUMBER],
            _finding(
                CommandReferenceDefect.UNKNOWN_OPTION,
                "devops scan complexity",
                "--max-nesting-depth",
            ),
        ),
        (
            ["argo", "cd", "apps", "list", "--json"],
            _finding(CommandReferenceDefect.UNKNOWN_OPTION, "devops argo cd apps list", "--json"),
        ),
        (
            ["k8s", "audit", "stray"],
            _finding(CommandReferenceDefect.UNEXPECTED_ARGUMENT, "devops k8s audit", "stray"),
        ),
        (
            ["benchmark", "--suite"],
            _finding(CommandReferenceDefect.UNKNOWN_COMMAND, "devops", "benchmark"),
        ),
        (
            ["ai", "benchmark", "--suite", "--experiment", "x"],
            _finding(CommandReferenceDefect.UNKNOWN_OPTION, "devops ai benchmark", "--experiment"),
        ),
        (
            ["lint", "--nope"],
            _finding(CommandReferenceDefect.UNKNOWN_OPTION, "devops lint", "--nope"),
        ),
    ],
)
def test_a_defective_command_line_is_named_where_it_breaks(
    tokens: list[ArgvToken], expected: CommandReferenceFinding
) -> None:
    """Verify an unknown command, unknown option or extra argument is reported at its depth."""
    assert resolve_devops_argv(tokens) == expected


@pytest.mark.parametrize(
    "tokens",
    [
        ["argo", "cd", "apps", "list"],
        ["scan", "complexity", TARGET, "--max-complexity", NUMBER, "--max-indent", NUMBER],
        ["ai", "benchmark", "--suite", "--models", TARGET, "--dry-run"],
        ["ai", "benchmark", "--type", "embedding", "--samples", NUMBER],
        ["repos", "sync"],
        ["ci"],
        ["lint"],
        ["--dry-run", "repos", "list"],
        ["k8s", "chaos", TARGET, "--namespace", TARGET, "--dry-run"],
    ],
)
def test_a_real_command_line_resolves(tokens: list[ArgvToken]) -> None:
    """Verify command lines the CLI accepts, at every depth, report nothing."""
    assert resolve_devops_argv(tokens) is None


def test_a_placeholder_that_fails_conversion_does_not_hide_an_extra_argument() -> None:
    """Verify a placeholder an integer option rejects still lets the leftovers be checked.

    Click converts option values before it looks for extra arguments, so a strict parse
    stops at the placeholder; the lenient parse still finds the stray literal.
    """
    tokens: list[ArgvToken] = ["scan", "complexity", TARGET, "--max-complexity", NUMBER, "stray"]

    assert resolve_devops_argv(tokens) == _finding(
        CommandReferenceDefect.UNEXPECTED_ARGUMENT, "devops scan complexity", "stray"
    )


@pytest.mark.parametrize(
    "tokens",
    [
        ["ai", ArgvPlaceholder(expression="subcommand")],
        [ArgvPlaceholder(expression="group"), "list"],
        ["config", "output", ArgvPlaceholder(expression="flag")],
    ],
)
def test_a_placeholder_is_never_reported(tokens: list[ArgvToken]) -> None:
    """Verify a runtime value where a command or an extra argument sits is inconclusive.

    A placeholder can stand for anything, `--json` included, so only literal tokens are
    reported.
    """
    assert resolve_devops_argv(tokens) is None


def test_resolving_parses_without_invoking_or_spawning() -> None:
    """Verify a destructive command line resolves without its callback or a subprocess."""
    with (
        patch("devops_cli.k8s.chaos.execute_chaos_experiment") as experiment,
        patch("subprocess.Popen", side_effect=AssertionError("no subprocess")) as popen,
    ):
        finding = resolve_devops_argv(["k8s", "chaos", "pod-kill", "--namespace", "default"])

    assert (finding, experiment.called, popen.called) == (None, False, False)


def test_a_finding_describes_itself() -> None:
    """Verify each defect reads as the token and the command it was given to."""
    assert [
        _finding(defect, "devops scan", "x").describe() for defect in CommandReferenceDefect
    ] == [
        "unknown command 'x' under 'devops scan'",
        "unknown option 'x' for 'devops scan'",
        "unexpected extra argument 'x' for 'devops scan'",
    ]


def test_a_placeholder_renders_as_its_expression() -> None:
    """Verify a placeholder token reads as the source expression it replaced."""
    assert str(ArgvPlaceholder(expression="str(limit)")) == "<str(limit)>"
