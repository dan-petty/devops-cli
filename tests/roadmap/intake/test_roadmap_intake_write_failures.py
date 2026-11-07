"""How a failed write, a rate limit or an unread quota ends an intake round (#1335)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from typing import Any

import pytest

from devops_cli.exceptions.git import (
    GitHubOperationError,
    GitHubRateLimitError,
    GitHubUnauthenticatedError,
    GitHubUnreadError,
)
from devops_cli.exceptions.roadmap import RoadmapIntakeError
from devops_cli.github.rate_limiter import run_gh
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from devops_cli.roadmap.stores.store import (
    install_roadmap_store,
)
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_intake import REPO, FakeModel, Roadmap, labels_of


class GhLabelStore(InMemoryRoadmapStore):
    """The in-memory roadmap whose label write goes through the real `run_gh`, as the GitHub
    store's does, so each write waits its turn on the identity's ledger."""

    def label_issue(self, number: int, label: str) -> None:
        run_gh(["api", "--method", "POST", f"repos/{REPO}/issues/{number}/labels"])


# ── Resume and idempotence ────────────────────────────────────────────────────


def test_a_run_that_stops_after_the_status_write_is_finished_by_the_next_run(
    roadmap: Roadmap,
) -> None:
    """A run that wrote Status and stopped leaves a candidate: the next run decides it again,
    writes only what it holds no label for, and leaves one reason comment."""
    number = roadmap.issue("feat: resumable")
    roadmap.store.fail_write(write="set_field", applied=True)
    with pytest.raises(
        RoadmapIntakeError,
        match=f"#{number} \\(GitHubOperationError: HTTP 502 after the write applied\\)",
    ):
        roadmap.run(FakeModel())
    stopped = roadmap.fields(number)
    writes = roadmap.run(FakeModel())
    assert (
        stopped,
        roadmap.fields(number),
        len(roadmap.comments(number)),
        labels_of(roadmap, number),
        [(w.operation, w.key) for w in writes],
    ) == (
        ("New", None, None, None, None),
        ("New", "P2-Medium", "Medium", "Low", None),
        1,
        ("type/feature",),
        [
            ("set_field", "Value"),
            ("set_field", "Effort"),
            ("comment", None),
            ("set_field", "Priority"),
        ],
    )


def test_a_candidate_whose_write_fails_is_named_and_the_others_are_still_placed(
    roadmap: Roadmap,
) -> None:
    """GitHub refusing one issue's label write stops only that issue; the round reports it
    (#1443)."""
    first, refused, last = (roadmap.issue(f"feat: candidate {n}") for n in range(3))
    placed = ("New", "P2-Medium", "Medium", "Low", None)
    roadmap.store.fail_write(
        write="label_issue",
        item=refused,
        error=GitHubOperationError("HTTP 502: Bad Gateway", operation="roadmap.write"),
    )
    with pytest.raises(RoadmapIntakeError) as raised:
        roadmap.run(FakeModel())
    assert (
        raised.value.failed_items,
        f"#{refused} (GitHubOperationError: HTTP 502: Bad Gateway)" in str(raised.value),
        roadmap.fields(first),
        roadmap.fields(last),
        roadmap.store.item(refused),
    ) == ((refused,), True, placed, placed, None)


@pytest.mark.parametrize(
    "refusal",
    [
        GitHubRateLimitError("rate limit exceeded", operation="roadmap.write"),
        GitHubUnauthenticatedError(
            "gh has no GitHub login that GitHub accepts", operation="refresh_quota"
        ),
    ],
    ids=["rate-limit", "token-refused"],
)
def test_a_rate_limit_or_a_refused_token_stops_the_round_with_no_further_writes(
    roadmap: Roadmap, refusal: GitHubOperationError
) -> None:
    """Every later write would be refused too, so the round stops at the first (#1400): a rate
    limit or a token GitHub refuses (#983)."""
    roadmap.issue("feat: candidate 0")
    second = roadmap.issue("feat: candidate 1")
    roadmap.store.fail_write(write="label_issue", error=refusal)
    with pytest.raises(type(refusal)) as raised:
        roadmap.run(FakeModel())
    assert raised.value is refusal
    assert (roadmap.store.writes, roadmap.store.item(second), labels_of(roadmap, second)) == (
        ["label_issue"],
        None,
        (),
    )


def test_a_quota_that_could_not_be_read_skips_the_candidate_and_writes_the_next(
    roadmap: Roadmap,
) -> None:
    """An unread quota may be an outage that passes before the next candidate, so it skips the
    candidate, names it, and writes the next (#983)."""
    first, second = (roadmap.issue(f"feat: candidate {n}") for n in range(2))
    roadmap.store.fail_write(
        write="label_issue",
        item=first,
        error=GitHubUnreadError(
            "Failed to refresh rate limits from GitHub API: HTTP 502: Bad Gateway",
            operation="refresh_quota",
        ),
    )
    with pytest.raises(RoadmapIntakeError) as raised:
        roadmap.run(FakeModel())
    assert (raised.value.failed_items, roadmap.store.item(second) is not None) == ((first,), True)


@pytest.mark.parametrize(
    ("refused", "error"),
    [
        pytest.param("gh: Bad credentials (HTTP 401)", GitHubUnauthenticatedError, id="401"),
        pytest.param(
            "gh: You have exceeded a secondary rate limit. (HTTP 403)",
            GitHubRateLimitError,
            id="rate-limited",
        ),
    ],
)
def test_a_quota_refresh_github_refuses_stops_the_round_after_one_refresh(
    process_fake: ProcessFake, clock: ClockFake, refused: str, error: type[GitHubOperationError]
) -> None:
    """Each write goes through the real `run_gh`, whose ledger has no quota yet, and `gh api
    rate_limit` is refused: a refused token or a rate limit stops the round at the first
    candidate, so the refresh runs once (#983)."""
    process_fake.answer(("gh", "api", "rate_limit"), ProcessAnswer(returncode=1, stderr=refused))
    gh_roadmap = Roadmap(GhLabelStore())
    gh_roadmap.issue("feat: candidate 0")
    second = gh_roadmap.issue("feat: candidate 1")
    with pytest.raises(GitHubOperationError) as raised:
        gh_roadmap.run(FakeModel())
    assert (
        type(raised.value),
        [list(call.argv) for call in process_fake.calls],
        gh_roadmap.store.item(second),
    ) == (error, [["gh", "api", "rate_limit"]], None)


def test_a_quota_refresh_that_times_out_ends_the_plan_with_its_error_and_no_traceback(
    fake_model: FakeModel, process_fake: ProcessFake, cli: Callable[..., Any]
) -> None:
    """2026-10-18: `gh api rate_limit` ran past its timeout while intake read GitHub, and
    `devops roadmap intake --plan` ended in a `TimeoutExpired` traceback. The read of every
    issue goes through the real ledger here, with gh faked: the plan names the timed-out
    refresh and exits 1 (#983)."""
    install_roadmap_store(lambda repo, **_: GitHubRoadmapStore(repo))
    timed_out = subprocess.TimeoutExpired(["gh", "api", "rate_limit"], 10.0)
    process_fake.answer(("gh", "api", "rate_limit"), ProcessAnswer(side_effect=timed_out))
    result = cli("roadmap", "intake", "--repo", REPO, "--plan")
    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        type(result.exception),
        "Could not plan intake: Failed to refresh rate limits from GitHub API: gh api rate_limit "
        "timed out after 10 seconds" in output,
        "Traceback" in result.output,
        fake_model.requests,
    ) == (1, SystemExit, True, False, [])
