"""Argo CD Application overrides that carry the homelab's hosts from the active config.

The repository names every Ingress and IngressRoute host under the placeholder domain
(``CONST_K8S_TEMPLATE_DOMAIN_PLACEHOLDER``). ``devops k8s deploy-stack`` builds what each
homelab Application renders at the revision Argo CD builds, and writes the configured domain onto
the Application as Kustomize JSON patches in ``spec.source.kustomize``, which the ``cluster``
app-of-apps leaves alone (``k8s/argocd/bootstrap/cluster.yaml``). No homelab value enters git
(#1290).
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.k8s.template import normalize_domain, render_manifest_template

Run = Callable[..., subprocess.CompletedProcess[str]]
"""Runs a command as ``devops_cli.commands.k8s.cluster_runtime._run_cmd`` does."""


@dataclass(frozen=True)
class ApplicationSource:
    """The repository, revision and path an Argo CD Application renders."""

    repo_url: str
    revision: str
    path: str


def application_source(application_json: str) -> ApplicationSource:
    """The source of an Application as ``kubectl get application -o json`` prints it."""
    source = json.loads(application_json)["spec"]["source"]
    return ApplicationSource(
        repo_url=source["repoURL"],
        revision=source.get("targetRevision") or "HEAD",
        path=source.get("path") or ".",
    )


def _stdout(result: subprocess.CompletedProcess[str], cmd: list[str]) -> str:
    if result.returncode != 0:
        reason = (result.stderr or result.stdout or "").strip()
        raise KubernetesContextError(f"`{' '.join(cmd)}` failed: {reason}")
    return result.stdout or ""


def render_at_revision(source: ApplicationSource, workdir: Path, run: Run) -> str:
    """What Argo CD renders for `source`: its path built by Kustomize at its revision.

    The revision is fetched into `workdir`, never into the caller's checkout, so the hosts come
    from what Argo CD builds whichever branch the caller has checked out.
    """
    checkout = workdir / "checkout"
    for cmd in (
        ["git", "init", "--quiet", str(checkout)],
        [
            "git",
            "-C",
            str(checkout),
            "fetch",
            "--quiet",
            "--depth",
            "1",
            source.repo_url,
            source.revision,
        ],
        ["git", "-C", str(checkout), "checkout", "--quiet", "FETCH_HEAD"],
    ):
        _stdout(run(cmd, check=False, capture=True), cmd)
    target = (checkout / source.path).resolve()
    if not target.is_relative_to(checkout.resolve()):
        raise KubernetesContextError(f"Application path {source.path!r} leaves its repository.")
    cmd = ["kubectl", "kustomize", str(target)]
    return _stdout(run(cmd, check=False, capture=True), cmd)


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

    Each such host is first tested, then replaced by the same host under `domain`, substituted
    as ``render_manifest_template`` does for native deploys. A host that git has since reordered
    or removed within its object fails the Application's manifest generation instead of routing
    to another backend. Kustomize skips a patch whose object no longer exists, and nothing covers
    an object or host git adds, so deploy-stack runs again once such a change reaches the
    Application's revision.
    """
    configured = normalize_domain(domain)
    patches = []
    for doc in yaml.safe_load_all(rendered):
        if not isinstance(doc, dict):
            continue
        ops = []
        for pointer, value in _host_fields(doc):
            pinned = render_manifest_template(value, domain=configured)
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
