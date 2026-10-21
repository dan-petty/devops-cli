"""Tests for GitHub tab in devops dashboard (issue #685)."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from textual.widgets import DataTable, Static, TabbedContent
from typer.testing import CliRunner

from devops_cli.commands.dashboard import TAB_NUM_MAP
from devops_cli.commands.dashboard import app as dashboard_app
from devops_cli.config.constants import (
    CONST_DASHBOARD_DOMAIN_GITHUB,
    CONST_DASHBOARD_DOMAINS,
    CONST_LOGS_TAB_ID,
)
from devops_cli.exceptions.git import GitHubOperationError, GitHubRateLimitError
from devops_cli.github.check_verdict import CheckBucket, PRCheckItem
from devops_cli.github.pr_monitor import (
    CopilotReviewStatus,
    get_copilot_review_status,
    sort_prs_oldest_first,
)
from devops_cli.github.pr_queue import (
    GitHubPRSummary,
    GitHubQuotaSummary,
    PRChecksSummary,
    check_pacing_guard,
    parse_status_check_rollup,
)
from devops_cli.github.pr_threads import ReviewComment, ReviewThread
from devops_cli.github.rate_limiter import QuotaState
from devops_cli.github.run_view import fetch_workflow_run_view, run_view_args
from devops_cli.ui.dashboard import DashboardApp, HelpScreen
from devops_cli.ui.data_providers import GitHubSummary, fetch_github_status
from devops_cli.ui.projections import (
    github_banner,
    github_check_rows,
    github_rows,
    render_banner,
    render_rows,
)
from devops_cli.ui.refresh import refresh_domain
from devops_cli.ui.state import DashboardState
from devops_cli.ui.widgets import GitHubPanel, LogPane

runner = CliRunner()


# =============================================================================
# Helpers and Sample Builders
# =============================================================================


@pytest.fixture(autouse=True)
def mock_dashboard_fetchers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure dashboard tests do not invoke real network or subprocess fetchers."""
    from devops_cli.ui import refresh as refresh_module

    fake_fetchers = {d: (lambda: None) for d in CONST_DASHBOARD_DOMAINS}
    monkeypatch.setattr(refresh_module, "DOMAIN_FETCHERS", fake_fetchers)


def _make_pr(
    number: int,
    title: str = "Test PR",
    created_at: str = "2026-10-01T10:00:00Z",
    checks: PRChecksSummary | None = None,
    unresolved_threads_count: int = 0,
    threads_has_next_page: bool = False,
    is_draft: bool = False,
) -> GitHubPRSummary:
    return GitHubPRSummary(
        number=number,
        title=title,
        url=f"https://example.com/owner/repo/pull/{number}",
        created_at=created_at,
        is_draft=is_draft,
        base_ref_name="main",
        additions=10,
        deletions=5,
        changed_files=3,
        head_sha="abcdef123456",
        checks=checks or PRChecksSummary(),
        unresolved_threads_count=unresolved_threads_count,
        threads_has_next_page=threads_has_next_page,
    )


# =============================================================================
# Criterion 1: Tab Navigation, Keybindings, and Help
# =============================================================================


def test_tab_map_contains_github_index_and_name() -> None:
    """Opening the GitHub tab works via key '6', --tab github, or --tab 6."""
    assert TAB_NUM_MAP["6"] == "tab-github"
    assert TAB_NUM_MAP["github"] == "tab-github"
    assert CONST_DASHBOARD_DOMAINS[5] == CONST_DASHBOARD_DOMAIN_GITHUB


def test_dashboard_cli_help_lists_github_tab() -> None:
    """devops dashboard --help lists 6=github."""
    result = runner.invoke(dashboard_app, ["--help"])
    assert result.exit_code == 0
    assert "6=github" in result.output


@pytest.mark.asyncio
async def test_help_screen_documents_github_keys() -> None:
    """HelpScreen documents Enter (inspect), v and o."""
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        app.push_screen(HelpScreen())
        await pilot.pause()
        help_text = str(app.screen.query_one("#help-body", Static).content)
        assert "enter : Inspect highlighted PR" in help_text
        assert "v     : View failing check logs in Logs tab" in help_text
        assert "o     : Open PR in browser" in help_text


@pytest.mark.asyncio
async def test_dashboard_opens_github_tab_initially() -> None:
    """DashboardApp(initial_tab='tab-github') mounts with GitHub tab active."""
    app = DashboardApp(initial_tab="tab-github", refresh_interval=0)
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one(TabbedContent)
        assert tabs.active == "tab-github"
        panel = app.query_one("#panel-github", GitHubPanel)
        assert panel.domain == "github"


