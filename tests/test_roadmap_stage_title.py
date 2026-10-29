"""The title of the pull request that the stage job opens (#2714): a plan has the type
`docs(openspec)`, so release-please lists no changelog line for it, and the branch keeps the type
of the issue."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.stage import parse_filters, plan_stage
from devops_cli.roadmap.stage_change import SUMMARY_MAX_CHARS, staging_title
from devops_cli.roadmap.store import ItemField
from tests.support.builders import make_stage_proposal
from tests.support.roadmap_stage import STAGE_REPO, StageRepo

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

LONG_SUMMARY = "Report a clear error when a merge key is unset in the file"


def _summary_of(title: str) -> str:
    """The part after `<type>(<scope>): `, which the check `Semantic PR title` measures."""
    return title.partition(": ")[2]


def test_a_staging_title_has_the_type_docs_openspec_the_issue_and_the_summary() -> None:
    assert staging_title(2656, "Report a clear error") == (
        "docs(openspec): plan #2656 Report a clear error"
    )


@pytest.mark.parametrize("number", [7, 2656, 123456])
def test_the_summary_of_a_staging_title_has_at_most_sixty_characters_and_is_cut_at_a_word(
    number: int,
) -> None:
    assert len(LONG_SUMMARY) < SUMMARY_MAX_CHARS

    title = staging_title(number, LONG_SUMMARY + " as the user asked")

    summary = _summary_of(title)
    assert len(summary) <= SUMMARY_MAX_CHARS
    assert summary.startswith(f"plan #{number} Report a clear error")
    assert summary.endswith("...")


def test_a_summary_with_a_handle_has_it_in_a_code_span_so_that_the_title_pings_no_one() -> None:
    assert staging_title(3, "Ask @maintainer about it") == (
        "docs(openspec): plan #3 Ask `@maintainer` about it"
    )


@pytest.mark.parametrize(
    ("kind", "label", "branch_type"),
    [("bug", "type/bug", "fix"), ("feature", "type/feature", "feat")],
)
def test_the_staging_pull_request_of_a_bug_and_of_a_feature_has_the_docs_type_and_keeps_the_branch_type(
    kind: str,
    label: str,
    branch_type: str,
    model_fake: ModelFake,
    openspec_fake: OpenSpecFake,
    stage_repo: StageRepo,
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = store.seed_issue(
        f"{branch_type}(roadmap): the job drops a comment",
        labels=(label,),
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
    )
    model_fake.answer(make_stage_proposal())
    openspec_fake.installed = False

    plan = plan_stage(
        store,
        repo=STAGE_REPO,
        source=stage_repo.clone,
        filters=parse_filters(("status=ready", f"type={kind}")),
    )

    (change,) = plan.ready
    assert change.title == f"docs(openspec): plan #{number} Stop the job dropping a comment"
    assert change.target.branch.startswith(f"{branch_type}/{number}-")
