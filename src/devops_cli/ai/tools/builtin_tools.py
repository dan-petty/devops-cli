"""Built-in workspace inspection and execution tools for PydanticAgent."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from pathlib import Path

from devops_cli.config.constants import CONST_BINARY_EXTENSIONS
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
from devops_cli.core.repo import is_safe_subpath
from devops_cli.lang import ERRORS, MESSAGES

logger = logging.getLogger(__name__)


def _is_safe_workspace_path(target: Path, workspace_root: Path | None = None) -> bool:
    if target.is_symlink():
        return False
    root = workspace_root or Path.cwd()
    return is_safe_subpath(root, target)


def _run_tool_cmd(
    cmd: list[str],
    fallback_msg: str = "",
    max_chars: int = DEFAULT_TOOL_DIFF_MAX_CHARS,
    cwd: Path | None = None,
) -> str:
    """Safely run a subprocess command for an agent tool without blocking async loops."""

    def _exec() -> str:
        try:
            res = run_subprocess(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                cwd=cwd,
                timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
            )
            output = str(res.stdout).strip()
            if len(output) > max_chars:
                return str(output[:max_chars]) + f"\n... [truncated at {max_chars} chars]"
            return output or fallback_msg
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("Tool command %s failed: %s", cmd[0], exc)
            return ERRORS.tools.tool_execution_failed.format(tool=cmd[0], exc=exc)

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

    entries: list[str] = []
    for path in sorted(root.glob("*")):
        if path.name.startswith(".") or path.name == "__pycache__":
            continue
        if not _is_safe_workspace_path(path.resolve()):
            continue
        if path.is_file():
            entries.append(path.name)
        elif path.is_dir():
            for child in sorted(path.glob("*")):
                if child.name.startswith(".") or child.name == "__pycache__":
                    continue
                if not _is_safe_workspace_path(child.resolve()):
                    continue
                entries.append(f"{path.name}/{child.name}")

    return entries[:DEFAULT_TOOL_MAX_FILES]


def read_file(
    path: str,
    offset: int = 0,
    max_bytes: int = DEFAULT_TOOL_READ_MAX_BYTES,
) -> str:
    """Read contents of a text file from byte offset up to max_bytes with paging support."""
    max_bytes = max(1, min(max_bytes, DEFAULT_TOOL_MAX_BYTES_LIMIT))
    offset = max(0, offset)
    file_path = Path(path).resolve()
    if not _is_safe_workspace_path(file_path):
        logger.warning("Access denied attempting to read path outside workspace: %s", path)
        return ERRORS.tools.access_denied_outside_workspace.format(path=path)
    if not file_path.exists() or not file_path.is_file():
        return ERRORS.tools.file_not_found.format(path=path)
    try:
        file_size = file_path.stat().st_size
        if offset >= file_size:
            return f"(Offset {offset} is at or beyond end of file ({file_size} bytes).)"
        with open(file_path, "rb") as f:
            f.seek(offset)
            raw = f.read(max_bytes + 1)
        logger.debug("Read %d bytes from %s at offset %d", len(raw), path, offset)
        has_more = len(raw) > max_bytes
        chunk = raw[:max_bytes]
        text = chunk.decode("utf-8", errors="replace")
        if has_more:
            next_offset = offset + len(chunk)
            return (
                f"{text}\n\n"
                f"... [Page ended at byte {next_offset} of {file_size}. "
                f"Use read_file(path='{path}', offset={next_offset}) to read next page.]"
            )
        return text
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Error reading file %s: %s", path, exc)
        return ERRORS.tools.error_reading_file.format(exc=exc)


def git_status() -> str:
    """Return current git status summary."""
    return _run_tool_cmd(["git", "status", "-s"], fallback_msg=MESSAGES.tools.working_tree_clean)


def git_diff() -> str:
    """Return current unstaged git diff up to 4000 characters."""
    return _run_tool_cmd(
        ["git", "diff"],
        fallback_msg=MESSAGES.tools.no_unstaged_changes,
        max_chars=DEFAULT_TOOL_DIFF_MAX_CHARS,
    )


def _file_contains_bytes(path: Path, query_bytes: bytes, query_len: int) -> bool:
    """Check whether a file contains the given query byte sequence using buffered reading."""
    try:
        with open(path, "rb") as f:
            tail = b""
            while chunk := f.read(DEFAULT_TOOL_BUFFER_CHUNK_SIZE):
                search_buf = tail + chunk
                if query_bytes in search_buf:
                    return True
                tail = chunk[-(query_len - 1) :] if query_len > 1 else b""
    except Exception:
        return False
    return False


def search_code(query: str, directory: str = ".") -> list[str]:
    """Search workspace source code and manifest files for a string query."""
    root = Path(directory).resolve()
    if not _is_safe_workspace_path(root) or not root.exists():
        return []

    matches: list[str] = []
    query_bytes = query.encode("utf-8")
    query_len = len(query_bytes)

    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() in CONST_BINARY_EXTENSIONS:
            continue
        if "__pycache__" in path.parts or any(p.startswith(".") for p in path.parts):
            continue
        if not _is_safe_workspace_path(path.resolve()):
            continue
        if _file_contains_bytes(path, query_bytes, query_len):
            matches.append(str(path.relative_to(root)))
        if len(matches) >= DEFAULT_TOOL_MAX_SEARCH_MATCHES:
            break

    return matches


def k8s_pods(namespace: str = "default") -> str:
    """Query pods in a Kubernetes namespace."""
    return _run_tool_cmd(
        ["kubectl", "get", "pods", "-n", namespace],
        fallback_msg=MESSAGES.tools.no_pods_in_namespace.format(namespace=namespace),
    )


def k8s_jaeger_status(namespace: str = "observability") -> str:
    """Check Jaeger distributed tracing backend deployment status in cluster."""
    return _run_tool_cmd(
        ["kubectl", "get", "jaegers,deployments,services", "-n", namespace],
        fallback_msg=f"No Jaeger tracing resources found in namespace '{namespace}'.",
    )


def argo_apps() -> str:
    """List ArgoCD application sync and health statuses."""
    return _run_tool_cmd(
        ["argocd", "app", "list"],
        fallback_msg=MESSAGES.tools.no_argo_apps,
    )


def _run_workspace_security_scan(
    target: str | Path,
    cmd_builder: Callable[[Path], list[str]],
    *,
    fallback_msg: str = "",
    missing_tool_name: str | None = None,
    cwd: Path | None = None,
) -> str:
    """Validate target path security boundaries and execute scanner subprocess."""
    target_path = Path(target).resolve()
    if not _is_safe_workspace_path(target_path):
        return f"Access Denied: {target} is outside workspace."
    cmd = cmd_builder(target_path)
    res = _run_tool_cmd(
        cmd,
        cwd=cwd,
        fallback_msg=fallback_msg,
        max_chars=DEFAULT_TOOL_DIFF_MAX_CHARS,
    )
    if missing_tool_name and f"No such file or directory: '{missing_tool_name}'" in res:
        cap_name = missing_tool_name.capitalize()
        return f"{cap_name} static analysis tool is not installed in the environment."
    return res


def scan_trivy(target: str = ".") -> str:
    """Run Trivy filesystem security scanner for CVEs and configuration misconfigurations."""
    return _run_workspace_security_scan(
        target,
        lambda p: ["trivy", "fs", "--severity", "HIGH,CRITICAL", str(p)],
        fallback_msg="No HIGH/CRITICAL vulnerabilities detected by Trivy.",
    )


def scan_uv_audit(directory: str = ".", requirements_file: str = "") -> str:
    """Audit Python dependencies for known CVEs using uv audit / PyPI advisory database."""
    target_dir = Path(directory).resolve()
    if not _is_safe_workspace_path(target_dir):
        return f"Access Denied: {directory} is outside workspace."
    cmd = ["uv", "audit"]
    if requirements_file:
        req_path = Path(requirements_file).resolve()
        if not _is_safe_workspace_path(req_path):
            return f"Access Denied: {requirements_file} is outside workspace."
        cmd.extend(["-r", str(req_path)])
    return _run_tool_cmd(
        cmd,
        cwd=target_dir,
        fallback_msg="No dependency vulnerabilities detected by uv audit.",
        max_chars=DEFAULT_TOOL_DIFF_MAX_CHARS,
    )


def scan_kubelinter(target: str = ".") -> str:
    """Run Red Hat Kube-linter static security and best-practice analysis on K8s manifests."""
    return _run_workspace_security_scan(
        target,
        lambda p: ["kube-linter", "lint", str(p)],
        fallback_msg="No K8s manifest lint errors detected by Kube-linter.",
    )


def scan_pluto(target: str = ".") -> str:
    """Run Fairwinds Pluto to detect deprecated and removed Kubernetes API versions."""
    return _run_workspace_security_scan(
        target,
        lambda p: ["pluto", "detect-files", "-f" if p.is_file() else "-d", str(p)],
        fallback_msg="No deprecated Kubernetes APIs detected by Pluto.",
    )


def scan_bandit(target: str = "src") -> str:
    """Run PyCQA Bandit static security vulnerability analysis on Python source files."""
    return _run_workspace_security_scan(
        target,
        lambda p: ["bandit", "-r", str(p), "-ll", "-s", "B608", "-q"],
        fallback_msg="No high/medium security issues detected by Bandit.",
        missing_tool_name="bandit",
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


def scan_osv(package_name: str, version: str = "", ecosystem: str = "PyPI") -> str:
    """Query OSV.dev and NVD vulnerability databases for known package security flaws."""
    try:
        from devops_cli.security.vulnerability_lookup import OSVClient

        client = OSVClient()
        vulns = client.query_package(package_name, version=version, ecosystem=ecosystem)
        if not vulns:
            return f"No known vulnerabilities found in OSV/NVD for {package_name} ({ecosystem})."
        lines = [f"Found {len(vulns)} vulnerability record(s) for {package_name}:"]
        for record in vulns:
            fixed = record.fixed_version or "None"
            lines.append(f"- [{record.id}] Severity: {record.severity} | Fixed: {fixed}")
            if record.summary:
                lines.append(f"  Summary: {record.summary[:150]}")
        return "\n".join(lines)
    except Exception as exc:
        return f"OSV vulnerability query error: {exc}"


def check_threat_intel(target: str) -> str:
    """Check IP or domain threat intelligence via Shodan InternetDB or Cloudflare Radar."""
    try:
        from devops_cli.security.reference_extractor import is_public_ip
        from devops_cli.security.vulnerability_lookup import (
            CloudflareRadarClient,
            ShodanInternetDBClient,
        )

        if is_public_ip(target):
            shodan = ShodanInternetDBClient()
            rep = shodan.check_ip(target)
            ports = ", ".join(str(p) for p in rep.ports) or "None detected"
            vulns = ", ".join(rep.cves) or "None detected"
            return (
                f"Shodan Intelligence for IP {target}:\n"
                f"- Hostnames: {', '.join(rep.hostnames) or 'None'}\n"
                f"- Open Ports: {ports}\n"
                f"- Known CVEs: {vulns}\n"
                f"- Reputation Summary: {rep.reputation_summary}"
            )
        else:
            radar = CloudflareRadarClient()
            rep = radar.check_domain(target)
            return (
                f"Cloudflare Radar Intelligence for Domain {target}:\n"
                f"- Threat Categories: {', '.join(rep.tags) or 'General'}\n"
                f"- Reputation Summary: {rep.reputation_summary}"
            )
    except Exception as exc:
        return f"Threat intelligence check error: {exc}"
