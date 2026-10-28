"""The monitor's own reads: the pull request of a branch, Copilot's review state and the
reviewers' verdicts (#983, #1345).

The monitor judges the rest through the merge-readiness verdict; its loop and exit codes are
tested over GitHub's two edges in `tests/commands/test_pr.py`.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.pr_monitor import (
    _CopilotTimeline,
    _fetch_raw_reviews,
    _query_timeline_copilot_state,
    resolve_branch_pr_number,
)
from devops_cli.github.pr_threads import ReviewComment, ReviewThread
from tests.copilot_review_payloads import (
    FIRST_REVIEW_ID,
    MAINTAINER,
    NO_CHANGES,
    SECOND_REVIEW_ID,
    TIMELINE_COPILOT,
    copilot_pass,
    copilot_review,
    review_requested,
    reviewed,
    work_started,
)
from tests.support.fakes.github import GitHubApiFake, github_json, next_page

# The timeline and the reviews of PR #168, as the GitHub session reads them (#983).
_TIMELINE_168 = "/repos/dan-petty/devops-cli/issues/168/timeline?per_page=100"
_REVIEWS_168 = "/repos/dan-petty/devops-cli/pulls/168/reviews?per_page=100"
_CHECK_RUNS_7316135 = "/repos/dan-petty/devops-cli/commits/7316135/check-runs?per_page=100"


class TestResolveBranchPrNumber:
    """Test resolving PR number from branch."""

    def test_resolve_success(self) -> None:
        mock_proc = MagicMock(returncode=0, stdout="168\n", stderr="")
        with patch("devops_cli.github.pr_monitor.run_gh", return_value=mock_proc):
            num = resolve_branch_pr_number("feat/test")
            assert num == 168

    def test_resolve_failure_no_branch(self) -> None:
        mock_proc = MagicMock(returncode=1, stdout="", stderr="git error")
        with patch("devops_cli.github.pr_monitor.run_subprocess", return_value=mock_proc):
            with pytest.raises(
                GitHubOperationError, match="Unable to determine current git branch"
            ):
                resolve_branch_pr_number()

    def test_resolve_failure_no_pr(self) -> None:
        mock_proc = MagicMock(returncode=1, stdout="", stderr="no pull requests found")
        with patch("devops_cli.github.pr_monitor.run_gh", return_value=mock_proc):
            with pytest.raises(GitHubOperationError, match="No open pull request found"):
                resolve_branch_pr_number("feat/untracked")


class TestCopilotAndReviewState:
    """Copilot's review state and the reviewers' verdict, the monitor's review gate."""

    def test_detect_copilot_status_detects_changes_recommended_in_body(
        self, github_api: GitHubApiFake
    ) -> None:
        reviews_data = [
            {
                "user": {"login": "copilot-pull-request-reviewer[bot]"},
                "state": "COMMENTED",
                "body": "### 🟡 Changes recommended\n\nUnresolved concerns remain.",
                "submitted_at": "2026-09-12T14:00:00Z",
            }
        ]
        from devops_cli.github.pr_monitor import _detect_copilot_status

        github_api.route("GET", _TIMELINE_168, github_json([]))
        status = _detect_copilot_status("dan-petty", "devops-cli", 168, reviews_data)
        assert status.state == "changes_requested"
        assert status.is_active is False
        assert "recommended changes" in status.message

    def test_detect_copilot_status_completed_when_zero_unresolved_threads(
        self, github_api: GitHubApiFake
    ) -> None:
        reviews_data = [
            {
                "user": {"login": "copilot-pull-request-reviewer[bot]"},
                "state": "COMMENTED",
                "body": "### 🟡 Changes recommended\n\nUnresolved concerns remain.",
                "submitted_at": "2026-09-12T14:00:00Z",
            }
        ]
        from devops_cli.github.pr_monitor import _detect_copilot_status

        github_api.route("GET", _TIMELINE_168, github_json([]))
        status = _detect_copilot_status(
            "dan-petty", "devops-cli", 168, reviews_data, unresolved_threads=[]
        )
        assert status.state == "completed"
        assert status.is_active is False
        assert "resolved" in status.message

    def test_detect_copilot_status_retains_changes_requested_when_unresolved_threads_exist(
        self, github_api: GitHubApiFake
    ) -> None:
        reviews_data = [
            {
                "user": {"login": "copilot-pull-request-reviewer[bot]"},
                "state": "COMMENTED",
                "body": "### 🟡 Changes recommended\n\nUnresolved concerns remain.",
                "submitted_at": "2026-09-12T14:00:00Z",
            }
        ]
        unresolved = [
            ReviewThread(
                id="PRRT_123",
                is_resolved=False,
                path="src/main.py",
                line=10,
                comments=[ReviewComment(id="PRRC_1", body="Fix this", author="copilot")],
            )
        ]
        from devops_cli.github.pr_monitor import _detect_copilot_status

        github_api.route("GET", _TIMELINE_168, github_json([]))
        status = _detect_copilot_status(
            "dan-petty", "devops-cli", 168, reviews_data, unresolved_threads=unresolved
        )
        assert status.state == "changes_requested"
        assert status.is_active is False
        assert "recommended changes" in status.message

    def test_detect_copilot_status_unread_when_timeline_read_fails(
        self, github_api: GitHubApiFake
    ) -> None:
        reviews_data = [
            {
                "user": {"login": "copilot-pull-request-reviewer[bot]"},
                "state": "COMMENTED",
                "body": "### 🟢 No changes recommended\n\nLooks good!",
                "submitted_at": "2026-09-12T14:00:00Z",
            }
        ]
        from devops_cli.github.pr_monitor import _detect_copilot_status

        github_api.route(
            "GET", _TIMELINE_168, github_json({"message": "Resource not accessible"}, status=403)
        )
        status = _detect_copilot_status("dan-petty", "devops-cli", 168, reviews_data)
        assert (
            status.state,
            "HTTP 403" in status.unread_reason,
            status.is_active,
            f"could not be read: {status.unread_reason}" in status.message,
        ) == ("unread", True, False, True)

    def test_detect_copilot_status_unread_wins_over_changes_requested(
        self, github_api: GitHubApiFake
    ) -> None:
        reviews_data = [
            {
                "user": {"login": "copilot-pull-request-reviewer[bot]"},
                "state": "COMMENTED",
                "body": "### 🟡 Changes recommended\n\nFix this.",
                "submitted_at": "2026-09-12T14:00:00Z",
            }
        ]
        from devops_cli.github.pr_monitor import _detect_copilot_status

        github_api.route("GET", _TIMELINE_168, github_json({"message": "Server Error"}, status=500))
        status = _detect_copilot_status("dan-petty", "devops-cli", 168, reviews_data)
        assert (status.state, "HTTP 500" in status.unread_reason, status.is_active) == (
            "unread",
            True,
            False,
        )

    def test_detect_copilot_status_excludes_no_changes_recommended(
        self, github_api: GitHubApiFake
    ) -> None:
        reviews_data = [
            {
                "user": {"login": "copilot-pull-request-reviewer[bot]"},
                "state": "COMMENTED",
                "body": "### 🟢 No changes recommended\n\nAll automated checks look clean.",
                "submitted_at": "2026-09-12T14:00:00Z",
            }
        ]
        from devops_cli.github.pr_monitor import _detect_copilot_status

        github_api.route("GET", _TIMELINE_168, github_json([]))
        status = _detect_copilot_status("dan-petty", "devops-cli", 168, reviews_data)
        assert status.state == "completed"
        assert status.is_active is False

    def test_detect_copilot_status_uses_latest_review_state(
        self, github_api: GitHubApiFake
    ) -> None:
        reviews_data = [
            {
                "user": {"login": "copilot-pull-request-reviewer[bot]"},
                "state": "CHANGES_REQUESTED",
                "submitted_at": "2026-09-12T13:00:00Z",
            },
            {
                "user": {"login": "copilot-pull-request-reviewer[bot]"},
                "state": "APPROVED",
                "submitted_at": "2026-09-12T14:00:00Z",
            },
        ]
        from devops_cli.github.pr_monitor import _detect_copilot_status

        github_api.route("GET", _TIMELINE_168, github_json([]))
        status = _detect_copilot_status("dan-petty", "devops-cli", 168, reviews_data)
        assert status.state == "completed"
        assert status.is_active is False

    def test_detect_copilot_status_human_review_does_not_clear_copilot(
        self, github_api: GitHubApiFake
    ) -> None:
        reviews_data = [copilot_review(FIRST_REVIEW_ID)]
        timeline = json.dumps(
            [*copilot_pass(FIRST_REVIEW_ID), work_started(), reviewed(5444000001, MAINTAINER)]
        )
        from devops_cli.github.pr_monitor import _detect_copilot_status

        github_api.route("GET", _TIMELINE_168, github_json(json.loads(timeline)))
        status = _detect_copilot_status("dan-petty", "devops-cli", 168, reviews_data)
        assert (status.is_active, status.state) == (True, "working")

    def test_resolve_review_decision_latest_per_reviewer(self) -> None:
        from devops_cli.github.pr_monitor import _resolve_review_decision

        raw_reviews = [
            {"user": {"login": "alice"}, "state": "CHANGES_REQUESTED"},
            {"user": {"login": "bob"}, "state": "COMMENTED"},
            {"user": {"login": "alice"}, "state": "APPROVED"},
        ]
        assert _resolve_review_decision(raw_reviews) == "APPROVED"

    def test_resolve_review_decision_ignores_copilot_bot_reviews(self) -> None:
        from devops_cli.github.pr_monitor import _resolve_review_decision

        raw_reviews = [
            {"user": {"login": "copilot-pull-request-reviewer[bot]"}, "state": "CHANGES_REQUESTED"},
            {"user": {"login": "alice"}, "state": "APPROVED"},
        ]
        assert _resolve_review_decision(raw_reviews) == "APPROVED"

    def test_is_copilot_changes_recommended_heading_only(self) -> None:
        """Verify heading extraction correctly flags changes recommended even if body mentions no changes."""
        from devops_cli.github.pr_monitor import _is_copilot_changes_recommended

        body = (
            "### 🟡 Changes recommended\n\n"
            "Summary of changes:\n"
            "- File A: Needs fix\n"
            "- File B: No changes requested\n"
        )
        assert _is_copilot_changes_recommended(body) is True

        no_changes_body = "### 🟢 No changes recommended\n\nLooks great to me!\n"
        assert _is_copilot_changes_recommended(no_changes_body) is False

    def test_resolve_review_decision_stale_commit_id(self) -> None:
        """Verify _resolve_review_decision rejects approvals targeting stale commit_id."""
        from devops_cli.github.pr_monitor import _resolve_review_decision

        raw_reviews = [
            {"user": {"login": "alice"}, "state": "APPROVED", "commit_id": "commit_sha_1"},
        ]
        # When current revision is commit_sha_2, approval on commit_sha_1 is stale
        decision = _resolve_review_decision(raw_reviews, head_sha="commit_sha_2")
        assert decision == "REVIEW_REQUIRED"

        # When current revision matches, approval is valid
        decision_valid = _resolve_review_decision(raw_reviews, head_sha="commit_sha_1")
        assert decision_valid == "APPROVED"


