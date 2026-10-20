"""Kubernetes manifest template substitution and domain rendering engine."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from devops_cli.config.constants import (
    CONST_K8S_KUSTOMIZATION_NAMES,
    CONST_K8S_SUBDOMAIN_RE,
    CONST_K8S_TEMPLATE_DOMAIN_PLACEHOLDER,
    CONST_K8S_TEMPLATE_DOMAIN_VARS,
    CONST_K8S_TEMPLATE_EXTENSIONS,
)
from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.config.settings import load_settings
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.k8s import KubernetesContextError


def normalize_domain(domain: str) -> str:
    """Normalize and validate a target domain string for template substitution."""
    norm = domain.strip().lower().lstrip(".")
    if not norm or not CONST_K8S_SUBDOMAIN_RE.match(norm):
        raise KubernetesContextError(
            f"Invalid domain name for template substitution: {domain!r}. "
            "Must be a valid RFC 1123 domain name."
        )
    return norm


def resolve_template_domain(domain_override: str | None = None) -> str:
    """Resolve the effective domain from CLI override, config settings, or environment."""
    if domain_override and domain_override.strip():
        return normalize_domain(domain_override)

    settings: Any = load_settings()
    k8s_domain = getattr(getattr(settings, "k8s", None), "domain", None)
    if k8s_domain and str(k8s_domain).strip():
        return normalize_domain(str(k8s_domain))

    cf_domain = getattr(getattr(settings, "cloudflare", None), "domain", None)
    if cf_domain and str(cf_domain).strip():
        return normalize_domain(str(cf_domain))

    env_domain = os.environ.get("DEVOPS_CLI_K8S_DOMAIN") or os.environ.get("DEVOPS_CLI_DOMAIN")
    if env_domain and env_domain.strip():
        return normalize_domain(env_domain)

    raise KubernetesContextError(
        "No domain configured for template substitution. "
        "Specify --domain <domain> or set 'k8s.domain: <domain>' in config.yaml."
    )


def holds_template_domain_value(text: str) -> bool:
    """Whether `text` contains the placeholder domain or a template domain variable (#1343)."""
    if not text:
        return False
    if re.search(re.escape(CONST_K8S_TEMPLATE_DOMAIN_PLACEHOLDER), text, re.IGNORECASE):
        return True
    return any(
        f"${{{var_name}}}" in text or f"${var_name}" in text
        for var_name in CONST_K8S_TEMPLATE_DOMAIN_VARS
    )


def render_manifest_template(
    content: str,
    domain: str,
    extra_vars: dict[str, str] | None = None,
) -> str:
    """Substitute placeholder domain and environment variables in manifest content."""
    normalized_domain = normalize_domain(domain)
    # Case-insensitive substitution of the canonical placeholder domain (e.g. example.com)
    rendered = re.sub(
        re.escape(CONST_K8S_TEMPLATE_DOMAIN_PLACEHOLDER),
        normalized_domain,
        content,
        flags=re.IGNORECASE,
    )

    # Standard template variable substitutions (e.g. ${DOMAIN}, $DOMAIN)
    for var_name in CONST_K8S_TEMPLATE_DOMAIN_VARS:
        rendered = rendered.replace(f"${{{var_name}}}", normalized_domain)
        rendered = rendered.replace(f"${var_name}", normalized_domain)

    if extra_vars:
        for key, val in extra_vars.items():
            rendered = rendered.replace(f"${{{key}}}", val)
            rendered = rendered.replace(f"${key}", val)

    return rendered


def _build_kustomize_dir(target_dir: Path) -> str:
    """Run kustomize build on a directory without template substitution."""
    cmd = ["kubectl", "kustomize", str(target_dir)]
    proc = run_subprocess(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    )
    if proc.returncode != 0:
        err_msg = (proc.stderr or proc.stdout or "kubectl kustomize failed").strip()
        raise KubernetesContextError(f"Kustomize build failed for '{target_dir}': {err_msg}")
    return proc.stdout or ""


def _build_yaml_dir(target_dir: Path) -> str:
    """Read all YAML files in a directory and return them as a combined stream."""
    yaml_files = sorted(
        f
        for f in target_dir.iterdir()
        if f.is_file() and f.suffix.lower() in CONST_K8S_TEMPLATE_EXTENSIONS
    )
    if not yaml_files:
        raise KubernetesContextError(f"No YAML manifests found in directory: {target_dir}")

    parts = [yf.read_text(encoding="utf-8") for yf in yaml_files]
    return "\n---\n".join(parts)


def build_manifest_path(path: str | Path) -> str:
    """Build a manifest file or directory without domain and template substitution (#1343)."""
    target = Path(path).resolve()
    if not target.exists():
        raise KubernetesContextError(f"Manifest path not found: {path}")

    if target.is_file():
        return target.read_text(encoding="utf-8")

    if target.is_dir():
        has_kustomize = any((target / kf).exists() for kf in CONST_K8S_KUSTOMIZATION_NAMES)
        if has_kustomize:
            return _build_kustomize_dir(target)
        return _build_yaml_dir(target)

    raise KubernetesContextError(f"Invalid manifest target path: {path}")


def render_manifest_path(
    path: str | Path,
    domain: str,
    extra_vars: dict[str, str] | None = None,
) -> str:
    """Render a manifest file or directory with domain and template variables substituted."""
    raw = build_manifest_path(path)
    return render_manifest_template(raw, domain=domain, extra_vars=extra_vars)
