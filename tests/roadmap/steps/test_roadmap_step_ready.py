"""Tests for devops_cli.roadmap.steps.ready: draft readiness and mark_ready wrapper (#5021)."""

from __future__ import annotations

import json
import subprocess
from typing import Any

import pytest

from devops_cli.exceptions import RoadmapImplementError
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

draft_readiness: Any = None
mark_ready: Any = None
try:
    from devops_cli.roadmap.steps.ready import draft_readiness as loaded_draft_readiness
    from devops_cli.roadmap.steps.ready import mark_ready as loaded_mark_ready

    draft_readiness = loaded_draft_readiness
    mark_ready = loaded_mark_ready
except ImportError:
    pass

pytestmark = pytest.mark.usefixtures("keyring_store")


@pytest.fixture(autouse=True)
def _check_module_available() -> None:
    if mark_ready is None:
        pytest.fail("devops_cli.roadmap.steps.ready is not implemented on base branch")


class _Ready:
    """The `gh pr ready` calls that the fake `gh` receives, and the pull requests it refuses."""

    def __init__(self, gh: ProcessFake) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.refused: set[str] = set()
        self.head_sha: str = "1234567890ab"
        gh.answer(
            lambda call: tuple(call.argv[1:3]) == ("pr", "ready"),
            ProcessAnswer(side_effect=self),
        )
        gh.answer(
            lambda call: len(call.argv) > 2 and call.argv[1] == "api" and "/pulls/" in call.argv[2],
            ProcessAnswer(side_effect=self._pr_details),
        )

    def _pr_details(self, call: ProcessCall) -> subprocess.CompletedProcess[str]:
        payload = {"head": {"sha": self.head_sha}}
        return subprocess.CompletedProcess(call.argv, 0, stdout=json.dumps(payload), stderr="")

    def __call__(self, call: ProcessCall) -> subprocess.CompletedProcess[str]:
        self.calls.append(tuple(call.argv[1:]))
        code = 1 if call.argv[3] in self.refused else 0
        stderr = "GraphQL: pull request is locked" if code else ""
        return subprocess.CompletedProcess(call.argv, code, stdout="", stderr=stderr)


@pytest.fixture
def api_and_ready(
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
) -> tuple[GitHubApiFake, _Ready]:
    api, gh = github_api_and_gh
    return api, _Ready(gh)


def test_mark_ready_calls_gh_pr_ready(
    api_and_ready: tuple[GitHubApiFake, _Ready],
) -> None:
    """When the remote head equals expected_head, mark_ready calls gh pr ready."""
    api, ready = api_and_ready
    ready.head_sha = "1234567890ab"
    payload = {
        "state": "open",
        "draft": True,
        "merged": False,
        "head": {"sha": "1234567890ab"},
    }
    api.route("GET", "/repos/owner/repo/pulls/42", github_json(payload))

    mark_ready("owner/repo", 42, expected_head="1234567890ab")

    assert len(ready.calls) == 1
    assert ready.calls[0] == ("pr", "ready", "42", "--repo", "owner/repo")


def test_mark_ready_refuses_when_head_moved(
    api_and_ready: tuple[GitHubApiFake, _Ready],
) -> None:
    """When the remote head does not match expected_head, mark_ready raises without calling gh."""
    api, ready = api_and_ready
    ready.head_sha = "diffhead1234"
    payload = {
        "state": "open",
        "draft": True,
        "merged": False,
        "head": {"sha": "diffhead1234"},
    }
    api.route("GET", "/repos/owner/repo/pulls/42", github_json(payload))

    with pytest.raises(RoadmapImplementError, match="head moved"):
        mark_ready("owner/repo", 42, expected_head="orighead5678")

    assert len(ready.calls) == 0


def test_mark_ready_raises_when_gh_fails(
    api_and_ready: tuple[GitHubApiFake, _Ready],
) -> None:
    """When gh pr ready fails, mark_ready raises RoadmapImplementError."""
    api, ready = api_and_ready
    ready.head_sha = "1234567890ab"
    ready.refused.add("42")
    payload = {
        "state": "open",
        "draft": True,
        "merged": False,
        "head": {"sha": "1234567890ab"},
    }
    api.route("GET", "/repos/owner/repo/pulls/42", github_json(payload))

    with pytest.raises(RoadmapImplementError, match="pull request is locked"):
        mark_ready("owner/repo", 42, expected_head="1234567890ab")


def test_mark_ready_without_expected_head_calls_gh_pr_ready(
    api_and_ready: tuple[GitHubApiFake, _Ready],
) -> None:
    """When expected_head is None, mark_ready calls gh pr ready directly."""
    _api, ready = api_and_ready
    mark_ready("owner/repo", 42)
    assert len(ready.calls) == 1
    assert ready.calls[0] == ("pr", "ready", "42", "--repo", "owner/repo")


def test_draft_readiness_delegates_to_implement_pull() -> None:
    """draft_readiness evaluates draft readiness through implement_pull."""
    from devops_cli.github.client import PullStatus
    from devops_cli.roadmap.implement.implement_pull import Answer, Draft, DraftKind

    pull = PullStatus(state="open", draft=True)
    draft = Draft(kind=DraftKind.STAGE_PLAN, pull=pull)
    result = draft_readiness(draft)
    assert result.answer is Answer.READY