# ── Timeline and reviews through the GitHub session (#983) ───────────────────────────────────────

_TIMELINE = "/repos/octo/repo/issues/168/timeline?per_page=100"
_TIMELINE_PAGE_2 = "/repositories/1/issues/168/timeline?per_page=100&page=2"
_REVIEWS = "/repos/octo/repo/pulls/168/reviews?per_page=100"
_REVIEWS_PAGE_2 = "/repositories/1/pulls/168/reviews?per_page=100&page=2"


def test_a_two_page_timeline_gives_both_copilot_events(github_api: GitHubApiFake) -> None:
    """Copilot starting on page 1 and finishing on page 2 reads as finished: every page is read."""
    github_api.route(
        "GET",
        _TIMELINE,
        github_json([work_started(), {"event": "commented"}], headers=next_page(_TIMELINE_PAGE_2)),
    )
    github_api.route("GET", _TIMELINE_PAGE_2, github_json([reviewed(FIRST_REVIEW_ID)]))
    state = _query_timeline_copilot_state("octo", "repo", 168, frozenset({FIRST_REVIEW_ID}))
    assert (state, len(github_api.sent)) == (_CopilotTimeline(event="reviewed"), 2)


def test_a_timeline_page_that_is_no_list_leaves_the_copilot_state_unread(
    github_api: GitHubApiFake,
) -> None:
    """A malformed second page is a read failure, never a timeline that ends early."""
    github_api.route(
        "GET", _TIMELINE, github_json([work_started()], headers=next_page(_TIMELINE_PAGE_2))
    )
    github_api.route("GET", _TIMELINE_PAGE_2, github_json({"message": "Server Error"}))
    state = _query_timeline_copilot_state("octo", "repo", 168, frozenset())
    assert (state.working, state.event, "page 2" in state.error) == (False, "", True)


