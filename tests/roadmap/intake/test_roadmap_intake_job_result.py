"""Intake logs one result line for each candidate that it writes (#4845)."""

from __future__ import annotations

import logging

import pytest

from devops_cli.roadmap.intake.intake import apply_intake
from tests.support.roadmap_intake import REPO, FakeModel, Roadmap
from tests.support.roadmap_job_result import result_fields

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_each_candidate_logs_one_line_with_its_result_and_the_class_of_a_failed_write(
    roadmap: Roadmap, caplog: pytest.LogCaptureFixture
) -> None:
    """A placed candidate, a possible duplicate that intake places too, a proposal off the lists
    and a candidate whose write fails give one line each, in the order of the plan."""
    placed = roadmap.issue("Cache embeddings")
    duplicate = roadmap.issue("Keep embeddings cached")
    skipped = roadmap.issue("Odd proposal")
    failing = roadmap.issue("Write refused")
    model = FakeModel(
        duplicates={"Keep embeddings cached": "Cache embeddings"},
        proposals={"Odd proposal": {"value": "Enormous"}},
    )
    roadmap.store.fail_write(write="set_field", item=failing)
    plan = roadmap.plan(model)

    with caplog.at_level(logging.INFO):
        apply_intake(roadmap.store, plan, repo=REPO)

    assert result_fields(caplog) == [
        {
            "job": "intake",
            "repo": REPO,
            "item": f"#{number}",
            "result": result,
            "success": success,
            "class": failure,
            "infra": infra,
        }
        for number, result, success, failure, infra in (
            (placed, "placed", "true", "none", "false"),
            (duplicate, "duplicate", "true", "none", "false"),
            (skipped, "skipped", "false", "none", "false"),
            (failing, "failed", "false", "ci_infra", "true"),
        )
    ]
