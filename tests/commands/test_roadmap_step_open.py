"""`devops roadmap step open`: command tests for roadmap step open (#5020)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pytest

from tests.support.fakes.github import github_json
from tests.support.roadmap_stage import STAGE_REPO, seed_stageable

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

pytestmark = pytest.mark.usefixtures("keyring_store")

Cli = Callable[..., Any]
BRANCH = "feat/test-open-step"
TITLE = "feat: open step test"


def _open(cli: Cli, *args: str) -> Any:
    return cli("roadmap", "step", "open", "--repo", STAGE_REPO, *args)


def test_open_cmd_requires_head_and_title(cli: Cli) -> None:
    result = _open(cli)
    assert result.exit_code != 0
    assert "Pass --head" in result.output

    result2 = _open(cli, "--head", BRANCH)
    assert result2.exit_code != 0
    assert "Pass --title" in result2.output


def test_open_cmd_creates_pr_and_prints_json_line(
    cli: Cli,
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
) -> None:
    number = seed_stageable(roadmap_store)
    roadmap_store.seed_file(
        ".github/labels.yml",
        "labels:\n  - name: type/feature\n  - name: scope/open\n",
    )
    # No open PR exists
    github_api.route(
        "GET",
        f"/repos/{STAGE_REPO}/pulls?head=example:{BRANCH}&state=open",
        github_json([]),
    )
    # Draft PR created
    github_api.route(
        "POST",
        f"/repos/{STAGE_REPO}/pulls",
        github_json(
            {
                "number": 101,
                "title": TITLE,
                "body": "Body text",
                "draft": True,
                "html_url": f"https://github.com/{STAGE_REPO}/pull/101",
            },
            status=201,
        ),
    )

    result = _open(
        cli,
        "--item",
        str(number),
        "--head",
        BRANCH,
        "--base",
        "main",
        "--title",
        TITLE,
        "--body",
        "Body text",
        "--kind",
        "plan",
    )

    assert result.exit_code == 0, result.output
    # Parse json line from stdout
    line = [entry for entry in result.output.strip().splitlines() if "open" in entry][-1]
    parsed = json.loads(line)
    assert parsed["job"] == "open"
    assert parsed["number"] == 101
    assert parsed["status"] == "created"


def test_open_cmd_dry_run(
    cli: Cli,
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
) -> None:
    number = seed_stageable(roadmap_store)
    result = _open(
        cli,
        "--item",
        str(number),
        "--head",
        BRANCH,
        "--base",
        "main",
        "--title",
        TITLE,
        "--dry-run",
    )

    assert result.exit_code == 0, result.output
    line = [entry for entry in result.output.strip().splitlines() if "open" in entry][-1]
    parsed = json.loads(line)
    assert parsed["job"] == "open"
    assert parsed["number"] == 0
    assert parsed["status"] == "created"
    assert github_api.requested == []
