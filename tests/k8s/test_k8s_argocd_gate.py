"""Tests for the deterministic offline Argo CD application build gate (#1343)."""

from __future__ import annotations

import io
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import yaml

from devops_cli.exceptions.k8s import ArgoCDGateError
from devops_cli.k8s.argocd_gate import check_argocd_gate
from devops_cli.k8s.environment import EnvironmentTree
from tests.support.fakes.git import GitFake
from tests.support.fakes.process import ProcessAnswer, ProcessCall


@pytest.fixture(autouse=True)
def _stub_git(git_fake: GitFake, monkeypatch: pytest.MonkeyPatch) -> GitFake:
    """git and `kubectl kustomize` answer from the fake. The lookup of kubectl on PATH is part of
    its fake, so the gate finds kubectl on a host that holds none, such as the runner image of the
    roadmap jobs (#5132)."""
    real_which = shutil.which

    def which(cmd: str, *args: Any, **kwargs: Any) -> str | None:
        if Path(cmd).name == "kubectl":
            return "/usr/local/bin/kubectl"
        return real_which(cmd, *args, **kwargs)

    monkeypatch.setattr(shutil, "which", which)
    git_fake.answer(
        lambda call: "config" in call.argv and "remote.origin.url" in call.argv,
        ProcessAnswer(returncode=1, stdout="", stderr=""),
    )

    def _handle_kubectl(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        target = Path(call.argv[2])
        kust_file = target / "kustomization.yaml"
        if kust_file.exists():
            data = yaml.safe_load(kust_file.read_text(encoding="utf-8")) or {}
            parts = []
            for r in data.get("resources", []):
                rf = target / r
                if not rf.exists():
                    return subprocess.CompletedProcess(
                        list(call.argv),
                        1,
                        "",
                        f"kubectl kustomize: error reading {rf}: no such file or directory",
                    )
                parts.append(rf.read_text(encoding="utf-8"))
            return subprocess.CompletedProcess(list(call.argv), 0, "\n---\n".join(parts), "")
        return subprocess.CompletedProcess(list(call.argv), 1, "", f"no kustomization at {target}")

    git_fake.answer(
        lambda call: len(call.argv) > 1 and call.argv[1] == "kustomize",
        ProcessAnswer(side_effect=_handle_kubectl),
    )
    return git_fake


def _env(root: Path) -> EnvironmentTree:
    """The environment tree `k8s` of the repository at `root`."""
    return EnvironmentTree(root / "k8s", root)


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
        check_argocd_gate(_env(tmp_path))

    err = str(exc_info.value)
    assert ("broken" in err, "nonexistent.yaml" in err) == (True, True)


def test_a_placeholder_in_a_configmap_of_devops_fails_only_outside_its_data_values(
    tmp_path: Path,
) -> None:
    """deploy-stack sets the configured domain in a data value of a homelab ConfigMap, so the
    gate allows the placeholder there and refuses it in each other field (#5306)."""
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
        "  annotations:\n"
        "    note: start.example.com\n"
        "data:\n"
        "  endpoint: http://example.com\n",
        encoding="utf-8",
    )

    with pytest.raises(ArgoCDGateError) as exc_info:
        check_argocd_gate(_env(tmp_path))

    assert exc_info.value.failures == {
        "devops": [
            "Placeholder domain value 'start.example.com' at ConfigMap/devops-config "
            "/metadata/annotations/note is not permitted in application 'devops'"
        ]
    }


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
        check_argocd_gate(_env(tmp_path))

    err = str(exc_info.value)
    assert ("monitoring" in err, "Ingress/grafana-ingress" in err, "/spec/rules/0/host" in err) == (
        True,
        True,
        True,
    )


def test_a_placeholder_in_a_devops_deployment_fails_only_outside_its_env_values(
    tmp_path: Path,
) -> None:
    """deploy-stack sets the configured domain in an env value of a homelab Deployment, so the
    gate allows the placeholder there and refuses it in each other field (#4542)."""
    _write_app(tmp_path, "devops", path="k8s/devops")
    devops_dir = tmp_path / "k8s" / "devops"
    devops_dir.mkdir(parents=True)
    (devops_dir / "kustomization.yaml").write_text(
        "apiVersion: kustomize.config.k8s.io/v1beta1\n"
        "kind: Kustomization\n"
        "resources:\n"
        "  - deployment.yaml\n",
        encoding="utf-8",
    )
    (devops_dir / "deployment.yaml").write_text(
        "apiVersion: apps/v1\n"
        "kind: Deployment\n"
        "metadata:\n"
        "  name: start\n"
        "spec:\n"
        "  template:\n"
        "    spec:\n"
        "      initContainers:\n"
        "        - name: wait\n"
        "          env:\n"
        "            - name: TARGET\n"
        "              value: start.example.com\n"
        "      containers:\n"
        "        - name: homepage\n"
        "          args: ['--host', 'start.example.com']\n"
        "          env:\n"
        "            - name: HOMEPAGE_VAR_DOMAIN\n"
        "              value: example.com\n",
        encoding="utf-8",
    )

    with pytest.raises(ArgoCDGateError) as exc_info:
        check_argocd_gate(_env(tmp_path))

    assert exc_info.value.failures == {
        "devops": [
            "Placeholder domain value 'start.example.com' at Deployment/start "
            "/spec/template/spec/containers/0/args/1 is not permitted in application 'devops'"
        ]
    }


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
        check_argocd_gate(_env(tmp_path))

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
        check_argocd_gate(_env(tmp_path))

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
        check_argocd_gate(_env(tmp_path))

    err = str(exc_info.value)
    assert ("custom" in err, "Chart.yaml" in err) == (True, True)


