"""A stop of the Service after each write of the stage job leaves the next round no second
comment to post (ADR 0021, #4793).

The roadmap is the in-memory store, the GitHub session is the fake, and the round is the `stage`
row of the Service's model lane.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest

from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.roadmap.run import MODEL_LANE_ROWS
from devops_cli.roadmap.stores.store import ItemField
from tests.support.fakes.github import github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_implement import merge_plan
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    seed_stageable,
    validate_args,
)
from tests.support.write_stops import stop_after_each_write

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

STAGE_ROW = next(row for row in MODEL_LANE_ROWS if row.name == "stage")
NEW_MODULE = "src/devops_cli/roadmap/stage_constants.py"
OPEN_PLAN = f"""\
# Tasks

## 1. The constants

Reads: `src/devops_cli/shout.py`. Changes: `{NEW_MODULE}` (new).

- [ ] Add `{NEW_MODULE}`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_constants.py`
"""
# The GraphQL answer of a repository with no open pull request.
NO_OPEN_PULLS = {
    "data": {
        "repository": {
            "pullRequests": {
                "nodes": [],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            }
        }
    }
}


@pytest.fixture(autouse=True)
def valid_openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    for name in ("1-the-job-drops-a-comment", "2-the-job-drops-a-label", "3-the-job-drops-a-tag"):
        openspec_fake.script_sequence(validate_args(name), (0, VALID_REPORT))
    return openspec_fake


def test_a_stop_after_each_write_of_a_dependency_return_posts_no_second_comment(
    stage_repo: StageRepo, model_fake: ModelFake, github_api: GitHubApiFake
) -> None:
    """The return of an item to New, because an open plan creates a path that it cites, writes
    its comment and then its Status. After a stop after either write, the next round posts no
    second comment (#3418, #4793)."""
    get_github_rate_limiter().update_quota(
        "graphql", remaining=5000, limit=5000, reset_epoch=time.time() + 600.0
    )
    github_api.route("POST", "/graphql", github_json(NO_OPEN_PULLS))
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    open_plan = store.seed_issue(
        "fix(roadmap): add the stage constants",
        body="The stage job reads constants.",
        labels=("type/bug",),
        fields={ItemField.STATUS: "Planned", ItemField.PRIORITY: "P1-High"},
    )
    merge_plan(stage_repo, open_plan, tasks=OPEN_PLAN)
    seed_stageable(store, body=f"The job needs `{NEW_MODULE}`.")

    replay = stop_after_each_write(
        store,
        lambda copied: STAGE_ROW.runner(store=copied, repo=STAGE_REPO, clone_path=stage_repo.clone),
    )

    assert (
        replay.whole,
        [(run.at, run.again) for run in replay.runs],
        replay.extra_comments(),
        model_fake.calls,
    ) == (("comment", "set_field"), [(1, ("set_field",)), (2, ())], [], [])
