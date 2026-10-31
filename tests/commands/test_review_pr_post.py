"""Tests for PR review comment formatting and --post execution (Issue #604 Part 2)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.ai.personas import PERSONAS, Persona, PersonaDefinition
from devops_cli.ai.review.runner import format_pr_review_comment
from devops_cli.ai.review_schema import Finding, ReviewResult
from tests.support.fakes.github import (
    github_json,
    pull_request_file_payload,
    pull_request_payload,
    route_pull_request,
)

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake

pytestmark = [pytest.mark.usefixtures("keyring_store", "scanner_fake")]


def test_zero_findings_comment_names_files_personas_and_analyzers() -> None:
    """Verify zero-findings PR comment states exact files, personas, and analyzers that ran."""
    persona_devsec = PERSONAS[Persona.DEVSECOPS]
    res = ReviewResult(
        persona=Persona.DEVSECOPS,
        recommendation="APPROVE",
        findings=[],
        summary="No defects found; consider adding docstrings.",
    )
    reviews: list[tuple[PersonaDefinition, ReviewResult | str]] = [(persona_devsec, res)]
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
        f"- **Personas:** {persona_devsec.title}",
        "- **Analyzers:** Bandit, Gitleaks",
        "## Model Notes (Not Verified)",
        "No defects found; consider adding docstrings.",
    )
    assert (
        all(frag in comment for frag in expected_fragments),
        "Positive observations" in comment,
    ) == (True, False)


def test_zero_findings_comment_with_no_analyzers_and_no_summary() -> None:
    """Verify zero-findings comment when no analyzers ran and no summary was emitted."""
    persona_qa = PERSONAS[Persona.QA]
    res = ReviewResult(
        persona=Persona.QA,
        recommendation="APPROVE",
        findings=[],
        summary="",
    )
    reviews: list[tuple[PersonaDefinition, ReviewResult | str]] = [(persona_qa, res)]

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
        f"- **Personas:** {persona_qa.title}",
        "- **Analyzers:** None",
    ]
    assert (
        comment.strip().splitlines() == expected_lines,
        "Model Notes (Not Verified)" in comment,
    ) == (True, False)


def test_zero_findings_comment_multiple_personas_model_notes() -> None:
    """Verify model notes from multiple personas are formatted under persona subheadings."""
    p_devsec = PERSONAS[Persona.DEVSECOPS]
    p_arch = PERSONAS[Persona.ARCHITECT]
    r1 = ReviewResult(
        persona=Persona.DEVSECOPS,
        recommendation="APPROVE",
        findings=[],
        summary="Security posture is clean.",
    )
    r2 = ReviewResult(
        persona=Persona.ARCHITECT,
        recommendation="APPROVE",
        findings=[],
        summary="Architecture exhibits low coupling.",
    )
    reviews: list[tuple[PersonaDefinition, ReviewResult | str]] = [
        (p_devsec, r1),
        (p_arch, r2),
    ]

    comment = format_pr_review_comment(
        reviews=reviews,
        files=["main.py"],
        static_analyzers={"Bandit": "ran"},
    )

    expected_fragments = (
        "## 🤖 AI Code Review",
        "Zero findings identified.",
        "- **Files checked:** `main.py`",
        f"- **Personas:** {p_devsec.title}, {p_arch.title}",
        "- **Analyzers:** Bandit",
        "## Model Notes (Not Verified)",
        f"### {p_devsec.title}\n\nSecurity posture is clean.",
        f"### {p_arch.title}\n\nArchitecture exhibits low coupling.",
    )
    assert all(frag in comment for frag in expected_fragments) is True


def test_comment_with_findings_renders_findings_and_model_notes() -> None:
    """Verify PR comment with findings renders finding details and unverified notes."""
    p_devsec = PERSONAS[Persona.DEVSECOPS]
    finding = Finding(
        severity="HIGH",
        title="Unvalidated URL Redirect",
        description="Redirect target not validated against allowlist",
        location="src/auth.py:42-50",
        fix="Use validate_redirect_url(target)",
        verified=True,
    )
    res = ReviewResult(
        persona=Persona.DEVSECOPS,
        recommendation="REQUEST CHANGES",
        findings=[finding],
        summary="Review completed with 1 high finding.",
    )
    reviews: list[tuple[PersonaDefinition, ReviewResult | str]] = [(p_devsec, res)]

    comment = format_pr_review_comment(reviews=reviews, files=["src/auth.py"])

    expected_fragments = (
        "## 🤖 AI Code Review",
        f"## Review by {p_devsec.title}",
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
    ) == (True, False, False)


def _route_the_pull_request(
    api: GitHubApiFake, *, files: list[dict[str, Any]], diff: str, comments: bool
) -> None:
    """Serve pull request 42 of org/repo, with `files` and `diff`; with `comments`, GitHub also
    accepts a comment on it."""
    route_pull_request(
        api,
        "org/repo",
        42,
        pull_request_payload(title="Test PR", head_repo="org/repo", base_repo="org/repo"),
        files=files,
        diff=diff,
    )
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


def test_devops_review_pr_post_stops_when_the_files_of_the_pull_request_cannot_be_read(
    cli: Callable[..., Any], github_api: GitHubApiFake
) -> None:
    """A diff of routed files names no file, so the comment lists the pull request's files. When
    GitHub fails that second read, the command exits 1 and posts nothing: a comment that names
    no file would look like a review of an empty change."""
    _route_the_pull_request(
        github_api,
        files=[pull_request_file_payload("openspec/changes/1-x/tasks.md", "added")],
        diff="diff --git a/openspec/changes/1-x/tasks.md b/openspec/changes/1-x/tasks.md\n+- [x] Done.\n",
        comments=True,
    )
    files = "/repos/org/repo/pulls/42/files?per_page=100"
    github_api.route(
        "GET",
        files,
        github_json([pull_request_file_payload("openspec/changes/1-x/tasks.md", "added")]),
        github_json({"message": "Server Error"}, status=500),
    )

    result = _post_the_review_without_a_model(cli)

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert _posted(github_api) == []
    assert "(HTTP 500)" in result.output


def test_devops_review_pr_post_names_the_files_the_pull_request_leaves_in_place(
    cli: Callable[..., Any], github_api: GitHubApiFake
) -> None:
    """A diff of routed files names no file, so the comment lists the pull request's files, and a
    file the pull request removes is not one of the files checked."""
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