# =============================================================================
# Criterion 2: Queue Ordering and Failing Checks Count
# =============================================================================


def test_sort_prs_oldest_first() -> None:
    """A stubbed queue read returning #12, #7, and #9 lists them as 7, 9, 12."""
    prs = [_make_pr(12), _make_pr(7), _make_pr(9)]
    sorted_prs = sort_prs_oldest_first(prs)
    assert [p.number for p in sorted_prs] == [7, 9, 12]


def test_github_banner_shows_failing_checks_count() -> None:
    """Banner correctly counts PRs with failing checks."""
    passing_pr = _make_pr(
        1,
        checks=PRChecksSummary(
            pass_count=2, items=[PRCheckItem(name="c1", bucket=CheckBucket.PASS)]
        ),
    )
    failing_pr = _make_pr(
        2, checks=PRChecksSummary(fail=1, items=[PRCheckItem(name="c2", bucket=CheckBucket.FAIL)])
    )
    summary = GitHubSummary(total_count=2, prs=[passing_pr, failing_pr])
    banner = github_banner(summary)
    assert "2 open PRs" in banner
    assert "1 with failing checks" in banner


# =============================================================================
# Criterion 3: Inspector View (Checks, Threads, Copilot Status)
# =============================================================================


def test_github_check_rows_lists_non_passing_first() -> None:
    """Checks are listed non-passing first in inspector."""
    items = [
        PRCheckItem(name="build", bucket=CheckBucket.PASS, workflow="CI"),
        PRCheckItem(name="lint", bucket=CheckBucket.FAIL, workflow="Lint"),
        PRCheckItem(name="test", bucket=CheckBucket.PENDING, workflow="CI"),
    ]
    rows = github_check_rows(items)
    # Non-passing checks (FAIL, PENDING) come before PASS
    assert rows[0][0] == "lint"
    assert rows[0][2] == "fail"
    assert rows[1][0] == "test"
    assert rows[1][2] == "pending"
    assert rows[2][0] == "build"
    assert rows[2][2] == "pass"


def test_get_copilot_review_status_agreement() -> None:
    """get_copilot_review_status calls _detect_copilot_status and matches pr monitor."""
    with (
        patch("devops_cli.github.pr_monitor._fetch_raw_reviews", return_value=[]),
        patch(
            "devops_cli.github.pr_monitor._detect_copilot_status",
            return_value=CopilotReviewStatus(state="completed"),
        ) as mock_detect,
    ):
        status = get_copilot_review_status("owner", "repo", 42)
        assert status.state == "completed"
        mock_detect.assert_called_once()


@pytest.mark.asyncio
async def test_inspector_renders_pr_details_and_handles_error() -> None:
    """Inspector renders single PR data, threads, and handles failed reads fail-closed."""
    pr = _make_pr(
        42,
        title="Sample Feature",
        checks=PRChecksSummary(
            items=[
                PRCheckItem(
                    name="test",
                    bucket=CheckBucket.FAIL,
                    workflow="CI",
                    link="https://example.com/owner/repo/actions/runs/1/job/2",
                )
            ]
        ),
    )
    thread = ReviewThread(
        id="t1",
        is_resolved=False,
        path="src/main.py",
        line=10,
        comments=[ReviewComment(id="c1", body="LGTM", author="reviewer")],
    )
    copilot_status = CopilotReviewStatus(state="idle")

    # Mount panel inside minimal app
    app = DashboardApp(initial_tab="tab-github", refresh_interval=0)
    async with app.run_test() as pilot:
        await pilot.pause()
        target_panel = app.query_one(GitHubPanel)
        target_panel._set_inspector_data(pr, [thread], "", copilot_status)

        summary_text = str(target_panel.query_one("#github-inspector-summary", Static).render())
        assert "PR #42" in summary_text
        assert "Sample Feature" in summary_text
        assert "Copilot (as `pr monitor` reports it): idle" in summary_text

        checks_table = target_panel.query_one("#github-checks-table", DataTable)
        assert checks_table.row_count == 1

        threads_text = str(target_panel.query_one("#github-inspector-details", Static).render())
        assert "src/main.py:10 (reviewer)" in threads_text

        # Test single-PR error
        target_panel._set_inspector_error(42, "Network timeout")
        err_summary = str(target_panel.query_one("#github-inspector-summary", Static).render())
        assert "PR #42 unread: Network timeout" in err_summary
        assert target_panel.query_one("#github-checks-table", DataTable).row_count == 0


# =============================================================================
# Criterion 4: API Quota Display & Unread Behavior
# =============================================================================


