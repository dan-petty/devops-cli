"""The table of the steps in the comment on the pull request and in the stop comment (#3032)."""

from __future__ import annotations

import pytest
from pydantic_ai.messages import ModelResponse

from devops_cli.roadmap.implement.implement_trace import ImplementTrace, decode
from devops_cli.roadmap.stores.store import ImplementRecordKey
from tests.support.fakes.process import ProcessAnswer
from tests.support.implement_step import command_text
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import (
    FAIL,
    PULL,
    SHOUT,
    JobWorld,
    group_one_calls,
    two_groups,
)

pytestmark = pytest.mark.usefixtures("keyring_store")

CHECK = "Tests & Coverage"
LINT = "uv run ruff check"


def _rows(comment: str) -> list[list[str]]:
    """The cells of the data rows of the table of a comment."""
    lines = [line for line in comment.splitlines() if line.startswith("| ")][2:]
    return [[cell.strip() for cell in line.strip("|").split(" | ")] for line in lines]


def test_the_comment_on_the_pull_request_has_a_row_for_each_step_and_the_scoped_lines(
    job_world: JobWorld,
) -> None:
    job_world.run(two_groups())

    (comment,) = job_world.sent("POST", f"issues/{PULL}/comments")
    rows = _rows(comment["body"])
    assert [(row[0], row[1], row[2]) for row in rows] == [
        ("group 1", "done", "1"),
        ("group 2", "done", "1"),
    ]
    assert all("/" in row[3] for row in rows)
    assert "- scoped check static: passed" in comment["body"]


def test_a_step_that_stops_on_a_failed_command_has_its_row_before_the_reason(
    job_world: JobWorld,
) -> None:
    job_world.programs.answer(
        lambda call: command_text(call).startswith(LINT),
        ProcessAnswer(returncode=1, stdout="E501 line too long\n"),
    )
    script = ModelScript(tool_calls(*group_one_calls()), say("Done."), say("Nothing."), say("No."))

    applied = job_world.run(script)

    (comment,) = job_world.issue_comments()
    (row,) = _rows(comment)
    assert applied.stopped == (1,)
    assert row[0] == "group 1"
    assert row[1] == "stopped"
    assert int(row[2]) > 1
    assert LINT in row[4]
    assert comment.index("Failure class") < comment.index("| group 1 ") < comment.index("Reason:")


def test_a_command_of_the_job_that_fails_gets_a_row_of_its_own(job_world: JobWorld) -> None:
    job_world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops docs generate"),
        ProcessAnswer(returncode=3, stderr="boom"),
    )

    applied = job_world.run(two_groups())

    (comment,) = job_world.issue_comments()
    rows = _rows(comment)
    assert applied.stopped == (1,)
    assert rows[-1][0] == "docs"
    assert "docs generate" in rows[-1][4]


def _fix(round_number: int) -> tuple[ModelResponse, ModelResponse]:
    """A fix that changes the code in a way that no earlier fix did."""
    changed = SHOUT + "".join(f"\n\nVALUE_{k} = {k}\n" for k in range(round_number))
    path = "src/devops_cli/shout.py"
    return (
        tool_calls(("write_file", {"path": path, "content": changed})),
        say(f"Fixed round {round_number}."),
    )


def test_a_failed_check_of_the_pull_request_gives_a_row_for_the_step_of_the_checks(
    job_world: JobWorld,
) -> None:
    job_world.pull.runs = [[FAIL]]

    job_world.run(two_groups(*_fix(1), *_fix(2), *_fix(3)))

    (comment,) = job_world.issue_comments()
    last = _rows(comment)[-1]
    assert last[0] == "checks"
    assert last[4] == f"`{CHECK}`"
    held = job_world.store.item(1)
    assert held is not None
    assert isinstance(decode(held.job_record[ImplementRecordKey.TRACE] or ""), ImplementTrace)
