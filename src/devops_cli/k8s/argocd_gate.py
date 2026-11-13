"""Deterministic offline build gate and validation for Argo CD applications (#1343).

The gate reads the Applications of an environment tree (#5131). A git source of the repository that
holds the tree reads the checkout, and a source of another public repository is fetched at its
revision (`devops_cli.k8s.app_sources`).
"""

from __future__ import annotations

import io
import shutil
import tarfile
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

from devops_cli.config.constants import CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS
from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.k8s import ApplicationSourceError, ArgoCDGateError, KubernetesError
from devops_cli.k8s.app_sources import (
    SourceTrees,
    application_sources,
    normalize_git_url,
    ref_sources,
    repository_origin,
    source_revision,
)
from devops_cli.k8s.argocd_overrides import _host_fields
from devops_cli.k8s.environment import EnvironmentTree
from devops_cli.k8s.template import build_manifest_path, holds_template_domain_value


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


def discover_argocd_applications(application_dirs: Iterable[Path]) -> dict[str, dict[str, Any]]:
    """Discover every kind: Application in the folders of the Applications of a tree
    (`EnvironmentTree.application_dirs`)."""
    apps: dict[str, dict[str, Any]] = {}
    for target_dir in application_dirs:
        if not target_dir.is_dir():
            continue
        for file_path in sorted(target_dir.iterdir()):
            for name, doc in _load_applications_from_file(file_path):
                apps[name] = doc
    return apps


def discover_path_applications(
    env: EnvironmentTree, apps_dir: Path | None = None
) -> dict[str, Path]:
    """Discover applications with a git source path, optionally filtered by directory. The path is
    under the repository that holds the tree."""
    all_apps = discover_argocd_applications(env.application_dirs)
    result: dict[str, Path] = {}
    for name, doc in all_apps.items():
        spec = doc.get("spec", {})
        source = spec.get("source", {})
        path_str = source.get("path")
        if not path_str:
            continue
        target_path = env.repo / path_str
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


def _check_helm_source(
    helm_source: dict[str, Any], trees: SourceTrees, refs: dict[str, Any]
) -> list[str]:
    """Check value files of a Helm chart source for existence, YAML syntax, and placeholders."""
    errors: list[str] = []
    helm_conf = helm_source.get("helm", {})
    value_files = helm_conf.get("valueFiles", [])

    for vf in value_files:
        rel_path = vf.split("/", 1)[1] if vf.startswith("$") else vf
        try:
            val_path = trees.value_file(str(vf), refs)
        except ApplicationSourceError as exc:
            errors.append(exc.message)
            continue
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


def _check_path_source(app_name: str, source: dict[str, Any], trees: SourceTrees) -> list[str]:
    """Validate and build an application path source with kustomize or yaml parsing, in the
    folder of its repository at its revision."""
    errors: list[str] = []
    path_str = source.get("path", "")
    try:
        root = trees.tree(str(source.get("repoURL") or trees.origin), source_revision(source)).root
    except ApplicationSourceError as exc:
        return [exc.message]
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


def _check_application(name: str, doc: dict[str, Any], trees: SourceTrees) -> list[str]:
    """Check a single Argo CD Application's sources and manifests."""
    errors: list[str] = []
    sources = application_sources(doc)
    refs = ref_sources(sources)

    for s in sources:
        if "chart" in s:
            errors.extend(_check_helm_source(s, trees, refs))
        if "path" in s:
            errors.extend(_check_path_source(name, s, trees))

    return errors


def _check_tree(env: EnvironmentTree, *, origin_url: str) -> list[str]:
    """Execute offline Argo CD gate over the Applications of an environment tree."""
    apps = discover_argocd_applications(env.application_dirs)
    if not apps:
        return []

    if shutil.which("kubectl") is None:
        raise ArgoCDGateError(
            "kubectl is required to build Argo CD applications. "
            "Run 'devops install-tools --tool kubectl'."
        )

    failures: dict[str, list[str]] = {}
    with tempfile.TemporaryDirectory(prefix="argocd-gate-") as workdir:
        trees = SourceTrees(env.repo, normalize_git_url(origin_url), Path(workdir))
        for name, doc in sorted(apps.items()):
            app_errors = _check_application(name, doc, trees)
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
    env: EnvironmentTree,
    *,
    ref: str | None = None,
    origin_url: str | None = None,
) -> list[str]:
    """Check that every Argo CD application of the environment tree `env` builds and adheres to
    placeholder invariants (#1343). A git source of the origin of `env.repo` (or `origin_url`)
    reads the checkout, and a source of another public repository is fetched at its revision.

    If `ref` is provided, exports `git archive <ref>` of `env.repo` into a clean temporary
    directory first so gitignored or uncommitted local files never reach the build.
    """
    root = env.repo
    has_local_dirs = any(d.is_dir() for d in env.application_dirs)
    if not has_local_dirs and not (root / ".git").exists() and not (root / ".git").is_file():
        return []

    expected_origin = origin_url or repository_origin(root)
    if ref is None:
        return _check_tree(env, origin_url=expected_origin)

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
        exported = EnvironmentTree(tmp_path / env.root.resolve().relative_to(root), tmp_path)
        return _check_tree(exported, origin_url=expected_origin)
