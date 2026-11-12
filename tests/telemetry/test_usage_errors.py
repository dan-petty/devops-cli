"""A usage error of the CLI leaves one record of its kind and names, and no argument value (#4839).

The record goes to three sinks: a line of the usage-error ledger under the user data root, the
log record `cli_usage_error` and the counter `devops_cli_usage_error_total`. The tests read the
ledger file, and the OTLP fake for the log record and the counter.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from devops_cli import __version__
from devops_cli.ai.mcp.dispatcher import InProcessDispatcher
from devops_cli.lang import MESSAGES
from tests.support.agent_markers import agent_marker_names
from tests.support.fakes.otlp import FakeCollector, plain_attributes

_LEDGER = "usage-errors.jsonl"
_COUNTER = "devops_cli_usage_error_total"
_LOG_BODY = "cli_usage_error"

# Values that a caller types where the CLI expects a name: a GitHub token, a random hex token, a
# number and a path. None of them may reach a sink.
_VALUES = (
    "ghp_" + "A1b2C3d4" * 4 + "e5F6",
    "deadbeefcafebabe0123456789abcdef",
    "4839",
    "docs/private/notes.txt",
)

Ledger = Callable[[], list[dict[str, Any]]]


@pytest.fixture
def ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Ledger:
    """A user data root of the test's own, and a caller with no agent or CI marker: a person.

    The reader gives each ledger line without its time, which is the one field a test cannot
    know before the call."""
    for name in agent_marker_names():
        monkeypatch.delenv(name, raising=False)
    root = tmp_path / "data"
    monkeypatch.setenv("DEVOPS_CLI_USER_DATA_ROOT", str(root))

    def read() -> list[dict[str, Any]]:
        path = root / _LEDGER
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        return [{k: v for k, v in json.loads(line).items() if k != "at"} for line in lines]

    return read


def _record(
    kind: str,
    command_path: str,
    name: str | None = None,
    suggestion: str | None = None,
    *,
    caller: str = "person",
    agent_tool: str | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "command_path": command_path,
        "name": name,
        "suggestion": suggestion,
        "caller": caller,
        "agent_tool": agent_tool,
        "version": __version__,
    }


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (("gh", "prr", "list"), _record("unknown_command", "gh", "prr", "pr")),
        (("pr", "view", "1", "--repoo"), _record("unknown_option", "pr view", "--repoo", "--repo")),
        (("pr", "describe"), _record("missing_argument", "pr describe", "issue")),
        (("pr", "describe", "1"), _record("missing_option", "pr describe", "summary")),
        (("pr", "view", "1", "2"), _record("extra_argument", "pr view")),
        (("pr", "list", "--limit", "many"), _record("bad_value", "pr list", "limit")),
        (("pr", "list", "--limit"), _record("option_usage", "pr list", "--limit")),
        (("prr", "list"), _record("unknown_command", "", "prr", "pr")),
    ],
)
def test_a_usage_error_leaves_one_ledger_line_of_its_kind(
    cli: Callable[..., Any], ledger: Ledger, args: tuple[str, ...], expected: dict[str, Any]
) -> None:
    result = cli(*args)

    assert (result.exit_code, ledger()) == (2, [expected])


@pytest.mark.parametrize("value", _VALUES)
def test_a_value_in_the_place_of_a_command_name_is_recorded_as_a_value(
    cli: Callable[..., Any], ledger: Ledger, value: str
) -> None:
    result = cli("gh", value, "list")

    assert (result.exit_code, ledger()) == (2, [_record("unknown_command", "gh", "<value>")])


def test_no_argument_value_reaches_a_ledger_line_a_log_record_or_a_counter_label(
    cli: Callable[..., Any], ledger: Ledger, otlp: FakeCollector, tmp_path: Path
) -> None:
    token, hex_token, number, path = _VALUES
    calls = (
        ("gh", token, "list"),
        ("gh", hex_token),
        ("pr", "view", number, path),
        ("pr", "list", "--limit", token),
        ("pr", "view", "1", "--repo", hex_token, "--repoo"),
        ("pr", "describe", number),
    )

    codes = [cli(*call).exit_code for call in calls]

    # The body and the attributes of each log record: its time and trace ids are random digits,
    # which can hold the number by chance.
    logged = [
        {"body": r["body"], **plain_attributes(r["attributes"])}
        for r in otlp.log_records
        if r["body"]["stringValue"] == _LOG_BODY
    ]
    sinks = {
        "ledger": (tmp_path / "data" / _LEDGER).read_text(encoding="utf-8"),
        "log": json.dumps(logged),
        "counter": json.dumps(otlp.points(_COUNTER)),
    }
    leaks = {sink: [v for v in _VALUES if v in text] for sink, text in sinks.items()}
    assert (codes, len(ledger()), len(logged), leaks) == (
        [2] * len(calls),
        len(calls),
        len(calls),
        {"ledger": [], "log": [], "counter": []},
    )


def test_the_counter_holds_only_the_kind_the_command_path_and_the_caller(
    cli: Callable[..., Any], ledger: Ledger, otlp: FakeCollector
) -> None:
    cli("gh", "prr", "list")

    assert otlp.points(_COUNTER) == [
        ({"kind": "unknown_command", "command_path": "gh", "caller": "person"}, 1.0)
    ]


def test_the_log_record_holds_the_names_of_the_ledger_line(
    cli: Callable[..., Any], ledger: Ledger, otlp: FakeCollector
) -> None:
    cli("pr", "view", "1", "--repoo")

    records = [r for r in otlp.log_records if r["body"]["stringValue"] == _LOG_BODY]
    usage = [
        {k: v for k, v in plain_attributes(r["attributes"]).items() if k.startswith("usage.")}
        for r in records
    ]
    assert usage == [
        {
            "usage.kind": "unknown_option",
            "usage.command_path": "pr view",
            "usage.name": "--repoo",
            "usage.suggestion": "--repo",
            "usage.caller": "person",
            "usage.version": __version__,
        }
    ]


def test_the_error_box_and_the_exit_code_of_a_usage_error_stay_the_same(
    cli: Callable[..., Any], ledger: Ledger, snapshot: SnapshotAssertion
) -> None:
    """The record is silent: the person sees the error box of Typer and nothing of the record."""
    result = cli("gh", "prr", "list")

    assert {"exit_code": result.exit_code, "output": result.output} == snapshot


@pytest.mark.parametrize(
    "args",
    [("gh", "prr", "--help"), ("--dry-run", "gh", "prr", "list")],
)
def test_a_help_query_and_a_dry_run_record_their_usage_error_once(
    cli: Callable[..., Any], ledger: Ledger, args: tuple[str, ...]
) -> None:
    result = cli(*args)

    assert (result.exit_code, ledger()) == (2, [_record("unknown_command", "gh", "prr", "pr")])


def test_a_usage_error_of_an_mcp_tool_records_the_caller_mcp(ledger: Ledger) -> None:
    code, _ = InProcessDispatcher().dispatch(["devops", "gh", "prr", "list"])

    assert (code, ledger()) == (2, [_record("unknown_command", "gh", "prr", "pr", caller="mcp")])


@pytest.mark.parametrize(
    ("markers", "caller", "agent_tool"),
    [
        ({"AI_AGENT": "claude-code_2-1-322_agent"}, "agent", "claude_code"),
        ({"AI_AGENT": "devops-implement"}, "agent", "devops_implement"),
        ({"AI_AGENT": "a-new-tool"}, "agent", "other"),
        ({"GEMINI_CLI": "1"}, "agent", "gemini_cli"),
        ({"KILO": "1", "OPENCODE": "1"}, "agent", "kilo"),
        ({"OPENCODE": "1"}, "agent", "opencode"),
        ({"CI": "true"}, "ci", None),
        ({"GITHUB_ACTIONS": "true"}, "ci", None),
        ({}, "person", None),
    ],
)
def test_the_markers_of_the_environment_name_the_caller(
    cli: Callable[..., Any],
    ledger: Ledger,
    markers: dict[str, str],
    caller: str,
    agent_tool: str | None,
) -> None:
    cli("gh", "prr", "list", env=markers)

    assert ledger() == [
        _record("unknown_command", "gh", "prr", "pr", caller=caller, agent_tool=agent_tool)
    ]


def test_a_request_for_help_with_no_arguments_is_no_usage_error(
    cli: Callable[..., Any], ledger: Ledger
) -> None:
    result = cli()

    assert (result.exit_code, ledger()) == (2, [])


def test_the_setting_turns_the_ledger_off(
    cli: Callable[..., Any], ledger: Ledger, config: Callable[..., Path]
) -> None:
    config(telemetry={"usage_ledger": False})

    result = cli("gh", "prr", "list")

    assert (result.exit_code, ledger()) == (2, [])


def test_settings_that_cannot_load_keep_the_ledger_off(
    cli: Callable[..., Any], ledger: Ledger, config: Callable[..., Path]
) -> None:
    """Such settings can be the ones that turn the ledger off, so it does not fail open (#956)."""
    config(telemetry={"usage_ledger": "sometimes"})

    result = cli("gh", "prr", "list")

    assert (result.exit_code, ledger()) == (2, [])


@pytest.mark.parametrize("blocked", ["root-is-a-file", "ledger-is-a-directory"])
def test_a_ledger_that_cannot_be_written_gives_one_warning_and_keeps_the_exit_code(
    cli: Callable[..., Any],
    ledger: Ledger,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    blocked: str,
) -> None:
    root = tmp_path / "blocked"
    if blocked == "root-is-a-file":
        root.write_text("", encoding="utf-8")
    else:
        (root / _LEDGER).mkdir(parents=True)
    monkeypatch.setenv("DEVOPS_CLI_USER_DATA_ROOT", str(root))
    warning = MESSAGES.telemetry.usage_ledger_unwritable.split("{", 1)[0]

    result = cli("gh", "prr", "list")

    assert (result.exit_code, result.output.count(warning)) == (2, 1)
