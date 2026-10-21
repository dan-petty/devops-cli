"""Deterministic offline build gate and validation for Argo CD applications (#1343)."""

from __future__ import annotations

import io
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from devops_cli.config.constants import (
    CONST_CANONICAL_OCI_SOURCE,
    CONST_K8S_ARGOCD_APPLICATION_DIRS,
    CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS,
)
from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.k8s import ArgoCDGateError, KubernetesError
from devops_cli.k8s.argocd_overrides import _host_fields
from devops_cli.k8s.template import build_manifest_path, holds_template_domain_value


def _normalize_git_url(url: str) -> str:
    """Normalize git URLs for origin comparison."""
    norm = url.strip().rstrip("/")
    if norm.endswith(".git"):
        norm = norm[:-4]
    if norm.startswith("git@github.com:"):
        return f"https://github.com/{norm[len('git@github.com:') :]}"
    parsed = urlsplit(norm)
    if parsed.scheme == "ssh" and parsed.netloc == "git@github.com":
        path = parsed.path.lstrip("/")
        return f"https://github.com/{path}"
    return norm


def _get_repo_origin(root: Path) -> str:
    """Determine expected origin URL from git config, falling back to canonical source."""
    proc = run_subprocess(
        ["git", "-C", str(root), "config", "--get", "remote.origin.url"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0 and proc.stdout and proc.stdout.strip():
        return _normalize_git_url(proc.stdout.strip())
    return _normalize_git_url(CONST_CANONICAL_OCI_SOURCE)


def _load_applications_from_file(file_path: Path) -> list[tuple[str, dict[str, Any]]]:
    """Load kind: Application documents from a single yaml file."""
    if file_path.name == "projects.yaml" or file_path.suffix.lower() not in (".yaml", ".yml"):
        return []
    try:
        content = file_path.read_text(encoding="utf-8")
        docs = list(yaml.safe_load_all(content))
    except yaml.YAMLError, OSError, UnicodeDecodeError:
        return []
    apps: list[tuple[str, dict[str, Any]]] = []
    for doc in docs:
        if isinstance(doc, dict) and doc.get("kind") == "Application":
            name = doc.get("metadata", {}).get("name")
            if isinstance(name, str) and name:
                apps.append((name, doc))
    return apps


def discover_argocd_applications(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Discover every kind: Application in k8s/argocd/apps and k8s/argocd/bootstrap."""
    apps: dict[str, dict[str, Any]] = {}
    for rel_dir in CONST_K8S_ARGOCD_APPLICATION_DIRS:
        target_dir = repo_root / rel_dir
        if not target_dir.is_dir():
            continue
        for file_path in sorted(target_dir.iterdir()):
            for name, doc in _load_applications_from_file(file_path):
                apps[name] = doc
    return apps


def discover_path_applications(repo_root: Path, apps_dir: Path | None = None) -> dict[str, Path]:
    """Discover applications with a git source path, optionally filtered by directory."""
    all_apps = discover_argocd_applications(repo_root)
    result: dict[str, Path] = {}
    for name, doc in all_apps.items():
        spec = doc.get("spec", {})
        source = spec.get("source", {})
        path_str = source.get("path")
        if not path_str:
            continue
        target_path = repo_root / path_str
        if apps_dir is not None:
            source_file = apps_dir / f"{name}.yaml"
            if not source_file.is_file():
                source_file_yml = apps_dir / f"{name}.yml"
                if not source_file_yml.is_file():
                    continue
        result[name] = target_path
    return result


def _json_pointer_escape(token: str) -> str:
    """Escape tokens per RFC 6901 JSON pointer specification."""
    return token.replace("~", "~0").replace("/", "~1")


def find_template_domain_occurrences(obj: Any, pointer: str = "") -> list[tuple[str, str]]:
    """Find all JSON pointers and values where template domain values appear."""
    occurrences: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            k_str = str(k)
            k_esc = _json_pointer_escape(k_str)
            child_pointer = f"{pointer}/{k_esc}"
            if holds_template_domain_value(k_str):
                occurrences.append((f"{child_pointer}#key", k_str))
            occurrences.extend(find_template_domain_occurrences(v, child_pointer))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            child_pointer = f"{pointer}/{i}"
            occurrences.extend(find_template_domain_occurrences(item, child_pointer))
    elif isinstance(obj, str):
        if holds_template_domain_value(obj):
            occurrences.append((pointer, obj))
    return occurrences


def _check_helm_source(app_name: str, helm_source: dict[str, Any], root: Path) -> list[str]:
    """Check value files of a Helm chart source for existence, YAML syntax, and placeholders."""
    errors: list[str] = []
    helm_conf = helm_source.get("helm", {})
    value_files = helm_conf.get("valueFiles", [])

    for vf in value_files:
        rel_path = vf.split("/", 1)[1] if vf.startswith("$") else vf
        val_path = root / rel_path
        if not val_path.is_file():
            errors.append(f"Helm value file '{rel_path}' does not exist")
            continue
        try:
            val_text = val_path.read_text(encoding="utf-8")
            val_docs = list(yaml.safe_load_all(val_text))
        except (yaml.YAMLError, OSError, UnicodeDecodeError) as e:
            errors.append(f"Helm value file '{rel_path}' failed to parse: {e}")
            continue

        for doc in val_docs:
            if not isinstance(doc, dict):
                continue
            for ptr, val in find_template_domain_occurrences(doc):
                errors.append(
                    f"Placeholder domain value '{val}' at Helm value file {rel_path} {ptr}"
                )
    return errors


def _check_rendered_doc_placeholders(app_name: str, doc: dict[str, Any]) -> list[str]:
    """Validate that placeholders appear only in authorized host fields of homelab applications."""
    errors: list[str] = []
    doc_kind = doc.get("kind", "Unknown")
    doc_name = doc.get("metadata", {}).get("name", "unknown")
    doc_id = f"{doc_kind}/{doc_name}"

    allowed_pointers = (
        {ptr for ptr, _ in _host_fields(doc)}
        if app_name in CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS
        else set()
    )

    for ptr, val in find_template_domain_occurrences(doc):
        if ptr not in allowed_pointers:
            errors.append(
                f"Placeholder domain value '{val}' at {doc_id} {ptr} "
                f"is not permitted in application '{app_name}'"
            )
    return errors


def _check_path_source(app_name: str, source: dict[str, Any], root: Path) -> list[str]:
    """Validate and build an application path source with kustomize or yaml parsing."""
    errors: list[str] = []
    path_str = source.get("path", "")
    target_path = (root / path_str).resolve()
    root_resolved = root.resolve()

    if not target_path.is_relative_to(root_resolved):
        return [f"Path '{path_str}' leaves repository tree"]
    if (target_path / "Chart.yaml").exists():
        return [f"Path '{path_str}' holds Chart.yaml and cannot be built offline"]
    if not target_path.exists():
        return [f"Path '{path_str}' does not exist"]

    try:
        rendered = build_manifest_path(target_path)
    except (KubernetesError, OSError) as e:
        msg = e.message if isinstance(e, KubernetesError) else str(e)
        return [f"Kustomize build failed for path '{path_str}': {msg}"]

    try:
        docs = list(yaml.safe_load_all(rendered))
    except yaml.YAMLError as e:
        return [f"Rendered output for path '{path_str}' failed to parse: {e}"]

    for doc in docs:
        if isinstance(doc, dict):
            errors.extend(_check_rendered_doc_placeholders(app_name, doc))

    return errors


def _check_application(
    name: str, doc: dict[str, Any], root: Path, expected_origin: str
) -> list[str]:
    """Check a single Argo CD Application's sources and manifests."""
    errors: list[str] = []
    spec = doc.get("spec", {})
    sources: list[dict[str, Any]] = (
        spec.get("sources", []) if "sources" in spec else [spec.get("source", {})]
    )

    for s in sources:
        if not isinstance(s, dict):
            continue
        repo_url = s.get("repoURL")
        if "chart" not in s and repo_url:
            norm_repo = _normalize_git_url(repo_url)
            if norm_repo != expected_origin:
                errors.append(
                    f"Git source repoURL '{repo_url}' is not repository origin '{expected_origin}'"
                )
        if "chart" in s:
            errors.extend(_check_helm_source(name, s, root))
        if "path" in s:
            errors.extend(_check_path_source(name, s, root))

    return errors


def _check_tree(tree_root: Path, *, origin_url: str | None = None) -> list[str]:
    """Execute offline Argo CD gate over a repository filesystem tree."""
    apps = discover_argocd_applications(tree_root)
    if not apps:
        return []

    if shutil.which("kubectl") is None:
        raise ArgoCDGateError(
            "kubectl is required to build Argo CD applications. "
            "Run 'devops install-tools --tool kubectl'."
        )

    expected_origin = origin_url or _get_repo_origin(tree_root)
    failures: dict[str, list[str]] = {}

    for name, doc in sorted(apps.items()):
        app_errors = _check_application(name, doc, tree_root, expected_origin)
        if app_errors:
            failures[name] = app_errors

    if failures:
        lines = [f"Argo CD gate failed for {len(failures)} application(s):"]
        for app_name, reasons in sorted(failures.items()):
            for r in reasons:
                lines.append(f"  - {app_name}: {r}")
        raise ArgoCDGateError("\n".join(lines), failures=failures)

    return sorted(apps.keys())


def check_argocd_gate(
    root: Path,
    *,
    ref: str | None = None,
    origin_url: str | None = None,
) -> list[str]:
    """Check that every Argo CD application builds offline and adheres to placeholder invariants (#1343).

    If `ref` is provided, exports `git archive <ref>` into a clean temporary directory first
    so gitignored or uncommitted local files never reach the build.
    """
    has_local_dirs = any((root / d).is_dir() for d in CONST_K8S_ARGOCD_APPLICATION_DIRS)
    if not has_local_dirs and not (root / ".git").exists() and not (root / ".git").is_file():
        return []

    if ref is None:
        return _check_tree(root, origin_url=origin_url)

    expected_origin = origin_url or _get_repo_origin(root)
    proc = run_subprocess(
        ["git", "-C", str(root), "archive", ref],
        capture_output=True,
        text=False,
        check=False,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    )
    if proc.returncode != 0:
        err = (
            proc.stderr.decode("utf-8", errors="replace")
            if isinstance(proc.stderr, bytes)
            else str(proc.stderr or "")
        )
        raise ArgoCDGateError(f"Failed to export git archive for '{ref}': {err.strip()}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        raw_bytes = (
            proc.stdout
            if isinstance(proc.stdout, bytes)
            else str(proc.stdout or "").encode("utf-8")
        )
        with tarfile.open(fileobj=io.BytesIO(raw_bytes)) as tar:
            tar.extractall(path=tmp_path, filter="data")
        return _check_tree(tmp_path, origin_url=expected_origin)
