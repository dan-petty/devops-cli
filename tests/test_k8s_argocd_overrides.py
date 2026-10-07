"""Deploy-time Argo CD Application overrides carry the homelab hosts the repository never holds (#1290)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from devops_cli.config.constants import CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS
from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.k8s.argocd_overrides import (
    ApplicationSource,
    application_patch,
    application_source,
    host_patches,
    render_at_revision,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
K8S_DIR = REPO_ROOT / "k8s"
# The configured domain has to differ from the repository's placeholder, example.com, for a
# substitution to show; example.org is reserved for documentation by RFC 2606 like example.com.
DOMAIN = "example.org"

RENDERED = """\
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: chat
  namespace: llm
spec:
  rules:
    - host: chat.example.com
    - host: example.com
    - host: "*.example.com"
  tls:
    - hosts:
        - chat.example.com
---
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: dashboard
  namespace: kube-system
spec:
  routes:
    - match: Host(`traefik.example.com`) && PathPrefix(`/dashboard`)
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: local
  namespace: llm
spec:
  rules:
    - host: localhost
---
apiVersion: v1
kind: Service
metadata:
  name: chat
  namespace: llm
"""


def _decoded(patches: list[dict]) -> list[tuple[dict, list[dict]]]:
    return [(p["target"], json.loads(p["patch"])) for p in patches]


def test_each_placeholder_host_is_checked_then_set_to_the_configured_domain() -> None:
    ingress = {"group": "networking.k8s.io", "version": "v1", "kind": "Ingress"}
    route = {"group": "traefik.io", "version": "v1alpha1", "kind": "IngressRoute"}
    assert _decoded(host_patches(RENDERED, DOMAIN)) == [
        (
            {**ingress, "name": "chat", "namespace": "llm"},
            [
                {"op": "test", "path": "/spec/rules/0/host", "value": "chat.example.com"},
                {"op": "replace", "path": "/spec/rules/0/host", "value": "chat.example.org"},
                {"op": "test", "path": "/spec/rules/1/host", "value": "example.com"},
                {"op": "replace", "path": "/spec/rules/1/host", "value": "example.org"},
                {"op": "test", "path": "/spec/rules/2/host", "value": "*.example.com"},
                {"op": "replace", "path": "/spec/rules/2/host", "value": "*.example.org"},
                {"op": "test", "path": "/spec/tls/0/hosts/0", "value": "chat.example.com"},
                {"op": "replace", "path": "/spec/tls/0/hosts/0", "value": "chat.example.org"},
            ],
        ),
        (
            {**route, "name": "dashboard", "namespace": "kube-system"},
            [
                {
                    "op": "test",
                    "path": "/spec/routes/0/match",
                    "value": "Host(`traefik.example.com`) && PathPrefix(`/dashboard`)",
                },
                {
                    "op": "replace",
                    "path": "/spec/routes/0/match",
                    "value": "Host(`traefik.example.org`) && PathPrefix(`/dashboard`)",
                },
            ],
        ),
    ]


def test_a_domain_that_is_not_a_hostname_is_refused() -> None:
    with pytest.raises(KubernetesContextError, match="Invalid domain name"):
        host_patches(RENDERED, "not a domain")


def test_the_patch_sets_the_kustomize_patches_of_the_application_source() -> None:
    patches = host_patches(RENDERED, DOMAIN)
    assert application_patch(patches) == {"spec": {"source": {"kustomize": {"patches": patches}}}}


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        ({"sources": [{"repoURL": "https://example.com/repo"}]}, "several sources"),
        ({"source": {"path": "k8s/x"}}, "names no spec.source.repoURL"),
    ],
)
def test_an_application_the_overrides_cannot_follow_is_refused_by_name(
    spec: dict, message: str
) -> None:
    printed = json.dumps({"metadata": {"name": "ingress"}, "spec": spec})
    with pytest.raises(KubernetesContextError, match=f"Application 'ingress' .*{message}"):
        application_source(printed)


def test_a_revision_or_repository_from_the_cluster_is_never_read_as_a_git_option(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path, "chat.example.com")
    marker = tmp_path / "marker"
    hostile = ApplicationSource(".", f"--upload-pack=touch {marker}; git-upload-pack", "k8s/app")
    with pytest.raises(KubernetesContextError):
        render_at_revision(hostile, repo / "work", _run)
    assert not marker.exists()


def test_an_applications_source_is_read_from_its_kubectl_json() -> None:
    printed = json.dumps(
        {
            "spec": {
                "source": {
                    "repoURL": "https://example.com/repo",
                    "targetRevision": "main",
                    "path": "k8s/x",
                }
            }
        }
    )
    assert application_source(printed) == ApplicationSource(
        "https://example.com/repo", "main", "k8s/x"
    )


def _run(
    cmd: list[str],
    *,
    check: bool = False,
    capture: bool = True,
    timeout: float | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=check,
        timeout=timeout,
        env={**os.environ, **(env or {})},
    )


def _repo(tmp_path: Path, host: str) -> Path:
    repo = tmp_path / "repo"
    (repo / "k8s" / "app").mkdir(parents=True)
    (repo / "k8s" / "app" / "kustomization.yaml").write_text("resources:\n  - ingress.yaml\n")
    (repo / "k8s" / "app" / "ingress.yaml").write_text(
        "apiVersion: networking.k8s.io/v1\nkind: Ingress\nmetadata:\n  name: chat\n"
        f"spec:\n  rules:\n    - host: {host}\n"
    )
    for cmd in (
        ["init", "-q", "-b", "main"],
        ["add", "-A"],
        ["-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "app"],
    ):
        subprocess.run(["git", "-C", str(repo), *cmd], check=True, capture_output=True)
    return repo


def test_an_application_renders_what_its_revision_holds(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "chat.example.com")
    rendered = render_at_revision(
        ApplicationSource(repo.as_uri(), "main", "k8s/app"), tmp_path / "work", _run
    )
    assert [d["spec"]["rules"] for d in yaml.safe_load_all(rendered)] == [
        [{"host": "chat.example.com"}]
    ]


@pytest.mark.parametrize(
    ("revision", "path", "message"),
    [("main", "../outside", "leaves its repository"), ("missing", "k8s/app", "git -C")],
)
def test_a_revision_that_cannot_render_is_refused(
    tmp_path: Path, revision: str, path: str, message: str
) -> None:
    repo = _repo(tmp_path, "chat.example.com")
    with pytest.raises(KubernetesContextError, match=message):
        render_at_revision(
            ApplicationSource(repo.as_uri(), revision, path), tmp_path / "work", _run
        )


def _kustomize(directory: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["kubectl", "kustomize", str(directory)], capture_output=True, text=True, check=False
    )


def _hosts(rendered: str) -> list[str]:
    hosts = []
    for doc in yaml.safe_load_all(rendered):
        if doc and doc.get("kind") == "Ingress":
            hosts += [rule["host"] for rule in doc["spec"]["rules"] if "host" in rule]
        if doc and doc.get("kind") == "IngressRoute":
            hosts += [route["match"] for route in doc["spec"]["routes"]]
    return hosts


def _overlay(tmp_path: Path, source: Path, patches: list[dict]) -> Path:
    """A kustomization over `source` with `patches`, the way Argo CD builds an Application."""
    (tmp_path / "kustomization.yaml").write_text(
        yaml.safe_dump({"resources": [os.path.relpath(source, tmp_path)], "patches": patches}),
        encoding="utf-8",
    )
    return tmp_path


@pytest.mark.parametrize("application", CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS)
def test_kustomize_applies_the_overrides_to_every_host_the_application_renders(
    application: str, tmp_path: Path
) -> None:
    manifest = yaml.safe_load((K8S_DIR / "argocd" / "apps" / f"{application}.yaml").read_text())
    source = REPO_ROOT / manifest["spec"]["source"]["path"]
    before = _kustomize(source).stdout
    after = _kustomize(_overlay(tmp_path, source, host_patches(before, DOMAIN)))
    hosts = _hosts(after.stdout)
    assert (
        after.returncode,
        len(hosts) == len(_hosts(before)) > 0,
        [h for h in hosts if "example.com" in h],
        all("example.org" in h for h in hosts),
    ) == (0, True, [], True)


def test_overrides_fail_the_build_when_git_moved_a_host_rather_than_route_it_elsewhere(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "ingress.yaml").write_text(RENDERED, encoding="utf-8")
    (source / "kustomization.yaml").write_text("resources:\n  - ingress.yaml\n", encoding="utf-8")
    patches = host_patches(RENDERED, DOMAIN)
    swapped = RENDERED.replace("chat.example.com", "SWAP").replace(
        "- host: example.com", "- host: chat.example.com"
    )
    (source / "ingress.yaml").write_text(swapped.replace("SWAP", "example.com"), encoding="utf-8")
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    result = _kustomize(_overlay(overlay, source, patches))
    assert (result.returncode != 0, "test" in result.stderr.lower()) == (True, True)
