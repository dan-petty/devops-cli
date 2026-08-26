"""Kubeconform fast Kubernetes OpenAPI and JSONSchema validator."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

from devops_cli.ai.review_schema import Finding
from devops_cli.config.defaults import (
    DEFAULT_KUBECONFORM_VERSION,
    DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
)
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


def _run_native_fallback_k8s_validation(manifest_path: Path) -> list[Finding]:
    """Fallback basic schema check for Kubernetes YAML manifests when kubeconform is absent."""
    findings: list[Finding] = []
    resolved = manifest_path.resolve()
    files = list(resolved.rglob("*.yaml")) if resolved.is_dir() else [resolved]

    for f in files:
        if not f.is_file() or any(part.startswith(".") for part in f.parts):
            continue
        try:
            rel_str = str(f.relative_to(resolved if resolved.is_dir() else resolved.parent))
            content = f.read_text(encoding="utf-8", errors="replace")
            # Check for apiVersion and kind
            has_api = "apiVersion:" in content
            has_kind = "kind:" in content
            if not (has_api and has_kind):
                findings.append(
                    Finding(
                        severity="HIGH",
                        location=f"{rel_str}:1",
                        title="Invalid Kubernetes manifest schema",
                        description="Manifest missing required apiVersion or kind fields.",
                        fix="Specify canonical apiVersion and kind metadata headers.",
                    )
                )
        except Exception as exc:
            logger.debug("Fallback validation error for %s: %s", f, exc)

    return findings


@trace_span("k8s.kubeconform")
def run_kubeconform_validation(
    manifest_path: Path,
    k8s_version: str = DEFAULT_KUBECONFORM_VERSION,
    strict: bool = True,
    timeout: float = DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
) -> list[Finding]:
    """Validate Kubernetes manifests against target version schema using Kubeconform."""
    kubeconform_bin = shutil.which("kubeconform")
    if not kubeconform_bin:
        logger.debug("Kubeconform binary not found in PATH; running native schema fallback.")
        return _run_native_fallback_k8s_validation(manifest_path)

    cmd = [kubeconform_bin, "-output", "json", "-kubernetes-version", k8s_version]
    if strict:
        cmd.append("-strict")

    target = str(manifest_path)
    cmd.append(target)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if not proc.stdout.strip():
            return []

        findings: list[Finding] = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                item = json.loads(line)
                status = item.get("status", "")
                if status.lower() in ("invalid", "error"):
                    resource_path = item.get("filename", "")
                    msg = item.get("msg", "Schema validation failure")
                    findings.append(
                        Finding(
                            severity="HIGH",
                            location=f"{resource_path}:1" if resource_path else ":1",
                            title=f"Kubeconform Schema Validation Error: {status}",
                            description=msg,
                            fix="Align resource specification with Kubernetes OpenAPI schema.",
                        )
                    )
            except json.JSONDecodeError:
                continue

        return findings
    except Exception as exc:
        logger.debug("Kubeconform run error: %s", exc)
        return _run_native_fallback_k8s_validation(manifest_path)
