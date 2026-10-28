"""Kubeconform, the Kubernetes manifest validator against the JSON schemas, which `tools.lock` pins
(#2214)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, ClassVar

from devops_cli.ai.review_schema import Finding
from devops_cli.config.constants import (
    CONST_K8S_MANIFEST_EXTENSIONS,
    CONST_KUBECONFORM_FINDING_STATUSES,
    CONST_KUBECONFORM_STATUS_INVALID,
    CONST_MAX_INSPECT_FILE_SIZE_BYTES,
)
from devops_cli.config.defaults import (
    DEFAULT_KUBECONFORM_VERSION,
    DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS,
)
from devops_cli.review.manifests import manifest_object_key
from devops_cli.security.base import BaseSecurityScanner, ScanOutcome
from devops_cli.security.kubelinter import manifest_location
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
    a values key, so keying on it reports correct values files as broken manifests. Across
    this repository every real manifest declares both fields.

    A document omitting `apiVersion` is therefore skipped. That trades away detection of a
    manifest missing it entirely, which `kubectl apply` rejects immediately with a clearer
    message, for not flagging correct files -- the failure that teaches people to ignore a
    validator.
    """
    return isinstance(document, dict) and "apiVersion" in document


def is_kubernetes_manifest(path: Path | str) -> bool:
    """Report whether a file exists and contains a Kubernetes manifest document."""
    p = Path(path)
    if not (p.is_file() and p.suffix.lower() in CONST_K8S_MANIFEST_EXTENSIONS):
        return False
    try:
        if p.stat().st_size > CONST_MAX_INSPECT_FILE_SIZE_BYTES:
            return False
        content = p.read_text(encoding="utf-8", errors="replace")
        if "apiVersion" not in content:
            return False
        if p.suffix.lower() == ".json":
            data = json.loads(content)
            return _is_manifest_document(data)
        documents = _parse_documents(p)
        return bool(documents and any(_is_manifest_document(doc) for doc in documents))
    except Exception:
        return False


def _kubeconform_finding(resource: dict[str, Any]) -> Finding:
    """One resource of a kubeconform report as a HIGH finding at its manifest and object.

    kubeconform writes the `filename`, `kind`, `name`, `status` and `msg` of each resource, and
    `validationErrors` for an invalid one, but no namespace and no line. The object is
    `Kind/name`, as kube-linter and Pluto name it. A resource that kubeconform could not read,
    such as a file that is not YAML, has an empty `kind`, and is named by its manifest alone.
    """
    manifest = manifest_location(resource["filename"])
    kind, name, status = resource["kind"], resource["name"], resource["status"]
    location = f"{manifest}:{manifest_object_key(kind, name)}" if kind else manifest
    subject = f"{kind} '{name}'" if kind else manifest
    if status == CONST_KUBECONFORM_STATUS_INVALID:
        errors = "; ".join(
            f"{error['path']}: {error['msg']}" if error["path"] else error["msg"]
            for error in resource.get("validationErrors") or []
        )
        title = f"[Kubeconform {status}] {subject} does not match its schema"
        fix = (
            f"Correct the resource to match its schema: {errors}."
            if errors
            else "Correct the resource to match its schema."
        )
    else:
        title = f"[Kubeconform {status}] {subject} could not be validated"
        fix = (
            "Correct the resource so that kubeconform can read it, or give kubeconform a schema "
            "for its kind."
        )
    return Finding(
        severity="HIGH",
        location=location,
        title=title,
        description=resource["msg"],
        fix=fix,
        confidence_score=None,
    )


def parse_kubeconform_json(data: dict[str, Any]) -> list[Finding]:
    """The findings of the one JSON object that `kubeconform -output json` writes: one for each
    resource with `statusInvalid` or `statusError`, in the order of the report. A resource that
    is valid or that kubeconform skipped, which only `-verbose` lists, is no finding."""
    return [
        _kubeconform_finding(resource)
        for resource in data["resources"]
        if resource["status"] in CONST_KUBECONFORM_FINDING_STATUSES
    ]


class KubeconformScanner(BaseSecurityScanner):
    """Declarative security scanner adapter for Kubeconform OpenAPI manifest validator."""

    name: str = "kubeconform"
    binary_name: str = "kubeconform"
    gating: ClassVar[bool] = True

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
        """Parse the one JSON object that kubeconform writes into Finding models."""
        return parse_kubeconform_json(data)


@trace_span("k8s.kubeconform")
def run_kubeconform_validation(
    manifest_path: Path,
    k8s_version: str = DEFAULT_KUBECONFORM_VERSION,
    strict: bool = True,
    timeout: float = DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS,
) -> ScanOutcome:
    """Validate Kubernetes manifests against target version schema using Kubeconform."""
    scanner = KubeconformScanner()
    return scanner.scan(manifest_path, timeout=timeout, k8s_version=k8s_version, strict=strict)


__all__ = [
    "KubeconformScanner",
    "is_kubernetes_manifest",
    "parse_kubeconform_json",
    "run_kubeconform_validation",
]
