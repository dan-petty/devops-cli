"""The deliveries of the webhooks of a repository that got no 2xx answer, as GitHub records them
(#5017).

A refusal at the Cloudflare edge never gets to the webhook route, so only GitHub's record of each
delivery shows it. GitHub is faked at the `gh` process edge, and the gauge is read from the
Service's metrics. A read counts from the last good read of the repository and follows the pages
back to it, so no failed delivery between two reads of the metrics row is lost (#6012).
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any

import pytest

from devops_cli.config.constants import CONST_SERVICE_METRIC_WEBHOOK_DELIVERY_FAILURES
from devops_cli.config.defaults import (
    DEFAULT_SERVICE_HOOK_DELIVERY_MAX_PAGES,
    DEFAULT_SERVICE_HOOK_DELIVERY_PAGE_SIZE,
)
from devops_cli.exceptions import GitHubOperationError
from devops_cli.github.hook_deliveries import report_delivery_failures
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from tests.support.fakes.github_repository import GitHubFake
from tests.support.fakes.process import ProcessFake
from tests.support.roadmap_run import NOW, REPO

pytestmark = pytest.mark.usefixtures("keyring_store")

HOOK = 692250036
OTHER_HOOK = 692250037
REFUSED = "gh: Resource not accessible by integration (HTTP 403)"
NO_DELIVERY = (0, "[]")


@pytest.fixture(autouse=True)
def no_gauge() -> None:
    """Each test starts with no series of the gauge, as a new process does."""
    GLOBAL_METRICS.clear_metric(CONST_SERVICE_METRIC_WEBHOOK_DELIVERY_FAILURES)


@pytest.fixture
def github(process_fake: ProcessFake) -> GitHubFake:
    """The repository at the `gh` process edge."""
    fake = GitHubFake(REPO)
    fake.install(process_fake)
    return fake


def _delivery(minutes_ago: float, code: int) -> dict[str, Any]:
    """One delivery as GitHub lists it, `minutes_ago` minutes before `NOW`."""
    at = NOW - timedelta(minutes=minutes_ago)
    return {
        "id": 3853613591598989312,
        "guid": "4c086790-de82-11f1-89a0-9e9c9debeac0",
        "delivered_at": at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "redelivery": False,
        "duration": 0.08,
        "status": "Invalid HTTP Response: 403" if code == 403 else "OK",
        "status_code": code,
        "event": "issues",
        "action": "labeled",
    }


def _failures(code: str) -> float:
    """The gauge of the repository and `code`."""
    return GLOBAL_METRICS.get_gauge_value(
        CONST_SERVICE_METRIC_WEBHOOK_DELIVERY_FAILURES, labels={"repo": REPO, "code": code}
    )


def _deliveries_path(hook: int, offset: int = 0) -> str:
    """The path of the page of the failed deliveries of `hook` from `offset` on, newest first."""
    path = (
        f"repos/{REPO}/hooks/{hook}/deliveries"
        f"?per_page={DEFAULT_SERVICE_HOOK_DELIVERY_PAGE_SIZE}&status=failure"
    )
    return path if offset == 0 else f"{path}&cursor=v1_{offset}"


def test_two_403_answers_in_the_window_set_the_gauge_to_2(github: GitHubFake) -> None:
    """The first read of a process counts the last 15 minutes. A page with two 403 answers of
    that time sets the gauge of code 403 to 2. A 202 answer and a 403 answer from before the
    window do not count. The read sends one request for the hooks and one for the page of the
    failed deliveries of the hook."""
    github.seed_hook(
        HOOK,
        [_delivery(1, 403), _delivery(2, 202), _delivery(5, 403), _delivery(20, 403)],
    )

    failed = report_delivery_failures(REPO, NOW)

    assert (dict(failed), _failures("403"), _failures("202"), github.hook_calls()) == (
        {"403": 2},
        2.0,
        0.0,
        [f"repos/{REPO}/hooks", _deliveries_path(HOOK)],
    )


def test_the_gauge_adds_the_active_hooks_by_code_and_reads_no_inactive_hook(
    github: GitHubFake,
) -> None:
    """Each active hook adds its failed deliveries under their code, a 502 and a 504 included.
    An inactive hook gets no request."""
    github.seed_hook(HOOK, [_delivery(1, 403), _delivery(3, 502), _delivery(4, 200)])
    github.seed_hook(OTHER_HOOK, [_delivery(2, 403), _delivery(6, 504)])
    github.seed_hook(1, [_delivery(1, 403)], active=False)

    failed = report_delivery_failures(REPO, NOW)

    assert (
        dict(failed),
        [_failures(code) for code in ("403", "502", "504")],
        github.hook_calls(),
    ) == (
        {"403": 2, "502": 1, "504": 1},
        [2.0, 1.0, 1.0],
        [f"repos/{REPO}/hooks", _deliveries_path(HOOK), _deliveries_path(OTHER_HOOK)],
    )


def test_a_code_that_the_next_read_does_not_find_is_set_to_0(github: GitHubFake) -> None:
    """The metrics hold no call that removes a series, so a code that the last read set and the
    next read does not find goes to 0, and the alert ends."""
    github.seed_hook(HOOK, [_delivery(1, 403), _delivery(2, 403)])
    report_delivery_failures(REPO, NOW)
    before = _failures("403")
    github.seed_hook(HOOK, [_delivery(-12, 202), _delivery(3, 202)])

    failed = report_delivery_failures(REPO, NOW + timedelta(minutes=13))

    assert (before, dict(failed), _failures("403")) == (2.0, {}, 0.0)


def test_a_read_counts_each_failed_delivery_since_the_last_read_over_two_pages(
    github: GitHubFake,
) -> None:
    """The metrics row runs when a trigger comes after its interval, so 30 minutes can pass
    between two reads: longer than the window of 15 minutes. A burst of 100 failed deliveries in
    the last 10 minutes fills one page. The read counts each failed delivery since the last good
    read: it follows the link to the next page until a delivery is older than that read, and
    asks for no page after it. A delivery from before the last read is not counted again
    (#6012)."""
    burst = [_delivery(minute / 10, 403) for minute in range(100)]
    older = [_delivery(22, 502), _delivery(29, 403), _delivery(31, 403), _delivery(40, 403)]
    github.seed_hook(HOOK, [*burst, _delivery(21, 202), *older])
    github.deliveries_answers = [NO_DELIVERY]
    report_delivery_failures(REPO, NOW - timedelta(minutes=30))

    failed = report_delivery_failures(REPO, NOW)

    assert (dict(failed), _failures("403"), _failures("502"), github.hook_calls()[2:]) == (
        {"403": 101, "502": 1},
        101.0,
        1.0,
        [f"repos/{REPO}/hooks", _deliveries_path(HOOK), _deliveries_path(HOOK, 100)],
    )


def test_a_read_that_fails_keeps_the_start_of_the_next_read(github: GitHubFake) -> None:
    """A read that fails is no good read: the next read still counts from the last good one, so
    the failed deliveries of the time of the failed read are counted then (#6012)."""
    github.seed_hook(HOOK, [_delivery(1, 202), _delivery(25, 403), _delivery(45, 403)])
    github.deliveries_answers = [NO_DELIVERY, (1, REFUSED)]
    report_delivery_failures(REPO, NOW - timedelta(minutes=40))
    with pytest.raises(GitHubOperationError, match="not accessible by integration"):
        report_delivery_failures(REPO, NOW - timedelta(minutes=20))

    failed = report_delivery_failures(REPO, NOW)

    assert dict(failed) == {"403": 1}


def test_a_long_gap_reads_at_most_the_page_limit_and_says_so(
    github: GitHubFake, caplog: pytest.LogCaptureFixture
) -> None:
    """A row that did not run for hours reads at most `DEFAULT_SERVICE_HOOK_DELIVERY_MAX_PAGES`
    pages of a hook, so the read costs a bounded number of requests, and a warning names the
    hook whose older failed deliveries the read leaves out (#6012)."""
    pages = DEFAULT_SERVICE_HOOK_DELIVERY_MAX_PAGES
    size = DEFAULT_SERVICE_HOOK_DELIVERY_PAGE_SIZE
    github.seed_hook(HOOK, [_delivery(1 + item / 10, 403) for item in range(size * (pages + 1))])
    github.deliveries_answers = [NO_DELIVERY]
    report_delivery_failures(REPO, NOW - timedelta(days=1))

    with caplog.at_level(logging.WARNING):
        failed = report_delivery_failures(REPO, NOW)

    assert (
        dict(failed),
        len(github.hook_calls()[2:]),
        [record.getMessage() for record in caplog.records if str(HOOK) in record.getMessage()],
    ) == (
        {"403": size * pages},
        1 + pages,
        [
            f"The read of the failed deliveries of hook {HOOK} of {REPO} stopped after {pages} "
            "pages: older failed deliveries are not counted."
        ],
    )


def test_a_next_page_on_another_host_raises_and_is_not_read(github: GitHubFake) -> None:
    """The read sends the token to GitHub's API only: a page that links its next page on another
    host fails the read, and gh gets no request for that page (#6012)."""
    github.seed_hook(HOOK)
    github.deliveries_answers = [(0, json.dumps([_delivery(1, 403)]))]
    github.deliveries_answer_link = "https://example.com/repos/next?cursor=v1_1"

    with pytest.raises(GitHubOperationError, match="another origin"):
        report_delivery_failures(REPO, NOW)

    assert github.hook_calls() == [f"repos/{REPO}/hooks", _deliveries_path(HOOK)]


def test_a_refused_read_of_the_hooks_raises_and_keeps_the_gauge(github: GitHubFake) -> None:
    """A token with no Webhooks permission gets 403 for the hooks. The read raises, so the
    metrics row fails and shows it, and the gauge keeps the value of the last read."""
    github.seed_hook(HOOK, [_delivery(1, 403), _delivery(2, 403)])
    report_delivery_failures(REPO, NOW)
    github.hooks_answer = (1, REFUSED)

    with pytest.raises(GitHubOperationError, match="not accessible by integration"):
        report_delivery_failures(REPO, NOW + timedelta(minutes=13))

    assert _failures("403") == 2.0
