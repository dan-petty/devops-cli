"""`devops roadmap step scaffold`: command tests for roadmap step scaffold (#5499)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pytest

from tests.support.fakes.github import github_json
from tests.support.roadmap_stage import STAGE_REPO, StageRepo, seed_stageable

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

pytestmark = pytest.mark.usefixtures("keyring_store")

Cli = Callable[..., Any]
BRANCH = "fix/1-the-job-drops-a-comment"


def _scaffold(cli: Cli, repo: StageRepo, *args: str) -> Any:
    return cli(
        "roadmap", "step", "scaffold", "--repo", STAGE_REPO, "--source", str(repo.clone), *args
    )


def test_scaffold_cmd_creates_ref_and_prints_json_line(
    cli: Cli,
    roadmap_store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    github_api: GitHubApiFake,
) -> None:
    number = seed_stageable(roadmap_store)
    main_sha = stage_repo.origin_git("rev-parse", "main")
    github_api.route(
        "POST",
        f"/repos/{STAGE_REPO}/git/refs",
        github_json({"ref": f"refs/heads/{BRANCH}", "object": {"sha": main_sha}}, status=201),
    )

    result = _scaffold(cli, stage_repo, "--item", str(number), "--kind", "plan")

    assert result.exit_code == 0, result.output
    # Parse json line from output
    line = [entry for entry in result.output.strip().splitlines() if "scaffold" in entry][-1]
    parsed = json.loads(line)
    assert parsed["job"] == "scaffold"
    assert parsed["result"] == "created"
    assert parsed["item"] == number
    assert parsed["branch"] == BRANCH


def test_scaffold_cmd_held_exits_zero_with_json_line(
    cli: Cli,
    roadmap_store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    github_api: GitHubApiFake,
) -> None:
    number = seed_stageable(roadmap_store)
    stage_repo.push_branch(BRANCH, author="Person")

    result = _scaffold(cli, stage_repo, "--item", str(number), "--kind", "plan")

    assert result.exit_code == 0, result.output
    line = [entry for entry in result.output.strip().splitlines() if "scaffold" in entry][-1]
    parsed = json.loads(line)
    assert parsed["job"] == "scaffold"
    assert parsed["result"] == "held"
    assert "holder" in parsed


def test_scaffold_cmd_dry_run_sends_no_requests(
    cli: Cli,
    roadmap_store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    github_api: GitHubApiFake,
) -> None:
    number = seed_stageable(roadmap_store)

    result = _scaffold(cli, stage_repo, "--item", str(number), "--kind", "plan", "--dry-run")

    assert result.exit_code == 0, result.output
    assert github_api.requested == []


def test_scaffold_cmd_missing_item_exits_one(cli: Cli, stage_repo: StageRepo) -> None:
    result = _scaffold(cli, stage_repo, "--kind", "plan")
    assert result.exit_code == 1
    assert "Pass --item" in result.output


def test_scaffold_cmd_invalid_repo_exits_one(cli: Cli, stage_repo: StageRepo) -> None:
    result = _scaffold(cli, stage_repo, "--item", "1", "--repo", "invalid")
    assert result.exit_code == 1
    assert "Cannot resolve the repository" in result.output


def test_scaffold_cmd_devops_cli_error_exits_one(
    cli: Cli, stage_repo: StageRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    from devops_cli.exceptions import DevOpsCLIError
    from devops_cli.roadmap.steps import scaffold as scaffold_mod

    def _fail(*args: Any, **kwargs: Any) -> Any:
        raise DevOpsCLIError("Simulated failure")

    monkeypatch.setattr(scaffold_mod, "run_scaffold", _fail)
    result = _scaffold(cli, stage_repo, "--item", "1", "--kind", "plan")
    assert result.exit_code == 1
    assert "Could not scaffold item" in result.output