def test_github_banner_shows_quota() -> None:
    """Banner shows core and GraphQL remaining/limit with time to reset."""
    quota = GitHubQuotaSummary(
        core_limit=5000,
        core_remaining=4500,
        core_reset_epoch=time.time() + 1800,  # 30m
        graphql_limit=5000,
        graphql_remaining=4900,
        graphql_reset_epoch=time.time() + 1800,
    )
    summary = GitHubSummary(total_count=1, prs=[_make_pr(1)], quota=quota)
    banner = github_banner(summary)
    assert "core 4500/5000" in banner
    assert "graphql 4900/5000" in banner
    assert "reset in 30m" in banner


def test_github_banner_shows_quota_unread_when_missing() -> None:
    """When quota read fails, banner shows 'quota unread' and queue still renders."""
    summary = GitHubSummary(total_count=1, prs=[_make_pr(1)], quota=None)
    banner = github_banner(summary)
    assert "quota unread" in banner
    rows = github_rows(summary)
    assert len(rows) == 1


# =============================================================================
# Criterion 5: Check Counts Classification
# =============================================================================


def test_classify_status_check_rollup() -> None:
    """Rollup classification with FAILURE, IN_PROGRESS and 3 SUCCESS shows fail 1, pending 1, pass 3."""
    rollup = {
        "contexts": {
            "pageInfo": {"hasNextPage": False},
            "nodes": [
                {
                    "__typename": "CheckRun",
                    "name": "lint",
                    "status": "COMPLETED",
                    "conclusion": "FAILURE",
                },
                {
                    "__typename": "CheckRun",
                    "name": "build",
                    "status": "IN_PROGRESS",
                    "conclusion": None,
                },
                {
                    "__typename": "CheckRun",
                    "name": "test1",
                    "status": "COMPLETED",
                    "conclusion": "SUCCESS",
                },
                {
                    "__typename": "CheckRun",
                    "name": "test2",
                    "status": "COMPLETED",
                    "conclusion": "SUCCESS",
                },
                {
                    "__typename": "CheckRun",
                    "name": "test3",
                    "status": "COMPLETED",
                    "conclusion": "SUCCESS",
                },
            ],
        }
    }
    summary = parse_status_check_rollup(rollup)
    assert summary.format_counts() == "fail 1, pending 1, pass 3"
    assert summary.has_failing_checks is True


def test_classify_unknown_and_expected_states_count_as_unread() -> None:
    """StatusContext EXPECTED and CheckRun COMPLETED without conclusion count as unread."""
    rollup = {
        "contexts": {
            "pageInfo": {"hasNextPage": False},
            "nodes": [
                {"__typename": "StatusContext", "context": "code-review", "state": "EXPECTED"},
                {
                    "__typename": "CheckRun",
                    "name": "security",
                    "status": "COMPLETED",
                    "conclusion": None,
                },
            ],
        }
    }
    summary = parse_status_check_rollup(rollup)
    assert summary.unread == 2
    assert summary.format_counts() == "unread 2"
    assert summary.has_failing_checks is False


def test_classify_null_rollup_shows_none() -> None:
    """A null rollup shows 'none'."""
    summary = parse_status_check_rollup(None)
    assert summary.format_counts() == "none"


def test_classify_has_next_page_shows_plus() -> None:
    """A rollup with hasNextPage displays incomplete counts with +."""
    rollup = {
        "contexts": {
            "pageInfo": {"hasNextPage": True},
            "nodes": [
                {
                    "__typename": "CheckRun",
                    "name": "ci",
                    "status": "COMPLETED",
                    "conclusion": "SUCCESS",
                },
            ],
        }
    }
    summary = parse_status_check_rollup(rollup)
    assert summary.format_counts() == "pass 1+"


# =============================================================================
# Criterion 6: Failed Queue Read & Error Banner
# =============================================================================


def test_failed_queue_read_preserves_previous_rows() -> None:
    """If GraphQL query raises GitHubOperationError, error banner appears over previous rows."""
    state = DashboardState()
    initial_summary = GitHubSummary(total_count=1, prs=[_make_pr(1)])
    state.publish(CONST_DASHBOARD_DOMAIN_GITHUB, initial_summary)

    def failing_fetcher() -> Any:
        raise GitHubOperationError("GraphQL query failed: timeout")

    snapshot = refresh_domain(
        state, CONST_DASHBOARD_DOMAIN_GITHUB, {CONST_DASHBOARD_DOMAIN_GITHUB: failing_fetcher}
    )
    assert snapshot is not None
    assert snapshot.error is not None
    assert "GitHubOperationError: GraphQL query failed: timeout" in snapshot.error
    assert snapshot.data is not None

    banner = render_banner(snapshot)
    assert "refresh failed" in banner
    rows = render_rows(snapshot)
    assert len(rows) == 1


