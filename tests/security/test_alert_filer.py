"""The filer of the open `Trivy-config` code scanning alerts: which alerts it reads, how it groups
them, which groups get an issue, and the text of that issue (#4401). GitHub is faked at the HTTP
edge.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from devops_cli.github.session import get_github_session
from devops_cli.security.alert_filer import (
    AlertGroup,
    CodeScanningAlert,
    file_alert_issues,
    group_alerts,
    plan_filing,
)
from tests.support.fakes.github import GitHubApiFake, github_json

_REPO = "owner/repo"
_ALERTS = f"/repos/{_REPO}/code-scanning/alerts?state=open&tool_name=Trivy-config&per_page=100"
_ISSUES = f"/repos/{_REPO}/issues?state=open&per_page=100"
_NEW_ISSUE = f"/repos/{_REPO}/issues"
_GPU = "k8s/gpu-feature-discovery/daemonset.yaml"


def _raw(
    number: int, rule: str, path: str, severity: str = "high", tool: str = "Trivy-config"
) -> dict[str, Any]:
    """One alert as GitHub's code scanning API answers it, with the fields the filer reads."""
    return {
        "number": number,
        "tool": {"name": tool},
        "rule": {"id": rule, "severity": "error", "security_severity_level": severity},
        "most_recent_instance": {"location": {"path": path}},
    }


def _alert(*args: Any, **kwargs: Any) -> CodeScanningAlert:
    return CodeScanningAlert.model_validate(_raw(*args, **kwargs))


def _group(rule: str, path: str, severity: str = "HIGH", *numbers: int) -> AlertGroup:
    return AlertGroup(rule_id=rule, path=path, severity=severity, numbers=numbers or (1,))


def test_the_groups_hold_the_trivy_config_alerts_and_no_other_tool() -> None:
    alerts = [
        _alert(1, "KSV-0017", _GPU),
        _alert(2, "DS-0002", ".devcontainer/Dockerfile"),
        _alert(3, "AZU-0041", "tf/azure/main.tf", "critical"),
        _alert(4, "py/sql-injection", "src/a.py", tool="CodeQL"),
    ]

    groups = group_alerts(alerts)

    assert sorted(n for group in groups for n in group.numbers) == [1, 2, 3]


def test_two_alerts_of_one_rule_in_one_file_make_one_group_that_names_both() -> None:
    alerts = [_alert(7, "KSV-0017", _GPU), _alert(9, "KSV-0017", _GPU)]

    (group,) = group_alerts(alerts)

    assert group.numbers == (7, 9)
    assert "alert 7" in group.body(_REPO)
    assert "alert 9" in group.body(_REPO)


def test_a_rule_in_two_files_makes_two_groups_and_the_worst_severity_comes_first() -> None:
    alerts = [
        _alert(1, "KSV-0001", "k8s/a.yaml", "low"),
        _alert(2, "KSV-0001", "k8s/b.yaml", "critical"),
    ]

    groups = group_alerts(alerts)

    assert [(g.path, g.severity) for g in groups] == [
        ("k8s/b.yaml", "CRITICAL"),
        ("k8s/a.yaml", "LOW"),
    ]


def test_the_title_and_body_hold_the_rule_the_path_the_severity_and_the_alert_number() -> None:
    group = _group("DS-0002", ".devcontainer/Dockerfile", "HIGH", 214)

    body = group.body(_REPO)

    assert group.title == "fix(security): judge Trivy-config DS-0002 in .devcontainer/Dockerfile"
    assert "HIGH" in body
    assert "alert 214" in body
    assert f"https://github.com/{_REPO}/security/code-scanning/214" in body
    assert "#214" not in body


def test_a_group_that_an_open_issue_names_gets_no_new_issue() -> None:
    held = _group("KSV-0017", _GPU)
    new = _group("DS-0002", ".devcontainer/Dockerfile")

    plan = plan_filing([held, new], {held.title}, limit=5)

    assert (plan.to_file, plan.left) == ((new,), ())


def test_a_run_files_at_most_the_limit_and_names_the_groups_it_leaves() -> None:
    groups = [_group(f"KSV-{i:04d}", "k8s/a.yaml") for i in range(8)]

    plan = plan_filing(groups, set(), limit=5)

    assert (plan.to_file, plan.left) == (tuple(groups[:5]), tuple(groups[5:]))


def test_a_group_that_an_open_issue_holds_does_not_use_the_limit() -> None:
    groups = [_group(f"KSV-{i:04d}", "k8s/a.yaml") for i in range(3)]

    plan = plan_filing(groups, {groups[0].title}, limit=2)

    assert (plan.to_file, plan.left) == (tuple(groups[1:]), ())


@pytest.fixture
def api(github_api: GitHubApiFake) -> GitHubApiFake:
    """Three alerts of two groups, and one open issue that is no group."""
    alerts = [
        _raw(1, "KSV-0017", _GPU),
        _raw(2, "KSV-0017", _GPU),
        _raw(3, "DS-0002", ".devcontainer/Dockerfile"),
    ]
    github_api.route("GET", _ALERTS, github_json(alerts))
    github_api.route("GET", _ISSUES, github_json([{"number": 5, "title": "feat: something"}]))
    github_api.route("POST", _NEW_ISSUE, github_json({"number": 60}, status=201))
    return github_api


def test_the_filer_files_one_issue_for_each_group_with_no_open_issue(api: GitHubApiFake) -> None:
    outcome = file_alert_issues(get_github_session(), _REPO, limit=5)

    posted = [json.loads(r.content) for r in api.sent if r.method == "POST"]
    assert [p["title"] for p in posted] == [
        "fix(security): judge Trivy-config DS-0002 in .devcontainer/Dockerfile",
        f"fix(security): judge Trivy-config KSV-0017 in {_GPU}",
    ]
    assert all(p["labels"] == ["type/bug", "scope/security"] for p in posted)
    assert len(outcome.filed) == 2


def test_the_filer_files_nothing_when_each_group_has_an_open_issue(
    github_api: GitHubApiFake,
) -> None:
    group = _group("DS-0002", ".devcontainer/Dockerfile", "HIGH", 3)
    github_api.route(
        "GET",
        _ALERTS,
        github_json([_raw(3, "DS-0002", ".devcontainer/Dockerfile")]),
    )
    github_api.route("GET", _ISSUES, github_json([{"number": 8, "title": group.title}]))

    outcome = file_alert_issues(get_github_session(), _REPO, limit=5)

    assert [r for r in github_api.sent if r.method == "POST"] == []
    assert (outcome.filed, outcome.held) == ((), (group,))


def test_an_open_pull_request_with_the_title_of_a_group_is_no_issue(
    github_api: GitHubApiFake,
) -> None:
    group = _group("DS-0002", ".devcontainer/Dockerfile", "HIGH", 3)
    github_api.route(
        "GET",
        _ALERTS,
        github_json([_raw(3, "DS-0002", ".devcontainer/Dockerfile")]),
    )
    github_api.route(
        "GET", _ISSUES, github_json([{"number": 8, "title": group.title, "pull_request": {}}])
    )
    github_api.route("POST", _NEW_ISSUE, github_json({"number": 60}, status=201))

    outcome = file_alert_issues(get_github_session(), _REPO, limit=5)

    assert [number for _, number in outcome.filed] == [60]
