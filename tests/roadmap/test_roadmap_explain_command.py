"""`devops roadmap explain`: the arguments, the options, the report and the exit code (#2911)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from devops_cli.roadmap.store import ItemField
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
    assert job_world.pull.ready_calls == []


def test_the_report_names_the_failing_rule_of_an_item_of_medium_effort(
    cli: Cli, job_world: JobWorld
) -> None:
    number = job_world.store.seed_issue(
        "fix(roadmap): another job drops a label",
        labels=("type/bug", "effort/medium"),
        fields={ItemField.STATUS: "Planned", ItemField.PRIORITY: "P1-High"},
        author_association="OWNER",
    )

    result = _explain(cli, job_world, number)

    assert result.exit_code == 0, result.output
    assert (
        "Implement job: no. The filter takes effort low. The item has effort medium."
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
