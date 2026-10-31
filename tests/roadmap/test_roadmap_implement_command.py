"""`devops roadmap implement` (#2664): what the command layer owns, the options, the report, the
exit code and the dry run. The step itself is tested in `test_roadmap_implement_step.py`."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.client import factory
from devops_cli.roadmap.implement_step import StepOutcome, StepStatus, render_outcome
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import ImplementRecordKey, ItemField
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.implement_step import BODY, DOCS, command_text, git, the_whole_group
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import BRANCH, PULL, TITLE, JobWorld, two_groups
from tests.support.roadmap_stage import STAGE_REPO

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/roadmap"


@pytest.fixture
def item(roadmap_store: InMemoryRoadmapStore) -> int:
    """Item 1 of the roadmap that every store a command opens reads."""
    return roadmap_store.seed_issue(
        "Make the sample shout",
        body=BODY,
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
    )


def _implement(cli: Callable[..., Any], checkout: Path, *extra: str, group: int = 1) -> Any:
    return cli(
        "roadmap",
        "implement",
        "--item",
        "1",
        "--group",
        str(group),
        "--repo",
        REPO,
        "--source",
        str(checkout),
        *extra,
    )


def test_a_done_step_prints_its_outcome_as_json_and_exits_0(
    cli: Callable[..., Any],
    item: int,
    implement_checkout: Path,
    implement_programs: ProcessFake,
) -> None:
    script = ModelScript(tool_calls(*the_whole_group()), say("The group is done."))
    factory.set_llm_client_override(script.model())

    result = _implement(cli, implement_checkout, "--format", "json")

    printed = json.loads(result.stdout)
    assert (
        result.exit_code,
        {
            key: printed[key]
            for key in ("item", "group", "title", "status", "reason", "last_message")
        },
        printed["commit"] == git(implement_checkout, "rev-parse", "HEAD"),
        printed["requests"],
    ) == (
        0,
        {
            "item": 1,
            "group": 1,
            "title": "The first group",
            "status": "done",
            "reason": "",
            "last_message": "The group is done.",
        },
        True,
        2,
    )
    assert result.stderr.splitlines() == ["Tool call: write_file, ok."] * 3


def test_a_done_step_prints_a_table_with_its_commit(
    cli: Callable[..., Any],
    item: int,
    implement_checkout: Path,
    implement_programs: ProcessFake,
) -> None:
    factory.set_llm_client_override(
        ModelScript(tool_calls(*the_whole_group()), say("The group is done.")).model()
    )

    result = _implement(cli, implement_checkout)

    commit = git(implement_checkout, "rev-parse", "HEAD")
    assert (result.exit_code, "done" in result.output, commit in result.output) == (0, True, True)


def test_a_stopped_step_exits_1_and_prints_its_reason_as_json(
    cli: Callable[..., Any],
    item: int,
    implement_checkout: Path,
    implement_programs: ProcessFake,
) -> None:
    implement_programs.answer(
        lambda call: command_text(call) == DOCS, ProcessAnswer(returncode=1, stdout="no docs\n")
    )
    factory.set_llm_client_override(
        ModelScript(tool_calls(*the_whole_group()), say("Done.")).model()
    )

    result = _implement(cli, implement_checkout, "--json")

    printed = json.loads(result.stdout)
    assert (result.exit_code, printed["status"], printed["reason"], printed["commit"]) == (
        1,
        "stopped",
        f"{DOCS} exited with status 1.\nno docs",
        "",
    )


def test_a_refused_step_exits_1_and_names_the_refusal(
    cli: Callable[..., Any],
    item: int,
    implement_checkout: Path,
    implement_programs: ProcessFake,
) -> None:
    result = _implement(cli, implement_checkout, group=9)

    assert (result.exit_code, "The change 1-sample-change has no group 9." in result.output) == (
        1,
        True,
    )


def test_a_step_writes_nothing_to_github(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    item: int,
    implement_checkout: Path,
    implement_programs: ProcessFake,
) -> None:
    before = roadmap_store.item(item)
    factory.set_llm_client_override(
        ModelScript(tool_calls(*the_whole_group()), say("Done.")).model()
    )

    _implement(cli, implement_checkout)

    assert (roadmap_store.item(item), roadmap_store.comments_on(item)) == (before, [])


def test_a_dry_run_makes_no_request_and_lists_the_item_read_and_the_model_requests(
    cli: Callable[..., Any],
    roadmap_store_repos: list[str],
    item: int,
    implement_checkout: Path,
    implement_programs: ProcessFake,
) -> None:
    script = ModelScript(say("Done."))
    factory.set_llm_client_override(script.model())

    result = _implement(cli, implement_checkout, "--dry-run", "--format", "json")

    printed = json.loads(result.output)
    assert (
        result.exit_code,
        printed["dry_run"],
        printed["planned_requests"],
        script.seen,
        roadmap_store_repos,
        git(implement_checkout, "status", "--porcelain"),
        implement_programs.calls,
    ) == (
        0,
        True,
        [
            f"gh api repos/{REPO}/issues/1",
            "model request devops-coder for group 1 of item #1  [repeated up to 80 times]",
        ],
        [],
        [],
        "",
        [],
    )


# ── The job (#2665) ───────────────────────────────────────────────────────────────────────


def _job(cli: Callable[..., Any], world: JobWorld, *flags: str) -> Any:
    return cli(
        "roadmap",
        "implement",
        "--repo",
        STAGE_REPO,
        "--source",
        str(world.repo.clone),
        *flags,
    )


def test_the_plan_names_the_staged_item_and_runs_nothing(
    cli: Callable[..., Any], job_world: JobWorld
) -> None:
    result = _job(cli, job_world, "--plan")

    assert result.exit_code == 0
    assert "# Implement plan for example/roadmap" in result.output
    assert f"- #1 {TITLE}: branch `{BRANCH}`, pull request #{PULL}" in result.output
    assert job_world.pull.ready_calls == []
    assert job_world.origin_log() == ["fix(roadmap): plan"]


def test_a_run_with_no_mode_flag_is_a_plan_with_a_note(
    cli: Callable[..., Any], job_world: JobWorld
) -> None:
    result = _job(cli, job_world)

    assert result.exit_code == 0
    assert "runs as --plan" in " ".join(result.output.split())
    assert job_world.origin_log() == ["fix(roadmap): plan"]


def test_the_plan_names_an_item_that_the_job_leaves_out_with_its_reason(
    cli: Callable[..., Any], job_world: JobWorld
) -> None:
    held = job_world.store.item(1)
    assert held is not None
    job_world.store.set_marks(held, {ImplementRecordKey.STOPPED: "group 2"})

    result = _job(cli, job_world, "--plan")

    assert "## Left out" in result.output
    assert "A step stopped it at group 2." in " ".join(result.output.split())


def test_why_lists_the_items_that_matched_no_filter_with_the_family_they_miss(
    cli: Callable[..., Any], job_world: JobWorld
) -> None:
    result = _job(cli, job_world, "--plan", "--filter", "effort=high", "--why")

    assert result.exit_code == 0, result.output
    assert "## Matched no filter" in result.output
    assert f"- #1 {TITLE}: The filter takes effort high. The item has effort low." in " ".join(
        result.output.split()
    )
    assert "No item to implement." in result.output


def test_without_why_the_plan_has_no_section_for_the_items_that_matched_no_filter(
    cli: Callable[..., Any], job_world: JobWorld
) -> None:
    result = _job(cli, job_world, "--plan", "--filter", "effort=high")

    assert result.exit_code == 0, result.output
    assert "Matched no filter" not in result.output


def test_confirm_outside_a_runner_exits_1_and_runs_nothing(
    cli: Callable[..., Any], job_world: JobWorld, config: Callable[..., Path]
) -> None:
    config(roadmap={"implement": {"in_runner": False}})
    script = two_groups()
    factory.set_llm_client_override(script.model())

    result = _job(cli, job_world, "--confirm")

    assert result.exit_code == 1
    assert "roadmap.implement.in_runner" in " ".join(result.output.split())
    assert (script.seen, job_world.programs.calls, job_world.api.requested) == ([], [], [])


def test_confirm_without_a_token_for_the_one_repository_exits_1_and_runs_nothing(
    cli: Callable[..., Any], job_world: JobWorld, config: Callable[..., Path]
) -> None:
    config(service={"github_app": {"token_repository": None}})
    script = two_groups()
    factory.set_llm_client_override(script.model())

    result = _job(cli, job_world, "--confirm")

    assert result.exit_code == 1
    assert "service.github_app.token_repository" in " ".join(result.output.split())
    assert (script.seen, job_world.programs.calls, job_world.api.requested) == ([], [], [])


def test_confirm_in_a_runner_takes_the_item_to_a_ready_pull_request(
    cli: Callable[..., Any], job_world: JobWorld
) -> None:
    factory.set_llm_client_override(two_groups().model())

    result = _job(cli, job_world, "--confirm")

    assert result.exit_code == 0
    assert "Took 1 item(s) to a ready pull request, stopped 0." in result.output
    assert job_world.pull.ready_calls == [("pr", "ready", str(PULL), "--repo", STAGE_REPO)]


def test_confirm_reports_a_stopped_item_and_exits_0(
    cli: Callable[..., Any], job_world: JobWorld
) -> None:
    factory.set_llm_client_override(ModelScript(say("Stuck.")).model())

    result = _job(cli, job_world, "--confirm")

    assert result.exit_code == 0
    assert "Took 0 item(s) to a ready pull request, stopped 1." in result.output


def test_confirm_reports_an_item_that_a_person_claimed_during_the_run(
    cli: Callable[..., Any], job_world: JobWorld
) -> None:
    script = two_groups()
    script.effects[2] = lambda: job_world.store.as_actor("alice").add_label(1, "owner/human")
    factory.set_llm_client_override(script.model())

    result = _job(cli, job_world, "--confirm")

    assert result.exit_code == 0
    assert "Took 0 item(s) to a ready pull request, stopped 0." in result.output
    assert "Left 1 item(s) to the owner that claimed them." in result.output


def test_the_job_dry_run_makes_no_request_and_lists_the_requests_of_a_run(
    cli: Callable[..., Any], job_world: JobWorld
) -> None:
    result = _job(cli, job_world, "--dry-run")

    assert result.exit_code == 0
    assert "Dry run: no request was made" in result.output
    assert "pr ready" in result.output
    assert (job_world.programs.calls, job_world.api.requested) == ([], [])


def test_a_filter_on_an_unknown_family_exits_1(
    cli: Callable[..., Any], job_world: JobWorld
) -> None:
    result = _job(cli, job_world, "--plan", "--filter", "color=red")

    assert result.exit_code == 1
    assert "not a label family" in " ".join(result.output.split())


def test_a_step_with_a_job_option_is_refused(
    cli: Callable[..., Any], item: int, implement_checkout: Path
) -> None:
    result = _implement(cli, implement_checkout, "--confirm")

    assert result.exit_code == 1
    assert "options of the job" in " ".join(result.output.split())


def test_a_step_needs_its_item(cli: Callable[..., Any], implement_checkout: Path) -> None:
    result = cli(
        "roadmap", "implement", "--group", "1", "--repo", REPO, "--source", str(implement_checkout)
    )

    assert result.exit_code == 1
    assert "needs --item" in " ".join(result.output.split())


def test_a_reason_with_a_closing_tag_prints_in_the_table(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The reason holds the message of a pydantic-ai error (#2758), which can hold brackets."""
    outcome = StepOutcome(
        item=1,
        group=1,
        title="Make the sample shout",
        status=StepStatus.STOPPED,
        reason="Tool x [/oops] failed",
        last_message="Run [/it] now",
    )

    render_outcome(outcome, REPO, "table")

    assert "Tool x [/oops] failed" in capsys.readouterr().out.replace("\n", " ")
