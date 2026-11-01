"""Tests for Argo CD models."""

from devops_cli.models.argo import ArgoCDApp, ArgoResourceState


def test_argocd_app_from_api_item_single_source() -> None:
    """Test that ArgoCDApp.from_api_item reads repoURL from spec.source when present."""
    item = {
        "metadata": {"name": "test-app"},
        "spec": {"source": {"repoURL": "https://github.com/example/test-repo.git"}},
        "status": {
            "sync": {"status": "Synced", "revision": "abc123"},
            "health": {"status": "Healthy"},
        },
    }

    app = ArgoCDApp.from_api_item(item)
    assert app.repo_url == "https://github.com/example/test-repo.git"


def test_argocd_app_from_api_item_multi_source() -> None:
    """Test that ArgoCDApp.from_api_item falls back to spec.sources[0].repoURL when spec.source is absent."""
    item = {
        "metadata": {"name": "test-app"},
        "spec": {"sources": [{"repoURL": "https://github.com/example/test-repo.git"}]},
        "status": {
            "sync": {"status": "Synced", "revision": "abc123"},
            "health": {"status": "Healthy"},
        },
    }

    app = ArgoCDApp.from_api_item(item)
    assert app.repo_url == "https://github.com/example/test-repo.git"


def test_argocd_app_from_api_item_no_source() -> None:
    """Test that ArgoCDApp.from_api_item returns empty string when neither spec.source nor spec.sources is present."""
    item = {
        "metadata": {"name": "test-app"},
        "spec": {},
        "status": {
            "sync": {"status": "Synced", "revision": "abc123"},
            "health": {"status": "Healthy"},
        },
    }

    app = ArgoCDApp.from_api_item(item)
    assert app.repo_url == ""


def test_argocd_resource_state_from_manifest_single_source() -> None:
    """Test that ArgoResourceState.from_manifest reads repoURL from spec.source when present."""
    manifest = {
        "metadata": {"name": "test-app", "namespace": "argocd"},
        "spec": {
            "source": {"repoURL": "https://github.com/example/test-repo.git"},
            "project": "test-project",
        },
        "status": {
            "sync": {"status": "Synced", "revision": "abc123"},
            "health": {"status": "Healthy"},
        },
        "kind": "Application",
    }

    state = ArgoResourceState.from_manifest(manifest)
    assert state.repo_url == "https://github.com/example/test-repo.git"


def test_argocd_resource_state_from_manifest_multi_source() -> None:
    """Test that ArgoResourceState.from_manifest falls back to spec.sources[0].repoURL when spec.source is absent."""
    manifest = {
        "metadata": {"name": "test-app", "namespace": "argocd"},
        "spec": {
            "sources": [{"repoURL": "https://github.com/example/test-repo.git"}],
            "project": "test-project",
        },
        "status": {
            "sync": {"status": "Synced", "revision": "abc123"},
            "health": {"status": "Healthy"},
        },
        "kind": "Application",
    }

    state = ArgoResourceState.from_manifest(manifest)
    assert state.repo_url == "https://github.com/example/test-repo.git"


def test_argocd_resource_state_from_manifest_no_source() -> None:
    """Test that ArgoResourceState.from_manifest returns empty string when neither spec.source nor spec.sources is present."""
    manifest = {
        "metadata": {"name": "test-app", "namespace": "argocd"},
        "spec": {"project": "test-project"},
        "status": {
            "sync": {"status": "Synced", "revision": "abc123"},
            "health": {"status": "Healthy"},
        },
        "kind": "Application",
    }

    state = ArgoResourceState.from_manifest(manifest)
    assert state.repo_url == ""
