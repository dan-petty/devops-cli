"""Kubeconform fast Kubernetes OpenAPI and JSONSchema validator."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from devops_cli.ai.review_schema import Finding
from devops_cli.config.defaults import (
    DEFAULT_KUBECONFORM_VERSION,
    DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
)
from devops_cli.core.repo import find_repo_root, is_ignored_by_git
from devops_cli.security.base import BaseSecurityScanner
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


def _parse_documents(f: Path) -> list[Any] | None:
    """Parse a YAML file into documents, or return ``None`` if it cannot be parsed."""
    import yaml

    try:
        return list(yaml.safe_load_all(f.read_text(encoding="utf-8", errors="replace")))
    except Exception as exc:
        logger.debug("Could not parse YAML in %s: %s", f, exc)
        return None


def _is_manifest_document(document: Any) -> bool:
    """Report whether a YAML document is a Kubernetes manifest.

    `apiVersion` is the discriminator, not `kind`. Helm charts legitimately expose `kind` as
    a values key -- fluent-bit uses it to choose between a DaemonSet and a Deployment -- so
    keying on it reports correct values files as broken manifests. Across this repository
    every real manifest declares both fields and exactly one values file declares `kind`
    alone.

    A document omitting `apiVersion` is therefore skipped. That trades away detection of a
    manifest missing it entirely, which `kubectl apply` rejects immediately with a clearer
    message than this fallback could give, for not flagging correct files -- the failure
    that teaches people to ignore a validator.
    """
    return isinstance(document, dict) and "apiVersion" in document


def _validate_single_k8s_file_fallback(f: Path, rel_root: Path) -> Finding | None:
    """Check the Kubernetes manifests in a YAML file for required schema headers.

    A file with no manifest documents is skipped rather than reported. Treating the absence
    of `apiVersion` and `kind` as a defect inverted the test: that absence is precisely how
    a non-manifest is recognised, so every Helm values file in this repository was reported
    as a broken manifest -- nine HIGH findings, all false, which is how a validator teaches
    people to ignore it.
    """
    rel_str = str(f.relative_to(rel_root)) if f.is_relative_to(rel_root) else f.name
    documents = _parse_documents(f)
    if documents is None:
        return Finding(
            severity="HIGH",
            location=f"{rel_str}:1",
            title="Unparseable YAML document",
            description="File could not be parsed as YAML and cannot be validated.",
            fix="Correct the YAML syntax so the document can be parsed.",
        )

    manifests = [document for document in documents if _is_manifest_document(document)]
    if not manifests:
        return None

    for document in manifests:
        if not document.get("kind"):
            return Finding(
                severity="HIGH",
                location=f"{rel_str}:1",
                title="Invalid Kubernetes manifest schema",
                description="Manifest declares apiVersion but is missing kind.",
                fix="Specify the canonical kind metadata header.",
            )
    return None


def _run_native_fallback_k8s_validation(manifest_path: Path) -> list[Finding]:
    """Fallback basic schema check for Kubernetes YAML manifests when kubeconform is absent."""
    findings: list[Finding] = []
    resolved = manifest_path.resolve()
    files = list(resolved.rglob("*.yaml")) if resolved.is_dir() else [resolved]
    rel_root = resolved if resolved.is_dir() else resolved.parent
    repo_root = find_repo_root(rel_root)

    for f in files:
        if not f.is_file() or is_ignored_by_git(repo_root, f):
            continue
        try:
            if not f.resolve().is_relative_to(rel_root):
                continue
        except ValueError, OSError:
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


class KubeconformScanner(BaseSecurityScanner):
    """Declarative security scanner adapter for Kubeconform OpenAPI manifest validator."""

    name: str = "kubeconform"
    binary_name: str = "kubeconform"

    def build_command(
        self,
        target_path: Path,
        k8s_version: str = DEFAULT_KUBECONFORM_VERSION,
        strict: bool = True,
        **kwargs: Any,
    ) -> list[str]:
        """Build argument command list for invoking Kubeconform."""
        cmd = [self.binary_name, "-output", "json", "-kubernetes-version", k8s_version]
        if strict:
            cmd.append("-strict")
        cmd.append(str(target_path))
        return cmd

    def parse_output(self, data: Any, target_path: Path) -> list[Finding]:
        """Parse raw Kubeconform JSON or line-delimited records into Finding models."""
        findings: list[Finding] = []
        if isinstance(data, dict):
            finding = _parse_kubeconform_line(json.dumps(data))
            if finding:
                findings.append(finding)
        elif isinstance(data, list):
            for item in data:
                finding = _parse_kubeconform_line(
                    json.dumps(item) if isinstance(item, dict) else str(item)
                )
                if finding:
                    findings.append(finding)
        return findings

    def fallback_scan(self, target_path: Path) -> list[Finding]:
        """Execute native fallback validation for Kubernetes manifests."""
        return _run_native_fallback_k8s_validation(target_path)


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

    scanner = KubeconformScanner()
    cmd = scanner.build_command(manifest_path, k8s_version=k8s_version, strict=strict)

    try:
        from devops_cli.core.process import run_subprocess

        proc = run_subprocess(
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
