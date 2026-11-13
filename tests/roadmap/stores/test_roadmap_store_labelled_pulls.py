"""The open pull requests with a label, from the listing of every issue that the store keeps for a
round: the queue of the fix_plan row (#5470)."""

from __future__ import annotations

from devops_cli.roadmap.stage.stage_verify import PLAN_NEEDS_FIX_LABEL
from devops_cli.roadmap.stores.store import GitHubState
from tests.support.fakes.github import API
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_github_store import (
    ISSUES_IN_MILESTONE,
    OPEN_ISSUES,
    REPO,
    labeled,
    recorded_store,
)

# The recorded pull request #918 had merged; each copy here sets its own number and state.
PULL = OPEN_ISSUES[0]


def test_the_github_store_gives_the_open_pulls_with_the_label_from_the_kept_listing() -> None:
    """Two open pull requests hold the label, a closed one holds it too, an open one does not, and
    an issue that is no pull request holds it: the store gives the two open pull requests. The read
    of the items before it keeps the listing, so the count sends no request."""
    listing = [
        {**labeled(PULL, PLAN_NEEDS_FIX_LABEL), "state": "open"},
        {**labeled(PULL, PLAN_NEEDS_FIX_LABEL), "number": 921, "state": "open"},
        {**labeled(PULL, PLAN_NEEDS_FIX_LABEL), "number": 922, "state": "closed"},
        {**PULL, "number": 923, "state": "open"},
        labeled(OPEN_ISSUES[2], PLAN_NEEDS_FIX_LABEL),
        *ISSUES_IN_MILESTONE,
    ]
    store, runner = recorded_store({"issues?state=all": listing})

    store.items()
    found = store.labelled_pulls(PLAN_NEEDS_FIX_LABEL)

    assert (found, [args for args, _ in runner.calls]) == (
        [918, 921],
        [[f"{API}/repos/{REPO}/issues?state=all&per_page=100"]],
    )


def test_the_fake_store_gives_the_open_pulls_with_the_label() -> None:
    """The fake of the tests gives the same answer as the GitHub store."""
    store = InMemoryRoadmapStore(repo=REPO)
    first = store.seed_issue("plan one", pull_request=True, labels=(PLAN_NEEDS_FIX_LABEL,))
    second = store.seed_issue("plan two", pull_request=True, labels=(PLAN_NEEDS_FIX_LABEL,))
    store.seed_issue(
        "plan three",
        pull_request=True,
        labels=(PLAN_NEEDS_FIX_LABEL,),
        state=GitHubState.CLOSED,
    )
    store.seed_issue("plan four", pull_request=True)
    store.seed_issue("an issue", labels=(PLAN_NEEDS_FIX_LABEL,))

    assert store.labelled_pulls(PLAN_NEEDS_FIX_LABEL) == [first, second]
