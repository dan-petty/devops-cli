"""Tests for argo command input validation and CLI execution."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from devops_cli.commands.argo import _validate_k8s_name
from devops_cli.commands.argo import app as argo_app
from devops_cli.main import app as main_app

runner = CliRunner()


def _mock_proc(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["argocd"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


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

    # Full item
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

    # Empty / malformed item defaults safely
    empty_app = ArgoCDApp.from_api_item({})
    assert empty_app.name == ""
    assert empty_app.sync_status == "Unknown"
    assert empty_app.health_status == "Unknown"


def test_argo_commands_execution() -> None:
    """Verify argo list and status subcommands."""
    mock_apps = {
        "items": [
            {
                "metadata": {"name": "guestbook", "namespace": "argocd"},
                "status": {"sync": {"status": "Synced"}, "health": {"status": "Healthy"}},
            }
        ]
    }
    with (
        patch(
            "devops_cli.core.process.run_subprocess",
            return_value=_mock_proc(0, json.dumps(mock_apps)),
        ),
        patch(
            "devops_cli.commands.argo.run_subprocess",
            return_value=_mock_proc(0, "OK"),
        ),
    ):
        res_list = runner.invoke(main_app, ["--dry-run", "argo", "list"])
        assert res_list.exit_code == 0

        res_status = runner.invoke(main_app, ["--dry-run", "argo", "status", "guestbook"])
        assert res_status.exit_code == 0

        res_workflows = runner.invoke(argo_app, ["workflows", "list"])
        assert res_workflows.exit_code == 0

        res_rollouts = runner.invoke(argo_app, ["rollouts", "list"])
        assert res_rollouts.exit_code == 0