def _serve_repository(git_fake: GitFake, files: dict[str, str], *, error: str = "") -> None:
    """git fetches another repository: `git init` makes the folder, and the fetch writes `files`
    into it, or fails with `error`."""

    def init(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        Path(call.argv[-1]).mkdir(parents=True)
        return subprocess.CompletedProcess(list(call.argv), 0, "", "")

    def fetch(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        if error:
            return subprocess.CompletedProcess(list(call.argv), 128, "", error)
        for name, text in files.items():
            target = Path(call.argv[2]) / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        return subprocess.CompletedProcess(list(call.argv), 0, "", "")

    git_fake.answer(lambda call: call.argv[:2] == ("git", "init"), ProcessAnswer(side_effect=init))
    git_fake.answer(
        lambda call: call.argv[:1] == ("git",) and "fetch" in call.argv,
        ProcessAnswer(side_effect=fetch),
    )
    git_fake.answer(lambda call: "FETCH_HEAD" in call.argv, ProcessAnswer())


_PRODUCT = "https://github.com/example/product"


def test_the_sources_of_another_public_repository_build_at_their_revision(
    tmp_path: Path, git_fake: GitFake
) -> None:
    """An infra repo whose Application `devops` names the product base of another repository, and
    whose Application `prometheus` has a second ref on it, passes the gate (#5131)."""
    _write_app(tmp_path, "devops", path="k8s/devops", repo_url=_PRODUCT)
    _write_app(
        tmp_path,
        "prometheus",
        chart="prometheus",
        value_files=[
            "$values/k8s/monitoring/prometheus-values.yaml",
            "$product/k8s/devops/monitoring/rules-values.yaml",
        ],
    )
    app = tmp_path / "k8s" / "argocd" / "apps" / "prometheus.yaml"
    doc = yaml.safe_load(app.read_text(encoding="utf-8"))
    doc["spec"]["sources"].append({"repoURL": _PRODUCT, "targetRevision": "main", "ref": "product"})
    app.write_text(yaml.dump(doc), encoding="utf-8")
    (tmp_path / "k8s" / "monitoring").mkdir(parents=True)
    (tmp_path / "k8s" / "monitoring" / "prometheus-values.yaml").write_text(
        "server: {}\n", encoding="utf-8"
    )
    _serve_repository(
        git_fake,
        {
            "k8s/devops/kustomization.yaml": "resources:\n  - cm.yaml\n",
            "k8s/devops/cm.yaml": "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: product\n",
            "k8s/devops/monitoring/rules-values.yaml": "serverFiles: {}\n",
        },
    )

    built = check_argocd_gate(_env(tmp_path))

    fetches = [call.argv for call in git_fake.calls if "fetch" in call.argv]
    assert (built, [argv[-3:] for argv in fetches]) == (
        ["devops", "prometheus"],
        [("--end-of-options", _PRODUCT, "main")],
    )


def test_a_source_of_another_repository_that_does_not_fetch_fails(
    tmp_path: Path, git_fake: GitFake
) -> None:
    _write_app(tmp_path, "foreign", path="k8s/foreign", repo_url=_PRODUCT)
    _serve_repository(git_fake, {}, error="fatal: could not read Username for 'https://github.com'")

    with pytest.raises(ArgoCDGateError) as exc_info:
        check_argocd_gate(_env(tmp_path))

    assert exc_info.value.failures == {
        "foreign": [
            f"The fetch of {_PRODUCT} at main failed: fatal: could not read Username for "
            "'https://github.com'"
        ]
    }


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

    built = check_argocd_gate(_env(tmp_path))
    assert built == ["app-a", "app-b"]


def test_a_tree_with_no_k8s_argocd_passes(tmp_path: Path) -> None:
    built = check_argocd_gate(_env(tmp_path))
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
            check_argocd_gate(_env(tmp_path))

    err = str(exc_info.value)
    assert "devops install-tools --tool kubectl" in err


def test_a_file_in_working_tree_but_not_in_commit_does_not_reach_the_build(
    tmp_path: Path, git_fake: GitFake
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

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

    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w") as tar:
        for p in repo.rglob("*"):
            if p.is_file():
                tar.add(p, arcname=str(p.relative_to(repo)))
    tar_bytes = tar_buf.getvalue()

    # Now create uncommitted.yaml in the working tree only:
    (app_dir / "uncommitted.yaml").write_text(
        "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: uncommitted-cm\n",
        encoding="utf-8",
    )

    git_fake.answer(
        lambda call: "archive" in call.argv,
        ProcessAnswer(
            side_effect=lambda call: subprocess.CompletedProcess[Any](
                list(call.argv),
                0,
                tar_bytes,
                "",
            )
        ),
    )

    # Building from HEAD via git archive will not see uncommitted.yaml:
    with pytest.raises(ArgoCDGateError) as exc_info:
        check_argocd_gate(_env(repo), ref="HEAD")

    err = str(exc_info.value)
    assert ("tested-app" in err, "uncommitted.yaml" in err) == (True, True)
