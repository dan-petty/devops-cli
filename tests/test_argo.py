"""Tests for argo command input validation and CLI execution."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from devops_cli.commands.argo import _validate_k8s_name
from devops_cli.commands.argo import app as argo_app
from devops_cli.config.settings import Settings
from devops_cli.main import app as main_app

runner = CliRunner()


@pytest.mark.parametrize(
    "value",
    [
        "my-namespace",
        "namespace1",
        "a",
        "ab",
        "x" * 63,
    ],
)
def test_valid_k8s_label_names(value: str) -> None:
    _validate_k8s_name(value, "namespace", namespace=True)


@pytest.mark.parametrize(
    "value",
    [
        "; rm -rf /",
        "",
        "UPPERCASE",
        "-leading-dash",
        "trailing-dash-",
        "has.dot",  # dots not allowed in namespace (RFC 1123 label)
        "x" * 64,  # exceeds 63-char label limit
        "../etc/passwd",
        "a b",
    ],
)
def test_invalid_k8s_label_names_rejected(value: str) -> None:
    with pytest.raises(typer.Exit):
        _validate_k8s_name(value, "namespace", namespace=True)


@pytest.mark.parametrize(
    "value",
    [
        "my-workflow",
        "workflow.v2",  # dots allowed in resource names (RFC 1123 subdomain)
        "a",
        "x" * 253,
    ],
)
def test_valid_k8s_resource_names(value: str) -> None:
    _validate_k8s_name(value, "workflow name")


@pytest.mark.parametrize(
    "value",
    [
        "; rm -rf /",
        "",
        "UPPERCASE",
        "-leading",
        "trailing-",
        "x" * 254,  # exceeds 253-char subdomain limit
        "has space",
    ],
)
def test_invalid_k8s_resource_names_rejected(value: str) -> None:
    with pytest.raises(typer.Exit):
        _validate_k8s_name(value, "workflow name")


def test_argocd_app_from_api_item() -> None:
    """Verify ArgoCDApp parses full and partial API responses."""
    from devops_cli.models.argo import ArgoCDApp

    item = {
        "metadata": {"name": "frontend-app"},
        "spec": {"project": "default", "source": {"repoURL": "https://github.com/org/repo.git"}},
        "status": {
            "sync": {"status": "Synced", "revision": "abcdef123456789"},
            "health": {"status": "Healthy"},
        },
    }
    app_obj = ArgoCDApp.from_api_item(item)
    assert app_obj.name == "frontend-app"
    assert app_obj.project == "default"
    assert app_obj.sync_status == "Synced"
    assert app_obj.health_status == "Healthy"
    assert app_obj.repo_url == "https://github.com/org/repo.git"
    assert app_obj.revision == "abcdef12"

    empty_app = ArgoCDApp.from_api_item({})
    assert empty_app.name == ""
    assert empty_app.sync_status == "Unknown"
    assert empty_app.health_status == "Unknown"

    non_dict_item = {
        "metadata": "invalid_meta",
        "spec": 123,
        "status": False,
    }
    non_dict_app = ArgoCDApp.from_api_item(non_dict_item)  # type: ignore[arg-type]
    assert non_dict_app.name == ""
    assert non_dict_app.project == ""

    nested_non_dict_item = {
        "metadata": {},
        "spec": {"source": "invalid_source"},
        "status": {"sync": "invalid_sync", "health": "invalid_health"},
    }
    nested_app = ArgoCDApp.from_api_item(nested_non_dict_item)  # type: ignore[arg-type]
    assert nested_app.repo_url == ""
    assert nested_app.sync_status == "Unknown"
    assert nested_app.health_status == "Unknown"


def test_argo_commands_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify argo cd, workflows, and rollouts subcommands."""
    monkeypatch.setattr(
        "devops_cli.http.validation.validate_service_url", lambda *args, **kwargs: None
    )
    mock_apps = {
        "items": [
            {
                "metadata": {"name": "guestbook", "namespace": "argocd"},
                "spec": {
                    "project": "default",
                    "source": {"repoURL": "https://github.com/org/repo.git"},
                },
                "status": {"sync": {"status": "Synced"}, "health": {"status": "Healthy"}},
            }
        ]
    }
    mock_app_detail = {
        "metadata": {"name": "guestbook", "namespace": "argocd"},
        "spec": {"project": "default", "source": {"repoURL": "https://github.com/org/repo.git"}},
        "status": {
            "sync": {"status": "Synced", "revision": "12345678"},
            "health": {"status": "Healthy"},
        },
    }

    mock_settings = Settings()
    mock_settings.argocd.url = "http://localhost:8080"
    mock_settings.ai.allow_private_network = True

    def mock_get(*args: object, **kwargs: object) -> MagicMock:
        resp = MagicMock()
        resp.status_code = 200
        url_str = ""
        for a in args:
            if isinstance(a, str) and ("http" in a or "/api/" in a):
                url_str = a
                break
        if not url_str and "url" in kwargs:
            url_str = str(kwargs["url"])

        if url_str.endswith("/applications"):
            resp.json.return_value = mock_apps
        else:
            resp.json.return_value = mock_app_detail
        return resp

    def mock_post(*args: object, **kwargs: object) -> MagicMock:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"status": "Synced"}
        return resp

    sample_wf = tmp_path / "workflow.yaml"
    sample_wf.write_text("apiVersion: argoproj.io/v1alpha1\nkind: Workflow\n", encoding="utf-8")

    with (
        patch("devops_cli.commands.argo.httpx2.Client.get", side_effect=mock_get),
        patch("devops_cli.commands.argo.httpx2.Client.post", side_effect=mock_post),
        patch("devops_cli.commands.argo.load_settings", return_value=mock_settings),
        patch("devops_cli.commands.argo.run_subprocess") as mock_subproc,
    ):
        mock_subproc.return_value = MagicMock(returncode=0)

        res_dry_main = runner.invoke(main_app, ["--dry-run", "argo", "cd", "apps", "list"])
        assert res_dry_main.exit_code == 0

        res_list = runner.invoke(argo_app, ["cd", "apps", "list"])
        assert res_list.exit_code == 0

        res_status = runner.invoke(argo_app, ["cd", "apps", "status", "guestbook"])
        assert res_status.exit_code == 0

        res_sync = runner.invoke(argo_app, ["cd", "apps", "sync", "guestbook"])
        assert res_sync.exit_code == 0

        res_wf_list = runner.invoke(argo_app, ["workflows", "list", "--namespace", "argocd"])
        assert res_wf_list.exit_code == 0

        res_wf_submit = runner.invoke(
            argo_app, ["workflows", "submit", str(sample_wf), "--namespace", "argocd", "--wait"]
        )
        assert res_wf_submit.exit_code == 0

        res_wf_logs = runner.invoke(
            argo_app, ["workflows", "logs", "my-wf", "--namespace", "argocd", "--follow"]
        )
        assert res_wf_logs.exit_code == 0

        res_ro_list = runner.invoke(argo_app, ["rollouts", "list", "--namespace", "argocd"])
        assert res_ro_list.exit_code == 0

        res_ro_status = runner.invoke(
            argo_app, ["rollouts", "status", "my-rollout", "--namespace", "argocd", "--watch"]
        )
        assert res_ro_status.exit_code == 0

        # Test bootstrap-gitops dry-run
        res_bg_dry = runner.invoke(
            main_app,
            [
                "--dry-run",
                "argo",
                "cd",
                "apps",
                "bootstrap-gitops",
                "--root-app",
                str(sample_wf),
            ],
        )
        assert res_bg_dry.exit_code == 0
        from devops_cli.dry_run import set_dry_run

        set_dry_run(False)

        # Test bootstrap-gitops execution
        res_bg = runner.invoke(
            argo_app,
            [
                "cd",
                "apps",
                "bootstrap-gitops",
                "--root-app",
                str(sample_wf),
                "--context",
                "minikube",
            ],
        )
        assert res_bg.exit_code == 0

        # Test bootstrap-gitops missing manifest
        res_bg_missing = runner.invoke(
            argo_app,
            [
                "cd",
                "apps",
                "bootstrap-gitops",
                "--root-app",
                str(tmp_path / "nonexistent.yaml"),
            ],
        )
        assert res_bg_missing.exit_code == 1


