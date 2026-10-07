"""Deploy-time Argo CD Application overrides carry the homelab hosts the repository never holds (#1290)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.k8s.argocd_overrides import (
    HOMELAB_APPLICATIONS,
    application_patch,
    application_source_dir,
    host_patches,
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


def test_each_homelab_application_names_its_directory_under_the_k8s_dir() -> None:
    assert {app: application_source_dir(K8S_DIR, app) for app in HOMELAB_APPLICATIONS} == {
        "devops": K8S_DIR / "overlays" / "homelab" / "devops",
        "ingress": K8S_DIR / "overlays" / "homelab" / "ingress",
    }


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


@pytest.mark.parametrize("application", HOMELAB_APPLICATIONS)
def test_kustomize_applies_the_overrides_to_every_host_the_application_renders(
    application: str, tmp_path: Path
) -> None:
    source = application_source_dir(K8S_DIR, application)
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
