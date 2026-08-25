"""Tests for argo command input validation."""

from __future__ import annotations

import pytest
import typer

from devops_cli.commands.argo import _validate_k8s_name


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
    app = ArgoCDApp.from_api_item(item)
    assert app.name == "frontend-app"
    assert app.project == "default"
    assert app.sync_status == "Synced"
    assert app.health_status == "Healthy"
    assert app.repo_url == "https://github.com/org/repo.git"
    assert app.revision == "abcdef12"

    # Empty / malformed item defaults safely
    empty_app = ArgoCDApp.from_api_item({})
    assert empty_app.name == ""
    assert empty_app.sync_status == "Unknown"
    assert empty_app.health_status == "Unknown"
