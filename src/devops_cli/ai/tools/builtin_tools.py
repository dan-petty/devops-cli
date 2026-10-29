"""Built-in workspace inspection and execution tools for PydanticAgent."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from devops_cli.config.constants import (
    CONST_AGENT_SCAN_STATUS_WORDS,
    CONST_BINARY_EXTENSIONS,
    CONST_SCAN_NO_RESULT_STATUSES,
)
from devops_cli.config.defaults import (
    DEFAULT_K8S_NAMESPACE,
    DEFAULT_OBSERVABILITY_NAMESPACE,
    DEFAULT_PACKAGE_ECOSYSTEM,
    DEFAULT_SEMGREP_CONFIG,
    DEFAULT_SRC_DIR,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    DEFAULT_TOOL_BUFFER_CHUNK_SIZE,
    DEFAULT_TOOL_DIFF_MAX_CHARS,
    DEFAULT_TOOL_MAX_BYTES_LIMIT,
    DEFAULT_TOOL_MAX_FILES,
    DEFAULT_TOOL_MAX_SEARCH_MATCHES,
    DEFAULT_TOOL_READ_MAX_BYTES,
)
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import find_repo_root, is_ignored_by_git, is_safe_subpath
from devops_cli.lang import ERRORS, MESSAGES
from devops_cli.models.vulnerability import VulnerabilityRecord

if TYPE_CHECKING:
    from devops_cli.ai.review_schema import Finding
    from devops_cli.security.base import ScanOutcome

logger = logging.getLogger(__name__)


def _is_safe_workspace_path(target: Path, workspace_root: Path | None = None) -> bool:
    if target.is_symlink():
        return False
    root = workspace_root or Path.cwd()
    return is_safe_subpath(root, target)


def _truncated(text: str, max_chars: int = DEFAULT_TOOL_DIFF_MAX_CHARS) -> str:
    """`text`, cut at `max_chars` characters with a line that says where, when it is longer."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... [truncated at {max_chars} chars]"


