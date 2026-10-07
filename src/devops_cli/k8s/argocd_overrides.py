"""Argo CD Application overrides that carry the homelab's hosts from the active config.

The repository names every Ingress and IngressRoute host under the placeholder domain
``example.com``. ``devops k8s deploy-stack`` writes the configured domain onto the Applications
that render them, as Kustomize JSON patches in ``spec.source.kustomize``, and the ``cluster``
app-of-apps leaves that field alone (``k8s/argocd/bootstrap/cluster.yaml``). No homelab value
enters git (#1290).
"""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.k8s.template import normalize_domain

PLACEHOLDER_DOMAIN = "example.com"

HOMELAB_APPLICATIONS: tuple[str, ...] = ("devops", "ingress")
"""The Applications whose rendered hosts come from the configured domain."""

_PLACEHOLDER_HOST = re.compile(
    rf"(?<![\w.-])((?:[a-z0-9-]+\.)*){re.escape(PLACEHOLDER_DOMAIN)}(?![\w.-])", re.IGNORECASE
)


def _under(domain: str, value: str) -> str:
    """`value` with every host under the placeholder domain moved under `domain`."""
    return _PLACEHOLDER_HOST.sub(lambda m: f"{m.group(1)}{domain}", value)


def _host_fields(doc: dict[str, Any]) -> list[tuple[str, str]]:
    """The JSON pointer and value of every host an Ingress or IngressRoute routes."""
    spec = doc.get("spec") or {}
    if doc.get("kind") == "Ingress":
        rules = [
            (f"/spec/rules/{i}/host", rule["host"])
            for i, rule in enumerate(spec.get("rules") or [])
            if isinstance(rule, dict) and "host" in rule
        ]
        tls = [
            (f"/spec/tls/{i}/hosts/{j}", host)
            for i, entry in enumerate(spec.get("tls") or [])
            if isinstance(entry, dict)
            for j, host in enumerate(entry.get("hosts") or [])
        ]
        return rules + tls
    if doc.get("kind") == "IngressRoute":
        return [
            (f"/spec/routes/{i}/match", route["match"])
            for i, route in enumerate(spec.get("routes") or [])
            if isinstance(route, dict) and "match" in route
        ]
    return []


def _target(doc: dict[str, Any]) -> dict[str, str]:
    """The Kustomize patch target selecting exactly `doc`."""
    group, _, version = str(doc["apiVersion"]).rpartition("/")
    metadata = doc.get("metadata") or {}
    target = {"group": group, "version": version, "kind": doc["kind"], "name": metadata["name"]}
    if metadata.get("namespace"):
        target["namespace"] = metadata["namespace"]
    return target


def host_patches(rendered: str, domain: str) -> list[dict[str, Any]]:
    """One Kustomize JSON patch per object in `rendered` that routes a host under the placeholder.

    Each such host is first tested, then replaced by the same host under `domain`. A rule that
    git has moved since fails the Application's manifest generation instead of sending a host to
    another backend.
    """
    configured = normalize_domain(domain)
    patches = []
    for doc in yaml.safe_load_all(rendered):
        if not isinstance(doc, dict):
            continue
        ops = []
        for pointer, value in _host_fields(doc):
            pinned = _under(configured, value)
            if pinned != value:
                ops += [
                    {"op": "test", "path": pointer, "value": value},
                    {"op": "replace", "path": pointer, "value": pinned},
                ]
        if ops:
            patches.append({"target": _target(doc), "patch": json.dumps(ops)})
    return patches


def application_patch(patches: list[dict[str, Any]]) -> dict[str, Any]:
    """The merge patch that makes `patches` an Application's Kustomize patches."""
    return {"spec": {"source": {"kustomize": {"patches": patches}}}}


def application_source_dir(k8s_dir: Path, application: str) -> Path:
    """The directory under `k8s_dir` that Application `application` renders."""
    manifest = k8s_dir / "argocd" / "apps" / f"{application}.yaml"
    source = PurePosixPath(
        yaml.safe_load(manifest.read_text(encoding="utf-8"))["spec"]["source"]["path"]
    )
    if source.parts[:1] != ("k8s",):
        raise KubernetesContextError(
            f"Argo CD Application '{application}' renders {source}, which is outside k8s/."
        )
    return k8s_dir.joinpath(*source.parts[1:])
