"""The writes to an issue that the GitHub roadmap store makes: create, comment, close, title and
labels (#1335).
"""

from __future__ import annotations

import json

import pytest

from devops_cli.exceptions.git import (
    GitHubOperationError,
)
from devops_cli.roadmap.stores.store import (
    CloseReason,
)
from tests.support.roadmap_github_store import OPEN_ISSUES, REPO, issue_payload, recorded_store

# ── Issues and files (#739) ───────────────────────────────────────────────────


def test_create_issue_posts_its_title_body_and_labels() -> None:
    opened = {**OPEN_ISSUES[1], "number": 950, "title": "Bare-Metal OS Installers"}
    store, runner = recorded_store({"-X POST": opened})
    created = store.create_issue("Bare-Metal OS Installers", "Rejected.", labels=["type/feature"])
    assert (runner.writes, created.number) == (
        [
            [
                "api",
                "-X",
                "POST",
                f"repos/{REPO}/issues",
                "-f",
                "title=Bare-Metal OS Installers",
                "-f",
                "body=Rejected.",
                "-f",
                "labels[]=type/feature",
            ]
        ],
        950,
    )


def test_comment_posts_one_comment() -> None:
    store, runner = recorded_store({"-X POST": {}})
    store.comment(740, "Status set to Ready.")
    assert runner.writes == [
        [
            "api",
            "-X",
            "POST",
            f"repos/{REPO}/issues/740/comments",
            "-f",
            "body=Status set to Ready.",
        ]
    ]


def test_a_close_reads_the_issue_then_comments_then_patches_its_state_and_reason() -> None:
    """The read refuses a pull request or a closed issue before any write; the comment comes
    before the close, so a failed close leaves the evidence (#1658)."""
    closed = issue_payload(740, state="closed", state_reason="not_planned")
    store, runner = recorded_store(
        {"-X POST": {}, "-X PATCH": closed, "issues/740": issue_payload(740)}
    )
    store.close(740, CloseReason.NOT_PLANNED, comment="Superseded by #2399.")
    issue = f"repos/{REPO}/issues/740"
    assert [(args, kwargs.get("input")) for args, kwargs in runner.calls] == [
        (["api", issue], None),
        (["api", "-X", "POST", f"{issue}/comments", "-f", "body=Superseded by #2399."], None),
        (
            ["api", "-X", "PATCH", issue, "--input", "-"],
            json.dumps({"state": "closed", "state_reason": "not_planned"}),
        ),
    ]


def test_a_refused_close_after_its_comment_says_the_comment_is_on_the_open_issue() -> None:
    store, _ = recorded_store(
        {
            "-X POST": {},
            "-X PATCH": (1, "gh: Validation Failed (HTTP 422)"),
            "issues/740": issue_payload(740),
        }
    )
    with pytest.raises(GitHubOperationError, match=r"comment is on #740.*still open"):
        store.close(740, CloseReason.NOT_PLANNED, comment="Superseded.")


def test_set_title_patches_only_the_title() -> None:
    store, runner = recorded_store(
        {"-X PATCH": issue_payload(950), "issues/950": issue_payload(950)}
    )

    store.set_title(950, "fix(roadmap): a short summary")

    assert runner.writes == [["api", "-X", "PATCH", f"repos/{REPO}/issues/950", "--input", "-"]]
    sent = next(kwargs["input"] for args, kwargs in runner.calls if "PATCH" in args)
    assert json.loads(sent) == {"title": "fix(roadmap): a short summary"}


def test_label_issue_posts_one_label_and_keeps_the_others() -> None:
    store, runner = recorded_store({"-X POST": []})
    store.label_issue(950, "type/bug")
    assert runner.writes == [
        ["api", "-X", "POST", f"repos/{REPO}/issues/950/labels", "-f", "labels[]=type/bug"]
    ]


def test_unlabel_issue_sends_one_delete() -> None:
    store, runner = recorded_store({"-X DELETE": []})
    store.unlabel_issue(950, "type/docs")
    assert runner.writes == [["api", "-X", "DELETE", f"repos/{REPO}/issues/950/labels/type%2Fdocs"]]


def test_a_refused_delete_of_a_label_raises() -> None:
    store, _ = recorded_store({"-X DELETE": (1, "gh: Not Found (HTTP 404)")})
    with pytest.raises(GitHubOperationError, match="Not Found"):
        store.unlabel_issue(950, "type/docs")