# A person's review and one by the coding agent, which the timeline also names `Copilot`.
_PERSON_REVIEW_ID = 5444000001
_CODING_AGENT_EVENT_ID = 5444000002
_BOT_REVIEWER = {"login": "github-actions[bot]", "type": "Bot", "id": 41898282}


@pytest.mark.parametrize(
    ("events", "state"),
    [
        pytest.param([], _CopilotTimeline(), id="no-events"),
        pytest.param(
            [work_started(), reviewed(_PERSON_REVIEW_ID, _BOT_REVIEWER)],
            _CopilotTimeline(working=True, event="copilot_work_started"),
            id="another-reviewer-leaves-copilot-working",
        ),
        pytest.param(
            copilot_pass(FIRST_REVIEW_ID),
            _CopilotTimeline(event="reviewed"),
            id="copilot-review-ends-the-work",
        ),
        pytest.param(
            [work_started(), reviewed(_PERSON_REVIEW_ID, MAINTAINER)],
            _CopilotTimeline(working=True, event="copilot_work_started"),
            id="a-persons-review-leaves-copilot-working",
        ),
        pytest.param(
            [work_started(), reviewed(_CODING_AGENT_EVENT_ID, TIMELINE_COPILOT)],
            _CopilotTimeline(working=True, event="copilot_work_started"),
            id="a-copilot-event-that-is-no-copilot-review-leaves-copilot-working",
        ),
        pytest.param(
            ["not an event", work_started()],
            _CopilotTimeline(working=True, event="copilot_work_started"),
            id="non-object-entries-skipped",
        ),
        pytest.param(
            [review_requested()],
            _CopilotTimeline(),
            id="a-request-copilot-has-not-started-is-no-pass",
        ),
        pytest.param(
            [*copilot_pass(FIRST_REVIEW_ID), review_requested()],
            _CopilotTimeline(event="reviewed"),
            id="a-request-after-a-finished-pass-starts-none",
        ),
    ],
)
def test_the_timeline_events_give_the_copilot_state(
    events: list[object], state: _CopilotTimeline
) -> None:
    """Copilot works from its start event until the `reviewed` event of one of its own reviews,
    named by the review's id, since the timeline names the account `Copilot` (#1345). A request
    to it starts no pass."""
    from devops_cli.github.pr_monitor import _timeline_copilot_state

    assert _timeline_copilot_state(events, frozenset({FIRST_REVIEW_ID})) == state


