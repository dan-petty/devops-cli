"""Test suite for closing issues linked by pull requests merged outside the default branch."""

from __future__ import annotations

import json
import subprocess
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.gh import app as gh_app
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.issue_closure import (
    ClosureResult,
    LinkedIssue,
    close_issue,
    close_issues_for_merged_pull_requests,
    close_issues_for_pull_request,
    closure_comment,
    extract_linked_issues,
    get_default_branch,
    get_issue_state,
    get_pull_request,
    list_merged_pull_requests,
    strip_non_prose,
)

runner = CliRunner()
REPO = "example/repository"


def _completed(stdout: str = "", returncode: int = 0, stderr: str = "") -> Any:
    """Build a CompletedProcess as run_gh returns."""
    return subprocess.CompletedProcess([], returncode=returncode, stdout=stdout, stderr=stderr)


def _gh_router(responses: dict[str, Any]) -> Any:
    """Route gh invocations by their leading subcommand words."""

    def route(args: list[str], **_: Any) -> Any:
        key = " ".join(args[:2])
        if key in responses:
            value = responses[key]
            return value(args) if callable(value) else value
        return _completed(returncode=1, stderr=f"unexpected gh call: {args}")

    return route


# =============================================================================
# Extracting Linked Issues
# =============================================================================


@pytest.mark.parametrize(
    "keyword",
    ["close", "closes", "closed", "fix", "fixes", "fixed", "resolve", "resolves", "resolved"],
)
def test_every_keyword_github_honours_is_recognised(keyword: str) -> None:
    """What this closes must be exactly what GitHub would have closed."""
    assert extract_linked_issues(f"{keyword} #317") == [LinkedIssue(number=317, keyword=keyword)]


def test_keyword_matching_is_case_insensitive() -> None:
    """Authors capitalise the start of a sentence."""
    assert extract_linked_issues("Closes #317")[0].number == 317


def test_a_colon_between_keyword_and_reference_is_accepted() -> None:
    """GitHub accepts `Closes: #317`."""
    assert extract_linked_issues("Closes: #317")[0].number == 317


def test_a_bare_reference_is_not_a_closing_link() -> None:
    """Mentioning an issue is not declaring that this closes it.

    Closing on a bare mention would shut issues merely referenced for context.
    """
    assert extract_linked_issues("Related to #317 and see #318") == []


def test_a_non_closing_verb_is_ignored() -> None:
    """Only GitHub's own keyword set counts."""
    assert extract_linked_issues("Addresses #317. Supersedes #318.") == []


def test_several_issues_are_all_extracted_and_ordered() -> None:
    """A pull request may close more than one issue."""
    body = "Closes #320\nFixes #317\nResolves #319"
    assert [issue.number for issue in extract_linked_issues(body)] == [317, 319, 320]


def test_a_repeated_reference_is_returned_once() -> None:
    """Restating a link must not attempt the close twice."""
    assert len(extract_linked_issues("Closes #317. Also closes #317.")) == 1


def test_a_fenced_code_block_is_not_scanned() -> None:
    """A body documenting the syntax must not be read as a live link.

    This project's own documentation shows `Closes #NNN` in examples; treating those as
    declarations would close whatever issue number the example happened to use.
    """
    body = "Explanation.\n\n```\nCloses #999\n```\n\nCloses #317"
    assert [issue.number for issue in extract_linked_issues(body)] == [317]


def test_inline_code_is_not_scanned() -> None:
    """The same reasoning applies to a backticked fragment."""
    assert extract_linked_issues("Write `Closes #999` in the body.") == []


def test_quoted_text_is_not_scanned() -> None:
    """A quoted review comment is someone else's text, not this author's declaration."""
    body = "> Closes #999\n\nI disagree, this closes nothing."
    assert extract_linked_issues(body) == []


def test_a_cross_repository_reference_is_ignored() -> None:
    """Closing the same-numbered issue in this repository would be wrong."""
    assert extract_linked_issues("Closes other/project#317", repo=REPO) == []


