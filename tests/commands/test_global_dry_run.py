"""The global `--dry-run` flag and the `DEVOPS_CLI_DRY_RUN` variable of the root command.

Every case runs a real command through the `cli` fixture. The process fake shows whether a
command started a program: a dry run starts none.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.support.fakes.process import ProcessFake

_STUB = "tests.support.dry_run_stub:app"
_TOFU_APPLY = ("tofu", "apply")


@pytest.fixture
def stub_commands() -> Iterator[None]:
    """Register the stub command module (`tests/support/dry_run_stub.py`) on the root app as `stub`."""
    from devops_cli.main import app

    app.add_typer(_STUB, name="stub")
    try:
        yield
    finally:
        app.registered_commands = [c for c in app.registered_commands if c.name != "stub"]


def _words(output: str) -> str:
    """The output with every run of white space as one space."""
    return " ".join(output.split())


def test_global_dry_run_refuses_an_unknown_option_of_the_command(
    cli: Callable[..., Any],
) -> None:
    result = cli("--dry-run", "repos", "--unknown-option")

    assert result.exit_code == 2
    assert "No such option" in result.output


@pytest.mark.parametrize(
    ("args", "printed"),
    [
        (["plain"], "Would run delegated command: devops stub plain"),
        (["plain", "--port", "8080"], "Would run delegated command: devops stub plain --port 8080"),
    ],
)
def test_global_dry_run_prints_the_command_line_of_a_command_without_dry_run(
    cli: Callable[..., Any], stub_commands: None, args: list[str], printed: str
) -> None:
    """A command with no class and no `--dry-run` is not run; the proxy prints the generic line."""
    result = cli("--dry-run", "stub", *args)

    assert result.exit_code == 0
    assert printed in _words(result.output)
    assert "plain ran" not in result.output


def test_global_dry_run_runs_a_command_that_makes_no_external_request(
    cli: Callable[..., Any], stub_commands: None
) -> None:
    result = cli("--dry-run", "stub", "marked")

    assert result.exit_code == 0
    assert "marked ran" in result.output
    assert "Would run delegated command" not in result.output


def test_global_dry_run_previews_a_group_that_has_its_own_options(
    cli: Callable[..., Any],
) -> None:
    result = cli("--dry-run", "ci", "--check")

    assert result.exit_code == 0
    assert "Dry run: no request was made." in result.output


def test_trailing_dry_run_reaches_the_subcommand(
    cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    result = cli("tf", "apply", "--dry-run")

    assert result.exit_code == 0
    assert "Plan for applying OpenTofu infrastructure" in result.output
    assert process_fake.calls == []


def test_an_exported_dry_run_variable_is_honoured(
    cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    """An exported DEVOPS_CLI_DRY_RUN makes a command that declares `--dry-run` plan its work."""
    result = cli("tf", "apply", env={"DEVOPS_CLI_DRY_RUN": "1"})

    assert result.exit_code == 0
    assert "Plan for applying OpenTofu infrastructure" in result.output
    assert process_fake.calls == []


def test_a_dry_run_flag_does_not_latch_for_later_commands(
    cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    """The flag applies to the invocation carrying it, not to the rest of the process."""
    cli("--dry-run", "tf", "apply")
    assert process_fake.calls == []

    result = cli("tf", "apply")

    assert result.exit_code == 0
    assert [call.argv for call in process_fake.calls] == [_TOFU_APPLY]


def test_no_flag_and_no_variable_still_executes(
    cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    """Honouring the variable must not leave dry-run latched on for ordinary runs."""
    result = cli("tf", "apply")

    assert result.exit_code == 0
    assert [call.argv for call in process_fake.calls] == [_TOFU_APPLY]


@pytest.mark.parametrize(
    ("cli_args", "planned", "not_planned"),
    [
        pytest.param(
            ["--dry-run", "k8s", "configure-urls", "--stack", "logging"],
            '"details": {}',
            "argocd.url",
            id="option-value-after-the-subcommand",
        ),
        pytest.param(
            ["--dry-run", "tf", "apply"],
            "Plan for applying OpenTofu infrastructure",
            "Plan for destroying",
            id="apply",
        ),
        pytest.param(
            ["--dry-run", "tf", "destroy"],
            "Plan for destroying OpenTofu infrastructure",
            "Plan for applying",
            id="destroy",
        ),
        pytest.param(
            ["--dry-run", "sandbox", "deploy", "--", "echo", "test"],
            '"command": ["echo", "test"]',
            "--dry-run",
            id="flag-before-the-separator",
        ),
        pytest.param(
            ["--dry-run", "ci", "--check", "lint"],
            "ruff check --config pyproject.toml",
            "pytest --durations",
            id="one-gate-row",
        ),
        pytest.param(
            ["--dry-run", "ci", "--check"],
            "pytest --durations",
            None,
            id="all-gate-rows",
        ),
    ],
)
def test_global_dry_run_plans_the_command_it_forwards_to(
    cli: Callable[..., Any],
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    cli_args: list[str],
    planned: str,
    not_planned: str | None,
) -> None:
    """The flag reaches the command before its positionals and before `--`, so the command plans."""
    # `sandbox deploy` takes the current directory as its workspace, and a checkout under a
    # home directory is not a valid workspace on a runner.
    monkeypatch.chdir(tmp_path)

    result = cli(*cli_args)

    assert result.exit_code == 0, result.output
    assert planned in result.output
    assert not_planned is None or not_planned not in result.output
    assert [call for call in process_fake.calls if not call.local_read] == []


def test_global_dry_run_shows_help_without_forwarding(cli: Callable[..., Any]) -> None:
    """--help bypasses dry-run forwarding and shows the help at once."""
    result = cli("--dry-run", "repos", "--help")

    assert result.exit_code == 0
    assert "Usage: devops repos" in result.output
