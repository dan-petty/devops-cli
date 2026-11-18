"""Tests for generated and hand-written row commands of the ci group."""

from __future__ import annotations

import json
import platform
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands.ci import (
    CHECK_ROW_NAMES,
    _planned_requests,
    app,
    get_check_spec,
    get_check_specs,
    resolve_selected_specs,
)
from tests.support.agent_markers import agent_marker_names
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

platform.processor()

runner = CliRunner()

_LEDGER = "usage-errors.jsonl"
Ledger = Callable[[], list[dict[str, Any]]]


@pytest.fixture
def ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Ledger:
    """A user data root of the test's own, and a caller with no agent or CI marker: a person."""
    for name in agent_marker_names():
        monkeypatch.delenv(name, raising=False)
    root = tmp_path / "data"
    monkeypatch.setenv("DEVOPS_CLI_USER_DATA_ROOT", str(root))

    def read() -> list[dict[str, Any]]:
        path = root / _LEDGER
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        return [{k: v for k, v in json.loads(line).items() if k != "at"} for line in lines]

    return read


@pytest.fixture
def recorder(process_fake: ProcessFake) -> list[list[str]]:
    """Capture the programs the runner is asked to start, answering each with success."""
    calls: list[list[str]] = []

    def record(call: ProcessCall) -> ProcessAnswer:
        calls.append(list(call.argv))
        return ProcessAnswer()

    process_fake.answer(lambda _call: True, record)
    return calls


def test_a_row_command_plans_only_its_row(recorder: list[list[str]]) -> None:
    """A row with no hand-written command runs dry-run and plans only its requests."""
    res_constructs = runner.invoke(app, ["constructs", "--dry-run"])
    assert res_constructs.exit_code == 0
    constructs_spec = get_check_spec("constructs")
    for req in _planned_requests(constructs_spec):
        assert req.line() in res_constructs.stdout

    test_tree_spec = get_check_spec("test-tree")
    for req in _planned_requests(test_tree_spec):
        assert req.line() not in res_constructs.stdout

    res_tree = runner.invoke(app, ["test-tree", "--dry-run"])
    assert res_tree.exit_code == 0
    for req in _planned_requests(test_tree_spec):
        assert req.line() in res_tree.stdout
    for req in _planned_requests(constructs_spec):
        assert req.line() not in res_tree.stdout


def test_the_gate_rows_run_with_the_malware_check_off() -> None:
    """The plan of `devops ci --only lint` gives every request `UV_MALWARE_CHECK` of `0` (#4881)."""
    requests = [
        request
        for spec in resolve_selected_specs(only=["lint"])
        for request in _planned_requests(spec)
    ]

    assert requests != []
    assert [dict(request.env).get("UV_MALWARE_CHECK") for request in requests] == ["0"] * len(
        requests
    )


def test_the_row_tuple_matches_the_registry() -> None:
    """The static row tuple in ci.py equals the check specs in registry order."""
    expected = tuple(spec.name for spec in get_check_specs())
    assert CHECK_ROW_NAMES == expected


def test_the_kube_linter_row_lints_the_applications_of_the_tree() -> None:
    """The row runs `devops k8s lint` with no target and no other command, before the rows of
    `tests/gate` (#6068)."""
    spec = get_check_spec("kube-linter")
    names = [row.name for row in get_check_specs()]

    assert (spec.cmd, spec.also_cmds, names.index("kube-linter") < names.index("k8s")) == (
        ["uv", "run", "devops", "k8s", "lint"],
        [],
        True,
    )


def test_a_row_with_a_hand_written_command_runs_dry_run(recorder: list[list[str]]) -> None:
    """A row with a hand-written command plans its command under dry-run."""
    res = runner.invoke(app, ["lint", "--dry-run"])
    assert res.exit_code == 0
    expected_cmd = "UV_MALWARE_CHECK=0 uv --preview-features malware-check,check-command run ruff check --config pyproject.toml --fix ."
    assert f"1. {expected_cmd}" in res.stdout


def test_a_misspelled_only_name_records_bad_value(cli: Callable[..., Any], ledger: Ledger) -> None:
    """A misspelled row name in --only raises bad parameter and records bad_value."""
    res = cli("ci", "--only", "constructz")
    assert res.exit_code == 2
    assert "constructs" in res.output
    records = ledger()
    assert len(records) == 1
    assert records[0]["kind"] == "bad_value"
    assert records[0]["command_path"] == "ci"


def test_a_misspelled_skip_name_records_bad_value(cli: Callable[..., Any], ledger: Ledger) -> None:
    """A misspelled row name in --skip raises bad parameter and records bad_value."""
    res = cli("ci", "--skip", "constructz")
    assert res.exit_code == 2
    records = ledger()
    assert len(records) == 1
    assert records[0]["kind"] == "bad_value"
    assert records[0]["command_path"] == "ci"


def test_ci_only_multiple_comma_separated_dry_run(recorder: list[list[str]]) -> None:
    """Comma-separated check rows in --only plan exactly those rows."""
    res = runner.invoke(app, ["--only", "constructs,openspec", "--dry-run"])
    assert res.exit_code == 0
    constructs_spec = get_check_spec("constructs")
    openspec_spec = get_check_spec("openspec")
    test_tree_spec = get_check_spec("test-tree")
    for req in _planned_requests(constructs_spec):
        assert req.line() in res.stdout
    for req in _planned_requests(openspec_spec):
        assert req.line() in res.stdout
    for req in _planned_requests(test_tree_spec):
        assert req.line() not in res.stdout


def test_ci_only_repeated_option_dry_run(recorder: list[list[str]]) -> None:
    """Repeated --only options plan exactly those rows."""
    res = runner.invoke(app, ["--only", "constructs", "--only", "openspec", "--dry-run"])
    assert res.exit_code == 0
    constructs_spec = get_check_spec("constructs")
    openspec_spec = get_check_spec("openspec")
    test_tree_spec = get_check_spec("test-tree")
    for req in _planned_requests(constructs_spec):
        assert req.line() in res.stdout
    for req in _planned_requests(openspec_spec):
        assert req.line() in res.stdout
    for req in _planned_requests(test_tree_spec):
        assert req.line() not in res.stdout


def test_the_selection_help_names_the_rows() -> None:
    """The help of --only and --skip lists each row name."""
    res = runner.invoke(app, ["--help"])
    assert res.exit_code == 0
    lines = res.stdout.splitlines()
    only_lines: list[str] = []
    skip_lines: list[str] = []
    target: list[str] | None = None
    for line in lines:
        if "--only" in line:
            target = only_lines
        elif "--skip" in line:
            target = skip_lines
        elif target is not None and line.strip().startswith("--"):
            target = None
        if target is not None:
            target.append(line)
    only_block = " ".join(only_lines)
    skip_block = " ".join(skip_lines)
    for name in CHECK_ROW_NAMES:
        assert name in only_block
        assert name in skip_block


def test_the_removed_run_command_records_unknown_command(
    cli: Callable[..., Any], ledger: Ledger
) -> None:
    """The removed 'run' subcommand exits 2 and records unknown_command with command path 'ci'."""
    res = cli("ci", "run")
    assert res.exit_code == 2
    records = ledger()
    assert len(records) == 1
    assert records[0]["kind"] == "unknown_command"
    assert records[0]["command_path"] == "ci"
    assert records[0]["name"] == "run"