def test_a_reference_qualified_with_this_repository_is_honoured() -> None:
    """An explicitly qualified link to this repository is still a link to it."""
    assert extract_linked_issues(f"Closes {REPO}#317", repo=REPO)[0].number == 317


def test_an_empty_body_links_nothing() -> None:
    """A pull request with no body closes nothing."""
    assert (extract_linked_issues(""), extract_linked_issues("   ")) == ([], [])


def test_stripping_leaves_ordinary_prose_intact() -> None:
    """The scan must still see the text that matters."""
    assert "Closes #317" in strip_non_prose("Some prose.\n\nCloses #317\n")


# =============================================================================
# Closing For One Pull Request
# =============================================================================


def _pr_payload(**overrides: Any) -> str:
    """Build a gh pr view payload."""
    payload = {
        "number": 361,
        "title": "feat: something",
        "body": "Closes #317",
        "state": "MERGED",
        "mergedAt": "2026-09-21T21:00:00Z",
        "baseRefName": "release/v0.2.22",
        "url": "https://github.com/example/repository/pull/361",
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_a_merged_release_branch_pull_request_closes_its_issue() -> None:
    """The case GitHub declines to handle."""
    responses = {
        "pr view": _completed(_pr_payload()),
        "issue view": _completed(json.dumps({"number": 317, "state": "OPEN"})),
        "issue close": _completed(),
    }
    with patch("devops_cli.github.issue_closure.run_gh", side_effect=_gh_router(responses)):
        result = close_issues_for_pull_request(REPO, 361, default_branch="main")
    assert (result.closed, result.merged, result.base_ref) == ([317], True, "release/v0.2.22")


def test_an_unmerged_pull_request_closes_nothing() -> None:
    """A closing keyword states what merging will do, not what has happened.

    Acting early closes issues whose work may never land.
    """
    responses = {"pr view": _completed(_pr_payload(mergedAt=None, state="OPEN"))}
    with patch("devops_cli.github.issue_closure.run_gh", side_effect=_gh_router(responses)):
        result = close_issues_for_pull_request(REPO, 361, default_branch="main")
    assert (result.closed, result.reason) == ([], "pull request is not merged")


def test_a_pull_request_merged_into_the_default_branch_is_left_to_github() -> None:
    """Doing it again would post a comment claiming credit for something GitHub did."""
    responses = {"pr view": _completed(_pr_payload(baseRefName="main"))}
    with patch("devops_cli.github.issue_closure.run_gh", side_effect=_gh_router(responses)):
        result = close_issues_for_pull_request(REPO, 361, default_branch="main")
    assert (result.closed, "default branch" in result.reason) == ([], True)


def test_a_pull_request_with_no_closing_keywords_closes_nothing() -> None:
    """Most pull requests link no issue at all."""
    responses = {"pr view": _completed(_pr_payload(body="A refactor with no linked issue."))}
    with patch("devops_cli.github.issue_closure.run_gh", side_effect=_gh_router(responses)):
        result = close_issues_for_pull_request(REPO, 361, default_branch="main")
    assert (result.closed, result.reason) == ([], "no closing keywords in the pull request body")


def test_an_already_closed_issue_is_reported_rather_than_reclosed() -> None:
    """Re-closing posts a second comment on an issue that is already settled."""
    responses = {
        "pr view": _completed(_pr_payload()),
        "issue view": _completed(json.dumps({"number": 317, "state": "CLOSED"})),
    }
    with patch("devops_cli.github.issue_closure.run_gh", side_effect=_gh_router(responses)):
        result = close_issues_for_pull_request(REPO, 361, default_branch="main")
    assert (result.closed, result.already_closed) == ([], [317])


def test_a_reference_that_is_not_an_issue_is_skipped() -> None:
    """A pull request number where an issue was expected must not be closed as one."""
    responses = {
        "pr view": _completed(_pr_payload()),
        "issue view": _completed(returncode=1, stderr="not found"),
    }
    with patch("devops_cli.github.issue_closure.run_gh", side_effect=_gh_router(responses)):
        result = close_issues_for_pull_request(REPO, 361, default_branch="main")
    assert result.skipped == [(317, "not an accessible issue")]


def test_a_failed_close_is_reported_rather_than_counted_as_success() -> None:
    """Reporting a close that did not happen is worse than reporting the failure."""
    responses = {
        "pr view": _completed(_pr_payload()),
        "issue view": _completed(json.dumps({"number": 317, "state": "OPEN"})),
        "issue close": _completed(returncode=1, stderr="permission denied"),
    }
    with patch("devops_cli.github.issue_closure.run_gh", side_effect=_gh_router(responses)):
        result = close_issues_for_pull_request(REPO, 361, default_branch="main")
    assert (result.closed, result.skipped) == ([], [(317, "close request failed")])


def test_a_dry_run_reports_what_it_would_close_without_closing_it() -> None:
    """The preview must not mutate anything."""
    calls: list[list[str]] = []

    def record(args: list[str], **_: Any) -> Any:
        calls.append(args)
        return _gh_router(
            {
                "pr view": _completed(_pr_payload()),
                "issue view": _completed(json.dumps({"number": 317, "state": "OPEN"})),
            }
        )(args)

    with patch("devops_cli.github.issue_closure.run_gh", side_effect=record):
        result = close_issues_for_pull_request(REPO, 361, default_branch="main", dry_run=True)
    assert (result.closed, any(call[:2] == ["issue", "close"] for call in calls)) == ([317], False)


def test_the_closing_comment_names_the_pull_request_and_the_branch() -> None:
    """A silent close leaves no way to tell completed work from tidying up."""
    comment = closure_comment(361, "release/v0.2.22", "https://example.com/pull/361")
    assert ("https://example.com/pull/361" in comment, "release/v0.2.22" in comment) == (
        True,
        True,
    )


def test_the_comment_falls_back_to_the_number_without_a_url() -> None:
    """The reference must survive a missing url."""
    assert "#361" in closure_comment(361, "release/v0.2.22")


# =============================================================================
# Sweeping Merged Pull Requests
# =============================================================================


def test_a_sweep_resolves_the_default_branch_once() -> None:
    """Resolving per pull request would cost an API call per candidate."""
    calls: list[list[str]] = []

    def record(args: list[str], **_: Any) -> Any:
        calls.append(args)
        return _gh_router(
            {
                "repo view": _completed(json.dumps({"defaultBranchRef": {"name": "main"}})),
                "pr list": _completed(json.dumps([{"number": 1}, {"number": 2}])),
                "pr view": _completed(_pr_payload(body="no links")),
            }
        )(args)

    with patch("devops_cli.github.issue_closure.run_gh", side_effect=record):
        close_issues_for_merged_pull_requests(REPO)
    assert sum(1 for call in calls if call[:2] == ["repo", "view"]) == 1


def test_an_unreadable_pull_request_is_recorded_as_an_error_not_a_clean_result() -> None:
    """A sweep where every lookup failed must not report that nothing needed closing.

    That output is indistinguishable from a genuinely up-to-date repository, which is how a
    broken sweep goes unnoticed.
    """

    def route(args: list[str], **_: Any) -> Any:
        if args[:2] == ["repo", "view"]:
            return _completed(json.dumps({"defaultBranchRef": {"name": "main"}}))
        if args[:2] == ["pr", "list"]:
            return _completed(json.dumps([{"number": 1}]))
        return _completed(returncode=1, stderr="api failure")

    with patch("devops_cli.github.issue_closure.run_gh", side_effect=route):
        results = close_issues_for_merged_pull_requests(REPO)
    assert (len(results), bool(results[0].error), results[0].closed) == (1, True, [])


def test_a_sweep_filters_by_base_branch() -> None:
    """Only release-branch merges need this treatment."""
    captured: list[list[str]] = []

    def record(args: list[str], **_: Any) -> Any:
        captured.append(args)
        return _gh_router(
            {
                "repo view": _completed(json.dumps({"defaultBranchRef": {"name": "main"}})),
                "pr list": _completed(json.dumps([])),
            }
        )(args)

    with patch("devops_cli.github.issue_closure.run_gh", side_effect=record):
        close_issues_for_merged_pull_requests(REPO, base="release/v0.2.22")
    listing = next(call for call in captured if call[:2] == ["pr", "list"])
    assert "--base" in listing and "release/v0.2.22" in listing


def test_merged_pull_requests_are_listed_by_number() -> None:
    """The sweep iterates numbers, not full payloads."""
    with patch(
        "devops_cli.github.issue_closure.run_gh",
        return_value=_completed(json.dumps([{"number": 5}, {"number": 3}])),
    ):
        assert list_merged_pull_requests(REPO) == [5, 3]


def test_a_malformed_listing_yields_no_pull_requests() -> None:
    """A non-list response must not raise mid-sweep."""
    with patch("devops_cli.github.issue_closure.run_gh", return_value=_completed(json.dumps({}))):
        assert list_merged_pull_requests(REPO) == []


# =============================================================================
# GitHub CLI Plumbing
# =============================================================================


def test_a_failing_gh_command_raises_with_its_stderr() -> None:
    """A silent failure here would be read as an empty result."""
    with patch(
        "devops_cli.github.issue_closure.run_gh",
        return_value=_completed(returncode=1, stderr="boom"),
    ):
        with pytest.raises(GitHubOperationError, match="boom"):
            get_pull_request(REPO, 1)


def test_malformed_json_from_gh_is_reported() -> None:
    """Truncated output must not be mistaken for a valid empty response."""
    with patch("devops_cli.github.issue_closure.run_gh", return_value=_completed("{not json")):
        with pytest.raises(GitHubOperationError, match="Malformed JSON"):
            get_pull_request(REPO, 1)


def test_a_non_object_pull_request_payload_is_rejected() -> None:
    """A list where an object was expected is not a pull request."""
    with patch("devops_cli.github.issue_closure.run_gh", return_value=_completed("[]")):
        with pytest.raises(GitHubOperationError, match="Unexpected response"):
            get_pull_request(REPO, 1)


def test_the_default_branch_is_resolved_from_the_repository() -> None:
    """Everything downstream depends on knowing which branch GitHub acts on."""
    with patch(
        "devops_cli.github.issue_closure.run_gh",
        return_value=_completed(json.dumps({"defaultBranchRef": {"name": "trunk"}})),
    ):
        assert get_default_branch(REPO) == "trunk"


def test_an_unresolvable_default_branch_is_an_error() -> None:
    """Guessing 'main' would close issues for pull requests GitHub already handled."""
    with patch("devops_cli.github.issue_closure.run_gh", return_value=_completed("{}")):
        with pytest.raises(GitHubOperationError, match="default branch"):
            get_default_branch(REPO)


def test_an_issue_state_is_normalized_to_lower_case() -> None:
    """gh reports OPEN; the comparison is against 'open'."""
    with patch(
        "devops_cli.github.issue_closure.run_gh",
        return_value=_completed(json.dumps({"number": 1, "state": "OPEN"})),
    ):
        assert get_issue_state(REPO, 1) == "open"


def test_an_unreadable_issue_state_is_none() -> None:
    """Absence is distinguishable from open or closed."""
    with patch("devops_cli.github.issue_closure.run_gh", return_value=_completed(returncode=1)):
        assert get_issue_state(REPO, 1) is None


def test_a_malformed_issue_payload_is_none() -> None:
    """Unparseable output is not a state."""
    with patch("devops_cli.github.issue_closure.run_gh", return_value=_completed("{oops")):
        assert get_issue_state(REPO, 1) is None


def test_closing_passes_the_comment_through() -> None:
    """The explanation has to reach the issue."""
    captured: list[list[str]] = []

    def record(args: list[str], **_: Any) -> Any:
        captured.append(args)
        return _completed()

    with patch("devops_cli.github.issue_closure.run_gh", side_effect=record):
        close_issue(REPO, 317, "because")
    assert "--comment" in captured[0] and "because" in captured[0]


def test_closing_without_a_comment_omits_the_flag() -> None:
    """An empty --comment would post a blank comment."""
    captured: list[list[str]] = []

    def record(args: list[str], **_: Any) -> Any:
        captured.append(args)
        return _completed()

    with patch("devops_cli.github.issue_closure.run_gh", side_effect=record):
        close_issue(REPO, 317, "")
    assert "--comment" not in captured[0]


def test_a_result_serializes_for_json_consumers() -> None:
    """The command exposes --json for scripting."""
    payload = ClosureResult(pull_request=1, base_ref="release/x", merged=True, closed=[7]).as_dict()
    assert (payload["pull_request"], payload["closed"], payload["merged"]) == (1, [7], True)


# =============================================================================
# CLI
# =============================================================================


def test_the_command_reports_what_it_closed() -> None:
    """The operator sees which issues were closed by which pull request."""
    with (
        patch(
            "devops_cli.commands.gh.close_issues_for_merged_pull_requests",
            return_value=[
                ClosureResult(pull_request=361, base_ref="release/x", merged=True, closed=[317])
            ],
        ),
        patch("devops_cli.commands.gh._resolve_repo", return_value=REPO),
    ):
        result = runner.invoke(gh_app, ["issues", "close-merged"])
    assert (result.exit_code, "#317" in result.stdout) == (0, True)


def test_the_command_targets_a_single_pull_request_when_asked() -> None:
    """Closing one pull request's issues should not sweep the repository."""
    with (
        patch(
            "devops_cli.commands.gh.close_issues_for_pull_request",
            return_value=ClosureResult(
                pull_request=361, base_ref="release/x", merged=True, closed=[317]
            ),
        ) as single,
        patch("devops_cli.commands.gh._resolve_repo", return_value=REPO),
    ):
        result = runner.invoke(gh_app, ["issues", "close-merged", "--pr", "361"])
    assert (result.exit_code, single.call_count) == (0, 1)


def test_the_command_exits_non_zero_when_lookups_failed() -> None:
    """A sweep that could read nothing must not look like a clean repository."""
    with (
        patch(
            "devops_cli.commands.gh.close_issues_for_merged_pull_requests",
            return_value=[ClosureResult(pull_request=1, error="api failure")],
        ),
        patch("devops_cli.commands.gh._resolve_repo", return_value=REPO),
    ):
        result = runner.invoke(gh_app, ["issues", "close-merged"])
    assert result.exit_code == 1


def test_a_clean_sweep_exits_zero() -> None:
    """An up-to-date repository is a success, not a warning."""
    with (
        patch(
            "devops_cli.commands.gh.close_issues_for_merged_pull_requests",
            return_value=[ClosureResult(pull_request=1, reason="no closing keywords")],
        ),
        patch("devops_cli.commands.gh._resolve_repo", return_value=REPO),
    ):
        result = runner.invoke(gh_app, ["issues", "close-merged"])
    assert result.exit_code == 0


def test_the_command_emits_json_when_requested() -> None:
    """Machine consumers need the structured result."""
    with (
        patch(
            "devops_cli.commands.gh.close_issues_for_merged_pull_requests",
            return_value=[
                ClosureResult(pull_request=361, base_ref="release/x", merged=True, closed=[317])
            ],
        ),
        patch("devops_cli.commands.gh._resolve_repo", return_value=REPO),
    ):
        result = runner.invoke(gh_app, ["issues", "close-merged", "--json"])
    payload = json.loads(result.stdout)
    assert (result.exit_code, payload[0]["closed"]) == (0, [317])
