"""`devops roadmap stage`: the re-stage of a draft plan that fails the check (#3387).

The stage job leaves an item out while its branch is on origin. When the one draft pull request of
the item holds a plan that fails `check_proposal`, the job stages the item again on that branch: it
clears the change folder of the old plan, pushes the new commit with a lease on the commit that
`stage.sha` records, sets the title and the body of the same draft, records `stage.restage` and
names the draft in its comment. It opens no second pull request.

The checkout is real git in `tmp_path` (`stage_repo`), as the stage job reads it, and the GitHub
reads and writes are the fake of the API.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest

from devops_cli.config.constants import CONST_ROADMAP_STAGE_COMMENT_MARKER
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.stage.plan_state import event_key, state_key
from devops_cli.roadmap.stage.stage import StageApplied, StagedChange, StagePlan, StageTarget
from devops_cli.roadmap.stage.stage_change import render_change
from devops_cli.roadmap.stage.stage_held import restage_record
from devops_cli.roadmap.stores.store import Item, StageRecordKey
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import API, GitHubApiFake, github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import (
    STAGE_NAME,
    STAGE_REPO,
    StageRepo,
    apply_stage,
    seed_stageable,
)

pytestmark = pytest.mark.usefixtures("keyring_store")

ISSUE = 1
PULL = 5
SLUG = "the-job-drops-a-comment"
CHANGE = f"{ISSUE}-{SLUG}"
BRANCH = f"fix/{CHANGE}"
ROOT = f"openspec/changes/{CHANGE}"
STALE = f"{ROOT}/specs/old-capability/spec.md"
TITLE = "docs(openspec): plan #1 Stop the job dropping a comment"
CREATED = date(2026, 11, 16)


@pytest.fixture(autouse=True)
def _app_slug(config: Callable[..., Path]) -> None:
    """The App whose bot pushes the branch of the stage job, as `stage_repo` names its author."""
    config(service={"github_app": {"slug": "devops-roadmap"}})


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    seed_stageable(store)
    store.seed_file(
        ".github/labels.yml",
        '- name: "type/docs"\n  color: "0075ca"\n- name: "scope/openspec"\n  color: "0e8a16"\n',
    )
    for i in range(2, 5):
        store.seed_issue(f"placeholder {i}")
    assert store.seed_pull("staging PR", head_ref=BRANCH, draft=True) == PULL
    return store


def _push_old_plan(repo: StageRepo) -> str:
    """Push one commit by the App that holds the plan the draft now carries, with a file that the
    new plan drops, and return the commit. The clone goes back to `main`, as a stage run finds it."""
    files = {
        f"{ROOT}/proposal.md": "The old plan of the item.\n",
        f"{ROOT}/tasks.md": "# Tasks\n- [ ] 1.1 The old work\n",
        STALE: "# old-capability Specification\n",
    }
    repo.git("switch", "-q", "-c", BRANCH)
    for path, text in files.items():
        target = repo.clone / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    repo.git("add", "-A")
    repo.git("-c", f"user.name={STAGE_NAME}", "commit", "-q", "-m", "plan")
    head = repo.git("rev-parse", "HEAD")
    repo.git("push", "-q", "origin", BRANCH)
    repo.git("switch", "-q", "main")
    repo.git("branch", "-q", "-D", BRANCH)
    return head


def _staged_item(store: InMemoryRoadmapStore, head: str) -> Item:
    """The item whose record holds the draft `PULL` of the branch at `head`."""
    item = store.item(ISSUE)
    assert item is not None
    store.set_marks(
        item,
        {
            StageRecordKey.BRANCH: BRANCH,
            StageRecordKey.PR: str(PULL),
            StageRecordKey.SHA: head,
        },
    )
    staged = store.item(ISSUE)
    assert staged is not None
    return staged


def _change(item: Item, *, replace_pull: int | None) -> StagedChange:
    """The new plan of `item`, on the draft `replace_pull` when the caller names one."""
    proposal = make_stage_proposal()
    return StagedChange(
        target=StageTarget(item, "fix", SLUG, replace_pull=replace_pull),
        title=TITLE,
        body="Plans #1",
        files=render_change(CHANGE, proposal, {"roadmap-refine"}, created=CREATED),
        groups=(),
        validated=True,
        budget=1000,
        proposal=proposal,
    )


def _route_update(api: GitHubApiFake, *, head: str) -> None:
    """Answer the read of the labels of the draft `PULL` and the update of its title and body."""
    api.route(
        "GET",
        f"/repos/{STAGE_REPO}/pulls/{PULL}",
        github_json(
            {
                "state": "open",
                "draft": True,
                "head": {"ref": BRANCH, "sha": head},
                "base": {"ref": "main"},
                "labels": [],
            }
        ),
    )
    api.route(
        "PATCH",
        f"/repos/{STAGE_REPO}/pulls/{PULL}",
        github_json({"number": PULL, "state": "open", "draft": True}),
    )


def _apply(
    store: InMemoryRoadmapStore, repo: StageRepo, change: StagedChange, base: str
) -> StageApplied:
    """Write the plan of one re-staged item through the writer of the job."""
    return apply_stage(
        store, StagePlan(repo=STAGE_REPO, sha=base, ready=(change,)), source=repo.clone
    )


def test_a_re_stage_pushes_to_the_same_branch_updates_its_draft_and_names_it(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    """The job replaces the plan of the one draft on its branch, opens no second pull request,
    records the re-stage and names the draft that it replaced (#3387)."""
    old = _push_old_plan(stage_repo)
    item = _staged_item(store, old)
    base = stage_repo.git("rev-parse", "HEAD")
    # The default branch moves after the draft read it, so the rebase rewrites the tip of the
    # branch and the push is no fast-forward.
    stage_repo.track({"README.md": "The default branch moved.\n"})
    _route_update(github_api, head=old)

    applied = _apply(store, stage_repo, _change(item, replace_pull=PULL), base)

    assert applied.staged == (ISSUE,)

    head = stage_repo.origin_git("rev-parse", BRANCH)
    assert head != old
    assert stage_repo.origin_git("log", "--format=%s", f"main..{BRANCH}").splitlines()[0] == TITLE
    files = stage_repo.origin_git("ls-tree", "-r", "--name-only", BRANCH, "--", ROOT).split()
    assert STALE not in files
    assert f"{ROOT}/proposal.md" in files
    assert [request for request in github_api.requested if request.startswith("PATCH")] == [
        f"PATCH {API}/repos/{STAGE_REPO}/pulls/{PULL}"
    ]
    assert [request for request in github_api.requested if request.endswith("/pulls")] == []
    assert [pull.number for pull in store.open_pulls() if pull.head_ref == BRANCH] == [PULL]
    staged = store.item(ISSUE)
    assert staged is not None
    assert staged.job_record[StageRecordKey.SHA] == head
    assert staged.job_record[StageRecordKey.RESTAGE] == restage_record(staged, PULL)
    (_, event) = [comment.body for comment in store.comments_on(ISSUE)]
    assert MESSAGES.roadmap.stage_comment_restaged.format(pull=PULL) in event


def test_a_re_stage_edits_the_plan_state_comment_of_its_draft_in_place(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    """The plan-state comment of the draft holds the plan of the first stage. The re-stage edits
    that comment and writes no second one, and the comment of the run names the replaced draft
    and holds no group (#6197)."""
    old = _push_old_plan(stage_repo)
    item = _staged_item(store, old)
    first = f"{CONST_ROADMAP_STAGE_COMMENT_MARKER}\n{state_key(PULL)}\nPlan state: the old plan."
    store.seed_comment(ISSUE, first, author_login=store._actor)
    base = stage_repo.git("rev-parse", "HEAD")
    _route_update(github_api, head=old)

    _apply(store, stage_repo, _change(item, replace_pull=PULL), base)

    state, event = [comment.body for comment in store.comments_on(ISSUE)]
    assert (
        state.startswith(f"{CONST_ROADMAP_STAGE_COMMENT_MARKER}\n{state_key(PULL)}\n"),
        "the old plan" in state,
        "budget of 1000 tokens" in state,
        event.startswith(f"{CONST_ROADMAP_STAGE_COMMENT_MARKER}\n{event_key(PULL)}\n"),
        MESSAGES.roadmap.stage_comment_restaged.format(pull=PULL) in event,
        "budget of" in event,
    ) == (True, False, True, True, True, False)


def test_a_branch_that_moved_past_the_recorded_commit_refuses_the_push(
    store: InMemoryRoadmapStore, stage_repo: StageRepo
) -> None:
    """The push carries a lease on the commit that `stage.sha` records, so a commit that the job
    did not read keeps the branch and the item (#3387)."""
    old = _push_old_plan(stage_repo)
    item = _staged_item(store, old)
    base = stage_repo.git("rev-parse", "HEAD")
    stage_repo.push_branch(BRANCH, author=STAGE_NAME)
    moved = stage_repo.git("rev-parse", f"origin/{BRANCH}")

    applied = _apply(store, stage_repo, _change(item, replace_pull=PULL), base)

    assert applied.staged == ()
    (failure,) = applied.failed
    # The lease on the recorded commit refuses the push (#3387).
    assert "stale info" in failure.reason
    assert stage_repo.origin_git("rev-parse", BRANCH) == moved
