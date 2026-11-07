"""Tests for ArgoCD automated GitOps drift detection and webhook synchronization."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest

from devops_cli.models.argo import GitOpsDriftEvent, GitOpsSyncTriggerResult
from tests.support.fakes.http import WebFake
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.waits import wait_until

pytestmark = pytest.mark.usefixtures("keyring_store")

ARGOCD = "https://example.com/argo"
SYNC_URL = f"{ARGOCD}/api/v1/applications/root-app/sync"


def test_gitops_models() -> None:
    """Verify serialization and defaults of GitOps drift and sync models."""
    event = GitOpsDriftEvent(
        path="k8s/deploy.yaml",
        change_type="modified",
        timestamp=1700000000.0,
        file_hash="abcdef123456",
    )
    assert event.path == "k8s/deploy.yaml"
    assert event.change_type == "modified"
    assert event.file_hash == "abcdef123456"

    result = GitOpsSyncTriggerResult(
        app_name="root-app",
        changed_files=["k8s/deploy.yaml"],
        status="Synced",
        sync_mode="api",
        message="Synced successfully",
        duration_seconds=0.45,
        timestamp=1700000001.0,
        success=True,
    )
    dumped = result.model_dump()
    assert dumped["app_name"] == "root-app"
    assert dumped["status"] == "Synced"
    assert dumped["success"] is True


def test_compute_manifest_state(tmp_path: Path) -> None:
    """Ensure manifest state computation correctly hashes YAML files and ignores non-manifests."""
    from devops_cli.argo.gitops import compute_manifest_state

    f1 = tmp_path / "app.yaml"
    f1.write_text("apiVersion: v1\nkind: ConfigMap", encoding="utf-8")
    f2 = tmp_path / "chart.yml"
    f2.write_text("apiVersion: v2\nname: test", encoding="utf-8")
    ignored = tmp_path / "notes.txt"
    ignored.write_text("ignore this", encoding="utf-8")

    sub = tmp_path / "sub"
    sub.mkdir()
    f3 = sub / "service.yaml"
    f3.write_text("kind: Service", encoding="utf-8")

    state = compute_manifest_state([tmp_path])
    assert f1.resolve() in state
    assert f2.resolve() in state
    assert f3.resolve() in state
    assert ignored.resolve() not in state

    # Validate hash and mtime
    mtime, sha = state[f1.resolve()]
    assert len(sha) == 64
    assert mtime > 0


def test_scan_manifest_drift(tmp_path: Path) -> None:
    """Ensure scan_manifest_drift detects creations, modifications, and deletions."""
    from devops_cli.argo.gitops import compute_manifest_state, scan_manifest_drift

    f1 = tmp_path / "deployment.yaml"
    f1.write_text("replicas: 1", encoding="utf-8")
    f2 = tmp_path / "service.yaml"
    f2.write_text("port: 80", encoding="utf-8")

    state1 = compute_manifest_state([tmp_path])

    # Modify f1, delete f2, create f3
    f1.write_text("replicas: 2", encoding="utf-8")
    f2.unlink()
    f3 = tmp_path / "ingress.yaml"
    f3.write_text("host: example.com", encoding="utf-8")
    assert wait_until(lambda: compute_manifest_state([tmp_path]) != state1)

    state2 = compute_manifest_state([tmp_path])
    events = scan_manifest_drift(state1, state2)

    change_types = {e.change_type: e for e in events}
    assert "modified" in change_types
    assert "deleted" in change_types
    assert "created" in change_types
    assert Path(change_types["modified"].path).name == "deployment.yaml"
    assert Path(change_types["deleted"].path).name == "service.yaml"
    assert Path(change_types["created"].path).name == "ingress.yaml"


def test_trigger_argocd_sync_dry_run() -> None:
    """Ensure dry-run skips external HTTP requests and returns simulated outcome."""
    from devops_cli.argo.gitops import trigger_argocd_sync

    result = trigger_argocd_sync(
        app_name="root-app",
        changed_files=["k8s/deployment.yaml"],
        dry_run=True,
    )
    assert result.status == "DryRun"
    assert result.success is True
    assert "Simulated" in result.message


@pytest.fixture
def argocd(config: Callable[..., Path], keyring_store: Any) -> str:
    """Point devops-cli at a fake Argo CD with the stored token `test-token`; return its URL."""
    config(argocd={"url": ARGOCD})
    keyring_store.values["argocd_token"] = "test-token"
    return ARGOCD


def test_trigger_argocd_sync_api_success(web: WebFake, argocd: str) -> None:
    """Ensure API sync succeeds with valid mock ArgoCD endpoint."""
    from devops_cli.argo.gitops import trigger_argocd_sync

    web.respond("POST", SYNC_URL, 200, {})

    result = trigger_argocd_sync(
        app_name="root-app",
        changed_files=["k8s/deployment.yaml"],
        prune=True,
        force=True,
        sync_mode="api",
    )

    assert (result.status, result.success) == ("Synced", True)
    [sent] = web.recorded
    assert (sent.method, sent.url, sent.json, sent.headers["authorization"]) == (
        "POST",
        SYNC_URL,
        {"prune": True, "strategy": {"apply": {"force": True}}},
        "Bearer test-token",
    )


def test_trigger_argocd_sync_webhook_success(
    web: WebFake, config: Callable[..., Path], keyring_store: Any
) -> None:
    """Ensure webhook sync succeeds with valid mock ArgoCD endpoint, with no token stored."""
    from devops_cli.argo.gitops import trigger_argocd_sync

    config(argocd={"url": ARGOCD})
    web.respond("POST", f"{ARGOCD}/api/webhook", 200, {})

    result = trigger_argocd_sync(
        app_name="root-app",
        changed_files=["k8s/values.yaml"],
        sync_mode="webhook",
    )

    assert (result.status, result.success) == ("Triggered", True)
    assert [(r.method, r.url, "authorization" in r.headers) for r in web.recorded] == [
        ("POST", f"{ARGOCD}/api/webhook", False)
    ]


def test_trigger_argocd_sync_failure(web: WebFake, argocd: str) -> None:
    """Ensure network failure is captured gracefully with status Failed."""
    from devops_cli.argo.gitops import trigger_argocd_sync

    web.refuse(SYNC_URL)

    result = trigger_argocd_sync(
        app_name="root-app",
        changed_files=["k8s/deployment.yaml"],
    )

    assert (result.status, result.success) == ("Failed", False)
    assert "Connection refused" in result.message


def test_gitops_watcher_lifecycle(tmp_path: Path) -> None:
    """Ensure GitOpsWatcher detects drift, aggregates changes, and triggers sync."""
    from devops_cli.argo.gitops import GitOpsWatcher, compute_manifest_state

    manifest = tmp_path / "deployment.yaml"
    manifest.write_text("replicas: 1", encoding="utf-8")

    sync_results: list[GitOpsSyncTriggerResult] = []
    drift_events: list[GitOpsDriftEvent] = []

    watcher = GitOpsWatcher(
        paths=[tmp_path],
        app_name="test-app",
        debounce_ms=50,
        poll_interval_seconds=0.05,
        dry_run=True,
        on_drift=lambda events: drift_events.extend(events),
        on_sync=lambda res: sync_results.append(res),
    )

    # Initial scan establishes baseline without drift
    initial = watcher.scan_drift()
    assert len(initial) == 0

    # Modify file
    manifest.write_text("replicas: 3", encoding="utf-8")
    assert wait_until(lambda: compute_manifest_state([tmp_path]) != watcher._last_state)

    # Run watcher with max_events=1
    results = watcher.watch(max_events=1)
    assert len(results) == 1
    assert results[0].app_name == "test-app"
    assert results[0].status == "DryRun"
    assert len(drift_events) >= 1
    assert len(sync_results) >= 1


def test_gitops_tables_formatting() -> None:
    """Ensure TablePayload formatting functions render correctly."""
    from devops_cli.output import format_gitops_drift_table, format_gitops_sync_table

    events = [
        GitOpsDriftEvent(
            path="k8s/app.yaml",
            change_type="modified",
            timestamp=1700000000.0,
            file_hash="1234567890abcdef",
        ),
        GitOpsDriftEvent(
            path="k8s/secret.yaml",
            change_type="created",
            timestamp=1700000005.0,
            file_hash="fedcba0987654321",
        ),
    ]
    drift_table = format_gitops_drift_table(events)
    assert "GitOps Manifest Drift" in drift_table.title
    assert len(drift_table.rows) == 2

    sync_results = [
        GitOpsSyncTriggerResult(
            app_name="root-app",
            changed_files=["k8s/app.yaml"],
            status="Synced",
            sync_mode="api",
            message="Reconciliation successful",
            duration_seconds=0.25,
            timestamp=1700000006.0,
            success=True,
        )
    ]
    sync_table = format_gitops_sync_table(sync_results)
    assert "GitOps Synchronization History" in sync_table.title
    assert len(sync_table.rows) == 1


def test_cli_gitops_watch_dry_run_once(tmp_path: Path, cli: Callable[..., Any]) -> None:
    """Test CLI command devops argo gitops watch with --dry-run intercept."""
    manifest = tmp_path / "app.yaml"
    manifest.write_text("apiVersion: v1", encoding="utf-8")

    result = cli(
        "argo",
        "gitops",
        "watch",
        "--path",
        str(tmp_path),
        "--app-name",
        "root-app",
        "--once",
        "--dry-run",
    )
    assert result.exit_code == 0
    assert "Plan for GitOps watch on 'root-app'" in result.output
    assert "api/v1/session" in result.output


def test_cli_gitops_watch_once_execution(tmp_path: Path, cli: Callable[..., Any]) -> None:
    """Test CLI command devops argo gitops watch with --once."""
    manifest = tmp_path / "app.yaml"
    manifest.write_text("apiVersion: v1", encoding="utf-8")

    result = cli(
        "argo", "gitops", "watch", "--path", str(tmp_path), "--app-name", "root-app", "--once"
    )
    assert (result.exit_code, "No manifest drift detected" in result.output) == (0, True)


def test_cli_gitops_watch_json_output(tmp_path: Path, cli: Callable[..., Any]) -> None:
    """Test CLI command devops argo gitops watch with --json."""
    manifest = tmp_path / "app.yaml"
    manifest.write_text("apiVersion: v1", encoding="utf-8")

    result = cli(
        "argo",
        "gitops",
        "watch",
        "--path",
        str(tmp_path),
        "--app-name",
        "root-app",
        "--once",
        "--json",
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "events" in data
    assert "synced" in data


def test_cli_gitops_drift_command(tmp_path: Path, cli: Callable[..., Any]) -> None:
    """Test CLI command devops argo gitops drift."""
    manifest = tmp_path / "app.yaml"
    manifest.write_text("apiVersion: v1", encoding="utf-8")

    result = cli("argo", "gitops", "drift", "--path", str(tmp_path))
    assert (result.exit_code, "No manifest drift detected" in result.output) == (0, True)


def test_cli_gitops_sync_command(cli: Callable[..., Any]) -> None:
    """Test CLI command devops argo gitops sync with --dry-run."""
    result = cli("argo", "gitops", "sync", "--app-name", "root-app", "--dry-run")
    assert (result.exit_code, "Plan for GitOps sync on 'root-app'" in result.output) == (0, True)


def test_cli_gitops_subcommand_under_cd(tmp_path: Path, cli: Callable[..., Any]) -> None:
    """Test mounting of gitops under devops argo cd."""
    result = cli(
        "argo",
        "cd",
        "gitops",
        "watch",
        "--path",
        str(tmp_path),
        "--app-name",
        "root-app",
        "--once",
        "--dry-run",
    )
    assert (result.exit_code, "Plan for GitOps watch on 'root-app'" in result.output) == (0, True)


def test_cli_gitops_invalid_app_name(cli: Callable[..., Any]) -> None:
    """Test validation rejection of invalid Kubernetes name."""
    result = cli("argo", "gitops", "watch", "--app-name", "INVALID_NAME!!!")
    assert result.exit_code != 0


def test_trigger_argocd_sync_secret_masking(web: WebFake, argocd: str) -> None:
    """Ensure sensitive credentials and URLs in error messages are masked."""
    from devops_cli.argo.gitops import trigger_argocd_sync

    sensitive_error = "Connection failed to https://admin:SuperSecretPassword123@example.com/argo"
    web.fail(SYNC_URL, httpx2.ConnectError(sensitive_error))

    result = trigger_argocd_sync(app_name="root-app")

    assert result.status == "Failed"
    assert "SuperSecretPassword123" not in result.message
    assert "<masked-password>" in result.message or "***" in result.message


def test_manifest_state_persistence(tmp_path: Path) -> None:
    """Ensure baseline state is correctly persisted and restored."""
    from devops_cli.argo.gitops import (
        compute_manifest_state,
        load_persisted_manifest_state,
        save_persisted_manifest_state,
    )

    f1 = tmp_path / "app.yaml"
    f1.write_text("replicas: 1", encoding="utf-8")

    state = compute_manifest_state([tmp_path])
    save_persisted_manifest_state([tmp_path], state)

    loaded = load_persisted_manifest_state([tmp_path])
    assert loaded is not None
    assert f1.resolve() in loaded
    assert loaded[f1.resolve()][1] == state[f1.resolve()][1]


def test_cli_gitops_watch_once_failure_exits_nonzero(
    tmp_path: Path, cli: Callable[..., Any], web: WebFake, argocd: str
) -> None:
    """Ensure failed reconciliation in one-shot mode propagates non-zero exit code."""
    from devops_cli.argo.gitops import compute_manifest_state, save_persisted_manifest_state

    manifest = tmp_path / "app.yaml"
    manifest.write_text("replicas: 1", encoding="utf-8")
    save_persisted_manifest_state([tmp_path], compute_manifest_state([tmp_path]))
    manifest.write_text("replicas: 2", encoding="utf-8")
    web.respond("POST", SYNC_URL, 500, {"error": "sync refused"})

    result = cli(
        "argo", "gitops", "watch", "--path", str(tmp_path), "--app-name", "root-app", "--once"
    )

    assert (result.exit_code, web.requested) == (1, [SYNC_URL])


@pytest.mark.parametrize("separator", ["\0", "\n"], ids=["nul-separated", "newline-separated"])
def test_inspect_git_manifest_drift_success(
    tmp_path: Path, process_fake: ProcessFake, separator: str
) -> None:
    """Test inspect_git_manifest_drift handles created, modified, deleted, and non-manifest files."""
    from devops_cli.argo.gitops import inspect_git_manifest_drift

    manifest1 = tmp_path / "deploy.yaml"
    manifest1.write_text("kind: Deployment", encoding="utf-8")
    manifest2 = tmp_path / "service.yml"
    manifest2.write_text("kind: Service", encoding="utf-8")
    manifest3 = tmp_path / "deleted.yaml"
    ignored_file = tmp_path / "notes.txt"
    ignored_file.write_text("not a manifest", encoding="utf-8")
    status = separator.join(
        [
            "??",  # short line (<4 chars)
            f"?? {manifest1.resolve()}",  # created
            f" M {manifest2.resolve()}",  # modified
            f" D {manifest3.resolve()}",  # deleted
            f" M {ignored_file.resolve()}",  # non-manifest
        ]
    )
    process_fake.answer(["git", "status"], ProcessAnswer(stdout=status))

    events = inspect_git_manifest_drift([tmp_path])

    assert {event.change_type for event in events} == {"created", "modified", "deleted"}
    assert len(events) == 3


def test_inspect_git_manifest_drift_error_handling(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    """Test inspect_git_manifest_drift returns empty list on failure or exception."""
    from devops_cli.argo.gitops import inspect_git_manifest_drift

    process_fake.answer(["git", "status"], ProcessAnswer(returncode=1))
    assert inspect_git_manifest_drift([tmp_path]) == []

    process_fake.answer(["git", "status"], ProcessAnswer(side_effect=RuntimeError("git gone")))
    assert inspect_git_manifest_drift([tmp_path]) == []


def test_inspect_git_manifest_drift_handles_spaces_non_ascii_and_renames(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    """The NUL-separated status of git names a path with a space, a non-ASCII path and a rename.

    The transcript is the output of `git status --porcelain=v1 -z` in a repository where one file
    changed, two files are new and one file moved: a rename lists the new path, then the old one.
    """
    from devops_cli.argo.gitops import inspect_git_manifest_drift

    repo = tmp_path / "repo"
    k8s = repo / "k8s"
    k8s.mkdir(parents=True)
    (repo / ".git").mkdir()
    status = "\0".join(
        [
            " M k8s/first.yaml",
            "?? k8s/space manifest.yaml",
            "?? k8s/café.yaml",
            "R  k8s/renamed.yaml",
            "k8s/old.yaml",
            "",
        ]
    )
    process_fake.answer(["git", "status"], ProcessAnswer(stdout=status))

    events = inspect_git_manifest_drift([k8s])

    assert {Path(event.path).relative_to(repo).as_posix() for event in events} == {
        "k8s/first.yaml",
        "k8s/space manifest.yaml",
        "k8s/café.yaml",
        "k8s/renamed.yaml",
    }
