"""Tests for devops roadmap onboard (#1359)."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.rag.indexer import WorkspaceIndexer
from devops_cli.ai.rag.ingest import ingest_repository
from devops_cli.config.constants import (
    CONST_GITHUB_APP_PRIVATE_KEY_ENV,
    CONST_ROADMAP_LABELS_PATH,
    CONST_ROADMAP_WEBHOOK_EVENTS,
)
from devops_cli.config.defaults import DEFAULT_RAG_COLLECTION, DEFAULT_RAG_DOCS_COLLECTION
from devops_cli.roadmap.workflow_labels import WORKFLOW_LABELS
from tests.support.fakes.embeddings import FakeEmbedder
from tests.support.fakes.github import (
    GitHubApiFake,
    github_json,
    route_installation_repositories,
)
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.fakes.qdrant import FakeQdrantClient, seed_chunk
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

REPO = "example/roadmap"
OTHER_REPO = "example/other"
OWNER, NAME = REPO.split("/")
# The RAG rows read Qdrant and the keyring, so every test of the command answers both edges.
pytestmark = pytest.mark.usefixtures("qdrant", "keyring_store")
VALID_LABELS_YAML = """
- name: scope/cli
  color: "dcdcd6"
  description: "CLI"
"""
ROW_3 = "3. .github/labels.yml is on the default branch and is valid"
ROW_4 = "4. Every workflow label and every label of .github/labels.yml exists on GitHub"
WORKFLOW = [(spec.name, spec.color, spec.description) for spec in WORKFLOW_LABELS]
WEBHOOK_URL = "https://hooks.example.com/webhooks/github"
MATCHING_HOOK = {
    "id": 1,
    "active": True,
    "events": ["issues"],
    "config": {"url": WEBHOOK_URL, "content_type": "json"},
}


def _seed_valid_repo(
    store: InMemoryRoadmapStore,
    api: GitHubApiFake,
    *,
    has_issues: bool = True,
    labels_yml: str | None = VALID_LABELS_YAML,
    repo_labels: list[tuple[str, str, str]] | None = None,
    visibility: str = "private",
) -> None:
    api.route("GET", "/user", github_json({"login": "octocat"}))
    api.route(
        "GET",
        f"/repos/{REPO}",
        github_json(
            {
                "has_issues": has_issues,
                "name": NAME,
                "owner": {"login": OWNER},
                "visibility": visibility,
            }
        ),
    )
    if labels_yml is not None:
        store.seed_file(CONST_ROADMAP_LABELS_PATH, labels_yml)
    api.route("GET", f"/repos/{REPO}/hooks", github_json([MATCHING_HOOK]))
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
    assert "5. The repository is in service.repos: present" in result.stdout
    assert (
        "6. The repository webhook posts the roadmap events to the Service: present"
        in result.stdout
    )
    assert "7. " not in result.stdout
    assert "clear-status" not in result.stdout
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


def _ready_confirmed_pass(
    monkeypatch: pytest.MonkeyPatch,
    config: Callable[..., Path],
    processes: ProcessFake,
    rag_dir: Path,
) -> None:
    """Let the confirmed start of #3771 run the pass of REPO: its settings, its checkout and its
    answers at the process edge."""
    _seed_rag_clone(rag_dir)
    monkeypatch.setenv("DEVOPS_CLI_DATA_RAG_DIR", str(rag_dir))
    config(service={"repos": [REPO]}, qdrant={"url": "http://127.0.0.1:6333"})
    processes.answer(
        "gh api repos/example/roadmap",
        ProcessAnswer(stdout=json.dumps({"visibility": "private"})),
    )
    processes.answer(
        lambda call: "ls-remote" in call.argv,
        ProcessAnswer(stdout="ref: refs/heads/main\tHEAD\nabc1234567890\tHEAD\n"),
    )


def test_onboard_confirm_creates_missing_labels_and_keeps_differing(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
    config: Callable[..., Path],
    embedder: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 2 missing labels: status/planned, scope/cli.
    # 1 differing label: type/bug exists with different color ("ffffff").
    api, processes = github_api_and_gh
    held = [
        ("type/bug", "ffffff", "A bug") if name == "type/bug" else (name, color, desc)
        for name, color, desc in WORKFLOW
        if name != "status/planned"
    ]
    _seed_valid_repo(roadmap_store, api, repo_labels=held)
    api.route("POST", f"/repos/{REPO}/labels", github_json({"name": "status/planned"}))
    _ready_confirmed_pass(monkeypatch, config, processes, tmp_path / "rag")

    result = cli("roadmap", "onboard", "--repo", REPO, "--confirm")

    post_label_requests = [
        req for req in api.sent if req.method == "POST" and f"/repos/{REPO}/labels" in str(req.url)
    ]
    assert len(post_label_requests) == 2
    patch_requests = [req for req in api.sent if req.method == "PATCH"]
    delete_requests = [req for req in api.sent if req.method == "DELETE"]
    assert patch_requests == []
    assert delete_requests == []
    assert "kept" in result.stdout
    assert "type/bug" in result.stdout


def test_onboard_confirm_second_run_sends_no_writes(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
    config: Callable[..., Path],
    embedder: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api, processes = github_api_and_gh
    _seed_valid_repo(roadmap_store, api)
    _ready_confirmed_pass(monkeypatch, config, processes, tmp_path / "rag")

    # First run on repository with all labels present
    assert cli("roadmap", "onboard", "--repo", REPO, "--confirm").exit_code == 0
    posts_after_first = [
        req for req in api.sent if req.method == "POST" and "/labels" in str(req.url)
    ]
    assert posts_after_first == []

    # Second run immediately after
    assert cli("roadmap", "onboard", "--repo", REPO, "--confirm").exit_code == 0
    posts_after_second = [
        req for req in api.sent if req.method == "POST" and "/labels" in str(req.url)
    ]
    assert posts_after_second == []
    assert [req for req in api.sent if req.method in ("PATCH", "DELETE")] == []


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
    assert "clear-status" not in result.stdout


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
    assert "5. The repository is in service.repos: missing" in result.stdout
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


ROW_6 = "6. The repository webhook posts the roadmap events to the Service"


def test_onboard_row_6_is_missing_with_no_hook(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("devops_cli.roadmap.onboard.acts_as_github_app", lambda: True)
    _seed_valid_repo(roadmap_store, github_api)
    github_api.route("GET", f"/repos/{REPO}/hooks", github_json([]))
    route_installation_repositories(github_api, [REPO])
    config(service={"repos": [REPO]})

    result = cli("roadmap", "onboard", "--repo", REPO, "--plan")

    assert result.exit_code == 1, result.output
    assert f"{ROW_6}: missing" in result.stdout
    assert WEBHOOK_URL in result.stdout
    assert "application/json" in result.stdout
    assert "issues" in result.stdout
    assert "devops config set service.webhook_secrets" in result.stdout


def test_onboard_row_6_names_each_wrong_field(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("devops_cli.roadmap.onboard.acts_as_github_app", lambda: True)
    _seed_valid_repo(roadmap_store, github_api)
    github_api.route(
        "GET",
        f"/repos/{REPO}/hooks",
        github_json(
            [
                {
                    "id": 1,
                    "active": True,
                    "events": ["push"],
                    "config": {"url": "https://other.example.com/hook", "content_type": "form"},
                }
            ]
        ),
    )
    route_installation_repositories(github_api, [REPO])
    config(service={"repos": [REPO]})

    result = cli("roadmap", "onboard", "--repo", REPO, "--plan")

    assert f"{ROW_6}: wrong" in result.stdout
    assert "url, content_type, events" in result.stdout


def test_onboard_row_6_names_an_inactive_hook(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("devops_cli.roadmap.onboard.acts_as_github_app", lambda: True)
    _seed_valid_repo(roadmap_store, github_api)
    github_api.route(
        "GET", f"/repos/{REPO}/hooks", github_json([{**MATCHING_HOOK, "active": False}])
    )
    route_installation_repositories(github_api, [REPO])
    config(service={"repos": [REPO]})

    result = cli("roadmap", "onboard", "--repo", REPO, "--plan")

    assert f"{ROW_6}: wrong" in result.stdout
    assert "Wrong: active." in result.stdout


def test_onboard_row_6_is_present_for_a_hook_that_also_sends_other_events(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The consumer events are a subset of the hook events (#5035): a hook that sends each event
    that the Service takes, and other events too, posts the roadmap events. The Service
    acknowledges an event that no consumer takes. Row 2 does not change row 6, so the command
    runs with no App key."""
    monkeypatch.delenv(CONST_GITHUB_APP_PRIVATE_KEY_ENV, raising=False)
    _seed_valid_repo(roadmap_store, github_api)
    events = ["issues", "milestone", "pull_request", "release"]
    github_api.route(
        "GET", f"/repos/{REPO}/hooks", github_json([{**MATCHING_HOOK, "events": events}])
    )
    config(service={"repos": [REPO]})

    result = cli("roadmap", "onboard", "--repo", REPO, "--plan")

    assert (result.exit_code, f"{ROW_6}: present" in result.stdout) == (0, True), result.output


