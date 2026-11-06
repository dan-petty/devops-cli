"""The step commit takes the type and the scope of the item (#3351)."""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.roadmap.implement_step import StepStatus, run_step
from devops_cli.roadmap.store import ItemField
from tests.support.fakes.process import ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.implement_step import (
    BODY,
    REPO,
    WINDOW,
    git,
    make_checkout,
    the_whole_group,
)
from tests.support.model_script import ModelScript, say, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

DOCS_TITLE = "docs(security): SECURITY.md says that the Valkey commands are not MCP tools"


@pytest.fixture
def docs_store() -> InMemoryRoadmapStore:
    """A private roadmap whose item 1 is a docs item."""
    roadmap = InMemoryRoadmapStore(repo=REPO, is_private=True)
    roadmap.seed_issue(
        DOCS_TITLE,
        body=BODY,
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
    )
    return roadmap


def test_a_step_of_a_docs_item_commits_with_its_type_and_scope(
    docs_store: InMemoryRoadmapStore, tmp_path: Path, implement_programs: ProcessFake
) -> None:
    checkout = make_checkout(tmp_path)
    script = ModelScript(tool_calls(*the_whole_group()), say("The group is done."))

    outcome = run_step(
        docs_store, item=1, group=1, source=checkout, model=script.model(), window=WINDOW
    )

    assert (outcome.status, git(checkout, "log", "-1", "--format=%s")) == (
        StepStatus.DONE,
        "docs(security): The first group (#1)",
    )
