"""The suite refuses to start a real gh or security scanner (#1666).

Each reaches beyond the test: gh acts as the developer's own login, and a scanner fetches rule
packs and advisories from a child process that the in-process network block cannot see, taking
seconds a run. The names are read from the scanner registry, so a scanner added there is refused
too. The refusal sits on `subprocess.Popen`, beneath every seam, so it holds whichever way a test
reaches the program, and it fails the test however the code that started the program handles
exceptions.
"""

from __future__ import annotations

import subprocess

import pytest

from devops_cli.config.commands import BIN_BANDIT, BIN_GITLEAKS, BIN_SEMGREP
from devops_cli.config.constants import CONST_GH_CLI
from tests.support.refused_programs import refused_programs


@pytest.mark.parametrize("program", sorted(refused_programs()))
def test_starting_a_refused_program_fails_the_test(
    program: str, unexpected_loopback_connects: list[str]
) -> None:
    """The program is refused by its name, at any path, before any process starts."""
    try:
        with pytest.raises(pytest.fail.Exception, match=f"real {program}"):
            subprocess.run([f"/usr/local/bin/{program}", "--version"], check=False)
    finally:
        unexpected_loopback_connects.clear()


def test_a_refused_shell_command_fails_the_test(
    unexpected_loopback_connects: list[str],
) -> None:
    """A command line given as one string is refused by its first word."""
    try:
        with pytest.raises(pytest.fail.Exception, match="real kubeconform"):
            subprocess.run("kubeconform -v", shell=True, check=False)
    finally:
        unexpected_loopback_connects.clear()


def test_a_refusal_fails_the_test_through_a_handler_of_every_exception(
    unexpected_loopback_connects: list[str],
) -> None:
    """A scanner adapter that reports any exception as a failed scan cannot hide the refusal."""

    def scan() -> str:
        try:
            subprocess.run(["gitleaks", "version"], check=False)
        except Exception:
            return "failed scan"
        return "ran"

    try:
        with pytest.raises(pytest.fail.Exception, match="real gitleaks"):
            scan()
    finally:
        unexpected_loopback_connects.clear()


def test_every_other_program_still_starts() -> None:
    """The refusal names programs; git, which tests run for real, is not one of them."""
    started = subprocess.run(["git", "--version"], capture_output=True, text=True, check=False)

    assert (started.returncode, started.stdout.startswith("git version")) == (0, True)


def test_the_refused_programs_include_gh_and_the_scanners_a_review_runs() -> None:
    """gh, and Semgrep, Gitleaks and Bandit among the registry's scanners, are refused."""
    named = {CONST_GH_CLI, BIN_SEMGREP, BIN_GITLEAKS, BIN_BANDIT}

    assert named - refused_programs() == set()
