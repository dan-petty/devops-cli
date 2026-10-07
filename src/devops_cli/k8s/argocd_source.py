"""Argo CD source parameter overrides generation for local development without git drift."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

from devops_cli.config.defaults import DEFAULT_K8S_DIR
from devops_cli.config.settings import load_settings
from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.k8s.configmap import render_devops_configmap_content


def _resolve_effective_domain(domain: str | None, settings: Any) -> str | None:
    """Resolve effective root domain for Ingress host parameter overrides."""
    if domain and domain.strip():
        return domain.strip().lower().lstrip(".")
    if settings is not None:
        cfg_domain = getattr(getattr(settings, "k8s", None), "domain", None) or getattr(
            getattr(settings, "cloudflare", None), "domain", None
        )
        if cfg_domain and str(cfg_domain).strip():
            return str(cfg_domain).strip().lower().lstrip(".")
    env_domain = os.environ.get("DEVOPS_CLI_K8S_DOMAIN") or os.environ.get("DEVOPS_CLI_DOMAIN")
    if env_domain and env_domain.strip():
        return env_domain.strip().lower().lstrip(".")
    return None


def _build_ingress_patch(domain: str | None) -> str:
    """Build Kustomize Ingress patch for roadmap-service if domain is configured."""
    if not domain:
        return ""
    clean_domain = domain.strip().lower().lstrip(".")
    return (
        "    - patch: |-\n"
        "        apiVersion: networking.k8s.io/v1\n"
        "        kind: Ingress\n"
        "        metadata:\n"
        "          name: roadmap-service\n"
        "          namespace: devops\n"
        "        spec:\n"
        "          rules:\n"
        f"            - host: hooks.{clean_domain}\n"
        "              http:\n"
        "                paths:\n"
        "                  - path: /webhooks/github\n"
        "                    pathType: Prefix\n"
        "                    backend:\n"
        "                      service:\n"
        "                        name: roadmap-service\n"
        "                        port:\n"
        "                          number: 8000\n"
    )


def render_argocd_source_content(
    template_content: str,
    repos: Sequence[str] | None = None,
    machine_account: str | None = None,
    settings: Any = None,
    drain_timeout_seconds: int | None = None,
    poll_interval_seconds: int | None = None,
    domain: str | None = None,
) -> str:
    """Render .argocd-source.yaml content with Kustomize patches for devops-cli-config and roadmap-service."""
    effective_repos = repos
    effective_account = machine_account
    effective_drain = drain_timeout_seconds
    effective_poll = poll_interval_seconds

    if settings is not None:
        svc = getattr(settings, "service", None)
        if effective_repos is None and svc is not None and svc.repos:
            effective_repos = list(svc.repos)
        if effective_account is None:
            effective_account = getattr(svc, "machine_account", None) or getattr(
                getattr(settings, "k8s", None), "github_account", None
            )
        if effective_drain is None and svc is not None:
            effective_drain = getattr(svc, "drain_timeout_seconds", None)
        if effective_poll is None and svc is not None:
            effective_poll = getattr(svc, "poll_interval_seconds", None)

    rendered_cm = render_devops_configmap_content(
        template_content,
        repos=effective_repos,
        machine_account=effective_account,
        drain_timeout_seconds=effective_drain,
        poll_interval_seconds=effective_poll,
    )

    parsed_cm = yaml.safe_load(rendered_cm)
    if not isinstance(parsed_cm, dict) or "data" not in parsed_cm:
        raise KubernetesContextError("Rendered ConfigMap is not a valid Kubernetes resource.")

    inner_cfg = parsed_cm["data"].get("devops-cli.yaml", "")
    indented_inner = "\n".join(
        "            " + line if line.strip() else "" for line in inner_cfg.strip().splitlines()
    )

    effective_domain = _resolve_effective_domain(domain, settings)
    ingress_patch = _build_ingress_patch(effective_domain)

    source_doc = (
        "kustomize:\n"
        "  patches:\n"
        "    - patch: |-\n"
        "        apiVersion: v1\n"
        "        kind: ConfigMap\n"
        "        metadata:\n"
        "          name: devops-cli-config\n"
        "          namespace: devops\n"
        "        data:\n"
        "          devops-cli.yaml: |\n"
        f"{indented_inner}\n"
        f"{ingress_patch}"
    )

    parsed_source = yaml.safe_load(source_doc)
    if (
        not isinstance(parsed_source, dict)
        or "kustomize" not in parsed_source
        or "patches" not in parsed_source["kustomize"]
    ):
        raise KubernetesContextError("Generated .argocd-source.yaml is malformed.")

    return source_doc


def _build_ingress_doc_patch(doc: Any, domain: str) -> dict[str, Any] | None:
    """Build a Kustomize patch object for a single Ingress or IngressRoute document."""
    if not isinstance(doc, dict):
        return None
    name = doc.get("metadata", {}).get("name")
    if name == "roadmap-service":
        return None
    ns = doc.get("metadata", {}).get("namespace")
    kind = doc.get("kind")
    api_ver = doc.get("apiVersion")
    spec = doc.get("spec", {})
    patch_obj: dict[str, Any] = {
        "apiVersion": api_ver,
        "kind": kind,
        "metadata": {"name": name, "namespace": ns},
    }
    if kind == "Ingress":
        new_rules = [
            dict(r, host=r["host"].replace("example.com", domain)) if "host" in r else dict(r)
            for r in spec.get("rules", [])
        ]
        patch_obj["spec"] = {"rules": new_rules}
        return patch_obj
    if kind == "IngressRoute":
        new_routes = [
            dict(r, match=r["match"].replace("example.com", domain)) if "match" in r else dict(r)
            for r in spec.get("routes", [])
        ]
        patch_obj["spec"] = {"routes": new_routes}
        return patch_obj
    return None


def render_ingress_argocd_source_content(
    routes_template_content: str,
    domain: str | None = None,
    settings: Any = None,
) -> str:
    """Render .argocd-source.yaml content with Kustomize patches for ingress routes."""
    effective_domain = _resolve_effective_domain(domain, settings)
    if not effective_domain:
        return "kustomize:\n  patches: []\n"

    parsed_docs = yaml.safe_load_all(routes_template_content)
    patches = [
        patch
        for doc in parsed_docs
        if (patch := _build_ingress_doc_patch(doc, effective_domain)) is not None
    ]

    lines = ["kustomize:", "  patches:"]
    for p in patches:
        dumped = yaml.dump(p, sort_keys=False).strip()
        indented = "\n".join("        " + line for line in dumped.splitlines())
        lines.append("    - patch: |-")
        lines.append(indented)

    source_doc = "\n".join(lines) + "\n"
    parsed_source = yaml.safe_load(source_doc)
    if (
        not isinstance(parsed_source, dict)
        or "kustomize" not in parsed_source
        or "patches" not in parsed_source["kustomize"]
    ):
        raise KubernetesContextError("Generated .argocd-source.yaml is malformed.")

    return source_doc


def _locate_configmap_template(base_dir: Path) -> Path:
    """Locate ConfigMap template under devops directory."""
    for name in ("configmap.yaml", "configmap.example.yaml"):
        candidate = base_dir / "devops" / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"DevOps ConfigMap template not found under {base_dir / 'devops'}. "
        "Ensure k8s/devops/configmap.yaml or configmap.example.yaml exists."
    )


def _locate_ingress_routes_template(base_dir: Path) -> Path | None:
    """Locate ingress-routes.yaml template under ingress directory."""
    candidate = base_dir / "ingress" / "ingress-routes.yaml"
    return candidate if candidate.is_file() else None


def _categorize_target(target_dir: Path) -> str:
    """Determine whether target directory is for ingress or devops overlays."""
    return "ingress" if "ingress" in target_dir.parts else "devops"


def _resolve_target_paths(
    base_k8s_dir: Path,
    app_dirs: Sequence[Path] | None,
) -> list[Path]:
    """Resolve target .argocd-source.yaml paths safely within base_k8s_dir."""
    if app_dirs is not None:
        candidates = [d if d.is_absolute() else base_k8s_dir / d for d in app_dirs]
    else:
        candidates = [
            base_k8s_dir / "overlays" / "homelab" / "devops",
            base_k8s_dir / "devops",
            base_k8s_dir / "overlays" / "homelab" / "ingress",
            base_k8s_dir / "ingress",
        ]

    resolved_targets: list[Path] = []
    for candidate_dir in candidates:
        try:
            resolved_dir = candidate_dir.resolve()
            if not resolved_dir.is_relative_to(base_k8s_dir):
                continue
            if resolved_dir.is_dir():
                resolved_targets.append(resolved_dir / ".argocd-source.yaml")
        except OSError, RuntimeError:
            continue
    return resolved_targets


def _render_source_for_target(
    target: Path,
    base_k8s_dir: Path,
    active_settings: Any,
    domain: str | None,
) -> str | None:
    """Render .argocd-source.yaml content appropriate for the target directory."""
    category = _categorize_target(target.parent)
    if category == "ingress":
        ingress_template = _locate_ingress_routes_template(base_k8s_dir)
        if ingress_template is None:
            return None
        return render_ingress_argocd_source_content(
            ingress_template.read_text(encoding="utf-8"),
            domain=domain,
            settings=active_settings,
        )
    devops_template = _locate_configmap_template(base_k8s_dir)
    return render_argocd_source_content(
        devops_template.read_text(encoding="utf-8"),
        settings=active_settings,
        domain=domain,
    )


def generate_argocd_source(
    k8s_dir: Path | None = None,
    settings: Any = None,
    app_dirs: Sequence[Path] | None = None,
    domain: str | None = None,
) -> list[Path]:
    """Generate gitignored .argocd-source.yaml files with local overrides."""
    base_k8s_dir = (k8s_dir or DEFAULT_K8S_DIR).resolve()
    active_settings = settings if settings is not None else load_settings()

    targets = _resolve_target_paths(base_k8s_dir, app_dirs)
    if not targets:
        _locate_configmap_template(base_k8s_dir)
    written: list[Path] = []
    for target in targets:
        content = _render_source_for_target(target, base_k8s_dir, active_settings, domain)
        if content is None:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(target)
    return written