def test_the_reviews_are_read_from_every_page(github_api: GitHubApiFake) -> None:
    """Both pages of a pull request's reviews are read, in order."""
    github_api.route(
        "GET",
        _REVIEWS,
        github_json(
            [{"user": {"login": "user1"}, "state": "APPROVED"}],
            headers=next_page(_REVIEWS_PAGE_2),
        ),
    )
    github_api.route(
        "GET", _REVIEWS_PAGE_2, github_json([{"user": {"login": "user2"}, "state": "COMMENTED"}])
    )
    reviews = _fetch_raw_reviews("octo", "repo", 168)
    assert ([review["user"]["login"] for review in reviews], reviews.error) == (
        ["user1", "user2"],
        "",
    )


def test_a_failed_reviews_read_is_reported_with_no_reviews(github_api: GitHubApiFake) -> None:
    """A reviews read that fails gives no reviews and the reason, not a shorter list."""
    github_api.route("GET", _REVIEWS, github_json({"message": "Bad Gateway"}, status=502))
    reviews = _fetch_raw_reviews("octo", "repo", 168)
    assert (list(reviews), "HTTP 502" in reviews.error) == ([], True)


def test_a_review_by_a_user_whose_login_contains_copilot_is_not_copilots(
    github_api: GitHubApiFake,
) -> None:
    """Only Copilot's own logins make a review Copilot's (#1345): a person named copilot-fan who
    recommends changes and approves is a person reviewing, so Copilot is idle and the approval
    counts."""
    from devops_cli.github.pr_monitor import _detect_copilot_status, _resolve_review_decision

    reviews = [
        {
            "user": {"login": "copilot-fan", "type": "User"},
            "state": "APPROVED",
            "commit_id": "7316135",
            "body": "### Changes recommended\n\nRename this.",
            "submitted_at": "2026-10-18T10:00:00Z",
        }
    ]
    github_api.route("GET", _TIMELINE_168, github_json([]))
    status = _detect_copilot_status("dan-petty", "devops-cli", 168, reviews)
    assert (status.state, _resolve_review_decision(reviews, head_sha="7316135")) == (
        "idle",
        "APPROVED",
    )


