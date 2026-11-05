"""The host overrides of the Argo CD Applications (#2164)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.config.constants import CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS
from devops_cli.k8s.argocd_overrides import host_patches
from tests.gate.k8s_render import kustomize
from tests.support.paths import REPO_ROOT

K8S_DIR = REPO_ROOT / "k8s"


DOMAIN = "example.org"


def _document_hosts(documents: Iterator[dict[str, Any] | None]) -> list[str]:
    hosts = []
    for doc in documents:
        if not isinstance(doc, dict):
            continue
        if doc.get("kind") == "Ingress":
            hosts += [rule["host"] for rule in doc["spec"]["rules"] if "host" in rule]
        if doc.get("kind") == "IngressRoute":
            hosts += [route["match"] for route in doc["spec"]["routes"]]
        if doc.get("kind") == "Mattermost":
            ingress = doc.get("spec", {}).get("ingress", {})
            if host := ingress.get("host"):
                hosts.append(host)
    return hosts


def _hosts(rendered: str) -> list[str]:
    return _document_hosts(yaml.safe_load_all(rendered))


def _overlay(tmp_path: Path, source: Path, patches: list[dict]) -> Path:
    """A kustomization over `source` with `patches`, the way Argo CD builds an Application."""
    (tmp_path / "kustomization.yaml").write_text(
        yaml.safe_dump({"resources": [os.path.relpath(source, tmp_path)], "patches": patches}),
        encoding="utf-8",
    )
    return tmp_path


@pytest.mark.parametrize("application", CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS)
def check_kustomize_applies_the_overrides_to_every_host_the_application_renders(
    application: str, tmp_path: Path
) -> None:
    manifest = yaml.safe_load((K8S_DIR / "argocd" / "apps" / f"{application}.yaml").read_text())
    source = REPO_ROOT / manifest["spec"]["source"]["path"]
    before = kustomize(source, check=False).stdout
    after = kustomize(_overlay(tmp_path, source, host_patches(before, DOMAIN)), check=False)
    hosts = _hosts(after.stdout)
    assert (
        after.returncode,
        len(hosts) == len(_hosts(before)) > 0,
        [h for h in hosts if "example.com" in h],
        all("example.org" in h for h in hosts),
    ) == (0, True, [], True)
