"""The deliveries of the webhooks of a repository that got no 2xx answer, as GitHub records them
(#5017).

A refusal at the Cloudflare edge never gets to the webhook route, so only GitHub's record of each
delivery shows it. GitHub is faked at the `gh` process edge, and the gauge is read from the
Service's metrics.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest

from devops_cli.config.constants import CONST_SERVICE_METRIC_WEBHOOK_DELIVERY_FAILURES
from devops_cli.config.defaults import (
    DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES,
    DEFAULT_SERVICE_HOOK_DELIVERY_PAGE_SIZE,
    DEFAULT_SERVICE_HOOK_DELIVERY_WINDOW_MINUTES,
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


def _deliveries_path(hook: int) -> str:
    return (
        f"repos/{REPO}/hooks/{hook}/deliveries?per_page={DEFAULT_SERVICE_HOOK_DELIVERY_PAGE_SIZE}"
    )


def test_two_403_answers_in_the_window_set_the_gauge_to_2(github: GitHubFake) -> None:
    """A page with two 403 answers of the last 15 minutes sets the gauge of code 403 to 2. A 202
    answer and a 403 answer from before the window do not count. The read sends one request for
    the hooks and one for the newest page of deliveries of the hook."""
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
    github.seed_hook(HOOK, [_delivery(1, 202)])

    failed = report_delivery_failures(REPO, NOW + timedelta(minutes=13))

    assert (before, dict(failed), _failures("403")) == (2.0, {}, 0.0)


def test_a_refused_read_of_the_hooks_raises_and_keeps_the_gauge(github: GitHubFake) -> None:
    """A token with no Webhooks permission gets 403 for the hooks. The read raises, so the
    metrics row fails and shows it, and the gauge keeps the value of the last read."""
    github.seed_hook(HOOK, [_delivery(1, 403), _delivery(2, 403)])
    report_delivery_failures(REPO, NOW)
    github.hooks_answer = (1, REFUSED)

    with pytest.raises(GitHubOperationError, match="not accessible by integration"):
        report_delivery_failures(REPO, NOW + timedelta(minutes=13))

    assert _failures("403") == 2.0


def test_the_window_holds_each_delivery_between_two_metrics_rounds() -> None:
    """The metrics row runs each `DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES`, so a window that is
    longer reads each delivery at least once."""
    assert DEFAULT_SERVICE_HOOK_DELIVERY_WINDOW_MINUTES > DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES
