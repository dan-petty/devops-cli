"""The items, candidates and issues that the GitHub roadmap store reads: their fields come from
labels and their state from REST (#1335).
"""

from __future__ import annotations

import pytest

from devops_cli.exceptions.git import (
    GitHubOperationError,
)
from devops_cli.roadmap.stores.store import (
    GitHubState,
    ItemField,
)
from tests.support.fakes.github import (
    API,
)
from tests.support.roadmap_github_store import (
    ISSUES_IN_MILESTONE,
    OPEN_ISSUES,
    REPO,
    labeled,
    read,
    recorded_store,
    seeded,
)

LISTING_IN_MILESTONE = f"repos/{REPO}/issues?milestone=43&state=all&per_page=100"


# ── Items and Candidates ──────────────────────────────────────────────────────


def test_items_in_a_milestone_take_their_fields_from_their_labels_and_state_from_rest() -> None:
    """A closed issue is an Item too: its state, milestone and fields come from the listing."""
    listing = [
        *ISSUES_IN_MILESTONE[:2],
        labeled(ISSUES_IN_MILESTONE[2], "priority/p1-high", "status/in-progress"),
        ISSUES_IN_MILESTONE[3],
    ]
    store, runner = recorded_store({"issues?milestone=43": listing})
    items = store.items(milestone=43)
    assert (
        [
            (item.number, item.state, item.state_reason, item.milestone, item.status, item.priority)
            for item in items
        ],
        [args for args, _ in runner.calls],
    ) == (
        [(737, GitHubState.CLOSED, "completed", "v0.2.25", "In Progress", "P1-High")],
        [[f"{API}/{LISTING_IN_MILESTONE}"]],
    )


def test_backlog_reads_the_open_issues_in_no_milestone() -> None:
    open_placed = labeled(ISSUES_IN_MILESTONE[1], "priority/p2-medium", milestone=None)
    store, runner = recorded_store({"issues?milestone=none": [open_placed]})
    assert ([item.number for item in store.backlog()], [args for args, _ in runner.calls]) == (
        [739],
        [[f"{API}/repos/{REPO}/issues?milestone=none&state=open&per_page=100"]],
    )


def test_items_carry_the_body_of_the_listing_they_were_read_from_with_no_request_per_issue() -> (
    None
):
    """The recorded listings hold no body, so one is put into a copy of each (#1539)."""
    in_milestone = labeled(ISSUES_IN_MILESTONE[2], "priority/p1-high", body="Planned text")
    in_backlog = labeled(
        ISSUES_IN_MILESTONE[1], "priority/p2-medium", milestone=None, body="Backlog text"
    )
    store, runner = recorded_store(
        {"issues?milestone=43": [in_milestone], "issues?milestone=none": [in_backlog]}
    )
    planned, backlog = store.items(milestone=43), store.backlog()
    assert (
        [(item.number, item.body) for item in planned],
        [(item.number, item.body) for item in backlog],
        [args[0] for args, _ in runner.calls],
    ) == (
        [(737, "Planned text")],
        [(739, "Backlog text")],
        [
            f"{API}/{LISTING_IN_MILESTONE}",
            f"{API}/repos/{REPO}/issues?milestone=none&state=open&per_page=100",
        ],
    )


def test_candidates_drop_a_pull_request_a_closed_issue_and_an_issue_with_a_priority() -> None:
    # The recorded pull request #918 had merged; it is reopened here, so only its
    # `pull_request` key can keep it out.
    listing = [
        {**OPEN_ISSUES[0], "state": "open"},
        labeled(OPEN_ISSUES[1], "priority/p2-medium"),
        OPEN_ISSUES[2],
        ISSUES_IN_MILESTONE[3],
    ]
    store, _ = recorded_store({"issues?state=all": listing})
    assert [(c.number, c.labels) for c in store.candidates()] == [
        (916, ("type/bug", "scope/security"))
    ]


def test_the_items_are_the_issues_with_a_priority_label() -> None:
    listing = [
        labeled(ISSUES_IN_MILESTONE[0], "priority/p2-medium"),
        ISSUES_IN_MILESTONE[1],
        labeled(ISSUES_IN_MILESTONE[2], "priority/p3-low"),
        labeled(OPEN_ISSUES[0], "priority/p1-high"),
    ]
    store, _ = recorded_store({"issues?state=all": listing})
    assert [(item.number, item.state, item.priority) for item in store.items()] == [
        (737, GitHubState.CLOSED, "P3-Low"),
        (768, GitHubState.OPEN, "P2-Medium"),
    ]


def test_an_item_is_one_read_of_its_issue_and_none_for_an_issue_that_is_no_item() -> None:
    store, runner = recorded_store(
        {
            "issues/737": labeled(ISSUES_IN_MILESTONE[2], "priority/p1-high"),
            "issues/739": ISSUES_IN_MILESTONE[1],
            "issues/918": labeled(OPEN_ISSUES[0], "priority/p1-high"),
            "issues/99": (1, "gh: Not Found (HTTP 404)"),
        }
    )
    found = [store.item(number) for number in (737, 739, 918, 99)]
    assert (
        [item.number if item else None for item in found],
        [args for args, _ in runner.calls],
    ) == (
        [737, None, None, None],
        [["api", f"repos/{REPO}/issues/{number}"] for number in (737, 739, 918, 99)],
    )


def test_the_listing_of_every_issue_is_read_once_for_the_stores_life() -> None:
    """`items()`, `issues()` and `candidates()` share one read (#1361)."""
    store, runner = recorded_store({"issues?state=all": ISSUES_IN_MILESTONE + OPEN_ISSUES})
    store.items()
    store.issues()
    store.candidates()
    store.items()
    assert [args for args, _ in runner.calls] == [
        [f"{API}/repos/{REPO}/issues?state=all&per_page=100"]
    ]


def test_items_carry_the_known_keys_of_the_record_block_in_their_body() -> None:
    """A key this version does not know, such as one another version writes, is left out: an
    `OtherTool` mark reads as nothing, and the body reads without the block."""
    block = '<!-- devops-roadmap-record {"OtherTool": "y", "Priority": "P1-High"} -->'
    listing = [labeled(ISSUES_IN_MILESTONE[0], "priority/p1-high", body=f"Text\n\n{block}")]
    store, _ = recorded_store({"issues?state=all": listing})
    assert [(item.number, item.body, item.job_record) for item in store.items()] == [
        (768, "Text", {ItemField.PRIORITY: "P1-High"})
    ]


# ── Item writes ───────────────────────────────────────────────────────────────


def test_a_value_that_is_not_a_field_value_raises_before_any_request() -> None:
    github, store = seeded(i7=("priority/p2-medium",))
    item = read(store, 7)
    sent = len(github.calls)
    with pytest.raises(GitHubOperationError, match="'P9-Someday' is not a Priority value"):
        store.set_field(item, ItemField.PRIORITY, "P9-Someday")
    assert github.calls[sent:] == []


def test_issues_read_every_state_and_drop_pull_requests() -> None:
    store, runner = recorded_store({"issues?state=all": ISSUES_IN_MILESTONE + OPEN_ISSUES})
    numbers = [issue.number for issue in store.issues()]
    assert (
        918 in numbers,
        len(numbers) < len(ISSUES_IN_MILESTONE + OPEN_ISSUES),
        runner.calls[0][0],
    ) == (
        False,
        True,
        [f"{API}/repos/{REPO}/issues?state=all&per_page=100"],
    )