def test_onboard_row_6_names_events_when_the_hook_does_not_send_an_event_the_service_takes(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A hook with the Service URL that does not send the Issues event is wrong, also when it
    sends other events (#5035)."""
    monkeypatch.delenv(CONST_GITHUB_APP_PRIVATE_KEY_ENV, raising=False)
    _seed_valid_repo(roadmap_store, github_api)
    events = ["pull_request", "release"]
    github_api.route(
        "GET", f"/repos/{REPO}/hooks", github_json([{**MATCHING_HOOK, "events": events}])
    )
    config(service={"repos": [REPO]})

    result = cli("roadmap", "onboard", "--repo", REPO, "--plan")

    assert (f"{ROW_6}: wrong" in result.stdout, "Wrong: events." in result.stdout) == (True, True)


def test_onboard_row_6_is_not_readable_without_administration_read(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("devops_cli.roadmap.onboard.acts_as_github_app", lambda: True)
    _seed_valid_repo(roadmap_store, github_api)
    github_api.route(
        "GET", f"/repos/{REPO}/hooks", github_json({"message": "Forbidden"}, status=403)
    )
    route_installation_repositories(github_api, [REPO])
    config(service={"repos": [REPO]})

    result = cli("roadmap", "onboard", "--repo", REPO, "--plan")

    assert result.exit_code == 0, result.output
    assert f"{ROW_6}: not readable as" in result.stdout
    assert "devops config set service.webhook_secrets" in result.stdout


def test_the_service_step_and_the_webhook_row_name_the_same_events() -> None:
    """Setup step 8 names the events that the webhook row requires of the hook, and lets the
    hook send more (#5035)."""
    step = Path("docs/CLUSTER.md").read_text(encoding="utf-8")
    section = step.split("8. Add each repo's webhook:", 1)[1].split("\n", 1)[0]

    assert (
        "at least the Issues event" in section,
        "its `events` must hold `issues`" in section,
        CONST_ROADMAP_WEBHOOK_EVENTS == frozenset({"issues"}),
    ) == (True, True, True)


RAG_INDEXED = "indexed"
RAG_VISIBILITY = "rag visibility"
RAG_SCHEDULE = "rag schedule"
_QDRANT_KEY = "qdrant-key-3771"


def _seed_project_points(
    qdrant: FakeQdrantClient,
    *,
    visibility: str | None = "private",
    code: int = 1,
    docs: int = 1,
) -> None:
    """Hold `code` and `docs` points of REPO in the two collections, as the pass writes them."""
    embedder = FakeEmbedder()
    recorded = {} if visibility is None else {"visibility": visibility}
    for index in range(code):
        seed_chunk(
            qdrant,
            embedder,
            f"def f{index}():\n    return {index}\n",
            collection=DEFAULT_RAG_COLLECTION,
            file_path=f"src/m{index}.py",
            project_name=REPO,
            **recorded,
        )
    for index in range(docs):
        seed_chunk(
            qdrant,
            embedder,
            f"# Document {index}\n",
            collection=DEFAULT_RAG_DOCS_COLLECTION,
            file_path=f"docs/d{index}.md",
            project_name=REPO,
            **recorded,
        )


def _repository_reads(api: GitHubApiFake) -> list[str]:
    """Each GET of the repository that row 1 reads, as the API received it."""
    return [
        str(request.url)
        for request in api.sent
        if request.method == "GET" and str(request.url).endswith(f"/repos/{REPO}")
    ]


def test_onboard_rag_rows_read_the_index_the_visibility_and_the_schedule(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    qdrant: FakeQdrantClient,
) -> None:
    _seed_valid_repo(roadmap_store, github_api, visibility="private")
    config(service={"repos": [REPO]})
    _seed_project_points(qdrant)

    result = cli("roadmap", "onboard", "--repo", REPO, "--plan")

    assert result.exit_code == 0, result.output
    assert f"{RAG_INDEXED}: present (code 1, docs 1)" in result.stdout
    assert f"{RAG_VISIBILITY}: private" in result.stdout
    assert f"{RAG_SCHEDULE}: present" in result.stdout


def test_onboard_rag_indexed_row_reads_partial_with_the_count_of_each_collection(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    qdrant: FakeQdrantClient,
) -> None:
    _seed_valid_repo(roadmap_store, github_api)
    config(service={"repos": [REPO]})
    _seed_project_points(qdrant, code=2, docs=0)

    result = cli("roadmap", "onboard", "--repo", REPO, "--plan")

    assert f"{RAG_INDEXED}: partial (code 2, docs 0)" in result.stdout


def test_onboard_rag_rows_read_missing_points_and_send_one_repository_read(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
) -> None:
    """A repository that the scheduled pass has not reached yet keeps the exit code at 0, and the
    visibility row sends no read of its own (#3771)."""
    _seed_valid_repo(roadmap_store, github_api)
    config(service={"repos": [REPO]})

    result = cli("roadmap", "onboard", "--repo", REPO, "--plan")

    assert result.exit_code == 0, result.output
    assert f"{RAG_INDEXED}: missing" in result.stdout
    assert f"{RAG_VISIBILITY}: not indexed" in result.stdout
    assert len(_repository_reads(github_api)) == 1


def test_onboard_rag_visibility_reports_a_mismatch_with_both_values(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    qdrant: FakeQdrantClient,
) -> None:
    _seed_valid_repo(roadmap_store, github_api, visibility="public")
    config(service={"repos": [REPO]})
    _seed_project_points(qdrant, visibility="private")

    result = cli("roadmap", "onboard", "--repo", REPO, "--plan")

    assert f"{RAG_VISIBILITY}: mismatch (points private, github public)" in result.stdout


def test_onboard_rag_visibility_reports_a_point_that_records_no_visibility(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    qdrant: FakeQdrantClient,
) -> None:
    _seed_valid_repo(roadmap_store, github_api, visibility="private")
    config(service={"repos": [REPO]})
    _seed_project_points(qdrant, visibility=None)

    result = cli("roadmap", "onboard", "--repo", REPO, "--plan")

    assert f"{RAG_VISIBILITY}: mismatch (points not recorded, github private)" in result.stdout


def test_onboard_rag_visibility_row_reads_not_readable_when_the_repository_read_fails(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    qdrant: FakeQdrantClient,
) -> None:
    _seed_valid_repo(roadmap_store, github_api)
    config(service={"repos": [REPO]})
    _seed_project_points(qdrant)
    github_api.route("GET", f"/repos/{REPO}", github_json({"message": "Not Found"}, status=404))

    result = cli("roadmap", "onboard", "--repo", REPO, "--plan")

    assert f"{RAG_VISIBILITY}: not readable (the repository read failed)" in result.stdout


def test_onboard_rag_schedule_prints_the_line_to_add(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
) -> None:
    _seed_valid_repo(roadmap_store, github_api)
    config(service={"repos": []})

    result = cli("roadmap", "onboard", "--repo", REPO, "--plan")

    assert f"{RAG_SCHEDULE}: missing" in result.stdout
    assert f"Add to service.repos in config.yaml:\n  - {REPO}" in result.stdout


def test_onboard_rag_indexed_row_reads_not_readable_when_the_count_fails(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    qdrant: FakeQdrantClient,
) -> None:
    _seed_valid_repo(roadmap_store, github_api)
    config(service={"repos": [REPO]})
    qdrant.fail_operation("count_points")

    result = cli("roadmap", "onboard", "--repo", REPO, "--plan")

    assert result.exit_code == 0, result.output
    assert f"{RAG_INDEXED}: not readable (Simulated count_points failure)" in result.stdout
    assert f"{RAG_VISIBILITY}: not readable" in result.stdout
    assert f"{RAG_SCHEDULE}: present" in result.stdout


def test_onboard_rag_rows_print_no_qdrant_api_key(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    qdrant: FakeQdrantClient,
    keyring_store: FakeKeyring,
) -> None:
    """The rows reach Qdrant with the configured key, and neither the report nor a reason prints
    it (#3771)."""
    _seed_valid_repo(roadmap_store, github_api)
    config(service={"repos": [REPO]}, qdrant={"api_key": _QDRANT_KEY})
    keyring_store.set_password("devops-cli", "qdrant_api_key", _QDRANT_KEY)
    qdrant.fail_operation("count_points")

    result = cli("roadmap", "onboard", "--repo", REPO, "--plan")

    assert f"{RAG_INDEXED}: not readable" in result.stdout
    assert _QDRANT_KEY not in result.output
    assert _QDRANT_KEY not in result.stdout


def _seed_rag_clone(rag_dir: Path) -> None:
    """A checkout of REPO at the head that the pass reads, as a shallow clone of the pass leaves it.

    The pass fetches and checks out a tree that holds `.git`, so the files below it are the files
    that the indexer reads.
    """
    tree = rag_dir / "repos" / OWNER / NAME / "tree"
    (tree / ".git").mkdir(parents=True)
    (tree / "src").mkdir()
    (tree / "src" / "main.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (tree / "README.md").write_text("# Roadmap\n", encoding="utf-8")


def _pass_calls(processes: ProcessFake) -> list[str]:
    """Each command that the ingestion pass started, as the process edge received it."""
    return [
        " ".join(call.argv)
        for call in processes.calls
        if "ls-remote" in call.argv or "repos/" in " ".join(call.argv)
    ]


def test_onboard_confirm_starts_the_pass_for_one_repository(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
    config: Callable[..., Path],
    qdrant: FakeQdrantClient,
    embedder: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With --confirm, the command runs the pass of #1389 for the named repository alone, and
    prints the point count of each collection (#3771)."""
    api, processes = github_api_and_gh
    monkeypatch.delenv(CONST_GITHUB_APP_PRIVATE_KEY_ENV, raising=False)
    _seed_valid_repo(roadmap_store, api)
    rag_dir = tmp_path / "rag"
    _seed_rag_clone(rag_dir)
    monkeypatch.setenv("DEVOPS_CLI_DATA_RAG_DIR", str(rag_dir))
    config(
        service={"repos": [REPO, OTHER_REPO]},
        qdrant={"url": "http://127.0.0.1:6333"},
    )
    processes.answer(
        "gh api repos/example/roadmap",
        ProcessAnswer(stdout=json.dumps({"visibility": "private"})),
    )
    processes.answer(
        lambda call: "ls-remote" in call.argv,
        ProcessAnswer(stdout="ref: refs/heads/main\tHEAD\nabc1234567890\tHEAD\n"),
    )

    result = cli("roadmap", "onboard", "--repo", REPO, "--confirm")

    assert result.exit_code == 0, result.output
    code_points = qdrant.count_points(DEFAULT_RAG_COLLECTION, filter_payload={"project_name": REPO})
    docs_points = qdrant.count_points(
        DEFAULT_RAG_DOCS_COLLECTION, filter_payload={"project_name": REPO}
    )
    assert (code_points, docs_points) != (0, 0), result.output
    assert f"RAG points: code {code_points}, docs {docs_points}" in result.stdout
    calls = _pass_calls(processes)
    assert any(f"repos/{REPO}" in call for call in calls), calls
    assert not any(OTHER_REPO in call for call in calls), calls


def test_onboard_confirm_refuses_a_repository_outside_service_repos(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
    config: Callable[..., Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--confirm starts no pass when service.repos leaves the repository out (#3771)."""
    api, processes = github_api_and_gh
    monkeypatch.delenv(CONST_GITHUB_APP_PRIVATE_KEY_ENV, raising=False)
    _seed_valid_repo(roadmap_store, api)
    config(
        service={"repos": [OTHER_REPO]},
        qdrant={"url": "http://127.0.0.1:6333"},
        data={"rag_dir": str(tmp_path / "rag")},
    )

    result = cli("roadmap", "onboard", "--repo", REPO, "--confirm")

    assert result.exit_code == 1, result.output
    assert f"{REPO} is not in service.repos" in result.output
    assert _pass_calls(processes) == []


def _run_git(cwd: Path, *args: str) -> None:
    """Run one git command in `cwd`, as a test that builds a remote to ingest does."""
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _make_bare_remote(tmp_path: Path, files: dict[str, str]) -> Path:
    """A bare git remote with one commit that holds `files`, as the pass clones it."""
    bare = tmp_path / "remote.git"
    bare.mkdir()
    _run_git(bare, "init", "--bare", "--initial-branch=main")
    work = tmp_path / "work"
    work.mkdir()
    _run_git(work, "init", "--initial-branch=main")
    _run_git(work, "config", "user.name", "Test User")
    _run_git(work, "config", "user.email", "test@example.com")
    for path_str, content in files.items():
        target = work / path_str
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    _run_git(work, "add", ".")
    _run_git(work, "commit", "-m", "commit 1")
    _run_git(work, "remote", "add", "origin", f"file://{bare}")
    _run_git(work, "push", "-u", "origin", "main")
    return bare


class _GhAnswer:
    """The answer of a gh runner: one repository payload."""

    def __init__(self, stdout: str) -> None:
        self.returncode = 0
        self.stdout = stdout
        self.stderr = ""


def _gh_visibility_runner(visibility: str) -> Any:
    """A gh runner that answers the repository read with `visibility`."""

    def _runner(_cmd: list[str], **_kwargs: Any) -> _GhAnswer:
        return _GhAnswer(json.dumps({"visibility": visibility, "name": NAME}))

    return _runner


def test_every_written_point_carries_the_repository_project_name(
    tmp_path: Path,
    qdrant: FakeQdrantClient,
    keyring_store: FakeKeyring,
) -> None:
    """The pass names each point `owner/name`, never the directory that it runs in (#3771)."""
    bare = _make_bare_remote(
        tmp_path,
        {"src/main.py": "def f():\n    return 1\n", "README.md": "# Roadmap\n"},
    )
    worktree = tmp_path / "w-3566"
    worktree.mkdir()
    indexer = WorkspaceIndexer(qdrant=qdrant, embedder=FakeEmbedder(), cache_dir=worktree)

    result = ingest_repository(
        REPO,
        data_dir=worktree,
        remote_url=f"file://{bare}",
        gh_runner=_gh_visibility_runner("private"),
        indexer=indexer,
    )

    assert result.success is True
    points = [point for collection in qdrant.collections.values() for point in collection]
    assert points
    assert {point["payload"]["project_name"] for point in points} == {REPO}
