"""Tests for PR review comment formatting and --post execution (Issue #604 Part 2)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.ai.review.runner import format_pr_review_comment, post_pr_review_comment
from devops_cli.ai.review_schema import Finding, ReviewResult
from tests.support.fakes.github import (
    github_json,
    pull_request_file_payload,
    pull_request_payload,
    route_pull_request,
    route_pull_request_changes,
)

if TYPE_CHECKING:
    from pathlib import Path

    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake

pytestmark = [pytest.mark.usefixtures("keyring_store", "scanner_fake")]


def test_zero_findings_comment_names_files_and_analyzers() -> None:
    """Verify zero-findings PR comment states exact files and analyzers that ran, and names no
    persona (#4827)."""
    res = ReviewResult(
        recommendation="APPROVE",
        findings=[],
        summary="No defects found; consider adding docstrings.",
    )
    reviews: list[ReviewResult | str] = [res]
    files = ["src/auth.py", "src/token.py"]
    analyzers = {
        "Bandit": "ran",
        "Gitleaks": "built-in patterns",
        "Semgrep": "not installed",
        "Trivy": "no files",
    }

    comment = format_pr_review_comment(
        reviews=reviews,
        files=files,
        static_analyzers=analyzers,
    )

    expected_fragments = (
        "## 🤖 AI Code Review",
        "Zero findings identified.",
        "- **Files checked:** `src/auth.py`, `src/token.py`",
        "- **Analyzers:** Bandit, Gitleaks",
        "## Model Notes (Not Verified)",
        "No defects found; consider adding docstrings.",
    )
    assert (
        all(frag in comment for frag in expected_fragments),
        "Positive observations" in comment,
        "Persona" in comment,
    ) == (True, False, False)


def test_zero_findings_comment_with_no_analyzers_and_no_summary() -> None:
    """Verify zero-findings comment when no analyzers ran and no summary was emitted."""
    res = ReviewResult(
        recommendation="APPROVE",
        findings=[],
        summary="",
    )
    reviews: list[ReviewResult | str] = [res]

    comment = format_pr_review_comment(
        reviews=reviews,
        files=[],
        static_analyzers={},
    )

    expected_lines = [
        "## 🤖 AI Code Review",
        "",
        "Zero findings identified.",
        "",
        "- **Files checked:** None",
        "- **Analyzers:** None",
    ]
    assert (
        comment.strip().splitlines() == expected_lines,
        "Model Notes (Not Verified)" in comment,
    ) == (True, False)


def test_zero_findings_comment_gives_the_model_notes_of_each_result() -> None:
    """Verify the model notes of two results follow one another under one heading (#4827)."""
    r1 = ReviewResult(
        recommendation="APPROVE",
        findings=[],
        summary="Security posture is clean.",
    )
    r2 = ReviewResult(
        recommendation="APPROVE",
        findings=[],
        summary="Architecture exhibits low coupling.",
    )
    reviews: list[ReviewResult | str] = [r1, r2]

    comment = format_pr_review_comment(
        reviews=reviews,
        files=["main.py"],
        static_analyzers={"Bandit": "ran"},
    )

    expected_fragments = (
        "## 🤖 AI Code Review",
        "Zero findings identified.",
        "- **Files checked:** `main.py`",
        "- **Analyzers:** Bandit",
        "## Model Notes (Not Verified)\n\nSecurity posture is clean.\n\n"
        "Architecture exhibits low coupling.",
    )
    assert (all(frag in comment for frag in expected_fragments), "###" in comment) == (True, False)


def test_comment_with_findings_renders_findings_and_model_notes() -> None:
    """Verify PR comment with findings renders finding details and unverified notes."""
    finding = Finding(
        severity="HIGH",
        title="Unvalidated URL Redirect",
        description="Redirect target not validated against allowlist",
        location="src/auth.py:42-50",
        fix="Use validate_redirect_url(target)",
        verified=True,
    )
    res = ReviewResult(
        recommendation="REQUEST CHANGES",
        findings=[finding],
        summary="Review completed with 1 high finding.",
    )
    reviews: list[ReviewResult | str] = [res]

    comment = format_pr_review_comment(reviews=reviews, files=["src/auth.py"])

    expected_fragments = (
        "## 🤖 AI Code Review\n\n**Recommendation: REQUEST CHANGES**",
        "## Findings",
        "### [HIGH] Unvalidated URL Redirect",
        "**Location:** `src/auth.py:42-50`",
        "Redirect target not validated against allowlist",
        "**Fix:** Use validate_redirect_url(target)",
        "## Model Notes (Not Verified)",
        "Review completed with 1 high finding.",
    )
    assert (
        all(frag in comment for frag in expected_fragments),
        "Zero findings identified" in comment,
        "Positive Observations" in comment,
        "Review by" in comment,
    ) == (True, False, False, False)


def _route_the_pull_request(
    api: GitHubApiFake,
    *,
    files: list[dict[str, Any]],
    diff: str,
    comments: bool,
    head_sha: str = "abc123",
) -> None:
    """Serve pull request 42 of org/repo at `head_sha`, whose compare with its base branch holds
    `files` and `diff`; with `comments`, GitHub also gives its comments, none, and accepts a
    comment on it."""
    pull = pull_request_payload(
        title="Test PR", head_sha=head_sha, head_repo="org/repo", base_repo="org/repo"
    )
    route_pull_request(api, "org/repo", 42, pull)
    route_pull_request_changes(api, pull, *files, merge_base="merge789", diff=diff)
    if comments:
        api.route("GET", "/repos/org/repo/issues/42/comments?per_page=100", github_json([]))
        api.route("POST", "/repos/org/repo/issues/42/comments", github_json({"id": 1}, status=201))


def _written(api: GitHubApiFake) -> list[tuple[str, str]]:
    """The method and the path of each write that the fake received."""
    return [
        (request.method, request.url.path)
        for request in api.sent
        if request.method in {"POST", "PATCH"}
    ]


def test_the_review_comment_names_the_head_commit_of_the_pull_request(
    cli: Callable[..., Any], github_api: GitHubApiFake
) -> None:
    """The command reads the comments of the pull request, holds none of its review, and posts
    one comment that names the head commit it reviewed (#6199)."""
    _route_the_pull_request(
        github_api,
        files=[pull_request_file_payload("src/app.py")],
        diff="diff --git a/src/app.py b/src/app.py\n+pass\n",
        comments=True,
        head_sha="def456",
    )

    result = cli("review", "pr", "42", "--repo", "org/repo", "--post", "--no-group-analysis")

    [(_, posted)] = _posted(github_api)
    assert (
        result.exit_code,
        "GET https://api.github.com/repos/org/repo/issues/42/comments?per_page=100"
        in github_api.requested,
        _written(github_api),
        "def456" in posted["body"],
    ) == (0, True, [("POST", "/repos/org/repo/issues/42/comments")], True)


_COMMENTS = "/repos/org/repo/issues/42/comments"
# What each test of the review comment gets: a writer of the review of a head commit that returns
# each write GitHub got, as its method, its path and the body it sent.
PostReview = Callable[..., list[tuple[str, str, str]]]


@pytest.fixture
def post_review(github_api: GitHubApiFake, tmp_path: Path) -> PostReview:
    """Write a review with no findings of a head on pull request 42 of org/repo, which holds the
    comments given (ids 1, 2, ...), as the command does after its review. Each call returns the
    writes GitHub got in that call. The review runs one time, so no two reviews share a session
    name."""
    review = ReviewResult(recommendation="APPROVE", findings=[], summary="No defects found.")

    def post(head_sha: str, *held: str) -> list[tuple[str, str, str]]:
        comments = [{"id": number, "body": body} for number, body in enumerate(held, start=1)]
        github_api.route("GET", f"{_COMMENTS}?per_page=100", github_json(comments))
        github_api.route("POST", _COMMENTS, github_json({"id": 9}, status=201))
        for comment in comments:
            path = f"/repos/org/repo/issues/comments/{comment['id']}"
            github_api.route("PATCH", path, github_json(comment))
        github_api.sent.clear()
        post_pr_review_comment(
            reviews=[review],
            pages=[],
            head_dir=tmp_path,
            repo_name="org/repo",
            number=42,
            base_revision=None,
            head_sha=head_sha,
        )
        return [
            (request.method, request.url.path, json.loads(request.content)["body"])
            for request in github_api.sent
            if request.method in {"POST", "PATCH"}
        ]

    return post


def test_a_rerun_on_the_same_head_edits_the_review_comment_of_that_head(
    post_review: PostReview,
) -> None:
    """The pull request holds the review comment of its head, with an older review, and a
    comment of a person. A rerun on the same head edits that review comment with the new review,
    and posts no second comment (#6199)."""
    [(_, _, posted)] = post_review("abc123")

    writes = post_review("abc123", "A note of a person.", f"{posted}\nAn older finding.")

    assert writes == [("PATCH", "/repos/org/repo/issues/comments/2", posted)]


def test_the_same_review_of_the_same_head_sends_no_write(post_review: PostReview) -> None:
    """The review comment of the head already holds the review, so a rerun writes nothing
    (#6199)."""
    [(_, _, posted)] = post_review("abc123")

    assert post_review("abc123", posted) == []


def test_a_review_of_a_new_head_posts_a_new_comment_and_keeps_the_older_one(
    post_review: PostReview,
) -> None:
    """The pull request holds the review comment of an older head. The review of a new head posts
    a new comment that names the new head, and sends no change of the older comment (#6199)."""
    [(_, _, posted)] = post_review("abc123")

    [(method, path, body)] = post_review("def456", posted)

    assert (method, path, "def456" in body, "def456" in posted) == (
        "POST",
        _COMMENTS,
        True,
        False,
    )


def test_a_dry_run_with_post_lists_the_read_of_the_comments_and_both_writes(
    cli: Callable[..., Any], github_api: GitHubApiFake
) -> None:
    """The plan lists the read of the comments of the pull request, the change of the review
    comment of the head, and the new comment, and GitHub receives no request (#6199)."""
    result = cli("review", "pr", "42", "--repo", "org/repo", "--post", "--dry-run")

    said = " ".join(result.output.split())
    api = "https://api.github.com/repos/org/repo/issues"
    assert (
        result.exit_code,
        github_api.requested,
        f"GET {api}/42/comments" in said,
        f"PATCH {api}/comments/<comment_id>" in said,
        f"POST {api}/42/comments" in said,
    ) == (0, [], True, True, True)


def _posted(api: GitHubApiFake) -> list[tuple[str, dict[str, Any]]]:
    """Each POST the fake received, as its path and JSON body."""
    return [
        (request.url.path, json.loads(request.content))
        for request in api.sent
        if request.method == "POST"
    ]


def test_devops_review_pr_post_publishes_comment(
    cli: Callable[..., Any],
    github_api: GitHubApiFake,
    pin_github_session: str,
) -> None:
    """Verify devops review pr --post creates one issue comment on the PR, through the session."""
    _route_the_pull_request(
        github_api,
        files=[pull_request_file_payload("src/app.py")],
        diff="diff --git a/src/app.py b/src/app.py\n+pass\n",
        comments=True,
    )

    result = cli("review", "pr", "42", "--repo", "org/repo", "--post", "--no-group-analysis")

    posts = _posted(github_api)
    posted_body = posts[0][1]["body"]
    assert (
        result.exit_code,
        [path for path, _ in posts],
        "Zero findings identified." in posted_body,
        "- **Files checked:** `src/app.py`" in posted_body,
        {request.headers["authorization"] for request in github_api.sent},
    ) == (
        0,
        ["/repos/org/repo/issues/42/comments"],
        True,
        True,
        {f"token {pin_github_session}"},
    )


def test_devops_review_pr_post_dry_run_skips_comment(
    cli: Callable[..., Any],
    github_api: GitHubApiFake,
) -> None:
    """Verify devops review pr --post --dry-run posts no comment to GitHub."""
    _route_the_pull_request(
        github_api,
        files=[pull_request_file_payload("src/app.py")],
        diff="diff --git a/src/app.py b/src/app.py\n+pass\n",
        comments=True,
    )

    result = cli(
        "review", "pr", "42", "--repo", "org/repo", "--post", "--dry-run", "--no-group-analysis"
    )

    assert (
        result.exit_code,
        _posted(github_api),
        "Would post PR comment on #42" in result.output,
    ) == (
        0,
        [],
        True,
    )


def test_devops_review_pr_post_empty_diff_makes_zero_model_calls(
    cli: Callable[..., Any],
    github_api: GitHubApiFake,
    model_fake: ModelFake,
) -> None:
    """Verify a PR diff of routed files only, with --post, makes zero model calls and exits 0 (#995)."""
    _route_the_pull_request(
        github_api,
        files=[pull_request_file_payload("openspec/changes/1-x/tasks.md", "added")],
        diff="diff --git a/openspec/changes/1-x/tasks.md b/openspec/changes/1-x/tasks.md\n+- [x] Done.\n",
        comments=True,
    )

    result = cli("review", "pr", "42", "--repo", "org/repo", "--post")

    assert (
        result.exit_code,
        model_fake.calls,
        [path for path, _ in _posted(github_api)],
    ) == (0, [], ["/repos/org/repo/issues/42/comments"])


def _post_the_review_without_a_model(cli: Callable[..., Any]) -> Any:
    """Review pull request 42 of org/repo with no model stage, and post the review as a comment."""
    return cli("review", "pr", "42", "--repo", "org/repo", "--post", "--no-group-analysis")


def test_devops_review_pr_post_names_the_files_the_pull_request_leaves_in_place(
    cli: Callable[..., Any], github_api: GitHubApiFake
) -> None:
    """A diff of routed files names no file, so the comment lists the files of the compare that
    the review read, and a file the pull request removes is not one of the files checked. The
    command reads the file list one time only (#5346)."""
    _route_the_pull_request(
        github_api,
        files=[
            pull_request_file_payload("openspec/changes/1-x/tasks.md", "added"),
            pull_request_file_payload("openspec/changes/2-y/tasks.md", "removed"),
        ],
        diff="diff --git a/openspec/changes/1-x/tasks.md b/openspec/changes/1-x/tasks.md\n+- [x] Done.\n",
        comments=True,
    )

    result = _post_the_review_without_a_model(cli)

    posted = _posted(github_api)
    file_lists = [r for r in github_api.requested if "/compare/main...abc123?per_page=1" in r]
    assert (result.exit_code, len(posted), len(file_lists)) == (0, 1, 1)
    assert "- **Files checked:** `openspec/changes/1-x/tasks.md`\n" in posted[0][1]["body"]
