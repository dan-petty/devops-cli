"""The `bwrap` row of `devops ci`: the contract suite of the real sandbox, which runs where the
host can make a sandbox and skips with the cause where it cannot (#4715)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.commands.ci import app, get_check_spec
from devops_cli.core.process import prepare_tool_cmd
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.paths import REPO_ROOT

pytestmark = pytest.mark.usefixtures("refuse_nested_test_runs")

runner = CliRunner()

_NAMESPACE_REFUSED = "bwrap: setting up uid map: Permission denied"
_CAUSE = f"bubblewrap cannot make a sandbox on this host: {_NAMESPACE_REFUSED}"


def _programs(process_fake: ProcessFake) -> list[str]:
    """The program of each command that the gate started, other than git."""
    return [call.argv[0] for call in process_fake.calls if call.argv[0] != "git"]


def test_the_bwrap_row_runs_the_tests_marked_bwrap_of_the_sandbox_contract_suites() -> None:
    """The row selects the `bwrap` mark in the two contract suites of the sandbox, in one process,
    and each file is in the tree."""
    cmd = get_check_spec("bwrap").cmd
    files = cmd[cmd.index("0") + 1 :]

    assert (cmd[: cmd.index("0") + 1], files, all((REPO_ROOT / f).is_file() for f in files)) == (
        ["uv", "run", "pytest", "-m", "bwrap", "-n", "0"],
        ["tests/sandbox/test_host_sandbox.py", "tests/ai/test_tool_executor_contract.py"],
        True,
    )


@pytest.mark.usefixtures("ci_root")
def test_the_bwrap_row_runs_the_suite_where_the_host_can_make_a_sandbox(
    sandbox_host: Path, process_fake: ProcessFake
) -> None:
    """The row checks the host with the check of the sandbox executor, then starts the suite."""
    result = runner.invoke(app, ["--only", "bwrap", "--check", "--no-cache"])

    assert (result.exit_code, _programs(process_fake), process_fake.calls[-1].argv) == (
        0,
        [str(sandbox_host), "uv"],
        tuple(prepare_tool_cmd(get_check_spec("bwrap").cmd)),
    )


@pytest.mark.usefixtures("ci_root")
def test_the_bwrap_row_skips_with_the_cause_where_the_host_cannot_make_a_sandbox(
    sandbox_host: Path, process_fake: ProcessFake
) -> None:
    """The row starts no suite, passes, and names the cause in its line and in the summary."""
    process_fake.answer(
        str(sandbox_host), ProcessAnswer(returncode=1, stderr=f"{_NAMESPACE_REFUSED}\n")
    )

    result = runner.invoke(app, ["--only", "bwrap", "--check", "--no-cache"])

    said = " ".join(result.output.split())
    assert (result.exit_code, _programs(process_fake), f"[bwrap] skipped: {_CAUSE}" in said) == (
        0,
        [str(sandbox_host)],
        True,
    )


def test_a_cached_verdict_keeps_the_skip_of_a_row(
    ci_root: Path, ci_head: ProcessFake, sandbox_host: Path
) -> None:
    """A gate that passed with the row skipped reads back from the cache as skipped, not passed."""
    ci_head.answer(str(sandbox_host), ProcessAnswer(returncode=1, stderr=f"{_NAMESPACE_REFUSED}\n"))
    first = runner.invoke(app, ["--check"])
    ci_head.calls.clear()

    cached = runner.invoke(app, ["--check"])

    rows = [line for line in cached.output.splitlines() if " bwrap " in line]
    assert (first.exit_code, cached.exit_code, _programs(ci_head), "skip" in rows[0]) == (
        0,
        0,
        [],
        True,
    )
