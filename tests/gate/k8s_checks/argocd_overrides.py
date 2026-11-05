"""The host patches over the committed overlays (#2164)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

from devops_cli.k8s.argocd_overrides import (
    host_patches,
)
from tests.gate.k8s_render import kustomize
from tests.support.paths import REPO_ROOT

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


def _overlay(tmp_path: Path, source: Path, patches: list[dict]) -> Path:
    """A kustomization over `source` with `patches`, the way Argo CD builds an Application."""
    (tmp_path / "kustomization.yaml").write_text(
        yaml.safe_dump({"resources": [os.path.relpath(source, tmp_path)], "patches": patches}),
        encoding="utf-8",
    )
    return tmp_path


def check_overrides_fail_the_build_when_git_moved_a_host_rather_than_route_it_elsewhere(
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
    result = kustomize(_overlay(overlay, source, patches), check=False)
    assert (result.returncode != 0, "test" in result.stderr.lower()) == (True, True)


def check_host_patches_over_k8s_mattermost() -> None:
    """host_patches over kustomize k8s/mattermost gives one patch for the Mattermost object (#1391)."""
    rendered = kustomize(K8S_DIR / "mattermost").stdout
    patches = host_patches(rendered, DOMAIN)
    assert len(patches) == 1
    target = patches[0]["target"]
    assert (target["kind"], target["name"], target["namespace"]) == (
        "Mattermost",
        "mattermost",
        "mattermost",
    )
    ops = json.loads(patches[0]["patch"])
    assert ops == [
        {"op": "test", "path": "/spec/ingress/host", "value": "mattermost.example.com"},
        {"op": "replace", "path": "/spec/ingress/host", "value": f"mattermost.{DOMAIN}"},
    ]
