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


_LONG_TITLE = (
    "test(docs): six docs tests read the DEVOPS_CLI_CONFIG of the shell, and this title is longer "
    "than the sixty-four characters the error used to keep"
)


def test_a_failed_create_names_the_full_title_the_command_and_the_stderr() -> None:
    """A failed `gh issue create` names the full title, the gh command and its stderr, so the
    reader sees what intake sent and what gh answered (#5269)."""
    store, _runner = recorded_store({"-X POST": (1, "unexpected end of JSON input")})

    with pytest.raises(GitHubOperationError) as err:
        store.create_issue(_LONG_TITLE, "Body.")

    text = str(err.value)
    assert (
        _LONG_TITLE in text,
        f"gh api -X POST repos/{REPO}/issues" in text,
        "exit 1" in text,
        "stderr: unexpected end of JSON input" in text,
        "GitHub returned malformed issue after it was opened" in text,
    ) == (True, True, True, True, False)


def test_a_failed_create_with_a_validation_error_names_its_command_and_stderr() -> None:
    """A gh validation error is named with the command, the exit code and the stderr (#5269)."""
    store, _runner = recorded_store({"-X POST": (1, "HTTP 422: Validation Failed")})

    with pytest.raises(GitHubOperationError) as err:
        store.create_issue("A title", "Body.")

    text = str(err.value)
    assert (
        f"gh api -X POST repos/{REPO}/issues" in text,
        "exit 1" in text,
        "stderr: HTTP 422: Validation Failed" in text,
    ) == (True, True, True)


def test_a_failed_create_with_no_stderr_says_it_is_empty() -> None:
    """A failed `gh issue create` that wrote no stderr says so (#5269)."""
    store, _runner = recorded_store({"-X POST": (1, "")})

    with pytest.raises(GitHubOperationError) as err:
        store.create_issue("A title", "Body.")

    assert "stderr: (empty)" in str(err.value)


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


def test_edit_comment_writes_the_new_text_of_the_comment_by_its_id() -> None:
    """The plan-state comment is edited in place (#6197): one `PATCH` of the comment."""
    store, runner = recorded_store({"-X PATCH": {}})
    store.edit_comment(740, 9001, "The new state.")
    assert runner.writes == [
        [
            "api",
            "-X",
            "PATCH",
            f"repos/{REPO}/issues/comments/9001",
            "-f",
            "body=The new state.",
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
