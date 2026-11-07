"""`devops roadmap explain`: the arguments, the options, the report and the exit code (#2911)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

from devops_cli.roadmap.implement.implement_trace import ImplementTrace
from devops_cli.roadmap.stores.store import ImplementRecordKey, ItemField
from tests.support.roadmap_implement import JobWorld
from tests.support.roadmap_stage import STAGE_REPO

pytestmark = pytest.mark.usefixtures("keyring_store")

Cli = Callable[..., Any]


def _explain(cli: Cli, world: JobWorld, number: int, *flags: str) -> Any:
    return cli(
        "roadmap",
        "explain",
        str(number),
        "--repo",
        STAGE_REPO,
        "--source",
        str(world.repo.clone),
        *flags,
    )


def test_the_report_gives_a_yes_for_the_staged_item(cli: Cli, job_world: JobWorld) -> None:
    result = _explain(cli, job_world, job_world.number)

    assert result.exit_code == 0, result.output
    assert "Implement job: yes." in result.output
    assert "Refine job:" in result.output
    assert job_world.pull.ready_calls == []


def test_the_report_names_the_failing_rule_of_an_item_of_high_effort(
    cli: Cli, job_world: JobWorld
) -> None:
    number = job_world.store.seed_issue(
        "fix(roadmap): another job drops a label",
        labels=("type/bug", "effort/high"),
        fields={ItemField.STATUS: "Planned", ItemField.PRIORITY: "P1-High"},
        author_association="OWNER",
    )

    result = _explain(cli, job_world, number)

    assert result.exit_code == 0, result.output
    assert (
        "Implement job: no. The filter takes effort low or medium. The item has effort high."
        in " ".join(result.output.split())
    )


def test_filter_replaces_the_filter_of_both_jobs(cli: Cli, job_world: JobWorld) -> None:
    number = job_world.store.seed_issue(
        "fix(roadmap): another job drops a label",
        labels=("type/bug", "effort/medium"),
        fields={ItemField.STATUS: "Planned", ItemField.PRIORITY: "P1-High"},
        author_association="OWNER",
    )

    result = _explain(cli, job_world, number, "--filter", "effort=medium")

    assert result.exit_code == 0, result.output
    assert "The filter takes" not in result.output


def test_limit_replaces_the_limit_of_both_jobs(cli: Cli, job_world: JobWorld) -> None:
    first = job_world.store.seed_issue(
        "fix(roadmap): another job drops a label",
        labels=("type/bug", "effort/low"),
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P0-Critical"},
        author_association="OWNER",
    )
    second = job_world.store.seed_issue(
        "fix(roadmap): a third job drops it",
        labels=("type/bug", "effort/low"),
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P2-Medium"},
        author_association="OWNER",
    )

    result = _explain(cli, job_world, second, "--limit", "1")

    assert first != second
    assert result.exit_code == 0, result.output
    assert "a run takes 1 item(s)" in " ".join(result.output.split())


def test_a_dry_run_makes_no_request_and_lists_the_reads(cli: Cli, job_world: JobWorld) -> None:
    result = _explain(cli, job_world, job_world.number, "--dry-run")

    assert result.exit_code == 0, result.output
    assert "Dry run: no request was made" in result.output
    assert f"issues/{job_world.number}" in result.output
    assert job_world.api.requested == []


# ── The option --trace (#3032) ────────────────────────────────────────────────────────────


def _with_trace(world: JobWorld, text: str) -> None:
    item = world.store.item(world.number)
    assert item is not None
    world.store.set_marks(item, {ImplementRecordKey.TRACE: text})


def test_the_trace_option_prints_the_events_oldest_first_and_no_verdict(
    cli: Cli, job_world: JobWorld
) -> None:
    trace = ImplementTrace(step="group 1")
    trace.retry("first")
    trace.retry("second")
    _with_trace(job_world, trace.encode())
    writes = job_world.store.job_writes

    result = _explain(cli, job_world, job_world.number, "--trace")

    assert result.exit_code == 0, result.output
    assert result.output.index("first") < result.output.index("second")
    assert "job: yes" not in result.output
    assert "job: no" not in result.output
    assert job_world.store.job_writes == writes


def test_an_issue_with_no_trace_says_so_and_exits_0(cli: Cli, job_world: JobWorld) -> None:
    result = _explain(cli, job_world, job_world.number, "--trace")

    assert result.exit_code == 0, result.output
    assert "has no trace of a run" in result.output


def test_a_trace_that_is_not_json_exits_1_and_names_the_key(cli: Cli, job_world: JobWorld) -> None:
    _with_trace(job_world, "not json")

    result = _explain(cli, job_world, job_world.number, "--trace")

    assert result.exit_code == 1
    assert "implement.trace" in result.output


def test_a_dry_run_with_the_trace_option_lists_the_read_of_the_issue_only(
    cli: Cli, job_world: JobWorld
) -> None:
    result = _explain(cli, job_world, job_world.number, "--trace", "--dry-run")

    assert result.exit_code == 0, result.output
    assert f"#{job_world.number}" in result.output
    assert "branch" not in result.output.lower().replace("branches", "")
    assert job_world.api.requested == []


# ── The option --json (#3217) ────────────────────────────────────────────────────────────


def _totals_trace() -> ImplementTrace:
    """The trace of a run with one model event and two attempts: a failed one that a repair
    round follows, and a passed one that ends the step."""
    trace = ImplementTrace(step="group 1")
    trace.model_call("model-a", 1200, 300, 90.0)
    trace.attempt(1, "standard", "check_failed", "ruff check . exited 1", repair=True)
    trace.attempt(2, "standard", "", "", repair=False)
    return trace


def test_the_json_option_gives_the_totals_of_the_last_run(cli: Cli, job_world: JobWorld) -> None:
    _with_trace(job_world, _totals_trace().encode())

    result = _explain(cli, job_world, job_world.number, "--json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "number": job_world.number,
        "tokens_total": 1500,
        "seconds_total": 90.0,
        "repair_rounds": 1,
        "outcomes": {"failed": 1, "passed": 1},
        "dropped": 0,
    }


def test_the_report_without_json_names_the_same_totals(cli: Cli, job_world: JobWorld) -> None:
    _with_trace(job_world, _totals_trace().encode())

    result = _explain(cli, job_world, job_world.number)

    assert result.exit_code == 0, result.output
    assert "1500 tokens" in result.output
    assert "90.0 s" in result.output
    assert "1 repair round(s)" in result.output
    assert "1 failed and 1 passed outcome(s)" in result.output


def test_the_json_option_gives_null_for_each_total_of_an_item_with_no_run(
    cli: Cli, job_world: JobWorld
) -> None:
    result = _explain(cli, job_world, job_world.number, "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["number"] == job_world.number
    assert (
        payload["tokens_total"],
        payload["seconds_total"],
        payload["repair_rounds"],
        payload["outcomes"],
        payload["dropped"],
    ) == (None, None, None, None, None)


def test_the_json_option_with_the_trace_option_exits_1_and_names_both(
    cli: Cli, job_world: JobWorld
) -> None:
    result = _explain(cli, job_world, job_world.number, "--json", "--trace")

    assert result.exit_code == 1
    assert "--json" in result.output
    assert "--trace" in result.output
