"""Native workspace inspection tools for PydanticAgent."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from devops_cli.config.defaults import (
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    DEFAULT_TOOL_BUFFER_CHUNK_SIZE,
    DEFAULT_TOOL_DIFF_MAX_CHARS,
    DEFAULT_TOOL_MAX_BYTES_LIMIT,
    DEFAULT_TOOL_MAX_FILES,
    DEFAULT_TOOL_MAX_SEARCH_MATCHES,
    DEFAULT_TOOL_READ_MAX_BYTES,
)
from devops_cli.core.process import run_subprocess

logger = logging.getLogger(__name__)


def _is_safe_workspace_path(target: Path) -> bool:
    cwd = Path.cwd().resolve()
    target_resolved = target.resolve()
    return target_resolved == cwd or target_resolved.is_relative_to(cwd)


def _run_tool_cmd(
    cmd: list[str], fallback_msg: str = "", max_chars: int = DEFAULT_TOOL_DIFF_MAX_CHARS
) -> str:
    """Safely run a subprocess command for an agent tool without blocking async loops."""

    def _exec() -> str:
        try:
            res = run_subprocess(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
            )
            output = str(res.stdout).strip()
            if len(output) > max_chars:
                return str(output[:max_chars]) + f"\n... [truncated at {max_chars} chars]"
            return output or fallback_msg
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("Tool command %s failed: %s", cmd[0], exc)
            return f"{cmd[0]} execution failed: {exc}"

    try:
        import asyncio

        loop = asyncio.get_running_loop()
        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(asyncio.to_thread(_exec), loop)
            return str(future.result(timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS + 5))
    except RuntimeError:
        pass

    return _exec()


def list_files(directory: str = ".") -> list[str]:
    """List non-hidden files in the specified directory up to 2 levels deep."""
    root = Path(directory).resolve()
    if not _is_safe_workspace_path(root) or not root.exists() or not root.is_dir():
        return []
    results: list[str] = []
    for path in root.glob("*"):
        if path.name.startswith(".") or path.name == "__pycache__":
            continue
        if not _is_safe_workspace_path(path.resolve()):
            continue
        if path.is_file():
            results.append(path.name)
        elif path.is_dir():
            for child in path.glob("*"):
                if child.name.startswith(".") or child.name == "__pycache__":
                    continue
                if not _is_safe_workspace_path(child.resolve()):
                    continue
                results.append(f"{path.name}/{child.name}")
    return sorted(results)[:DEFAULT_TOOL_MAX_FILES]


def read_file(path: str, max_bytes: int = DEFAULT_TOOL_READ_MAX_BYTES) -> str:
    """Read contents of a text file up to max_bytes."""
    max_bytes = max(1, min(max_bytes, DEFAULT_TOOL_MAX_BYTES_LIMIT))
    file_path = Path(path).resolve()
    if not _is_safe_workspace_path(file_path):
        logger.warning("Access denied attempting to read path outside workspace: %s", path)
        return f"Access Denied: {path} is outside workspace."
    if not file_path.exists() or not file_path.is_file():
        return f"File not found: {path}"
    try:
        file_size = file_path.stat().st_size
        bytes_to_read = min(file_size, max_bytes + 1)
        with open(file_path, "rb") as f:
            raw = f.read(bytes_to_read)
        logger.debug("Read %d bytes from %s", len(raw), path)
        if len(raw) > max_bytes:
            return (
                raw[:max_bytes].decode("utf-8", errors="replace")
                + f"\n... [truncated at {max_bytes} bytes]"
            )
        return raw.decode("utf-8", errors="replace")
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Error reading file %s: %s", path, exc)
        return f"Error reading file: {exc}"


def git_status() -> str:
    """Return current git status summary."""
    return _run_tool_cmd(["git", "status", "-s"], fallback_msg="Working tree clean.")


def git_diff() -> str:
    """Return current unstaged git diff up to 4000 characters."""
    return _run_tool_cmd(
        ["git", "diff"],
        fallback_msg="No unstaged changes.",
        max_chars=DEFAULT_TOOL_DIFF_MAX_CHARS,
    )


def search_code(query: str, directory: str = ".") -> list[str]:
    """Search workspace source code files for a string query."""
    root = Path(directory).resolve()
    if not _is_safe_workspace_path(root) or not root.exists():
        return []
    matches: list[str] = []
    query_bytes = query.encode("utf-8")
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts or any(p.startswith(".") for p in path.parts):
            continue
        if not _is_safe_workspace_path(path.resolve()):
            continue
        try:
            with open(path, "rb") as f:
                header = f.read(DEFAULT_TOOL_BUFFER_CHUNK_SIZE)
                if query_bytes in header:
                    matches.append(str(path.relative_to(root)))
        except Exception:
            pass
        if len(matches) >= DEFAULT_TOOL_MAX_SEARCH_MATCHES:
            break
    return matches


def k8s_pods(namespace: str = "default") -> str:
    """Query pods in a Kubernetes namespace."""
    return _run_tool_cmd(
        ["kubectl", "get", "pods", "-n", namespace],
        fallback_msg=f"No pods found in namespace {namespace}.",
    )


def argo_apps() -> str:
    """Query ArgoCD applications in minikube/k8s cluster."""
    return _run_tool_cmd(
        ["kubectl", "get", "applications", "-A"],
        fallback_msg="No ArgoCD applications found.",
    )


def scan_trivy(
    target: str = ".",
    scan_type: str = "fs",
    severity: str = "UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL",
) -> str:
    """Run Aqua Trivy vulnerability, secret, misconfiguration, and IaC scanner."""
    target_path = Path(target).resolve()
    if not _is_safe_workspace_path(target_path):
        return f"Access Denied: {target} is outside workspace."
    return _run_tool_cmd(
        ["trivy", scan_type, "--severity", severity, str(target_path)],
        fallback_msg="No vulnerabilities, secrets, or flaws found by Trivy.",
        max_chars=DEFAULT_TOOL_DIFF_MAX_CHARS,
    )


def scan_kubelinter(target: str = ".") -> str:
    """Run Red Hat Kube-linter static security and best-practice analysis on K8s manifests."""
    target_path = Path(target).resolve()
    if not _is_safe_workspace_path(target_path):
        return f"Access Denied: {target} is outside workspace."
    return _run_tool_cmd(
        ["kube-linter", "lint", str(target_path)],
        fallback_msg="No K8s manifest lint errors detected by Kube-linter.",
        max_chars=DEFAULT_TOOL_DIFF_MAX_CHARS,
    )


def scan_pluto(target: str = ".") -> str:
    """Run Fairwinds Pluto to detect deprecated and removed Kubernetes API versions."""
    target_path = Path(target).resolve()
    if not _is_safe_workspace_path(target_path):
        return f"Access Denied: {target} is outside workspace."
    cmd = (
        ["pluto", "detect-files", "-f", str(target_path)]
        if target_path.is_file()
        else ["pluto", "detect-files", "-d", str(target_path)]
    )
    return _run_tool_cmd(
        cmd,
        fallback_msg="No deprecated Kubernetes APIs detected by Pluto.",
        max_chars=DEFAULT_TOOL_DIFF_MAX_CHARS,
    )


def scan_bandit(target: str = "src") -> str:
    """Run PyCQA Bandit static security vulnerability analysis on Python source files."""
    target_path = Path(target).resolve()
    if not _is_safe_workspace_path(target_path):
        return f"Access Denied: {target} is outside workspace."
    return _run_tool_cmd(
        ["bandit", "-r", str(target_path), "-ll", "-s", "B608", "-q"],
        fallback_msg="No high/medium security issues detected by Bandit.",
        max_chars=DEFAULT_TOOL_DIFF_MAX_CHARS,
    )


def scan_popeye(namespace: str = "") -> str:
    """Run Popeye Kubernetes cluster and namespace resource sanitizer."""
    cmd = ["popeye"]
    if namespace:
        cmd.extend(["-n", namespace])
    return _run_tool_cmd(
        cmd,
        fallback_msg="Popeye cluster sanitize check passed.",
        max_chars=DEFAULT_TOOL_DIFF_MAX_CHARS,
    )


def run_security_scan(target: str = "src") -> str:
    """Perform static security analysis scan on Python workspace files (alias for scan_bandit)."""
    return scan_bandit(target=target)


def rag_search(
    query: str,
    top_k: int = 5,
    project: str | None = None,
    language: str | None = None,
    category: str | None = None,
) -> str:
    """Perform semantic vector retrieval over indexed workspace code, polyglot repos, and docs."""
    try:
        from devops_cli.ai.rag.embeddings import EmbeddingsEngine
        from devops_cli.ai.rag.qdrant import QdrantClient
        from devops_cli.ai.rag.retriever import SemanticRetriever
        from devops_cli.config.settings import get_ai_api_key, load_settings

        settings = load_settings()
        qdrant_url = settings.qdrant.url or "http://localhost:6333"
        prefix = settings.qdrant.collection_prefix or "devops"
        qdrant = QdrantClient(
            base_url=qdrant_url, allow_private_network=settings.ai.allow_private_network
        )
        if not qdrant.is_alive():
            return f"RAG vector database unavailable at {qdrant_url}. Fallback: use search_code."

        embedder = EmbeddingsEngine(ai_config=settings.ai, api_key=get_ai_api_key(settings))
        retriever = SemanticRetriever(
            qdrant=qdrant,
            embedder=embedder,
            code_collection=f"{prefix}_code",
            docs_collection=f"{prefix}_docs",
            default_top_k=top_k,
        )
        context = retriever.retrieve_context(
            query,
            top_k=top_k,
            project=project,
            language=language,
            category=category,
        )
        if not context.results:
            return f"No semantic matches found in vector store for: {query}"
        return context.formatted_text
    except Exception as exc:
        return f"RAG search error: {exc}"