def _run_tool_cmd(
    cmd: list[str],
    fallback_msg: str = "",
    max_chars: int = DEFAULT_TOOL_DIFF_MAX_CHARS,
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
            return _truncated(output, max_chars) if output else fallback_msg
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


def _is_valid_dir_entry(path: Path) -> bool:
    """Check if directory entry is non-hidden, non-cache and within safe workspace."""
    if path.name.startswith(".") or path.name == "__pycache__":
        return False
    return _is_safe_workspace_path(path.resolve())


def list_files(directory: str = ".") -> list[str]:
    """List non-hidden files in the specified directory up to 2 levels deep."""
    root = Path(directory).resolve()
    if not _is_safe_workspace_path(root) or not root.is_dir():
        return []

    entries: list[str] = []
    for path in sorted(root.glob("*")):
        if not _is_valid_dir_entry(path):
            continue
        if path.is_file():
            entries.append(path.name)
        elif path.is_dir():
            entries.extend(
                f"{path.name}/{child.name}"
                for child in sorted(path.glob("*"))
                if _is_valid_dir_entry(child)
            )

    return entries[:DEFAULT_TOOL_MAX_FILES]


def read_file(
    path: str,
    offset: int = 0,
    max_bytes: int = DEFAULT_TOOL_READ_MAX_BYTES,
) -> str:
    """Read contents of a text file from byte offset up to max_bytes with paging support."""
    try:
        parsed_offset = int(offset)
    except ValueError, TypeError:
        parsed_offset = 0
    try:
        parsed_max_bytes = int(max_bytes)
    except ValueError, TypeError:
        parsed_max_bytes = DEFAULT_TOOL_READ_MAX_BYTES

    max_bytes = max(1, min(parsed_max_bytes, DEFAULT_TOOL_MAX_BYTES_LIMIT))
    offset = max(0, parsed_offset)
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


def _is_searchable_file(path: Path, repo_root: Path | None = None) -> bool:
    """Check if file is text/manifest and within safe workspace path."""
    if not path.is_file() or path.suffix.lower() in CONST_BINARY_EXTENSIONS:
        return False
    root = repo_root or find_repo_root(path)
    if is_ignored_by_git(root, path):
        return False
    return _is_safe_workspace_path(path.resolve())


def search_code(query: str, directory: str = ".") -> list[str]:
    """Search workspace source code and manifest files for a string query."""
    root = Path(directory).resolve()
    if not _is_safe_workspace_path(root) or not root.exists():
        return []

    repo_root = find_repo_root(root)
    matches: list[str] = []
    query_bytes = query.encode("utf-8")
    query_len = len(query_bytes)

    for path in root.rglob("*"):
        if _is_searchable_file(path, repo_root) and _file_contains_bytes(
            path, query_bytes, query_len
        ):
            matches.append(str(path.relative_to(root)))
            if len(matches) >= DEFAULT_TOOL_MAX_SEARCH_MATCHES:
                break

    return matches


def k8s_pods(namespace: str = DEFAULT_K8S_NAMESPACE) -> str:
    """Query pods in a Kubernetes namespace."""
    return _run_tool_cmd(
        ["kubectl", "get", "pods", "-n", namespace],
        fallback_msg=MESSAGES.tools.no_pods_in_namespace.format(namespace=namespace),
    )


def k8s_tempo_status(namespace: str = DEFAULT_OBSERVABILITY_NAMESPACE) -> str:
    """Check Tempo distributed tracing backend deployment status in cluster."""
    return _run_tool_cmd(
        ["kubectl", "get", "deployments,statefulsets,services", "-n", namespace],
        fallback_msg=f"No Tempo tracing resources found in namespace '{namespace}'.",
    )


def argo_apps() -> str:
    """List ArgoCD application sync and health statuses."""
    return _run_tool_cmd(
        ["argocd", "app", "list"],
        fallback_msg=MESSAGES.tools.no_argo_apps,
    )


def argo_app_status(app_name: str) -> str:
    """Get detailed health and sync status for a specific ArgoCD application."""
    return _run_tool_cmd(
        ["argocd", "app", "get", app_name],
        fallback_msg=MESSAGES.tools.argo_app_not_found.format(app_name=app_name),
    )


def _workspace_target(target: str | Path) -> Path | None:
    """`target` resolved, when it lies inside the workspace; else None."""
    target_path = Path(target).resolve()
    return target_path if _is_safe_workspace_path(target_path) else None


def _outside_workspace_reply(target: str | Path) -> str:
    """The reply of a tool that refuses a target outside the workspace."""
    return f"Access Denied: {target} is outside workspace."


def _finding_line(finding: Finding) -> str:
    """One finding of a scan reply: its severity, location and title, then its fix if it has one."""
    line = MESSAGES.tools.scan_finding.format(
        severity=finding.severity, location=finding.location, title=finding.title
    )
    return (
        MESSAGES.tools.scan_finding_fix.format(finding=line, fix=finding.fix)
        if finding.fix
        else line
    )


def _scan_reply(scanner: str, outcome: ScanOutcome) -> str:
    """The reply of an agent scan tool: the status of the scan first, then why when the outcome
    says, then the findings, or that the scan gave no result (#1435).

    The whole reply is masked, then cut at the limit of a tool's output, so the cut cannot split a
    secret that the masking patterns would match.
    """
    from devops_cli.security.sanitizer import mask_secrets

    status = CONST_AGENT_SCAN_STATUS_WORDS.get(outcome.status, outcome.status)
    lines = [MESSAGES.tools.scan_status.format(scanner=scanner, status=status)]
    if outcome.reason:
        lines.append(MESSAGES.tools.scan_reason.format(reason=outcome.reason))
    if outcome.status in CONST_SCAN_NO_RESULT_STATUSES:
        lines.append(MESSAGES.tools.scan_gave_no_result)
    elif outcome.findings:
        lines.append(MESSAGES.tools.scan_findings.format(count=len(outcome.findings)))
        lines.extend(_finding_line(finding) for finding in outcome.findings)
    else:
        lines.append(MESSAGES.tools.scan_no_findings)
    return _truncated(mask_secrets("\n".join(lines)))


def _run_adapter_scan(scanner: str, target: str, scan: Callable[[Path], ScanOutcome]) -> str:
    """Run the scanner adapter `scan` over `target`, a path inside the workspace, and reply with
    its outcome."""
    target_path = _workspace_target(target)
    if target_path is None:
        return _outside_workspace_reply(target)
    return _scan_reply(scanner, scan(target_path))


def scan_trivy(target: str = ".") -> str:
    """Run Aqua Trivy filesystem security scanner for CVEs, secrets, and misconfigurations."""
    from devops_cli.security.trivy import run_trivy_scan

    return _run_adapter_scan("Trivy", target, run_trivy_scan)


def scan_uv_audit(directory: str = ".") -> str:
    """Audit the packages that the uv.lock of a project pins, as it is, for known vulnerabilities and adverse project statuses, with uv audit."""
    from devops_cli.security.uv_audit import run_uv_audit_scan

    return _run_adapter_scan("uv audit", directory, run_uv_audit_scan)


def scan_kubelinter(target: str = ".") -> str:
    """Run kube-linter static security and linting analysis across Kubernetes YAML manifests."""
    from devops_cli.security.kubelinter import run_kubelinter_scan

    return _run_adapter_scan("Kube-linter", target, run_kubelinter_scan)


def scan_pluto(target: str = ".") -> str:
    """Detect deprecated and removed Kubernetes API versions in Helm charts and manifests."""
    from devops_cli.security.pluto import run_pluto_scan

    return _run_adapter_scan("Pluto", target, run_pluto_scan)


def scan_bandit(target: str = DEFAULT_SRC_DIR) -> str:
    """Run PyCQA Bandit static security vulnerability analysis on Python source files."""
    from devops_cli.security.bandit import run_bandit_scan

    return _run_adapter_scan("Bandit", target, run_bandit_scan)


def scan_popeye(namespace: str = "") -> str:
    """Run Popeye Kubernetes cluster and namespace resource sanitizer."""
    from devops_cli.security.popeye import run_popeye_scan

    return _scan_reply("Popeye", run_popeye_scan(namespace=namespace or None))


def scan_gitleaks(target: str = ".") -> str:
    """Run Gitleaks secret pre-filter scan across workspace or targets."""
    from devops_cli.security.gitleaks import run_gitleaks_scan

    return _run_adapter_scan("Gitleaks", target, run_gitleaks_scan)


def scan_semgrep(target: str = ".", config: str = DEFAULT_SEMGREP_CONFIG) -> str:
    """Run Semgrep multilingual static AST pattern matching scan.

    A registry ruleset such as `p/default` is read from the cache `devops review rules fetch`
    writes: the scan reaches no registry, and runs from the cache directory so that rule ids are
    plain. With no cache it runs devops-cli's rule pack alone, and the reply calls it a coverage
    gap and names the fetch command (#1144).
    """
    from devops_cli.security.semgrep import run_semgrep_scan

    return _run_adapter_scan(
        "Semgrep", target, lambda target_path: run_semgrep_scan(target_path, config=config)
    )


def rag_search(
    query: str,
    top_k: int | None = None,
    project: str | None = None,
    language: str | None = None,
    category: str | None = None,
) -> str:
    """Perform semantic vector retrieval over indexed workspace code, polyglot repos, and docs."""
    from devops_cli.ai.rag.embeddings import EmbeddingsEngine, EmbeddingsError

    try:
        from devops_cli.ai.rag.qdrant import QdrantClient
        from devops_cli.ai.rag.retriever import SemanticRetriever
        from devops_cli.config.settings import get_ai_api_key, get_qdrant_api_key, load_settings

        settings = load_settings()
        qdrant_url = settings.qdrant.url
        if not qdrant_url:
            return "RAG vector database unconfigured (qdrant.url is not set). Fallback: use search_code."
        prefix = settings.qdrant.collection_prefix or "devops"
        qdrant = QdrantClient(
            base_url=qdrant_url,
            api_key=get_qdrant_api_key(settings),
            allow_private_network=settings.ai.allow_private_network,
            timeout=settings.qdrant.timeout,
        )
        if not qdrant.is_alive():
            return f"RAG vector database unavailable at {qdrant_url}. Fallback: use search_code."

        from devops_cli.ai.rag.kb_sync import ensure_knowledge_base_ready

        embedder = EmbeddingsEngine(ai_config=settings.ai, api_key=get_ai_api_key(settings))
        code_coll = f"{prefix}_code"
        docs_coll = f"{prefix}_docs"
        ensure_knowledge_base_ready(qdrant, embedder, docs_coll, code_coll)

        retriever = SemanticRetriever(
            qdrant=qdrant,
            embedder=embedder,
            code_collection=code_coll,
            docs_collection=docs_coll,
            # A `top_k` that the model does not give, and the score threshold, are the settings'.
            default_top_k=settings.ai.rag.top_k,
            default_score_threshold=settings.ai.rag.score_threshold,
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
    except EmbeddingsError as exc:
        return MESSAGES.rag.search_embedding_failed.format(error=exc.message)
    except Exception as exc:
        return f"RAG search error: {exc}"


def _osv_records_reply(
    package_name: str, ecosystem: str, records: list[VulnerabilityRecord]
) -> str:
    """The reply to a lookup OSV answered: its advisory records, or that it has none."""
    if not records:
        return f"No known vulnerabilities found in OSV for {package_name} ({ecosystem})."
    lines = [f"Found {len(records)} vulnerability record(s) for {package_name}:"]
    for record in records:
        fixed = record.fixed_version or "None"
        lines.append(f"- [{record.id}] Severity: {record.severity} | Fixed: {fixed}")
        if record.summary:
            lines.append(f"  Summary: {record.summary[:150]}")
    return "\n".join(lines)


def scan_osv(
    package_name: str, version: str = "", ecosystem: str = DEFAULT_PACKAGE_ECOSYSTEM
) -> str:
    """Query the OSV.dev vulnerability database for known package security flaws."""
    try:
        from devops_cli.security.vulnerability_lookup import OSVClient

        lookup = OSVClient().query_package(package_name, version=version, ecosystem=ecosystem)
        if lookup.status != "ok":
            return f"OSV lookup failed: {lookup.reason}"
        return _osv_records_reply(package_name, ecosystem, lookup.vulnerabilities)
    except Exception as exc:
        return f"OSV vulnerability query error: {exc}"


def _excluded_target_reply(target: str) -> str:
    """The reply about a documented example or an unspecified address, which no service is asked."""
    return (
        f"Target {target} is a documented example or an unspecified address: "
        "an example domain (RFC 2606 / RFC 6761), "
        "a documentation address (RFC 5737 / RFC 3849 / RFC 9637), "
        "a benchmarking address (RFC 2544 / RFC 5180), "
        "a fictional phone number (ATIS-0300115 / Ofcom drama numbers) "
        "or an unspecified address (RFC 1122 / RFC 4291). "
        "Excluded from external threat intelligence scanning."
    )


def _local_address_reply(target: str, address: str) -> str:
    """The reply about a local address, which no service is asked about."""
    return (
        f"Target {target} is a local address ({address}): private, loopback, link-local, "
        "shared, site-local, multicast or reserved space, which is not globally reachable. "
        "No threat intelligence service was asked."
    )


def _shodan_reply(address: str) -> str:
    """The reply Shodan InternetDB gives about a public address."""
    from devops_cli.security.vulnerability_lookup import ShodanInternetDBClient

    rep = ShodanInternetDBClient().check_ip(address)
    if rep.outcome in ("unavailable", "failed"):
        return (
            f"Shodan Intelligence for IP {address}:\n- Reputation Summary: {rep.reputation_summary}"
        )
    ports = ", ".join(str(p) for p in rep.ports) or "None detected"
    vulns = ", ".join(rep.cves) or "None detected"
    return (
        f"Shodan Intelligence for IP {address}:\n"
        f"- Hostnames: {', '.join(rep.hostnames) or 'None'}\n"
        f"- Open Ports: {ports}\n"
        f"- Known CVEs: {vulns}\n"
        f"- Reputation Summary: {rep.reputation_summary}"
    )


def _radar_reply(domain: str) -> str:
    """The reply Cloudflare Radar gives about a domain."""
    from devops_cli.security.vulnerability_lookup import CloudflareRadarClient

    rep = CloudflareRadarClient().check_domain(domain)
    if rep.outcome in ("unavailable", "failed"):
        return (
            f"Cloudflare Radar Intelligence for Domain {domain}:\n"
            f"- Reputation Summary: {rep.reputation_summary}"
        )
    return (
        f"Cloudflare Radar Intelligence for Domain {domain}:\n"
        f"- Threat Categories: {', '.join(rep.tags) or 'General'}\n"
        f"- Reputation Summary: {rep.reputation_summary}"
    )


def check_threat_intel(target: str) -> str:
    """Check IP or domain threat intelligence via Shodan InternetDB or Cloudflare Radar.

    A target that names an address (`network_target_address`), after prose punctuation, in a URL
    or in a numeric spelling, is that address: Shodan is asked about a public one, and no service
    about a local one, a documented example or an unspecified address. Radar is asked about the
    rest, which are domains.
    """
    try:
        from devops_cli.security.reference_extractor import (
            is_example_or_invalid_network_target,
            is_public_ip,
            network_target_address,
        )

        if is_example_or_invalid_network_target(target):
            return _excluded_target_reply(target)
        address = network_target_address(target)
        if address is None:
            return _radar_reply(target)
        if is_public_ip(str(address)):
            return _shodan_reply(str(address))
        return _local_address_reply(target, str(address))
    except Exception as exc:
        return f"Threat intelligence check error: {exc}"


def scan_iac(target: str = ".") -> str:
    """Run Trivy's misconfiguration scan (trivy config) on IaC files: Dockerfiles, Kubernetes
    manifests, Helm charts, Terraform and CloudFormation."""
    from devops_cli.security.trivy import TrivyConfigScanner

    return _run_adapter_scan("Trivy", target, TrivyConfigScanner().scan)


def tf_lint(target: str = ".") -> str:
    """Run TFLint static analysis on Terraform/OpenTofu code."""
    try:
        from devops_cli.security.tflint import run_tflint_scan

        findings = run_tflint_scan(target_dir=Path(target))
        if not findings:
            return f"TFLint scan clean for '{target}'. No issues found."
        lines = [f"Found {len(findings)} TFLint issue(s) in '{target}':"]
        for f in findings:
            lines.append(f"- [{f.severity}] {f.location}: {f.title}")
        return "\n".join(lines)
    except Exception as exc:
        return f"TFLint execution error: {exc}"


def k8s_validate_manifests(target: str = ".") -> str:
    """Validate Kubernetes YAML manifests against their JSON schemas using Kubeconform."""
    from devops_cli.security.kubeconform import run_kubeconform_validation

    return _run_adapter_scan("Kubeconform", target, run_kubeconform_validation)


def docker_analyze_layers(image: str) -> str:
    """Analyze container image layers and wasted space using Dive."""
    try:
        from devops_cli.security.dive import run_dive_analysis

        result = run_dive_analysis(image_name=image)
        if result.status == "unavailable":
            return f"Dive not available: {result.reason}"
        if result.status == "failed":
            return f"Dive analysis failed: {result.reason}"
        eff_pct = result.efficiency_score * 100
        wasted_mb = result.wasted_bytes / (1024 * 1024)
        total_mb = result.total_bytes / (1024 * 1024)
        return (
            f"Dive Container Analysis for '{image}':\n"
            f"- Efficiency Score: {eff_pct:.1f}%\n"
            f"- Total Image Size: {total_mb:.1f} MB\n"
            f"- Wasted Space: {wasted_mb:.1f} MB\n"
            f"- Total Layers Analyzed: {len(result.layers)}"
        )
    except Exception as exc:
        return f"Dive layer analysis error: {exc}"
