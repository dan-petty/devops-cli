"""Tests for devops roadmap onboard (#1359)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.constants import (
    CONST_GITHUB_APP_PRIVATE_KEY_ENV,
    CONST_ROADMAP_LABELS_PATH,
)
from devops_cli.roadmap.workflow_labels import WORKFLOW_LABELS
from tests.support.fakes.github import (
    GitHubApiFake,
    github_json,
    route_installation_repositories,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

REPO = "example/roadmap"
OWNER, NAME = REPO.split("/")
VALID_LABELS_YAML = """
- name: scope/cli
  color: "dcdcd6"
  description: "CLI"
"""
ROW_3 = "3. .github/labels.yml is on the default branch and is valid"
ROW_4 = "4. Every workflow label and every label of .github/labels.yml exists on GitHub"
WORKFLOW = [(spec.name, spec.color, spec.description) for spec in WORKFLOW_LABELS]


def _seed_valid_repo(
    store: InMemoryRoadmapStore,
    api: GitHubApiFake,
    *,
    has_issues: bool = True,
    labels_yml: str | None = VALID_LABELS_YAML,
    include_clear_status: bool = True,
    repo_labels: list[tuple[str, str, str]] | None = None,
) -> None:
    api.route("GET", "/user", github_json({"login": "octocat"}))
    api.route(
        "GET",
        f"/repos/{REPO}",
        github_json({"has_issues": has_issues, "name": NAME, "owner": {"login": OWNER}}),
    )
    if labels_yml is not None:
        store.seed_file(CONST_ROADMAP_LABELS_PATH, labels_yml)
    if include_clear_status:
        store.seed_file(".github/workflows/clear-status.yml", "name: Clear Status\n")
    seeded = [*WORKFLOW, ("scope/cli", "dcdcd6", "CLI")] if repo_labels is None else repo_labels
    for name, color, desc in seeded:
        store.seed_label(name, color, desc)


def test_onboard_all_prerequisites_present_exits_0(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("devops_cli.roadmap.onboard.acts_as_github_app", lambda: True)
    _seed_valid_repo(roadmap_store, github_api)
    route_installation_repositories(github_api, [REPO])
    config(service={"repos": [REPO]})

    result = cli("roadmap", "onboard", "--repo", REPO, "--plan")

    assert result.exit_code == 0, result.output
    assert "1. Issues are turned on: present" in result.stdout
    assert "2. The App devops-cli-service is installed on the repository: present" in result.stdout
    assert f"{ROW_3}: present" in result.stdout
    assert f"{ROW_4}: present" in result.stdout
    assert (
        "5. .github/workflows/clear-status.yml is on the default branch: present" in result.stdout
    )
    assert "6. The repository is in service.repos: present" in result.stdout
    assert "Not readable rows: 0." in result.stdout


def test_onboard_issues_turned_off_prints_patch_and_sends_none(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
) -> None:
    _seed_valid_repo(roadmap_store, github_api, has_issues=False)
    config(service={"repos": [REPO]})

    result = cli("roadmap", "onboard", "--repo", REPO, "--plan")

    assert result.exit_code == 1, result.output
    assert "1. Issues are turned on: missing" in result.stdout
    assert f"devops gh api -X PATCH repos/{REPO} -f has_issues=true" in result.stdout
    patch_requests = [req for req in github_api.sent if req.method == "PATCH"]
    assert patch_requests == []


def test_onboard_without_app_key_reads_not_readable_as_login_and_makes_no_installation_request(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(CONST_GITHUB_APP_PRIVATE_KEY_ENV, raising=False)
    _seed_valid_repo(roadmap_store, github_api)
    github_api.route("GET", "/user", github_json({"login": "test-user"}))
    config(service={"repos": [REPO]})

    result = cli("roadmap", "onboard", "--repo", REPO, "--plan")

    assert (
        "2. The App devops-cli-service is installed on the repository: not readable as test-user"
        in result.stdout
    )
    installation_requests = [
        req for req in github_api.sent if "/installation/repositories" in str(req.url)
    ]
    assert installation_requests == []


def test_onboard_as_app_present_and_missing(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("devops_cli.roadmap.onboard.acts_as_github_app", lambda: True)
    _seed_valid_repo(roadmap_store, github_api)
    route_installation_repositories(github_api, [REPO])
    config(service={"repos": [REPO]})

    # When present
    res_present = cli("roadmap", "onboard", "--repo", REPO, "--plan")
    assert (
        "2. The App devops-cli-service is installed on the repository: present"
        in res_present.stdout
    )

    # When missing from installation listing
    route_installation_repositories(github_api, ["other/repo"])
    res_missing = cli("roadmap", "onboard", "--repo", REPO, "--plan")
    assert (
        "2. The App devops-cli-service is installed on the repository: missing"
        in res_missing.stdout
    )
    assert res_missing.exit_code == 1


@pytest.mark.parametrize(
    ("labels_content", "expected_reason"),
    [
        (None, "labels.yml is missing"),
        ("invalid: [yaml: broken", "labels.yml is not YAML"),
        ("not_a_list: true", "labels.yml is not a list of labels"),
    ],
)
def test_onboard_invalid_labels_file_makes_row_3_missing_and_row_4_checks_the_workflow_labels(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    labels_content: str | None,
    expected_reason: str,
) -> None:
    _seed_valid_repo(roadmap_store, github_api, labels_yml=labels_content)
    config(service={"repos": [REPO]})

    result = cli("roadmap", "onboard", "--repo", REPO, "--plan")

    assert result.exit_code == 1
    assert f"{ROW_3}: missing ({expected_reason})" in result.stdout
    assert f"{ROW_4}: present" in result.stdout


def test_onboard_row_4_lists_a_workflow_label_that_github_lacks(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
) -> None:
    held = [label for label in WORKFLOW if label[0] != "status/planned"]
    _seed_valid_repo(roadmap_store, github_api, repo_labels=[*held, ("scope/cli", "dcdcd6", "CLI")])
    config(service={"repos": [REPO]})

    result = cli("roadmap", "onboard", "--repo", REPO, "--plan")

    assert (result.exit_code, f"{ROW_4}: missing (1 label(s) missing)" in result.stdout) == (
        1,
        True,
    )
    assert "Missing labels:\n  - status/planned\n" in result.stdout


def test_onboard_confirm_creates_missing_labels_and_keeps_differing(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
) -> None:
    # 2 missing labels: status/planned, scope/cli.
    # 1 differing label: type/bug exists with different color ("ffffff").
    held = [
        ("type/bug", "ffffff", "A bug") if name == "type/bug" else (name, color, desc)
        for name, color, desc in WORKFLOW
        if name != "status/planned"
    ]
    _seed_valid_repo(roadmap_store, github_api, repo_labels=held)
    github_api.route("POST", f"/repos/{REPO}/labels", github_json({"name": "status/planned"}))
    config(service={"repos": [REPO]})

    result = cli("roadmap", "onboard", "--repo", REPO, "--confirm")

    post_label_requests = [
        req
        for req in github_api.sent
        if req.method == "POST" and f"/repos/{REPO}/labels" in str(req.url)
    ]
    assert len(post_label_requests) == 2
    patch_requests = [req for req in github_api.sent if req.method == "PATCH"]
    delete_requests = [req for req in github_api.sent if req.method == "DELETE"]
    assert patch_requests == []
    assert delete_requests == []
    assert "kept" in result.stdout
    assert "type/bug" in result.stdout


def test_onboard_confirm_second_run_sends_no_writes(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
) -> None:
    _seed_valid_repo(roadmap_store, github_api)
    config(service={"repos": [REPO]})

    # First run on repository with all labels present
    assert cli("roadmap", "onboard", "--repo", REPO, "--confirm").exit_code == 0
    posts_after_first = [
        req for req in github_api.sent if req.method == "POST" and "/labels" in str(req.url)
    ]
    assert posts_after_first == []

    # Second run immediately after
    assert cli("roadmap", "onboard", "--repo", REPO, "--confirm").exit_code == 0
    posts_after_second = [
        req for req in github_api.sent if req.method == "POST" and "/labels" in str(req.url)
    ]
    assert posts_after_second == []
    assert [req for req in github_api.sent if req.method in ("PATCH", "DELETE")] == []


def test_onboard_dry_run_makes_zero_requests(
    cli: Callable[..., Any],
    github_api: GitHubApiFake,
) -> None:
    result = cli("roadmap", "onboard", "--repo", REPO, "--dry-run")

    assert result.exit_code == 0, result.output
    assert github_api.sent == []
    assert f"/repos/{REPO}" in result.stdout
    assert "/installation/repositories" in result.stdout
    assert f"/repos/{REPO}/labels" in result.stdout


def test_onboard_refuses_two_mode_flags(
    cli: Callable[..., Any],
    github_api: GitHubApiFake,
) -> None:
    result = cli("roadmap", "onboard", "--repo", REPO, "--plan", "--confirm")

    assert result.exit_code == 1
    assert (
        "exclusive" in result.output.lower()
        or "cannot be used together" in result.output.lower()
        or "--plan" in result.output
    )
    assert github_api.sent == []


def test_onboard_service_repos_missing_prints_command_and_leaves_config(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
) -> None:
    _seed_valid_repo(roadmap_store, github_api)
    config(service={"repos": []})

    result = cli("roadmap", "onboard", "--repo", REPO, "--plan")

    assert result.exit_code == 1
    assert "6. The repository is in service.repos: missing" in result.stdout
    assert "service.repos" in result.stdout
    assert "devops k8s deploy-stack" in result.stdout


def test_onboard_exit_code_0_when_no_missing_even_with_not_readable(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # All rows present except row 2 which is not readable as user
    monkeypatch.delenv(CONST_GITHUB_APP_PRIVATE_KEY_ENV, raising=False)
    _seed_valid_repo(roadmap_store, github_api)
    github_api.route("GET", "/user", github_json({"login": "human"}))
    config(service={"repos": [REPO]})

    result = cli("roadmap", "onboard", "--repo", REPO, "--plan")

    assert result.exit_code == 0, result.output
    assert "not readable as human" in result.stdout
    assert "Not readable rows: 1." in result.stdout
