"""Tests for ArgoCD automated GitOps drift detection and webhook synchronization."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.argo import app
from devops_cli.config.settings import Settings
from devops_cli.exceptions.k8s import GitOpsSyncError
from devops_cli.models.argo import GitOpsDriftEvent, GitOpsSyncTriggerResult

runner = CliRunner()


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


def test_gitops_sync_error_taxonomy() -> None:
    """Ensure GitOpsSyncError follows taxonomy and bounds details."""
    err = GitOpsSyncError("Sync failed", app_name="a" * 300)
    assert err.details is not None
    assert len(err.details.get("app_name", "")) <= 256
    assert err.error_code == "GITOPS_SYNC_ERROR"


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
    time.sleep(0.01)
    f1.write_text("replicas: 2", encoding="utf-8")
    f2.unlink()
    f3 = tmp_path / "ingress.yaml"
    f3.write_text("host: example.com", encoding="utf-8")

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


def test_trigger_argocd_sync_api_success() -> None:
    """Ensure API sync succeeds with valid mock ArgoCD endpoint."""
    from devops_cli.argo.gitops import trigger_argocd_sync

    settings = Settings()
    settings.argocd.url = "https://example.com/argo"

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.post.return_value = mock_resp

    with (
        patch("devops_cli.argo.gitops.load_settings", return_value=settings),
        patch("devops_cli.argo.gitops.get_argocd_token", return_value="test-token"),
        patch("httpx2.Client", return_value=mock_client),
    ):
        result = trigger_argocd_sync(
            app_name="root-app",
            changed_files=["k8s/deployment.yaml"],
            prune=True,
            force=True,
            sync_mode="api",
        )
        assert result.status == "Synced"
        assert result.success is True
        sync_calls = [c for c in mock_client.post.call_args_list if "example.com" in str(c)]
        assert len(sync_calls) == 1
        call_args = sync_calls[0]
        assert "/api/v1/applications/root-app/sync" in call_args[0][0]
        assert call_args[1]["json"] == {"sync": {"prune": True, "force": True}}
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-token"


def test_trigger_argocd_sync_webhook_success() -> None:
    """Ensure webhook sync succeeds with valid mock ArgoCD endpoint."""
    from devops_cli.argo.gitops import trigger_argocd_sync

    settings = Settings()
    settings.argocd.url = "https://example.com/argo"

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.post.return_value = mock_resp

    with (
        patch("devops_cli.argo.gitops.load_settings", return_value=settings),
        patch("devops_cli.argo.gitops.get_argocd_token", return_value=""),
        patch("httpx2.Client", return_value=mock_client),
    ):
        result = trigger_argocd_sync(
            app_name="root-app",
            changed_files=["k8s/values.yaml"],
            sync_mode="webhook",
        )
        assert result.status == "Triggered"
        assert result.success is True
        sync_calls = [c for c in mock_client.post.call_args_list if "example.com" in str(c)]
        assert len(sync_calls) == 1
        assert "/api/webhook" in sync_calls[0][0][0]


def test_trigger_argocd_sync_failure() -> None:
    """Ensure network failure is captured gracefully with status Failed."""
    from devops_cli.argo.gitops import trigger_argocd_sync

    settings = Settings()
    settings.argocd.url = "https://example.com/argo"

    with (
        patch("devops_cli.argo.gitops.load_settings", return_value=settings),
        patch("httpx2.Client.post", side_effect=RuntimeError("Connection refused")),
    ):
        result = trigger_argocd_sync(
            app_name="root-app",
            changed_files=["k8s/deployment.yaml"],
        )
        assert result.status == "Failed"
        assert result.success is False
        assert "Connection refused" in result.message


def test_gitops_watcher_lifecycle(tmp_path: Path) -> None:
    """Ensure GitOpsWatcher detects drift, aggregates changes, and triggers sync."""
    from devops_cli.argo.gitops import GitOpsWatcher

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
    time.sleep(0.02)
    manifest.write_text("replicas: 3", encoding="utf-8")

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


def test_cli_gitops_watch_dry_run_once(tmp_path: Path) -> None:
    """Test CLI command devops argo gitops watch with --dry-run intercept."""
    manifest = tmp_path / "app.yaml"
    manifest.write_text("apiVersion: v1", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "gitops",
            "watch",
            "--path",
            str(tmp_path),
            "--app-name",
            "root-app",
            "--once",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "DRY_RUN" in result.output
    assert "watch_gitops_drift" in result.output


def test_cli_gitops_watch_once_execution(tmp_path: Path) -> None:
    """Test CLI command devops argo gitops watch with --once."""
    manifest = tmp_path / "app.yaml"
    manifest.write_text("apiVersion: v1", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "gitops",
            "watch",
            "--path",
            str(tmp_path),
            "--app-name",
            "root-app",
            "--once",
        ],
    )
    assert result.exit_code == 0
    assert "No manifest drift detected" in result.output or "GitOps" in result.output


def test_cli_gitops_watch_json_output(tmp_path: Path) -> None:
    """Test CLI command devops argo gitops watch with --json."""
    manifest = tmp_path / "app.yaml"
    manifest.write_text("apiVersion: v1", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "gitops",
            "watch",
            "--path",
            str(tmp_path),
            "--app-name",
            "root-app",
            "--once",
            "--json",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "events" in data
    assert "synced" in data


def test_cli_gitops_drift_command(tmp_path: Path) -> None:
    """Test CLI command devops argo gitops drift."""
    manifest = tmp_path / "app.yaml"
    manifest.write_text("apiVersion: v1", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "gitops",
            "drift",
            "--path",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0


def test_cli_gitops_sync_command() -> None:
    """Test CLI command devops argo gitops sync with --dry-run."""
    result = runner.invoke(
        app,
        [
            "gitops",
            "sync",
            "--app-name",
            "root-app",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "DryRun" in result.output or "root-app" in result.output


def test_cli_gitops_subcommand_under_cd(tmp_path: Path) -> None:
    """Test mounting of gitops under devops argo cd."""
    result = runner.invoke(
        app,
        [
            "cd",
            "gitops",
            "watch",
            "--path",
            str(tmp_path),
            "--app-name",
            "root-app",
            "--once",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0


def test_cli_gitops_invalid_app_name() -> None:
    """Test validation rejection of invalid Kubernetes name."""
    result = runner.invoke(
        app,
        [
            "gitops",
            "watch",
            "--app-name",
            "INVALID_NAME!!!",
        ],
    )
    assert result.exit_code != 0
