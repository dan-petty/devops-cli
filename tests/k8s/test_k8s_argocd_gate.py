"""Tests for the deterministic offline Argo CD application build gate (#1343)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import yaml

from devops_cli.exceptions.k8s import ArgoCDGateError
from devops_cli.k8s.argocd_gate import check_argocd_gate


def _git_run(cwd: Path, *args: str) -> str:
    res = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return res.stdout.strip()


def _write_app(
    tree: Path,
    name: str,
    *,
    path: str | None = None,
    repo_url: str = "https://github.com/dan-petty/devops-cli",
    value_files: list[str] | None = None,
    chart: str | None = None,
    is_bootstrap: bool = False,
) -> None:
    target_dir = tree / ("k8s/argocd/bootstrap" if is_bootstrap else "k8s/argocd/apps")
    target_dir.mkdir(parents=True, exist_ok=True)
    app_file = target_dir / f"{name}.yaml"

    spec: dict[str, Any] = {
        "project": "homelab",
        "destination": {"server": "https://kubernetes.default.svc", "namespace": name},
    }

    if chart is not None:
        spec["sources"] = [
            {
                "repoURL": "https://example.com/charts",
                "chart": chart,
                "targetRevision": "1.0.0",
                "helm": {"valueFiles": value_files or []},
            },
            {
                "repoURL": repo_url,
                "targetRevision": "main",
                "ref": "values",
            },
        ]
    elif path is not None:
        spec["source"] = {
            "repoURL": repo_url,
            "targetRevision": "main",
            "path": path,
        }

    doc = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {"name": name, "namespace": "argocd"},
        "spec": spec,
    }
    app_file.write_text(yaml.dump(doc), encoding="utf-8")


def test_a_kustomization_that_lists_a_missing_file_fails(tmp_path: Path) -> None:
    _write_app(tmp_path, "broken", path="k8s/broken")
    app_dir = tmp_path / "k8s" / "broken"
    app_dir.mkdir(parents=True)
    (app_dir / "kustomization.yaml").write_text(
        "apiVersion: kustomize.config.k8s.io/v1beta1\n"
        "kind: Kustomization\n"
        "resources:\n"
        "  - nonexistent.yaml\n",
        encoding="utf-8",
    )

    with pytest.raises(ArgoCDGateError) as exc_info:
        check_argocd_gate(tmp_path)

    err = str(exc_info.value)
    assert ("broken" in err, "nonexistent.yaml" in err) == (True, True)


def test_a_placeholder_in_a_configmap_of_devops_fails(tmp_path: Path) -> None:
    _write_app(tmp_path, "devops", path="k8s/overlays/homelab/devops")
    devops_dir = tmp_path / "k8s" / "overlays" / "homelab" / "devops"
    devops_dir.mkdir(parents=True)
    (devops_dir / "kustomization.yaml").write_text(
        "apiVersion: kustomize.config.k8s.io/v1beta1\n"
        "kind: Kustomization\n"
        "resources:\n"
        "  - configmap.yaml\n",
        encoding="utf-8",
    )
    (devops_dir / "configmap.yaml").write_text(
        "apiVersion: v1\n"
        "kind: ConfigMap\n"
        "metadata:\n"
        "  name: devops-config\n"
        "data:\n"
        "  endpoint: http://example.com\n",
        encoding="utf-8",
    )

    with pytest.raises(ArgoCDGateError) as exc_info:
        check_argocd_gate(tmp_path)

    err = str(exc_info.value)
    assert ("devops" in err, "ConfigMap/devops-config" in err, "/data/endpoint" in err) == (
        True,
        True,
        True,
    )


def test_a_placeholder_ingress_host_in_a_non_homelab_application_fails(tmp_path: Path) -> None:
    _write_app(tmp_path, "monitoring", path="k8s/monitoring")
    mon_dir = tmp_path / "k8s" / "monitoring"
    mon_dir.mkdir(parents=True)
    (mon_dir / "kustomization.yaml").write_text(
        "apiVersion: kustomize.config.k8s.io/v1beta1\n"
        "kind: Kustomization\n"
        "resources:\n"
        "  - ingress.yaml\n",
        encoding="utf-8",
    )
    (mon_dir / "ingress.yaml").write_text(
        "apiVersion: networking.k8s.io/v1\n"
        "kind: Ingress\n"
        "metadata:\n"
        "  name: grafana-ingress\n"
        "spec:\n"
        "  rules:\n"
        "    - host: grafana.example.com\n",
        encoding="utf-8",
    )

    with pytest.raises(ArgoCDGateError) as exc_info:
        check_argocd_gate(tmp_path)

    err = str(exc_info.value)
    assert ("monitoring" in err, "Ingress/grafana-ingress" in err, "/spec/rules/0/host" in err) == (
        True,
        True,
        True,
    )


def test_a_placeholder_in_a_helm_value_file_fails(tmp_path: Path) -> None:
    _write_app(
        tmp_path,
        "loki",
        chart="loki",
        value_files=["$values/k8s/logging/loki-values.yaml"],
    )
    val_dir = tmp_path / "k8s" / "logging"
    val_dir.mkdir(parents=True)
    (val_dir / "loki-values.yaml").write_text(
        "external_url: https://example.com\n", encoding="utf-8"
    )

    with pytest.raises(ArgoCDGateError) as exc_info:
        check_argocd_gate(tmp_path)

    err = str(exc_info.value)
    assert ("loki" in err, "loki-values.yaml" in err, "/external_url" in err) == (
        True,
        True,
        True,
    )


def test_a_missing_value_file_fails(tmp_path: Path) -> None:
    _write_app(
        tmp_path,
        "loki",
        chart="loki",
        value_files=["$values/k8s/logging/missing-values.yaml"],
    )

    with pytest.raises(ArgoCDGateError) as exc_info:
        check_argocd_gate(tmp_path)

    err = str(exc_info.value)
    assert ("loki" in err, "missing-values.yaml" in err) == (True, True)


def test_a_path_holding_chart_yaml_fails(tmp_path: Path) -> None:
    _write_app(tmp_path, "custom", path="k8s/custom")
    custom_dir = tmp_path / "k8s" / "custom"
    custom_dir.mkdir(parents=True)
    (custom_dir / "Chart.yaml").write_text(
        "apiVersion: v2\nname: custom\nversion: 0.1.0\n", encoding="utf-8"
    )

    with pytest.raises(ArgoCDGateError) as exc_info:
        check_argocd_gate(tmp_path)

    err = str(exc_info.value)
    assert ("custom" in err, "Chart.yaml" in err) == (True, True)


def test_a_git_source_with_another_repourl_fails(tmp_path: Path) -> None:
    _write_app(
        tmp_path,
        "foreign",
        path="k8s/foreign",
        repo_url="https://github.com/different-org/different-repo",
    )
    foreign_dir = tmp_path / "k8s" / "foreign"
    foreign_dir.mkdir(parents=True)
    (foreign_dir / "manifest.yaml").write_text(
        "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: foreign-cm\n",
        encoding="utf-8",
    )

    with pytest.raises(ArgoCDGateError) as exc_info:
        check_argocd_gate(tmp_path)

    err = str(exc_info.value)
    assert ("foreign" in err, "different-org/different-repo" in err) == (True, True)


def test_a_clean_tree_passes_and_names_each_application_it_built(tmp_path: Path) -> None:
    _write_app(tmp_path, "app-a", path="k8s/app-a")
    a_dir = tmp_path / "k8s" / "app-a"
    a_dir.mkdir(parents=True)
    (a_dir / "kustomization.yaml").write_text(
        "apiVersion: kustomize.config.k8s.io/v1beta1\n"
        "kind: Kustomization\n"
        "resources:\n"
        "  - cm.yaml\n",
        encoding="utf-8",
    )
    (a_dir / "cm.yaml").write_text(
        "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: clean-cm\n",
        encoding="utf-8",
    )

    _write_app(
        tmp_path,
        "app-b",
        chart="my-chart",
        value_files=["$values/k8s/my-values.yaml"],
    )
    (tmp_path / "k8s" / "my-values.yaml").write_text("replicas: 2\n", encoding="utf-8")

    built = check_argocd_gate(tmp_path)
    assert built == ["app-a", "app-b"]


def test_a_tree_with_no_k8s_argocd_passes(tmp_path: Path) -> None:
    built = check_argocd_gate(tmp_path)
    assert built == []


def test_a_missing_kubectl_fails_naming_devops_install_tools(tmp_path: Path) -> None:
    _write_app(tmp_path, "clean-app", path="k8s/clean-app")
    app_dir = tmp_path / "k8s" / "clean-app"
    app_dir.mkdir(parents=True)
    (app_dir / "cm.yaml").write_text(
        "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: clean-cm\n",
        encoding="utf-8",
    )

    with patch("shutil.which", return_value=None):
        with pytest.raises(ArgoCDGateError) as exc_info:
            check_argocd_gate(tmp_path)

    err = str(exc_info.value)
    assert "devops install-tools --tool kubectl" in err


def test_a_file_in_working_tree_but_not_in_commit_does_not_reach_the_build(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_run(repo, "init", "--quiet")
    _git_run(repo, "config", "user.name", "Tester")
    _git_run(repo, "config", "user.email", "test@example.com")

    _write_app(repo, "tested-app", path="k8s/tested-app")
    app_dir = repo / "k8s" / "tested-app"
    app_dir.mkdir(parents=True)
    (app_dir / "kustomization.yaml").write_text(
        "apiVersion: kustomize.config.k8s.io/v1beta1\n"
        "kind: Kustomization\n"
        "resources:\n"
        "  - uncommitted.yaml\n",
        encoding="utf-8",
    )
    _git_run(repo, "add", "-A")
    _git_run(repo, "commit", "--quiet", "-m", "init commit")

    # Now create uncommitted.yaml in the working tree only:
    (app_dir / "uncommitted.yaml").write_text(
        "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: uncommitted-cm\n",
        encoding="utf-8",
    )

    # Building from HEAD via git archive will not see uncommitted.yaml:
    with pytest.raises(ArgoCDGateError) as exc_info:
        check_argocd_gate(repo, ref="HEAD")

    err = str(exc_info.value)
    assert ("tested-app" in err, "uncommitted.yaml" in err) == (True, True)
