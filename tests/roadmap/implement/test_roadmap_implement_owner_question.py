"""The owner question that the implement job asks (#3077).

An implement step that stops with the class `plan_defect` needs an owner decision, so it posts one
owner-question frame: the question whether to amend the plan or split the item once, two options
with their results, a recommendation, the evidence of the failing check and the hidden block with
the question hash. The record of the item holds the hash and the question in the same write as the
stop, so the inbox lists the open question and a trusted reply resumes the item.
"""

from __future__ import annotations

import pytest

from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.owner_question import frame_hash
from devops_cli.roadmap.stores.store import Item, OwnerQuestionRecordKey
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import JobWorld, group_one_calls

pytestmark = pytest.mark.usefixtures("keyring_store")


def _item(world: JobWorld) -> Item:
    item = world.store.item(1)
    assert item is not None
    return item


def _record(world: JobWorld) -> dict[str, str | None]:
    return {str(key): value for key, value in _item(world).job_record.items()}


def test_a_stop_of_class_plan_defect_posts_the_owner_question_frame(job_world: JobWorld) -> None:
    """The stop of group 2 changes no file, which is a plan defect, so the step asks the owner
    whether to amend the plan or split the item: one frame with the question once, the two options
    with their results, the recommendation, the item as the evidence, and the hidden block whose
    hash the record keeps with the question text."""
    script = ModelScript(
        tool_calls(*group_one_calls()),
        say("Group 1 is done."),
        say("I could not do group 2."),
    )

    applied = job_world.run(script)

    frames = [body for body in job_world.issue_comments() if frame_hash(body) is not None]
    record = _record(job_world)
    assert applied.stopped == (1,)
    assert record.get("implement.failure") == "plan_defect"
    assert len(frames) == 1
    (frame,) = frames
    assert frame.startswith(f"{CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER}\n")
    assert record.get(OwnerQuestionRecordKey.HASH) == frame_hash(frame)
    question = record.get(OwnerQuestionRecordKey.TEXT) or ""
    assert (question in frame, frame.count(question)) == (True, 1)
    options = MESSAGES.roadmap.implement_owner_question_options
    assert 2 <= len(options) <= 3
    assert [text in frame and result in frame for text, result in options.items()] == [True, True]
    assert MESSAGES.roadmap.implement_owner_question_recommendation in frame
    assert _item(job_world).url in frame
    assert record.get(OwnerQuestionRecordKey.ANSWER) is None