def test_no_open_pull_requests_appears_only_with_total_count_zero() -> None:
    """'No open pull requests' appears only after successful read with totalCount 0."""
    summary = GitHubSummary(total_count=0, prs=[])
    banner = github_banner(summary)
    assert "No open pull requests" in banner


def test_truncation_banner_text() -> None:
    """If totalCount is 73 and 50 PRs come back, banner reads 'showing oldest 50 of 73'."""
    prs = [_make_pr(i) for i in range(1, 51)]
    summary = GitHubSummary(total_count=73, prs=prs)
    banner = github_banner(summary)
    assert "showing oldest 50 of 73" in banner


# =============================================================================
# Criterion 7: Repository Validation
# =============================================================================


def test_repository_validation_raises_when_not_a_github_checkout() -> None:
    """If get_repo_origin_name returns None, raises 'not a GitHub checkout' without gh calls."""
    with (
        patch("devops_cli.ui.data_providers.get_repo_origin_name", return_value=None),
        patch("devops_cli.ui.data_providers.run_gh") as mock_run_gh,
    ):
        with pytest.raises(GitHubOperationError, match="not a GitHub checkout"):
            fetch_github_status()
        mock_run_gh.assert_not_called()


# =============================================================================
# Criterion 8: Pacing Guard
# =============================================================================


def test_pacing_guard_prevents_excessive_sleep_and_never_calls_sleep() -> None:
    """When quota is 0 with reset 30m away, pacing guard raises and never calls time.sleep."""
    mock_quota = QuotaState(
        limit=5000,
        remaining=0,
        reset_epoch=time.time() + 1800,  # 30m
    )
    with (
        patch("devops_cli.github.pr_queue.get_github_rate_limiter") as mock_limiter_fn,
        patch("time.sleep", side_effect=AssertionError("time.sleep must never be called")),
    ):
        mock_limiter = MagicMock()
        mock_limiter.get_quota.return_value = mock_quota
        mock_limiter_fn.return_value = mock_limiter

        with pytest.raises(GitHubRateLimitError) as exc_info:
            check_pacing_guard("graphql", max_pacing_seconds=5.0)

        assert "exceeds limit" in str(exc_info.value)
        assert "reset at" in str(exc_info.value)


# =============================================================================
# Criterion 9: `v` Key and Log Viewing
# =============================================================================


def test_run_view_args_construction() -> None:
    """run_view_args constructs correct gh run view command arguments."""
    args = run_view_args(1234, log_failed=True, job="5678", repo="owner/repo")
    assert args == ["run", "view", "1234", "--log-failed", "--job", "5678", "--repo", "owner/repo"]


def test_fetch_workflow_run_view_masks_output() -> None:
    """fetch_workflow_run_view executes with timeout and returns masked secrets."""
    mock_proc = MagicMock(returncode=0, stdout="Job log ghp_secrettoken123\n", stderr="")
    res = fetch_workflow_run_view(123, job="456", runner=lambda *a, **kw: mock_proc)
    assert res.returncode == 0
    assert "ghp_secrettoken" not in res.stdout


@pytest.mark.asyncio
async def test_v_key_on_actions_job_starts_log_stream() -> None:
    """Pressing 'v' on check linking to /actions/runs/1/job/2 streams output to Logs tab."""
    app = DashboardApp(initial_tab="tab-github", refresh_interval=0)
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.query_one(GitHubPanel)
        check_item = PRCheckItem(
            name="test",
            bucket=CheckBucket.FAIL,
            link="https://example.com/owner/repo/actions/runs/123/job/456",
        )
        pr = _make_pr(1, checks=PRChecksSummary(items=[check_item]))
        panel._current_inspector_pr = pr
        panel._inspector_check_items = {"['test', '']": check_item}

        with (
            patch("devops_cli.ui.widgets._highlighted_key", return_value="['test', '']"),
            patch("devops_cli.ui.widgets.get_repo_origin_name", return_value="owner/repo"),
            patch("devops_cli.ui.widgets.check_pacing_guard"),
            patch(
                "devops_cli.ui.widgets.fetch_workflow_run_view",
                return_value=MagicMock(returncode=0, stdout="Build failed line\n", stderr=""),
            ),
        ):
            panel.action_view_log()
            await pilot.pause()
            tabs = app.query_one(TabbedContent)
            assert tabs.active == CONST_LOGS_TAB_ID
            log_pane = app.query_one("#log-pane", LogPane)
            assert "GitHub run 123 job 456" in log_pane.title


