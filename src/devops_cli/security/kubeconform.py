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


def _validate_single_k8s_file_fallback(f: Path, rel_root: Path) -> Finding | None:
    """Check single YAML manifest for apiVersion and kind headers."""
    try:
        rel_str = str(f.relative_to(rel_root)) if f.is_relative_to(rel_root) else f.name
        content = f.read_text(encoding="utf-8", errors="replace")
        has_api = "apiVersion:" in content
        has_kind = "kind:" in content
        if not (has_api and has_kind):
            return Finding(
                severity="HIGH",
                location=f"{rel_str}:1",
                title="Invalid Kubernetes manifest schema",
                description="Manifest missing required apiVersion or kind fields.",
                fix="Specify canonical apiVersion and kind metadata headers.",
            )
    except Exception as exc:
        logger.debug("Fallback validation error for %s: %s", f, exc)
    return None


def _run_native_fallback_k8s_validation(manifest_path: Path) -> list[Finding]:
    """Fallback basic schema check for Kubernetes YAML manifests when kubeconform is absent."""
    findings: list[Finding] = []
    resolved = manifest_path.resolve()
    files = list(resolved.rglob("*.yaml")) if resolved.is_dir() else [resolved]
    rel_root = resolved if resolved.is_dir() else resolved.parent

    for f in files:
        if not f.is_file() or any(part.startswith(".") for part in f.parts):
            continue
        finding = _validate_single_k8s_file_fallback(f, rel_root)
        if finding:
            findings.append(finding)

    return findings


def _parse_kubeconform_line(line: str) -> Finding | None:
    """Parse a single JSON line from Kubeconform output into a Finding."""
    try:
        item = json.loads(line)
        status = item.get("status", "")
        if status.lower() in ("invalid", "error"):
            resource_path = item.get("filename", "")
            msg = item.get("msg", "Schema validation failure")
            return Finding(
                severity="HIGH",
                location=f"{resource_path}:1" if resource_path else ":1",
                title=f"Kubeconform Schema Validation Error: {status}",
                description=msg,
                fix="Align resource specification with Kubernetes OpenAPI schema.",
            )
    except json.JSONDecodeError:
        pass
    return None


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
    cmd.append(str(manifest_path))

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
            if line and line.startswith("{"):
                finding = _parse_kubeconform_line(line)
                if finding:
                    findings.append(finding)

        return findings
    except Exception as exc:
        logger.debug("Kubeconform run error: %s", exc)
        return _run_native_fallback_k8s_validation(manifest_path)
