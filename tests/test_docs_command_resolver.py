"""Tests for resolving `devops` command lines against the real Typer command tree."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from devops_cli.docs.command_resolver import (
    ArgvPlaceholder,
    ArgvToken,
    CommandReferenceDefect,
    CommandReferenceFinding,
    module_click_command,
    resolve_devops_argv,
)
from devops_cli.main import _COMMAND_SPECS


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
            ["benchmark", "--dry-run"],
            _finding(CommandReferenceDefect.UNKNOWN_COMMAND, "devops", "benchmark"),
        ),
        (
            ["ai", "benchmark", "--dry-run", "--experiment", "x"],
            _finding(CommandReferenceDefect.UNKNOWN_OPTION, "devops ai benchmark", "--experiment"),
        ),
        (
            ["lint", "--nope"],
            _finding(CommandReferenceDefect.UNKNOWN_OPTION, "devops lint", "--nope"),
        ),
        (
            ["scan", "gitleaks", "--help"],
            _finding(CommandReferenceDefect.UNKNOWN_COMMAND, "devops scan", "gitleaks"),
        ),
        (
            ["scan", "complexity", "--max-nesting-depth", "--help"],
            _finding(
                CommandReferenceDefect.UNKNOWN_OPTION,
                "devops scan complexity",
                "--max-nesting-depth",
            ),
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
        ["ai", "benchmark", "--models", TARGET, "--dry-run"],
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


def test_an_option_missing_its_value_is_not_an_extra_argument() -> None:
    """Verify a known option left without its value does not blame an earlier literal.

    Click's parser stops at the option, before it binds the positionals, so what that parse
    leaves over is not a set of extra arguments.
    """
    assert resolve_devops_argv(["scan", "sast", ".", "--config"]) is None


@pytest.mark.parametrize(
    "tokens",
    [
        [],
        ["--help"],
        ["--version"],
        ["k8s"],
        ["scan", "--help"],
        ["scan", "sast", "--help"],
        ["scan", "sast", ".", "-h"],
        ["scan", "--show-completion", "bash"],
    ],
)
def test_an_eager_option_or_a_bare_group_resolves_silently(
    tokens: list[ArgvToken], capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify `--help`, `--version`, a completion option or a bare group prints nothing.

    An eager option's callback prints and exits as the option is parsed, and a group given
    nothing prints its help. None of them names a missing command or option, so the walk
    stops there instead of parsing them.
    """
    finding = resolve_devops_argv(tokens)

    assert (finding, capsys.readouterr().out) == (None, "")


def test_a_completion_option_never_installs_completion() -> None:
    """Verify `--install-completion` resolves without writing a completion script or profile."""
    with patch("typer.completion.install", side_effect=AssertionError("installed")) as install:
        finding = resolve_devops_argv(["scan", "--install-completion", "bash"])

    assert (finding, install.called) == (None, False)


def test_resolving_parses_without_invoking_or_spawning() -> None:
    """Verify a destructive command line resolves without its callback or a subprocess.

    Importing a command module may spawn (GitPython runs `git version` on import), and
    `devops docs check` imports every module to generate the docs anyway, so the module is
    built before the guard and only the resolving runs inside it.
    """
    module_click_command(_COMMAND_SPECS["k8s"][0])
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
