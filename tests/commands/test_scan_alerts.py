"""`devops scan alerts` files one issue for each open `Trivy-config` alert group that has none
(#4401). The groups and the issue text are tested in `tests/security/test_alert_filer.py`. GitHub
is faked at the HTTP edge.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from tests.support.fakes.github import GitHubApiFake, github_json

_REPO = "owner/repo"


def _raw(number: int, rule: str, path: str, severity: str) -> dict[str, Any]:
    return {
        "number": number,
        "tool": {"name": "Trivy-config"},
        "rule": {"id": rule, "security_severity_level": severity},
        "most_recent_instance": {"location": {"path": path}},
    }


@pytest.fixture
def api(github_api: GitHubApiFake) -> GitHubApiFake:
    """Three alerts of three groups, and no open issue."""
    alerts = [
        _raw(1, "AZU-0041", "tf/azure/main.tf", "critical"),
        _raw(2, "DS-0002", ".devcontainer/Dockerfile", "high"),
        _raw(3, "KSV-0001", "k8s/a.yaml", "medium"),
    ]
    github_api.route(
        "GET",
        f"/repos/{_REPO}/code-scanning/alerts?state=open&tool_name=Trivy-config&per_page=100",
        github_json(alerts),
    )
    github_api.route("GET", f"/repos/{_REPO}/issues?state=open&per_page=100", github_json([]))
    github_api.route("POST", f"/repos/{_REPO}/issues", github_json({"number": 60}, status=201))
    return github_api


def _writes(api: GitHubApiFake) -> int:
    return len([r for r in api.sent if r.method == "POST"])


def test_alerts_files_each_group_and_says_which_issue_it_filed(
    cli: Callable[..., Any], api: GitHubApiFake
) -> None:
    result = cli("scan", "alerts", "--repo", _REPO)

    output = " ".join(result.output.split())
    assert (result.exit_code, _writes(api)) == (0, 3)
    assert "Filed #60: fix(security): judge Trivy-config AZU-0041 in tf/azure/main.tf" in output


def test_alerts_names_the_groups_that_the_limit_leaves_for_the_next_run(
    cli: Callable[..., Any], api: GitHubApiFake
) -> None:
    result = cli("scan", "alerts", "--repo", _REPO, "--limit", "1")

    output = " ".join(result.output.split())
    assert (result.exit_code, _writes(api)) == (0, 1)
    assert "Left for the next run: fix(security): judge Trivy-config DS-0002" in output
    assert "Left for the next run: fix(security): judge Trivy-config KSV-0001" in output


def test_a_dry_run_lists_the_requests_and_makes_none(
    cli: Callable[..., Any], api: GitHubApiFake
) -> None:
    result = cli("scan", "alerts", "--repo", _REPO, "--dry-run")

    assert (result.exit_code, api.sent) == (0, [])
    assert f"repos/{_REPO}/code-scanning/alerts" in result.output


def test_alerts_says_so_when_no_alert_is_open(
    cli: Callable[..., Any], github_api: GitHubApiFake
) -> None:
    github_api.route(
        "GET",
        f"/repos/{_REPO}/code-scanning/alerts?state=open&tool_name=Trivy-config&per_page=100",
        github_json([]),
    )
    github_api.route("GET", f"/repos/{_REPO}/issues?state=open&per_page=100", github_json([]))

    result = cli("scan", "alerts", "--repo", _REPO)

    assert result.exit_code == 0
    assert "No open Trivy-config alert" in " ".join(result.output.split())