# ── #1283's first two Copilot passes, as GitHub recorded them (#1345) ─────────────────────────────

_REVIEWS_1283 = "/repos/dan-petty/devops-cli/pulls/1283/reviews?per_page=100"
_TIMELINE_1283 = "/repos/dan-petty/devops-cli/issues/1283/timeline?per_page=100"
_HEAD_1283 = "1d2c3b4a5f6e"


def _route_1283(github_api: GitHubApiFake, *, second_body: str, then: list[object]) -> list[object]:
    """Route #1283's reviews and timeline: two finished Copilot passes, the second with
    `second_body`, a person's approval of the head, and the events in `then` after them."""
    reviews = [
        copilot_review(FIRST_REVIEW_ID),
        copilot_review(SECOND_REVIEW_ID, body=second_body, submitted_at="2026-10-07T15:35:57Z"),
        {"id": 5444999999, "user": MAINTAINER, "state": "APPROVED", "commit_id": _HEAD_1283},
    ]
    timeline = [*copilot_pass(FIRST_REVIEW_ID), *copilot_pass(SECOND_REVIEW_ID), *then]
    github_api.route("GET", _REVIEWS_1283, github_json(reviews))
    github_api.route("GET", _TIMELINE_1283, github_json(timeline))
    return reviews


def test_two_finished_copilot_passes_read_as_completed(github_api: GitHubApiFake) -> None:
    """Each `reviewed` event names one of Copilot's reviews, so both passes have ended."""
    from devops_cli.github.pr_monitor import _detect_copilot_status

    reviews = _route_1283(github_api, second_body=NO_CHANGES, then=[])
    status = _detect_copilot_status("dan-petty", "devops-cli", 1283, reviews, unresolved_threads=[])
    assert (status.is_active, status.state) == (False, "completed")


def test_a_pending_copilot_request_leaves_the_monitor_waiting_on_nothing(
    github_api: GitHubApiFake,
) -> None:
    """A request Copilot has not started is no running pass: the monitor never waits on a
    request Copilot may never take up (#1566, #1581 and #1615 got no Copilot review)."""
    from devops_cli.github.pr_monitor import _detect_copilot_status

    github_api.route("GET", _TIMELINE_168, github_json([review_requested()]))
    status = _detect_copilot_status("dan-petty", "devops-cli", 168, [])
    assert (status.is_active, status.state) == (False, "idle")
