"""`devops roadmap implement` (#2664): what the command layer owns, the options, the report, the
exit code and the dry run. The step itself is tested in `test_roadmap_implement_step.py`."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.client import factory
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import ItemField
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.implement_step import BODY, DOCS, command_text, git, the_whole_group
from tests.support.model_script import ModelScript, say, tool_calls

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

    printed = json.loads(result.output)
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

    printed = json.loads(result.output)
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
