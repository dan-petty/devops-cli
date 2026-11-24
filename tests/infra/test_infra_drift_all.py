"""Tests for `devops infra drift --all` (#5129).

Acceptance criteria:
- The command runs the drift of each repo in `infra.repos` whose agent access level is `plan` or higher.
- The command runs no drift for a repo at `none`.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.infra.drift import DRIFT_MARKER_PREFIX
from tests.support.fakes.github import GitHubApiFake, github_json, quota_headers
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.infra import (
    answer_default_branch,
    answer_runner,
    in_export,
    recorded_read,
)

PLAN_REPO = "example-org/infra-plan"
NONE_REPO = "example-org/infra-none"
_RUNNER = "ansible-runner"
_GALAXY = "ansible-galaxy"


@pytest.fixture(autouse=True)
def _seed_quota() -> None:
    """Seed rate limit quota so GitHub session pacing never falls back to gh CLI."""
    limiter = get_github_rate_limiter()
    limiter.update_quota("search", remaining=30, limit=30, reset_epoch=time.time() + 600.0)
    limiter.update_quota("core", remaining=5000, limit=5000, reset_epoch=time.time() + 600.0)


@pytest.fixture
def two_repos_ready(
    infra_repo: Path,
    ansible_installed: Path,
    ssh_key_dir: Path,
    process_fake: ProcessFake,
    config: Callable[..., Path],
) -> Path:
    """Settings fixture holding one repo at plan and one at none."""
    answer_default_branch(process_fake, infra_repo)
    listing = json.dumps(recorded_read("inventory", infra_repo))
    process_fake.answer(
        [str(ansible_installed / "ansible-inventory")], in_export(listing, infra_repo)
    )
    process_fake.answer([str(ansible_installed / _GALAXY)], ProcessAnswer())

    return config(
        infra={
            "repos": [
                {"repo": PLAN_REPO, "path": str(infra_repo), "agent_access": "plan"},
                {"repo": NONE_REPO, "path": str(infra_repo), "agent_access": "none"},
            ]
        },
        ssh={"key_dir": str(ssh_key_dir)},
    )


def test_plan_repo_drifts_and_none_repo_does_not(
    cli: Callable[..., Any],
    two_repos_ready: Path,
    ansible_installed: Path,
    process_fake: ProcessFake,
    github_api: GitHubApiFake,
    person_caller: None,
) -> None:
    """The command runs drift once for the plan repo and no time for the none repo."""
    answer_runner(process_fake, ansible_installed, "agent")
    search_payload = {"total_count": 0, "incomplete_results": False, "items": []}
    quota = quota_headers(30, resource="search", limit=30)
    github_api.route(
        "GET",
        f"/search/issues?q=%22{DRIFT_MARKER_PREFIX}%22+in%3Abody+is%3Aissue+repo%3A{PLAN_REPO.replace('/', '%2F')}&per_page=100&page=1",
        github_json(search_payload, headers=quota),
    )
    github_api.route("POST", f"/repos/{PLAN_REPO}/issues", github_json({"number": 10}, status=201))

    result = cli("infra", "drift", "--all")

    assert result.exit_code == 2, result.output
    assert PLAN_REPO in result.output
    assert NONE_REPO not in result.output


def test_drift_all_and_repo_are_mutually_exclusive(
    cli: Callable[..., Any],
    two_repos_ready: Path,
) -> None:
    """Passing both an infra repo and --all is refused."""
    result = cli("infra", "drift", PLAN_REPO, "--all")
    assert result.exit_code != 0
    assert "Give an infra repo or --all, not both." in result.output