def test_argo_cd_apps_list_and_status_dry_run() -> None:
    """Verify argo cd apps list and status in dry-run mode."""
    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        res_list = runner.invoke(argo_app, ["cd", "apps", "list"])
        assert res_list.exit_code == 0
        assert "list_argocd_apps" in res_list.output
    finally:
        set_dry_run(False)


def test_argo_cd_apps_list_and_status_render(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify live rendering for argo cd apps list and status."""
    import httpx2

    mock_app_data = {
        "metadata": {"name": "sample-app"},
        "spec": {
            "project": "default",
            "source": {"repoURL": "https://github.com/org/repo.git", "targetRevision": "main"},
        },
        "status": {
            "sync": {"status": "Synced", "revision": "abc1234"},
            "health": {"status": "Healthy"},
        },
    }

    def fake_get(self: object, url: str, **kwargs: object) -> httpx2.Response:
        req = httpx2.Request("GET", url)
        if "/api/v1/applications/sample-app" in url:
            return httpx2.Response(200, json=mock_app_data, request=req)
        return httpx2.Response(200, json={"items": [mock_app_data]}, request=req)

    monkeypatch.setattr(httpx2.Client, "get", fake_get)
    monkeypatch.setattr(
        "devops_cli.commands.argo.validate_service_url", lambda *args, **kwargs: None
    )

    mock_settings = Settings()
    mock_settings.argocd.url = "http://localhost:8080"
    mock_settings.ai.allow_private_network = True

    with patch("devops_cli.commands.argo.load_settings", return_value=mock_settings):
        res_list = runner.invoke(argo_app, ["cd", "apps", "list"])
        assert res_list.exit_code == 0
        assert "sample-app" in res_list.output

        res_status = runner.invoke(argo_app, ["cd", "apps", "status", "sample-app"])
        assert res_status.exit_code == 0
        assert "sample-app" in res_status.output
