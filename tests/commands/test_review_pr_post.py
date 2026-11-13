"""Tests for PR review comment formatting and --post execution (Issue #604 Part 2)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.ai.review.runner import format_pr_review_comment
from devops_cli.ai.review_schema import Finding, ReviewResult
from tests.support.fakes.github import (
    github_json,
    pull_request_file_payload,
    pull_request_payload,
    route_pull_request,
    route_pull_request_changes,
)

if TYPE_CHECKING:
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
    api: GitHubApiFake, *, files: list[dict[str, Any]], diff: str, comments: bool
) -> None:
    """Serve pull request 42 of org/repo, whose compare with its base branch holds `files` and
    `diff`; with `comments`, GitHub also accepts a comment on it."""
    pull = pull_request_payload(title="Test PR", head_repo="org/repo", base_repo="org/repo")
    route_pull_request(api, "org/repo", 42, pull)
    route_pull_request_changes(api, pull, *files, merge_base="merge789", diff=diff)
    if comments:
        api.route("POST", "/repos/org/repo/issues/42/comments", github_json({"id": 1}, status=201))


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
    the review read, and a file the pull request removes is not one of the files checked."""
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
    assert (result.exit_code, len(posted)) == (0, 1)
    assert "- **Files checked:** `openspec/changes/1-x/tasks.md`\n" in posted[0][1]["body"]
