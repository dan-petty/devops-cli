"""What the implement job keeps (#2665): its job record keys, the setting that lets it run steps,
the relation of a commenter to the repository, and the default filter it gives the stage job's
parser."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from devops_cli.config.settings import load_settings
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.stage import parse_filters
from devops_cli.roadmap.store import ImplementRecordKey, ItemField, decode_job_record
from tests.support.builders import make_item


def test_the_job_keeps_six_keys_in_the_record_of_an_item() -> None:
    store = InMemoryRoadmapStore()
    number = store.seed_issue("fix(x): y", fields={ItemField.PRIORITY: "P1-High"})
    item = store.item(number)
    assert item is not None

    store.set_marks(
        item,
        {
            ImplementRecordKey.GROUP: "2",
            ImplementRecordKey.SHA: "abc",
            ImplementRecordKey.BRANCH: "fix/1-y",
            ImplementRecordKey.PR: "9",
            ImplementRecordKey.STOPPED: "group 3",
            ImplementRecordKey.SPEND: '{"requests": 7}',
        },
    )

    held = store.item(number)
    assert held is not None
    assert held.job_record == {
        ImplementRecordKey.GROUP: "2",
        ImplementRecordKey.SHA: "abc",
        ImplementRecordKey.BRANCH: "fix/1-y",
        ImplementRecordKey.PR: "9",
        ImplementRecordKey.STOPPED: "group 3",
        ImplementRecordKey.SPEND: '{"requests": 7}',
    }


def test_a_record_block_from_a_person_edit_is_decoded_with_the_implement_keys() -> None:
    held = {
        "implement.stopped": "rebase",
        "implement.branch": "fix/4-z",
        "implement.pr": "4",
        "other.job": "kept",
    }

    assert decode_job_record(held) == {
        ImplementRecordKey.STOPPED: "rebase",
        ImplementRecordKey.BRANCH: "fix/4-z",
        ImplementRecordKey.PR: "4",
    }


def test_the_job_runs_no_step_unless_the_setting_says_it_is_in_a_runner(
    config: Callable[..., Path],
) -> None:
    assert load_settings().roadmap.implement.in_runner is False

    config(roadmap={"implement": {"in_runner": True}})

    assert load_settings().roadmap.implement.in_runner is True


def test_the_comment_of_a_trusted_commenter_keeps_its_relation_to_the_repository() -> None:
    store = InMemoryRoadmapStore()
    number = store.seed_issue("fix(x): y", fields={ItemField.PRIORITY: "P1-High"})

    store.seed_comment(number, "implement: retry", author_association="OWNER")
    store.comment(number, "from the job")

    assert [(c.body, c.author_association) for c in store.comments_on(number)] == [
        ("implement: retry", "OWNER"),
        ("from the job", None),
    ]


def test_the_stage_parser_takes_the_defaults_of_the_job() -> None:
    defaults = ("status=ready", "effort=low")

    parsed = parse_filters((), defaults)

    assert parsed.matches(make_item(labels=("status/ready", "effort/low")))
    assert not parsed.matches(make_item(labels=("status/ready", "effort/high")))