@pytest.mark.asyncio
async def test_v_key_on_non_actions_link_shows_notice() -> None:
    """On /runs/<id> or external link, shows notice and runs nothing."""
    app = DashboardApp(initial_tab="tab-github", refresh_interval=0)
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.query_one(GitHubPanel)
        check_item = PRCheckItem(
            name="codeql",
            bucket=CheckBucket.FAIL,
            link="https://example.com/owner/repo/runs/12345",
        )
        panel._current_inspector_pr = _make_pr(1, checks=PRChecksSummary(items=[check_item]))
        panel._inspector_check_items = {"['codeql', '']": check_item}

        with (
            patch("devops_cli.ui.widgets._highlighted_key", return_value="['codeql', '']"),
            patch("devops_cli.ui.widgets.fetch_workflow_run_view") as mock_fetch,
        ):
            panel.action_view_log()
            await pilot.pause()
            mock_fetch.assert_not_called()


# =============================================================================
# Criterion 10: `o` Key Opens PR URL
# =============================================================================


@pytest.mark.asyncio
async def test_o_key_opens_pr_url() -> None:
    """Pressing 'o' calls App.open_url with PR URL."""
    app = DashboardApp(initial_tab="tab-github", refresh_interval=0)
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.query_one(GitHubPanel)
        pr = _make_pr(42)
        panel._current_inspector_pr = pr

        with patch.object(app, "open_url") as mock_open:
            panel.action_open_url()
            mock_open.assert_called_once_with("https://example.com/owner/repo/pull/42")


@pytest.mark.asyncio
async def test_o_key_without_pr_shows_notice() -> None:
    """Pressing 'o' without PR in inspector shows notice and does nothing."""
    app = DashboardApp(initial_tab="tab-github", refresh_interval=0)
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.query_one(GitHubPanel)
        panel._current_inspector_pr = None

        with patch.object(app, "open_url") as mock_open:
            panel.action_open_url()
            mock_open.assert_not_called()


# =============================================================================
# Criterion 11: Refresh Interval and Schedule
# =============================================================================


def test_timer_refresh_schedule_registration() -> None:
    """Intervals register 5s for base domains and 60s for GitHub, or 300s when longer."""
    app5 = DashboardApp(refresh_interval=5)
    with (
        patch.object(app5, "action_refresh_data"),
        patch.object(app5, "set_interval") as mock_set_interval,
    ):
        app5.on_mount()
        # Expect two intervals: (5, _refresh_base_domains) and (60, _refresh_github)
        calls = mock_set_interval.call_args_list
        assert len(calls) == 2
        intervals = [call[0][0] for call in calls]
        assert intervals == [5, 60]

    app300 = DashboardApp(refresh_interval=300)
    with (
        patch.object(app300, "action_refresh_data"),
        patch.object(app300, "set_interval") as mock_set_interval,
    ):
        app300.on_mount()
        calls = mock_set_interval.call_args_list
        assert len(calls) == 2
        intervals = [call[0][0] for call in calls]
        assert intervals == [300, 300]

    app0 = DashboardApp(refresh_interval=0)
    with (
        patch.object(app0, "action_refresh_data"),
        patch.object(app0, "set_interval") as mock_set_interval,
    ):
        app0.on_mount()
        mock_set_interval.assert_not_called()


def test_r_key_github_cooldown() -> None:
    """Pressing 'r' within 60s shows notice; pressing after 60s refreshes GitHub."""
    app = DashboardApp(refresh_interval=0)
    with patch.object(app, "_refresh_worker") as mock_worker:
        # Initial refresh
        app.action_refresh_data()
        assert mock_worker.call_count == len(CONST_DASHBOARD_DOMAINS)
        assert app._last_github_refresh_epoch is not None
        last_epoch = app._last_github_refresh_epoch

        mock_worker.reset_mock()
        # 10s later -> GitHub should NOT refresh
        with patch("time.monotonic", return_value=last_epoch + 10.0):
            app.action_refresh_data()
            called_domains = [c[0][0] for c in mock_worker.call_args_list]
            assert CONST_DASHBOARD_DOMAIN_GITHUB not in called_domains
            assert len(called_domains) == len(CONST_DASHBOARD_DOMAINS) - 1

        mock_worker.reset_mock()
        # 61s later -> GitHub SHOULD refresh
        with patch("time.monotonic", return_value=last_epoch + 61.0):
            app.action_refresh_data()
            called_domains = [c[0][0] for c in mock_worker.call_args_list]
            assert CONST_DASHBOARD_DOMAIN_GITHUB in called_domains
            assert len(called_domains) == len(CONST_DASHBOARD_DOMAINS)
