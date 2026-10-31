"""The Status family has six labels, and Planned sits between Ready and In Progress (#2920)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from devops_cli.github.merge_readiness import ClosingRead
from devops_cli.roadmap import pull_status
from devops_cli.roadmap.grounding import ClosingIssue
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import FIELD_VALUES, ItemField, field_label

REPO = "example/roadmap"
LABELS_FILE = Path(".github/labels.yml")
SIX = ("New", "Ready", "Planned", "In Progress", "In Review", "Blocked")


def test_the_status_family_has_six_values_in_the_order_of_the_workflow() -> None:
    assert FIELD_VALUES[ItemField.STATUS] == SIX


def test_the_labels_file_declares_the_six_status_labels() -> None:
    declared = {entry["name"] for entry in yaml.safe_load(LABELS_FILE.read_text("utf-8"))}

    assert {field_label(ItemField.STATUS, value) for value in SIX} <= declared
    assert "status/planned" in declared


def test_an_issue_with_the_planned_label_reads_as_planned(
    roadmap_store: InMemoryRoadmapStore,
) -> None:
    number = roadmap_store.seed_issue(
        "fix(cli): one", labels=("priority/p2-medium", "status/planned")
    )

    item = roadmap_store.item(number)

    assert item is not None
    assert item.status == "Planned"


@pytest.mark.parametrize("target", ["In Progress", "In Review"])
def test_a_pull_request_replaces_the_planned_status(
    roadmap_store: InMemoryRoadmapStore, target: str
) -> None:
    number = roadmap_store.seed_issue(
        "fix(cli): one", fields={ItemField.PRIORITY: "P2-Medium", ItemField.STATUS: "Planned"}
    )
    closing = ClosingIssue.model_validate(
        {"number": number, "state": "OPEN", "repository": {"nameWithOwner": REPO}}
    )

    with patch.object(pull_status, "read_closing_issues", return_value=ClosingRead((closing,), 1)):
        pull_status.set_delivered_status(REPO, 7, target)

    item = roadmap_store.item(number)
    assert item is not None
    assert item.status == target
