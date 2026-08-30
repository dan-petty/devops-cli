"""Multi-Agent Pipeline Orchestrator for Code Reviews.

Example:
    >>> from devops_cli.ai.client import LLMClient
    >>> from devops_cli.ai.review import ReviewPipelineOrchestrator
    >>>
    >>> orchestrator = ReviewPipelineOrchestrator(session_id="session-001")
    >>> metadata = orchestrator.run_pre_analysis_refresh()
    >>> payloads = orchestrator.init_per_file_payloads(["src/main.py"], metadata)
    >>> orchestrator.execute_multi_persona_review(payloads, {"src/main.py": "def main(): pass"})
    >>> orchestrator.execute_finding_verification(payloads)
    >>> orchestrator.execute_finding_reranking(payloads)
    >>> data_out, report_md = orchestrator.generate_consolidated_report(payloads)
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from devops_cli.ai.agents.pipeline import MultiAgentPipeline
from devops_cli.ai.agents.pydantic_agent import PydanticAgent
from devops_cli.ai.analyze.cache import load_cached_analysis
from devops_cli.ai.analyze.outlines import analyze_single_file
from devops_cli.ai.client import LLMClient
from devops_cli.ai.personas import PERSONAS
from devops_cli.ai.review.flags import ReviewStageFlags
from devops_cli.ai.review.sanitization import (
    _escape_backticks,
    _mask_secrets_in_content,
    _sanitize_filename,
    _sanitize_prompt_boundary_tags,
)
from devops_cli.ai.review.verification import _validate_segment_findings
from devops_cli.ai.review_schema import (
    FileReviewPayload,
    Finding,
    ReviewResult,
    ReviewSessionPayload,
    SavedFinding,
    consolidate_duplicate_findings,
    format_clean_text_field,
    parse_review_response,
)
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.ai.thinking_stream import extract_think_blocks
from devops_cli.config.constants import (
    CONST_MAX_FILE_SIZE_BYTES,
)
from devops_cli.config.defaults import DEFAULT_CURRENT_PATH
from devops_cli.models.ai import FileAnalysisMeta
from devops_cli.models.vulnerability import (
    DependencySpec,
    NetworkReference,
    NetworkReputationRecord,
    VulnerabilityRecord,
)
from devops_cli.output import escape_text, print_info, print_panel, print_success, print_table
from devops_cli.security.reference_extractor import (
    extract_dependencies_from_text,
    extract_network_references,
)
from devops_cli.security.vulnerability_lookup import (
    CloudflareRadarClient,
    OSVClient,
    ShodanInternetDBClient,
)
from devops_cli.telemetry import ContextPropagatingThreadPoolExecutor as ThreadPoolExecutor
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)

_REVIEW_PIPELINE_EVAL = load_task_prompt("review_pipeline_eval.md")

_UNIVERSAL_MODULES: set[str] = {
    "__future__",
    "typing",
    "pathlib",
    "os",
    "sys",
    "re",
    "json",
    "logging",
    "time",
    "subprocess",
    "asyncio",
    "datetime",
    "unittest",
    "pytest",
    "abc",
    "collections",
    "collections.abc",
    "math",
    "shutil",
    "tempfile",
    "io",
    "copy",
    "functools",
    "itertools",
    "enum",
    "dataclasses",
    "contextlib",
    "threading",
    "traceback",
    "pydantic",
    "rich",
    "typer",
}

_SEV_ORDER: dict[str, int] = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
    "INFO": 0,
    "CLEAN": -1,
    "NONE": -1,
}


def _resolve_ollama_urls(config: Any) -> list[str]:
    """Safely resolve configured Ollama base URLs handling properties and callables."""
    if not config:
        return ["http://localhost:11434"]
    raw_urls = getattr(config, "get_ollama_urls", None)
    if callable(raw_urls):
        try:
            raw_urls = raw_urls()
        except Exception:
            raw_urls = None
    if isinstance(raw_urls, list) and raw_urls:
        return [str(u).strip().rstrip("/") for u in raw_urls if str(u).strip()]
    raw_list = getattr(config, "ollama_urls", None)
    if isinstance(raw_list, list) and raw_list:
        return [str(u).strip().rstrip("/") for u in raw_list if str(u).strip()]
    return ["http://localhost:11434"]


def _append_step_thoughts(step: Any, thoughts_list: list[str]) -> None:
    """Extract and append thoughts or think blocks from pipeline step to scratchpad."""
    if getattr(step, "thoughts", None):
        for t in step.thoughts:
            t_clean = t.strip()
            if t_clean and t_clean not in thoughts_list:
                thoughts_list.append(f"[{step.agent_name}] {t_clean}")
    elif getattr(step, "content", None):
        thinks, _ = extract_think_blocks(step.content)
        for t in thinks:
            t_clean = t.strip()
            if t_clean and t_clean not in thoughts_list:
                thoughts_list.append(f"[{step.agent_name}] {t_clean}")


def _process_pipeline_step_findings(
    step: Any,
    fpath: str,
    p_idx: int,
    total_pages: int,
    persona_lookup: dict[str, tuple[str, str]],
    thoughts_list: list[str],
    actual_servers: list[str],
    file_findings: list[SavedFinding],
) -> None:
    """Process findings and metadata from an individual agent review step."""
    if getattr(step, "backend_info", None) and step.backend_info not in actual_servers:
        actual_servers.append(step.backend_info)

    _append_step_thoughts(step, thoughts_list)

    parsed: ReviewResult | None = (
        step.parsed_data
        if getattr(step, "parsed_data", None) and isinstance(step.parsed_data, ReviewResult)
        else parse_review_response(getattr(step, "content", "") or "")
    )

    p_val, p_title = persona_lookup.get(
        step.agent_name,
        (step.agent_name.lower().replace(" ", "_"), step.agent_name),
    )

    rec_str = parsed.recommendation if parsed else "REVIEW"
    n_findings_step = len(parsed.findings) if parsed else 0
    p_suffix = f" [p.{p_idx}/{total_pages}]" if total_pages > 1 else ""
    thoughts_list.append(
        f"[{p_title}] Evaluated {fpath}{p_suffix}: {rec_str} ({n_findings_step} finding(s))"
    )

    if not parsed or not parsed.findings:
        return

    for f in parsed.findings:
        if f.is_empty:
            continue
        loc = f.location.strip() or fpath
        saved = SavedFinding(
            **f.model_dump(exclude={"location"}),
            location=loc,
            persona=p_val,
            persona_title=p_title,
        )
        if not saved.is_empty:
            file_findings.append(saved)


def _try_reuse_cached_analysis_meta(
    old_meta: FileAnalysisMeta, file_path: Path, file_mtime: datetime
) -> FileAnalysisMeta | None:
    """Attempt to reuse cached analysis metadata if file has not been modified and content matches."""
    if not (old_meta.last_analyzed and old_meta.pseudocode):
        return None
    try:
        if not file_path.is_file():
            return None
        st = file_path.stat()
        if old_meta.size_bytes and st.st_size != old_meta.size_bytes:
            return None
        analyzed_dt = datetime.fromisoformat(old_meta.last_analyzed)
        if file_mtime > analyzed_dt:
            return None
        cur_hash = hashlib.sha256(file_path.read_bytes(), usedforsecurity=False).hexdigest()
        if old_meta.content_hash and cur_hash != old_meta.content_hash:
            return None
        return old_meta.model_copy(update={"content_hash": cur_hash})
    except Exception as exc:
        logger.debug("Failed validating cached metadata for %s: %s", file_path, exc)
    return None


def _wrap_static_findings(findings: list[Finding]) -> list[SavedFinding]:
    """Wrap generic findings from static analyzers into DevSecOps SavedFindings."""
    return [
        SavedFinding(
            **f.model_dump(),
            persona="devsecops",
            persona_title="Principal DevSecOps Engineer",
        )
        for f in findings
    ]


def _match_static_findings_to_files(
    findings: list[SavedFinding], file_paths: list[str]
) -> dict[str, list[SavedFinding]]:
    """Map findings from static analyzers to corresponding target repository files."""
    by_file: dict[str, list[SavedFinding]] = {}
    for sf in findings:
        loc_path = sf.location.split(":")[0].strip()
        matched = next(
            (
                fp
                for fp in file_paths
                if fp == loc_path or loc_path.endswith(fp) or fp.endswith(loc_path)
            ),
            None,
        )
        if matched:
            by_file.setdefault(matched, []).append(sf)
    return by_file


def _scan_kubernetes_manifests(yaml_paths: list[Path]) -> list[SavedFinding]:
    """Scan Kubernetes YAML manifests with Kube-linter and Pluto."""
    from devops_cli.security.kubelinter import run_kubelinter_scan
    from devops_cli.security.pluto import run_pluto_scan

    findings: list[SavedFinding] = []
    for yp in yaml_paths:
        if kl := run_kubelinter_scan(yp):
            findings.extend(_wrap_static_findings(kl))
        if pl := run_pluto_scan(yp):
            findings.extend(_wrap_static_findings(pl))
    return findings


def _scan_container_and_lockfiles(docker_lock_paths: list[Path]) -> list[SavedFinding]:
    """Scan container files and lockfiles with Trivy."""
    from devops_cli.security.trivy import run_trivy_scan

    findings: list[SavedFinding] = []
    for dp in docker_lock_paths:
        scan_t = "config" if "docker" in dp.name.lower() else "fs"
        if t_findings := run_trivy_scan(dp, scan_type=scan_t):
            findings.extend(_wrap_static_findings(t_findings))
    return findings


def _build_vulnerability_finding(
    fpath: str, dep: DependencySpec, v: VulnerabilityRecord
) -> SavedFinding:
    """Build a verified SavedFinding for an identified vulnerable package dependency."""
    desc = f"Dependency '{dep.name}' ({dep.version_range}) is affected by {v.id}: {v.summary}"
    return SavedFinding(
        severity=v.severity,
        location=f"{fpath}:1",
        title=f"Vulnerable Dependency: {dep.name} ({v.id})",
        description=desc,
        fix=f"Upgrade '{dep.name}' to a patched release.",
        references=[v.details_url] if v.details_url else [],
        verification_criteria=[f"Package '{dep.name}' declared in {fpath}"],
        invalidation_criteria=["Dependency upgraded or patched in lockfile"],
        verified_criteria_matched=[f"Package '{dep.name}' declared in {fpath}"],
        status="VERIFIED",
        verified=True,
        reportable=True,
        confidence_score=getattr(v, "cvss_score", None),
        persona="devsecops",
        persona_title="Principal DevSecOps Engineer",
    )


def _build_malicious_network_finding(
    fpath: str, net: NetworkReference, rep: NetworkReputationRecord
) -> SavedFinding:
    """Build a verified SavedFinding for an identified suspicious external network target."""
    ref_urls = [f"https://internetdb.shodan.io/{rep.ip}"] if rep.ip else []
    desc = f"External host '{net.target}' flagged by {rep.source}: {rep.reputation_summary}"
    return SavedFinding(
        severity="HIGH",
        location=f"{fpath}:{net.line_number or 1}",
        title=f"Suspicious / Vulnerable Network Reference: {net.target}",
        description=desc,
        fix=f"Sanitize or remove external host reference '{net.target}'",
        references=ref_urls,
        verification_criteria=[f"Host '{net.target}' referenced in {fpath}"],
        invalidation_criteria=["Internal test fixture or isolated sandbox"],
        verified_criteria_matched=[f"Host '{net.target}' referenced in {fpath}"],
        status="VERIFIED",
        verified=True,
        reportable=True,
        confidence_score=None,
        persona="devsecops",
        persona_title="Principal DevSecOps Engineer",
    )


def _create_initial_scratchpad(fpath: str, initial_findings_count: int) -> dict[str, Any]:
    """Create initial tracking scratchpad payload for a reviewed file."""
    thoughts = [f"Tracking findings for {fpath}"]
    if initial_findings_count > 0:
        thoughts.append(f"Injected {initial_findings_count} static scan / threat intel finding(s)")
    return {
        "initialized_at": datetime.now(UTC).isoformat(),
        "stage": "initialized",
        "thoughts": thoughts,
    }


def _build_page_review_prompt(
    fpath: str,
    p_idx: int,
    total_pages: int,
    page_content: str,
    symbols: str,
    rag_context_str: str,
) -> str:
    """Construct sanitized review prompt for a specific paginated slice of source code."""
    masked = _mask_secrets_in_content(page_content)
    clean = _sanitize_prompt_boundary_tags(_escape_backticks(masked))
    prefix = (
        f"Review File: {fpath} (Page {p_idx}/{total_pages})\n"
        if total_pages > 1
        else f"Review File: {fpath}\n"
    )
    return f"{prefix}Key Symbols: {symbols}{rag_context_str}\n\nCode Content / Diff:\n{clean}"


def _collect_linked_snippets(
    linked_files: Sequence[FileAnalysisMeta],
    resolve_fn: Callable[[str], Path],
) -> list[str]:
    """Extract code context snippets from linked repository files."""
    snippets: list[str] = []
    for lmeta in linked_files:
        lpath = resolve_fn(lmeta.path)
        if lpath.exists() and lpath.is_file():
            try:
                snippet = lpath.read_text(encoding="utf-8", errors="replace")[:2000]
                snippets.append(f"Linked File ({lmeta.path}):\n{snippet}")
            except Exception as exc:
                logger.debug("Failed reading linked file %s: %s", lmeta.path, exc)
    return snippets


def _probe_single_dir_deps(
    p_dir: Path,
    raw_file_data: dict[str, tuple[list[DependencySpec], list[NetworkReference]]],
    all_unique_deps: set[tuple[str, str, str]],
) -> bool:
    """Probe a single directory for manifest files and extract declared dependencies."""
    try:
        candidates = sorted(p_dir.iterdir())
    except OSError:
        return False
    for candidate in candidates:
        if not candidate.is_file() or candidate.is_symlink():
            continue
        try:
            c_text = candidate.read_text(encoding="utf-8", errors="replace")
            c_rel = (
                str(candidate.relative_to(Path.cwd()))
                if candidate.is_relative_to(Path.cwd())
                else candidate.name
            )
            if extracted := extract_dependencies_from_text(c_text, c_rel):
                raw_file_data.setdefault(c_rel, ([], []))
                raw_file_data[c_rel][0].extend(extracted)
                all_unique_deps.update((d.name, d.version_range, d.ecosystem) for d in extracted)
        except Exception:
            pass
    return bool(all_unique_deps)


def _probe_manifest_deps_in_dirs(
    probe_dirs: list[Path],
    raw_file_data: dict[str, tuple[list[DependencySpec], list[NetworkReference]]],
    all_unique_deps: set[tuple[str, str, str]],
) -> None:
    """Probe directories for manifest files and extract declared dependencies."""
    for p_dir in probe_dirs:
        if _probe_single_dir_deps(p_dir, raw_file_data, all_unique_deps):
            break


def _probe_single_dir_nets(
    p_dir: Path,
    raw_file_data: dict[str, tuple[list[DependencySpec], list[NetworkReference]]],
    all_unique_nets: set[tuple[str, str]],
) -> bool:
    """Probe a single directory for source files and extract declared network targets."""
    try:
        candidates = sorted(p_dir.iterdir())
    except OSError:
        return False
    for candidate in candidates:
        if not candidate.is_file() or candidate.is_symlink() or candidate.name.startswith("."):
            continue
        try:
            c_text = candidate.read_text(encoding="utf-8", errors="replace")
            c_rel = (
                str(candidate.relative_to(Path.cwd()))
                if candidate.is_relative_to(Path.cwd())
                else candidate.name
            )
            if extracted := extract_network_references(c_text, c_rel):
                raw_file_data.setdefault(c_rel, ([], []))
                raw_file_data[c_rel][1].extend(extracted)
                all_unique_nets.update((n.target, n.reference_type) for n in extracted)
        except Exception:
            pass
    return bool(all_unique_nets)


def _probe_network_refs_in_dirs(
    probe_dirs: list[Path],
    raw_file_data: dict[str, tuple[list[DependencySpec], list[NetworkReference]]],
    all_unique_nets: set[tuple[str, str]],
) -> None:
    """Probe directories for source files and extract declared network targets."""
    for p_dir in probe_dirs:
        if _probe_single_dir_nets(p_dir, raw_file_data, all_unique_nets):
            break


def _format_extraction_summary(
    direct_deps_count: int,
    direct_nets_count: int,
    probed_deps_count: int,
    probed_nets_count: int,
) -> str:
    """Format summary string distinguishing in-file references from probed workspace references."""
    if probed_deps_count == 0 and probed_nets_count == 0:
        return (
            f"{direct_deps_count} unique dependency(ies) and {direct_nets_count} network target(s)"
        )

    probed_parts: list[str] = []
    if probed_deps_count > 0:
        probed_parts.append(
            f"{probed_deps_count} project dependencies probed from workspace manifests"
        )
    if probed_nets_count > 0:
        probed_parts.append(f"{probed_nets_count} network targets probed from workspace configs")
    probed_summary = ", ".join(probed_parts)

    if direct_deps_count == 0 and direct_nets_count == 0:
        return f"0 in-file references ({probed_summary})"

    return (
        f"{direct_deps_count} in-file dependency(ies) and {direct_nets_count} in-file network target(s) "
        f"({probed_summary})"
    )


def _execute_pre_analysis_batch(
    paths_to_analyze: list[tuple[Path, str]],
    repo: Path,
    ai_client: LLMClient,
    batch_capacity: int,
) -> list[FileAnalysisMeta]:
    """Execute parallel pre-analysis across batch of repository paths."""

    def _analyze_path(item: tuple[Path, str]) -> FileAnalysisMeta | None:
        path_obj, rel_path = item
        try:
            content = path_obj.read_text(encoding="utf-8", errors="replace")
            return analyze_single_file(
                rel_path,
                content,
                path_obj.stat().st_size,
                enhanced=True,
                repo_root=repo,
                ai_client=ai_client,
            )
        except Exception:
            return None

    results: list[FileAnalysisMeta] = []
    workers = min(len(paths_to_analyze), batch_capacity, 32)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for meta in executor.map(_analyze_path, paths_to_analyze):
            if meta is not None:
                results.append(meta)
    return results


def _execute_page_review_steps(
    pipeline: Any,
    prompt: str,
    fpath: str,
    p_idx: int,
    total_pages: int,
    persona_lookup: dict[str, tuple[str, str]],
    thoughts: list[str],
    actual_servers: list[str],
    file_findings: list[SavedFinding],
) -> int:
    """Execute review pipeline on a page prompt and process step findings."""
    result = pipeline.run(
        prompt, max_turns_per_agent=1, enable_thinking=False, parallel=True, skip_rag=True
    )
    for step in result.steps:
        _process_pipeline_step_findings(
            step=step,
            fpath=fpath,
            p_idx=p_idx,
            total_pages=total_pages,
            persona_lookup=persona_lookup,
            thoughts_list=thoughts,
            actual_servers=actual_servers,
            file_findings=file_findings,
        )
    return len(result.steps)


def _collect_paths_to_analyze(
    collected_paths: list[Path],
    repo: Path,
    existing_file_metas: dict[str, FileAnalysisMeta],
    force_refresh: bool,
    file_metas: list[FileAnalysisMeta],
    metadata_by_path: dict[str, FileAnalysisMeta],
) -> list[tuple[Path, str]]:
    """Filter candidate paths and reuse existing analysis metadata where available."""
    paths_to_analyze: list[tuple[Path, str]] = []
    for p in collected_paths:
        if p.stat().st_size > CONST_MAX_FILE_SIZE_BYTES:
            continue
        rel_str = str(p.relative_to(repo)) if p.is_relative_to(repo) else str(p)
        try:
            file_mtime = datetime.fromtimestamp(p.stat().st_mtime, UTC)
            old_meta = existing_file_metas.get(rel_str)
            if (
                not force_refresh
                and old_meta
                and (reused := _try_reuse_cached_analysis_meta(old_meta, p, file_mtime))
            ):
                file_metas.append(reused)
                metadata_by_path[rel_str] = reused
            else:
                paths_to_analyze.append((p, rel_str))
        except Exception as exc:
            logger.debug("Failed preparing path %s for analysis: %s", p, exc)
    return paths_to_analyze


def _scan_gitleaks_and_semgrep(all_resolved: list[Path]) -> list[SavedFinding]:
    """Run Gitleaks secret and Semgrep AST static analysis."""
    if not all_resolved:
        return []
    from devops_cli.security.gitleaks import run_gitleaks_scan
    from devops_cli.security.semgrep import run_semgrep_scan

    findings: list[SavedFinding] = []
    findings.extend(_wrap_static_findings(run_gitleaks_scan(all_resolved)))
    findings.extend(_wrap_static_findings(run_semgrep_scan(all_resolved)))
    return findings


def _get_finding_status_badge(status: str) -> str:
    """Return color-styled badge for finding verification status."""
    st_upper = status.upper()
    if st_upper == "VERIFIED":
        return "[green]✓ VERIFIED[/green]"
    if st_upper == "MITIGATED":
        return "[cyan]~ MITIGATED[/cyan]"
    if st_upper == "INVALIDATED":
        return "[red]✗ INVALIDATED[/red]"
    return f"[yellow]? {status}[/yellow]"


def _format_dependency_table_row(d: DependencySpec) -> list[str]:
    """Format a single dependency specification into table cell strings."""
    sev_upper = d.severity.upper()
    if sev_upper == "CRITICAL":
        sev_str = "[bold red]CRITICAL[/bold red]"
        status_str = f"[bold red]{d.security_status}[/bold red]"
    elif sev_upper == "HIGH":
        sev_str = "[red]HIGH[/red]"
        status_str = f"[red]{d.security_status}[/red]"
    elif sev_upper == "MEDIUM":
        sev_str = "[yellow]MEDIUM[/yellow]"
        status_str = f"[yellow]{d.security_status}[/yellow]"
    elif sev_upper == "LOW":
        sev_str = "[cyan]LOW[/cyan]"
        status_str = f"[cyan]{d.security_status}[/cyan]"
    else:
        sev_str = "[green]CLEAN[/green]"
        status_str = f"[green]{d.security_status}[/green]"

    return [
        sev_str,
        d.name,
        d.version_range,
        d.ecosystem,
        status_str,
        d.location or "—",
    ]


def _format_network_ref_table_row(n: NetworkReference) -> list[str]:
    """Format a single network reference into table cell strings."""
    scope_str = "[dim]Local[/dim]" if n.is_local else "[bold cyan]External[/bold cyan]"
    color = "red" if "⚠️" in n.security_status else ("cyan" if n.is_local else "green")
    return [
        n.target,
        n.reference_type,
        scope_str,
        f"[{color}]{n.security_status}[/{color}]",
        n.location or "—",
    ]


def _get_reviews_base_dir() -> Path:
    from devops_cli.config.settings import load_settings
    from devops_cli.core.repo import find_top_level_repo_root

    settings = load_settings()
    d = settings.data.reviews_dir
    if not d.is_absolute():
        d = (find_top_level_repo_root() / d).resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


class ReviewPipelineOrchestrator:
    """Orchestrates 6-stage multi-agent code reviews with per-file payloads and AI scratchpads."""

    def __init__(
        self,
        session_id: str | None = None,
        llm_client: LLMClient | None = None,
        target_dir: Path = DEFAULT_CURRENT_PATH,
        session_dir: Path | None = None,
    ) -> None:
        self.session_id = session_id or datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        self.target_dir = target_dir
        if session_dir is not None:
            self.session_dir = session_dir
        else:
            base_dir = _get_reviews_base_dir().resolve()
            self.session_dir = base_dir / self.session_id
        self.files_dir = self.session_dir / "files"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self.llm_client = llm_client or LLMClient()
        self.errored_files: dict[str, str] = {}

    def _resolve_file_path(self, fpath: str) -> Path:
        """Resolve fpath to an existing filesystem Path within target_dir or repo root."""
        from devops_cli.core.repo import find_repo_root

        target_root = self.target_dir.resolve()
        repo = find_repo_root(self.target_dir)
        p = Path(fpath)
        if p.is_absolute() and p.exists():
            return p.resolve()
        if (target_root / p).exists():
            return (target_root / p).resolve()
        if (repo / p).exists():
            return (repo / p).resolve()
        if (target_root / p.name).exists():
            return (target_root / p.name).resolve()

        try:
            candidate = p if p.is_absolute() else (target_root / p)
            resolved = candidate.resolve()
            if resolved.exists():
                return resolved
            if (repo / p).resolve().exists():
                return (repo / p).resolve()
        except (ValueError, OSError) as exc:
            logger.debug("Failed resolving path %s: %s", fpath, exc)

        # Fallback to sanitized in-target path
        safe_rel = Path(fpath.lstrip("/\\")).name
        return target_root / safe_rel

    def _get_server_info(self) -> str:
        """Return formatted string describing target AI/LLM provider, host, and model."""
        if not self.llm_client:
            return "LLM server"
        backend_info = getattr(self.llm_client, "backend_info", "")
        config = getattr(self.llm_client, "_config", None)
        model = getattr(config, "model", None) if config else None

        if backend_info and model:
            return f"{backend_info} [model: {model}]"
        if backend_info:
            return str(backend_info)
        if model:
            return f"LLM [model: {model}]"
        return "LLM server"

    # ── Stage 1: Pre-Analysis & Metadata Refresh ──────────────────────────────
    def run_pre_analysis_refresh(
        self,
        target_dir: Path = DEFAULT_CURRENT_PATH,
        target_type: Literal["branch", "pr", "path"] = "path",
        target_ref: str = ".",
        force_refresh: bool = False,
        stage_flags: ReviewStageFlags | None = None,
    ) -> dict[str, FileAnalysisMeta]:
        """Scan workspace and refresh metadata if files were edited or missing."""
        from devops_cli.ai.analyze.cache import save_analysis_metadata
        from devops_cli.core.repo import find_repo_root, list_repo_files
        from devops_cli.dry_run.state import is_dry_run

        if is_dry_run():
            return {}

        if stage_flags is not None and not stage_flags.pre_analysis:
            print_info(
                "[dim]Pre-analysis metadata scan skipped (disabled via flag)[/dim]",
                prefix=False,
            )
            return {}

        self.target_dir = target_dir
        with trace_span(
            "review.pre_analysis",
            attributes={"target_ref": target_ref, "target_type": target_type},
        ):
            repo = find_repo_root(target_dir)
            target_abs = (
                target_dir.resolve() if target_dir.is_absolute() else (repo / target_dir).resolve()
            )
            display_ref = str(target_abs) if (not target_ref or target_ref == ".") else target_ref
            print_info(
                f"[dim]Scanning pre-analysis metadata for '{display_ref}'...[/dim]",
                prefix=False,
            )

            existing_file_metas: dict[str, FileAnalysisMeta] = {}
            cached_meta = load_cached_analysis(repo)
            if cached_meta and not force_refresh:
                for fmeta in cached_meta.files:
                    existing_file_metas[fmeta.path] = fmeta

            collected_paths: list[Path] = []
            if target_abs.exists():
                if target_abs.is_file():
                    collected_paths = [target_abs]
                else:
                    collected_paths = list_repo_files(target_abs)
            else:
                collected_paths = list_repo_files(repo)

            metadata_by_path: dict[str, FileAnalysisMeta] = {}
            updated_any = False
            file_metas: list[FileAnalysisMeta] = []

            config = getattr(self.llm_client, "_config", None)
            ollama_urls = _resolve_ollama_urls(config)
            raw_par = getattr(config, "ollama_max_parallel", None)
            max_par = int(raw_par) if isinstance(raw_par, int) else 2
            batch_capacity = max(1, len(ollama_urls) * max_par)

            paths_to_analyze = _collect_paths_to_analyze(
                collected_paths,
                repo,
                existing_file_metas,
                force_refresh,
                file_metas,
                metadata_by_path,
            )

            if paths_to_analyze:
                new_metas = _execute_pre_analysis_batch(
                    paths_to_analyze, repo, self.llm_client, batch_capacity
                )
                for meta in new_metas:
                    file_metas.append(meta)
                    metadata_by_path[meta.path] = meta
                    updated_any = True

            if file_metas:
                title = f"{repo.name} pre-analysis: {target_ref}"
                save_analysis_metadata(
                    target_type, target_ref, title, file_metas, repo, enhanced=True
                )

            n_meta = len(metadata_by_path)
            status_msg = "refreshed with AI metadata" if updated_any else "up to date"
            print_info(
                f"[dim]  ✓ Pre-analysis metadata {status_msg} for {n_meta} file(s)[/dim]",
                prefix=False,
            )
            return metadata_by_path

    def _find_matching_metadata(
        self, fpath: str, metadata_by_path: dict[str, FileAnalysisMeta]
    ) -> FileAnalysisMeta | None:
        """Find FileAnalysisMeta for fpath with exact and normalized suffix matching."""
        if fpath in metadata_by_path:
            return metadata_by_path[fpath]

        norm_f = fpath.replace("\\", "/").strip("./")
        for key, meta in metadata_by_path.items():
            norm_k = key.replace("\\", "/").strip("./")
            if norm_k == norm_f or norm_k.endswith("/" + norm_f) or norm_f.endswith("/" + norm_k):
                return meta

        return None

    # ── Stage 2: Per-File Review Session JSON Initialization ──────────────────
    def _run_static_scanners(self, file_paths: list[str]) -> dict[str, list[SavedFinding]]:
        """Run Bandit, Kube-linter, Pluto, Trivy, Semgrep, and Gitleaks static analyzers."""
        static_findings_by_file: dict[str, list[SavedFinding]] = {}
        all_static_findings: list[SavedFinding] = []
        n_paths = len(file_paths)
        try:
            from devops_cli.security.bandit import run_bandit_scan

            print_info(
                "  • Running static security analyzers "
                "(Bandit, Kube-linter, Pluto, Trivy, Semgrep, Gitleaks)...",
                prefix=False,
            )

            with trace_span(
                "security.static_scanners", attributes={"file_count": n_paths}
            ) as sc_span:
                all_resolved = [self._resolve_file_path(f) for f in file_paths]

                # 1. Batch Bandit scan for Python files
                py_paths = [p for p in all_resolved if p.suffix == ".py"]
                if py_paths:
                    all_static_findings.extend(_wrap_static_findings(run_bandit_scan(py_paths)))

                # 2. Pluto & Kube-linter scan for Kubernetes manifests
                yaml_paths = [p for p in all_resolved if p.suffix in (".yaml", ".yml")]
                all_static_findings.extend(_scan_kubernetes_manifests(yaml_paths))

                # 3. Aqua Trivy scan for Dockerfiles and lockfiles
                docker_lock_paths = [
                    p
                    for p in all_resolved
                    if p.name.lower() in ("dockerfile", "containerfile")
                    or p.suffix in (".lock", ".lockb")
                ]
                all_static_findings.extend(_scan_container_and_lockfiles(docker_lock_paths))

                # 4. Gitleaks & Semgrep scans
                all_static_findings.extend(_scan_gitleaks_and_semgrep(all_resolved))

                static_findings_by_file = _match_static_findings_to_files(
                    all_static_findings, file_paths
                )

                sc_attrs = {
                    "findings_count": len(all_static_findings),
                    "python_files": len(py_paths),
                    "yaml_files": len(yaml_paths),
                    "docker_files": len(docker_lock_paths),
                }
                sc_span.set_attributes(sc_attrs)

            print_info(
                f"    [dim]✓ Static analyzers completed "
                f"({len(all_static_findings)} finding(s) detected)[/dim]",
                prefix=False,
            )
        except Exception as exc:
            logger.debug("Static security scanning failed or skipped: %s", exc)

        return static_findings_by_file

    def _extract_dependencies_and_network_references(
        self, file_paths: list[str]
    ) -> tuple[
        dict[str, tuple[list[DependencySpec], list[NetworkReference]]],
        set[tuple[str, str, str]],
        set[tuple[str, str]],
    ]:
        """Extract dependencies and network references across target files and dynamic probes."""
        n_paths = len(file_paths)
        print_info(
            f"  • Extracting dependencies and network references across {n_paths} file(s)...",
            prefix=False,
        )
        raw_file_data: dict[str, tuple[list[DependencySpec], list[NetworkReference]]] = {}
        all_unique_deps: set[tuple[str, str, str]] = set()
        all_unique_nets: set[tuple[str, str]] = set()

        def _extract_single_file(
            fpath: str,
        ) -> tuple[str, list[DependencySpec], list[NetworkReference]]:
            file_deps: list[DependencySpec] = []
            file_nets: list[NetworkReference] = []
            p_target = self._resolve_file_path(fpath)
            if p_target.exists() and p_target.is_file():
                try:
                    f_content = p_target.read_text(encoding="utf-8", errors="replace")
                    file_deps = extract_dependencies_from_text(f_content, fpath)
                    file_nets = extract_network_references(f_content, fpath)
                except Exception as exc:
                    logger.debug("Failed extracting references from %s: %s", fpath, exc)
            return fpath, file_deps, file_nets

        with trace_span(
            "security.extract_references", attributes={"file_count": n_paths}
        ) as ref_span:
            with ThreadPoolExecutor(max_workers=min(16, (os.cpu_count() or 4) * 2)) as executor:
                for fpath, file_deps, file_nets in executor.map(_extract_single_file, file_paths):
                    raw_file_data[fpath] = (file_deps, file_nets)
                    dep_tuples = ((d.name, d.version_range, d.ecosystem) for d in file_deps)
                    all_unique_deps.update(dep_tuples)
                    all_unique_nets.update((n.target, n.reference_type) for n in file_nets)

            direct_deps_count = len(all_unique_deps)
            direct_nets_count = len(all_unique_nets)

            # Dynamically discover project manifests and configuration files via
            # filesystem inspection if none were directly present in reviewed file paths
            probe_dirs: list[Path] = []
            for p_base in (self.target_dir, Path.cwd()):
                res_base = p_base.resolve()
                if res_base.is_dir() and not any(p.resolve() == res_base for p in probe_dirs):
                    probe_dirs.append(p_base)

            if not all_unique_deps:
                _probe_manifest_deps_in_dirs(probe_dirs, raw_file_data, all_unique_deps)

            if not all_unique_nets:
                _probe_network_refs_in_dirs(probe_dirs, raw_file_data, all_unique_nets)

            probed_deps_count = len(all_unique_deps) - direct_deps_count
            probed_nets_count = len(all_unique_nets) - direct_nets_count

            ref_span.set_attributes(
                {
                    "unique_deps_count": len(all_unique_deps),
                    "unique_nets_count": len(all_unique_nets),
                    "direct_deps_count": direct_deps_count,
                    "direct_nets_count": direct_nets_count,
                    "probed_deps_count": probed_deps_count,
                    "probed_nets_count": probed_nets_count,
                }
            )

        summary_str = _format_extraction_summary(
            direct_deps_count,
            direct_nets_count,
            probed_deps_count,
            probed_nets_count,
        )
        print_info(
            f"    [dim]✓ Extracted {summary_str}[/dim]",
            prefix=False,
        )
        return raw_file_data, all_unique_deps, all_unique_nets

    def _fetch_vulnerabilities_and_reputations(
        self,
        unique_deps: set[tuple[str, str, str]],
        unique_nets: set[tuple[str, str]],
    ) -> tuple[
        dict[tuple[str, str, str], list[VulnerabilityRecord]],
        dict[str, NetworkReputationRecord],
    ]:
        """Pre-fetch vulnerability records from OSV and threat intel from Shodan/Cloudflare."""
        dep_cache: dict[tuple[str, str, str], list[VulnerabilityRecord]] = {}
        net_cache: dict[str, NetworkReputationRecord] = {}

        from devops_cli.dry_run.state import is_dry_run

        if is_dry_run() or (not unique_deps and not unique_nets):
            return dep_cache, net_cache

        osv_client = OSVClient()
        shodan_client = ShodanInternetDBClient()
        radar_client = CloudflareRadarClient()

        def _fetch_dep(
            d_key: tuple[str, str, str],
        ) -> tuple[tuple[str, str, str], list[VulnerabilityRecord]]:
            name, ver, eco = d_key
            try:
                vulns = osv_client.query_package(name, ver, eco)
                return d_key, vulns
            except Exception:
                return d_key, []

        def _fetch_net(n_key: tuple[str, str]) -> tuple[str, NetworkReputationRecord]:
            target, rtype = n_key
            try:
                if rtype == "ip":
                    rep = shodan_client.check_ip(target)
                else:
                    rep = radar_client.check_domain(target)
                return target, rep
            except Exception:
                return target, NetworkReputationRecord(target=target, ip="")

        print_info(
            "  • Querying vulnerability databases & threat intelligence "
            "(OSV, Shodan, Cloudflare)...",
            prefix=False,
        )
        with trace_span(
            "security.vulnerability_lookups",
            attributes={
                "deps_count": len(unique_deps),
                "nets_count": len(unique_nets),
            },
        ):
            if unique_deps:
                batch_results = osv_client.query_batch(list(unique_deps))
                dep_cache.update(batch_results)
            if unique_nets:
                with ThreadPoolExecutor(max_workers=8) as executor:
                    net_cache.update(dict(executor.map(_fetch_net, list(unique_nets))))
        print_info(
            "    [dim]✓ Completed vulnerability and threat reputation lookups[/dim]", prefix=False
        )

        return dep_cache, net_cache

    def _find_linked_files(
        self,
        fpath: str,
        fmeta: FileAnalysisMeta,
        metadata_by_path: dict[str, FileAnalysisMeta],
    ) -> list[FileAnalysisMeta]:
        """Find up to 10 contextually linked files based on symbols, dependencies, and imports."""
        meaningful_deps = {d for d in fmeta.dependencies if d and d not in _UNIVERSAL_MODULES}
        meaningful_syms = {s for s in fmeta.key_symbols if s}

        linked: list[FileAnalysisMeta] = []
        for other_path, other_meta in metadata_by_path.items():
            if other_path == fpath:
                continue
            sym_match = any(sym in other_meta.key_symbols for sym in meaningful_syms)
            dep_match = any(
                dep in other_meta.dependencies
                for dep in meaningful_deps
                if dep not in _UNIVERSAL_MODULES
            )
            import_match = any(
                dep.replace(".", "/") in other_path
                or other_path.replace(".py", "").replace("/", ".") in dep
                for dep in meaningful_deps
            )
            if sym_match or dep_match or import_match:
                linked.append(other_meta)
                if len(linked) >= 10:
                    break
        return linked

    def _audit_file_dependencies(
        self,
        fpath: str,
        file_deps: list[DependencySpec],
        dep_cache: dict[tuple[str, str, str], list[VulnerabilityRecord]],
    ) -> list[SavedFinding]:
        """Audit dependencies against vulnerability cache and return any vulnerability findings."""
        findings: list[SavedFinding] = []
        for dep in file_deps:
            d_key = (dep.name, dep.version_range, dep.ecosystem)
            vulns = dep_cache.get(d_key, [])
            if vulns:
                dep.vulnerabilities = vulns
                highest_sev = max(
                    (v.severity.upper() for v in vulns),
                    key=lambda s: _SEV_ORDER.get(s, 0),
                    default="MEDIUM",
                )
                dep.severity = highest_sev
                dep.security_status = f"⚠️ {len(vulns)} Known Vuln(s) [{highest_sev}]"
            else:
                dep.severity = "CLEAN"
                dep.security_status = "✓ Clean"

            findings.extend(_build_vulnerability_finding(fpath, dep, v) for v in vulns)
        return findings

    def _audit_file_network_references(
        self,
        fpath: str,
        file_nets: list[NetworkReference],
        net_cache: dict[str, NetworkReputationRecord],
    ) -> list[SavedFinding]:
        """Audit network references against reputation cache and return any suspicious findings."""
        findings: list[SavedFinding] = []
        for net in file_nets:
            rep = net_cache.get(net.target, NetworkReputationRecord(target=net.target, ip=""))
            net.reputation = rep
            if rep.is_malicious:
                net.security_status = f"⚠️ Flagged ({rep.reputation_summary})"
            elif rep.ports:
                net.security_status = f"✓ Safe (Ports: {', '.join(map(str, rep.ports[:3]))})"
            else:
                net.security_status = "✓ Safe / Low Risk"

            if rep.is_malicious:
                findings.append(_build_malicious_network_finding(fpath, net, rep))
        return findings

    def _build_and_persist_single_payload(
        self,
        fpath: str,
        metadata_by_path: dict[str, FileAnalysisMeta],
        static_findings_by_file: dict[str, list[SavedFinding]],
        raw_file_data: dict[str, tuple[list[DependencySpec], list[NetworkReference]]],
        dep_cache: dict[tuple[str, str, str], list[VulnerabilityRecord]],
        net_cache: dict[str, NetworkReputationRecord],
    ) -> FileReviewPayload:
        """Construct, validate, and write a single file review tracking JSON payload."""
        fmeta = self._find_matching_metadata(fpath, metadata_by_path) or FileAnalysisMeta(
            path=fpath
        )
        linked = self._find_linked_files(fpath, fmeta, metadata_by_path)
        file_deps, file_nets = raw_file_data.get(fpath, ([], []))

        initial_findings = list(static_findings_by_file.get(fpath, []))
        initial_findings.extend(self._audit_file_dependencies(fpath, file_deps, dep_cache))
        initial_findings.extend(self._audit_file_network_references(fpath, file_nets, net_cache))

        sanitized_name = _sanitize_filename(fpath) + ".json"
        json_file = self.files_dir / sanitized_name
        json_file.parent.mkdir(parents=True, exist_ok=True)

        payload = FileReviewPayload(
            file_path=fpath,
            metadata=fmeta,
            linked_files=linked,
            findings=initial_findings,
            external_dependencies=file_deps,
            network_references=file_nets,
            ai_scratchpad=_create_initial_scratchpad(fpath, len(initial_findings)),
        )
        json_file.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
        return payload

    def _assemble_single_file_payload(
        self,
        fpath: str,
        metadata_by_path: dict[str, FileAnalysisMeta],
        static_findings_by_file: dict[str, list[SavedFinding]],
        raw_file_data: dict[str, tuple[list[DependencySpec], list[NetworkReference]]],
        dep_cache: dict[tuple[str, str, str], list[VulnerabilityRecord]],
        net_cache: dict[str, NetworkReputationRecord],
    ) -> FileReviewPayload | None:
        """Safely build and persist single file payload with error logging."""
        try:
            return self._build_and_persist_single_payload(
                fpath,
                metadata_by_path,
                static_findings_by_file,
                raw_file_data,
                dep_cache,
                net_cache,
            )
        except Exception as exc:
            logger.error("Error creating review payload for %s: %s", fpath, exc)
            self.errored_files[fpath] = f"Initialization: {exc}"
            warn_msg = f"  [yellow]• [bold red]Skipped errored file during init:[/bold red] [bold]{fpath}[/bold] [dim]({exc})[/dim][/yellow]"
            print_info(warn_msg, prefix=False)
            return None

    def _assemble_and_persist_payloads(
        self,
        file_paths: list[str],
        metadata_by_path: dict[str, FileAnalysisMeta],
        static_findings_by_file: dict[str, list[SavedFinding]],
        raw_file_data: dict[str, tuple[list[DependencySpec], list[NetworkReference]]],
        dep_cache: dict[tuple[str, str, str], list[VulnerabilityRecord]],
        net_cache: dict[str, NetworkReputationRecord],
    ) -> list[FileReviewPayload]:
        """Assemble FileReviewPayload models and persist tracking JSON files."""
        n_paths = len(file_paths)
        print_info(
            f"  • Assembling payload tracking files & linking dependency graphs for {n_paths} file(s)...",
            prefix=False,
        )
        payloads: list[FileReviewPayload] = []
        with trace_span("review.assemble_payloads", attributes={"file_count": n_paths}):
            for fpath in file_paths:
                p = self._assemble_single_file_payload(
                    fpath,
                    metadata_by_path,
                    static_findings_by_file,
                    raw_file_data,
                    dep_cache,
                    net_cache,
                )
                if p is not None:
                    payloads.append(p)

        return payloads

    def init_per_file_payloads(
        self,
        file_paths: list[str],
        metadata_by_path: dict[str, FileAnalysisMeta],
        target_dir: Path | None = None,
        stage_flags: ReviewStageFlags | None = None,
    ) -> list[FileReviewPayload]:
        """Initialize per-file JSON payloads under session files directory."""
        if target_dir is not None:
            self.target_dir = target_dir

        n_paths = len(file_paths)
        with trace_span("review.init_payloads", attributes={"file_count": n_paths}):
            print_info(
                f"[dim]Initializing payload tracking for {n_paths} file(s)...[/dim]",
                prefix=False,
            )

            # Static security tool batch scanning
            static_findings_by_file: dict[str, list[SavedFinding]]
            if stage_flags is not None and not stage_flags.static_scan:
                print_info(
                    "[dim]  • Static security analyzers skipped (disabled via flag)[/dim]",
                    prefix=False,
                )
                static_findings_by_file = {f: [] for f in file_paths}
            else:
                static_findings_by_file = self._run_static_scanners(file_paths)

            # Parse dependencies and network references across target files
            raw_file_data, unique_deps, unique_nets = (
                self._extract_dependencies_and_network_references(file_paths)
            )

            # Concurrently pre-fetch unique dependency vulnerabilities & reputations
            dep_cache, net_cache = self._fetch_vulnerabilities_and_reputations(
                unique_deps, unique_nets
            )

            # Assemble and persist FileReviewPayload objects
            payloads = self._assemble_and_persist_payloads(
                file_paths=file_paths,
                metadata_by_path=metadata_by_path,
                static_findings_by_file=static_findings_by_file,
                raw_file_data=raw_file_data,
                dep_cache=dep_cache,
                net_cache=net_cache,
            )

            print_info(
                f"[dim]  ✓ Initialized {len(payloads)} file review payload tracking file(s)[/dim]",
                prefix=False,
            )
            return payloads

    # ── Multi-Persona Code Content Review ──────────────────────────────────────
    def _read_target_conventions(self) -> str:
        """Read and sanitize AGENTS.md conventions from target repository."""
        target_agents_path = self.target_dir / "AGENTS.md"
        if target_agents_path.exists() and target_agents_path.is_file():
            try:
                from devops_cli.ai.review.sanitization import (
                    _mask_secrets_in_content,
                    _sanitize_prompt_boundary_tags,
                )

                c_text = target_agents_path.read_text(encoding="utf-8", errors="replace")[:3000]
                clean_c_text = _sanitize_prompt_boundary_tags(_mask_secrets_in_content(c_text))
                header = f"\n\nTarget Repository Conventions ({target_agents_path.name}):\n"
                return f"{header}{clean_c_text}\n"
            except Exception as exc:
                logger.debug("Failed reading AGENTS.md conventions: %s", exc)
        return ""

    def _build_multi_persona_pipeline(
        self, active_personas: list[str], target_conventions: str
    ) -> tuple[MultiAgentPipeline[ReviewResult], dict[str, tuple[str, str]]]:
        """Build multi-agent pipeline with configured persona agents."""
        from devops_cli.ai.personas import Persona

        pipeline = MultiAgentPipeline[ReviewResult](output_schema=ReviewResult)
        persona_lookup: dict[str, tuple[str, str]] = {}

        effective_personas = active_personas if active_personas else ["devsecops"]
        for p_key in effective_personas:
            try:
                persona_enum = Persona(p_key) if isinstance(p_key, str) else p_key
                p_val = persona_enum.value if hasattr(persona_enum, "value") else str(persona_enum)
            except ValueError:
                persona_enum = Persona.DEVSECOPS
                p_val = "devsecops"
            p_def = PERSONAS.get(persona_enum, PERSONAS[Persona.DEVSECOPS])
            persona_lookup[p_def.title] = (p_val, p_def.title)
            persona_lookup[p_val] = (p_val, p_def.title)
            sys_prompt = (
                f"You are {p_def.title}.\n{p_def.system_prompt}\n\n"
                f"{_REVIEW_PIPELINE_EVAL}\n"
                f"{target_conventions}"
            )
            agent = PydanticAgent[ReviewResult](
                client=self.llm_client,
                name=p_def.title,
                system_prompt=sys_prompt,
                output_schema=ReviewResult,
            )
            pipeline.add_agent(agent)

        if not pipeline.agents:
            p_def = PERSONAS[Persona.DEVSECOPS]
            persona_lookup[p_def.title] = ("devsecops", p_def.title)
            persona_lookup["devsecops"] = ("devsecops", p_def.title)
            agent = PydanticAgent[ReviewResult](
                client=self.llm_client,
                name=p_def.title,
                system_prompt=f"You are {p_def.title}.\n{p_def.system_prompt}\n\n{_REVIEW_PIPELINE_EVAL}\n{target_conventions}",
                output_schema=ReviewResult,
            )
            pipeline.add_agent(agent)

        return pipeline, persona_lookup

    def _review_single_file_payload(
        self,
        idx: int,
        total_files: int,
        payload: FileReviewPayload,
        diff_text_by_file: dict[str, str],
        active_personas: list[str],
        server_info: str,
        *,
        pipeline: MultiAgentPipeline[ReviewResult] | None = None,
        persona_lookup: dict[str, tuple[str, str]] | None = None,
    ) -> None:
        """Run multi-persona review for a single file across chunked diff pages."""
        fpath = payload.file_path
        ext = Path(fpath).suffix.lower()
        with trace_span(
            "review.file_review",
            attributes={
                "session_id": self.session_id,
                "file_path": fpath,
                "file_index": idx,
                "total_files": total_files,
                "review.personas": active_personas,
                "review.file_extension": ext,
                "review.stage": "inspection",
            },
        ) as file_span:
            content_or_diff = diff_text_by_file.get(fpath, "")
            if not content_or_diff and Path(fpath).exists():
                try:
                    content_or_diff = Path(fpath).read_text(encoding="utf-8", errors="replace")
                except Exception as exc:
                    logger.debug("Failed reading file content for %s: %s", fpath, exc)

            if not content_or_diff:
                print_info(
                    f"[dim]  [{idx}/{total_files}] Skipping empty/unreadable file: {fpath}[/dim]",
                    prefix=False,
                )
                return

            from devops_cli.ai.review.chunker import _diff_pages
            from devops_cli.config.defaults import (
                DEFAULT_AI_CONTEXT_WINDOW,
                DEFAULT_REVIEW_MAX_DIFF_CHARS,
            )

            ctx_win = (
                self.llm_client.get_context_window("analysis")
                if hasattr(self.llm_client, "get_context_window")
                else DEFAULT_AI_CONTEXT_WINDOW
            )
            max_diff_chars = max(DEFAULT_REVIEW_MAX_DIFF_CHARS, int(ctx_win * 3.5))

            pages = (
                _diff_pages(content_or_diff, max_chars=max_diff_chars)
                if len(content_or_diff) > max_diff_chars
                else [content_or_diff]
            )
            total_pages = len(pages)
            file_span.set_attributes(
                {
                    "review.file_chars": len(content_or_diff),
                    "review.page_count": total_pages,
                }
            )

            file_findings: list[SavedFinding] = []
            if pipeline is None or persona_lookup is None:
                target_conventions = self._read_target_conventions()
                pipeline, persona_lookup = self._build_multi_persona_pipeline(
                    active_personas, target_conventions
                )

            symbols = ", ".join(payload.metadata.key_symbols if payload.metadata else [])
            rag_context_str = ""
            try:
                from devops_cli.ai.rag.investigator import (
                    format_rag_investigation_for_prompt,
                    investigate_rag_context,
                )

                ctx = investigate_rag_context(f"{fpath} {symbols}", top_k=3)
                rag_context_str = format_rag_investigation_for_prompt(
                    ctx, "Cross-File Architecture & Context"
                )
            except Exception as exc:
                logger.debug("Failed investigating RAG context for %s: %s", fpath, exc)

            t_start = time.monotonic()
            actual_servers: list[str] = []
            thoughts: list[str] = list(payload.ai_scratchpad.get("thoughts", []))

            def _review_page(p_idx: int, page_content: str) -> int:
                prompt = _build_page_review_prompt(
                    fpath, p_idx, total_pages, page_content, symbols, rag_context_str
                )
                return _execute_page_review_steps(
                    pipeline,
                    prompt,
                    fpath,
                    p_idx,
                    total_pages,
                    persona_lookup,
                    thoughts,
                    actual_servers,
                    file_findings,
                )

            try:
                total_step_count = sum(
                    _review_page(p_idx, page_content) for p_idx, page_content in enumerate(pages, 1)
                )

                payload.findings = consolidate_duplicate_findings(file_findings)
                payload.ai_scratchpad["thoughts"] = thoughts
                payload.ai_scratchpad["stage"] = "reviewed"
                payload.ai_scratchpad["step_count"] = total_step_count

            except Exception as exc:
                payload.findings = []
                payload.ai_scratchpad["stage"] = "failed"
                payload.ai_scratchpad["error"] = str(exc)
                payload.ai_scratchpad.setdefault("thoughts", []).append(
                    f"Review failed for {fpath}: {exc}"
                )

            sanitized_name = _sanitize_filename(fpath) + ".json"
            json_target = self.files_dir / sanitized_name
            json_target.parent.mkdir(parents=True, exist_ok=True)
            json_target.write_text(payload.model_dump_json(indent=2), encoding="utf-8")

            elapsed_sec = time.monotonic() - t_start
            n_findings = len(file_findings)
            file_span.set_attribute("review.findings_count", n_findings)
            file_span.set_attribute("review.elapsed_seconds", elapsed_sec)
            file_span.add_event(
                "file_review_completed",
                {"findings_count": n_findings, "elapsed_seconds": elapsed_sec},
            )
            handled_by = ", ".join(actual_servers) if actual_servers else server_info
            try:
                sec_val = float(elapsed_sec)
                sec_str = f"{sec_val:.1f}s"
            except TypeError, ValueError:
                sec_str = "0.0s"

            print_info(
                f"[{idx}/{total_files}] Reviewed [bold]{fpath}[/bold] "
                f"({n_findings} finding(s)) [dim]handled by {handled_by} {sec_str}[/dim]",
                prefix=False,
            )

    def _safe_review_file_payload(
        self,
        idx: int,
        total_files: int,
        payload: FileReviewPayload,
        diff_text_by_file: dict[str, str],
        active_personas: list[str],
        server_info: str,
        *,
        pipeline: MultiAgentPipeline[ReviewResult] | None = None,
        persona_lookup: dict[str, tuple[str, str]] | None = None,
    ) -> None:
        """Safely execute review on single file payload with error capture."""
        if payload.file_path in self.errored_files:
            return
        try:
            self._review_single_file_payload(
                idx=idx,
                total_files=total_files,
                payload=payload,
                diff_text_by_file=diff_text_by_file,
                active_personas=active_personas,
                server_info=server_info,
                pipeline=pipeline,
                persona_lookup=persona_lookup,
            )
        except Exception as exc:
            logger.error("Error reviewing file %s: %s", payload.file_path, exc)
            payload.findings = []
            payload.ai_scratchpad["stage"] = "failed"
            payload.ai_scratchpad["error"] = str(exc)
            self.errored_files[payload.file_path] = f"Review: {exc}"
            print_info(
                f"[yellow][{idx}/{total_files}][/yellow] [bold red]Skipped errored file:[/bold red] "
                f"[bold]{payload.file_path}[/bold] [dim]({exc})[/dim]",
                prefix=False,
            )

    def execute_multi_persona_review(
        self,
        file_payloads: list[FileReviewPayload],
        diff_text_by_file: dict[str, str],
        personas: list[str] | None = None,
        stage_flags: ReviewStageFlags | None = None,
    ) -> None:
        """Run multi-persona review pipeline per file in parallel across configured AI nodes."""
        if stage_flags is not None and not stage_flags.persona_review:
            print_info(
                "[dim]Persona code review skipped (disabled via flag)[/dim]",
                prefix=False,
            )
            return

        active_personas = personas or ["devsecops", "architect", "qa"]
        total_files = len(file_payloads)
        server_info = self._get_server_info()

        with trace_span(
            "review.inspection",
            attributes={
                "review.total_files": total_files,
                "review.personas": ", ".join(active_personas),
            },
        ) as stage_span:
            from devops_cli.ai.personas import Persona

            persona_titles: list[str] = []
            for p_key in active_personas:
                try:
                    p_enum = Persona(p_key) if isinstance(p_key, str) else p_key
                    persona_titles.append(PERSONAS[p_enum].title)
                except Exception:
                    persona_titles.append(str(p_key))

            persona_label = (
                persona_titles[0]
                if len(persona_titles) == 1
                else f"Multi-persona ({', '.join(persona_titles)})"
            )

            print_info(
                f"[dim]{persona_label} review for {total_files} file(s) "
                f"-> Configured AI Server(s): {server_info}[/dim]",
                prefix=False,
            )

            config = getattr(self.llm_client, "_config", None)
            ollama_urls = _resolve_ollama_urls(config)
            raw_par = getattr(config, "ollama_max_parallel", None)
            max_par = int(raw_par) if isinstance(raw_par, int) else 2
            batch_capacity = max(1, len(ollama_urls) * max_par)
            n_workers = min(total_files, batch_capacity, 32) if total_files > 0 else 1

            stage_span.set_attribute("review.workers", n_workers)
            stage_span.set_attribute("review.batch_capacity", batch_capacity)
            stage_span.add_event(
                "stage_3_started",
                {"total_files": total_files, "workers": n_workers},
            )

            target_conventions = self._read_target_conventions()
            compiled_pipeline, persona_lookup = self._build_multi_persona_pipeline(
                active_personas, target_conventions
            )

            def _review_task(arg: tuple[int, FileReviewPayload]) -> None:
                idx, payload = arg
                self._safe_review_file_payload(
                    idx,
                    total_files,
                    payload,
                    diff_text_by_file,
                    active_personas,
                    server_info,
                    pipeline=compiled_pipeline,
                    persona_lookup=persona_lookup,
                )

            if n_workers > 1:
                with ThreadPoolExecutor(max_workers=n_workers) as executor:
                    list(executor.map(_review_task, list(enumerate(file_payloads, 1))))
            else:
                for item in enumerate(file_payloads, 1):
                    _review_task(item)

    # ── Cross-Referencing Verification & Reasoning ──────────────────────────
    def _safe_verify_file_payload(
        self,
        idx: int,
        total_files: int,
        payload: FileReviewPayload,
        server_info: str,
    ) -> None:
        """Safely execute finding verification on single file payload with error capture."""
        if payload.file_path in self.errored_files:
            return
        try:
            self._verify_single_file_payload(
                idx=idx,
                total_files=total_files,
                payload=payload,
                server_info=server_info,
            )
        except Exception as exc:
            logger.error("Error verifying file %s: %s", payload.file_path, exc)
            payload.ai_scratchpad["stage"] = "failed"
            payload.ai_scratchpad["error"] = str(exc)
            self.errored_files[payload.file_path] = f"Verification: {exc}"
            print_info(
                f"[yellow][{idx}/{total_files}][/yellow] [bold red]Skipped verification on errored file:[/bold red] "
                f"[bold]{payload.file_path}[/bold] [dim]({exc})[/dim]",
                prefix=False,
            )

    def _verify_single_file_payload(
        self,
        idx: int,
        total_files: int,
        payload: FileReviewPayload,
        server_info: str,
    ) -> None:
        """Verify findings for a single file using cross-referencing and LLM reasoning."""
        fpath = payload.file_path
        ext = Path(fpath).suffix.lower()
        with trace_span(
            "review.file_verify",
            attributes={
                "session_id": self.session_id,
                "file_path": fpath,
                "file_extension": ext,
                "candidate_findings": len(payload.findings),
                "review.stage": "stage_4_verification",
            },
        ) as file_v_span:
            target_file = self._resolve_file_path(fpath)
            file_code = ""
            if target_file.exists() and target_file.is_file():
                try:
                    file_code = target_file.read_text(encoding="utf-8", errors="replace")
                except Exception as exc:
                    logger.debug("Failed reading target file %s for verification: %s", fpath, exc)

            linked_snippets = _collect_linked_snippets(
                payload.linked_files, self._resolve_file_path
            )
            linked_str = "\n\n".join(linked_snippets) if linked_snippets else ""
            context = file_code + ("\n\n" + linked_str if linked_str else "")
            findings_to_verify = [Finding(**f.model_dump()) for f in payload.findings]

            t_start = time.monotonic()
            review_res, proc_sec, actual_backend = _validate_segment_findings(
                result=ReviewResult(findings=findings_to_verify),
                all_segments=[context],
                client=self.llm_client,
                repo_root=self.target_dir,
            )
            elapsed_sec = proc_sec if proc_sec is not None else (time.monotonic() - t_start)
            verified_list = review_res.findings

            updated_saved: list[SavedFinding] = []
            for orig, v in zip(payload.findings, verified_list):
                orig.status = v.status
                orig.verified = v.verified
                orig.mitigated = v.mitigated
                orig.reportable = v.reportable
                orig.invalidation_reason = v.invalidation_reason
                orig.confidence_score = v.confidence_score
                orig.verification_criteria = v.verification_criteria
                orig.invalidation_criteria = v.invalidation_criteria
                orig.verified_criteria_matched = v.verified_criteria_matched
                orig.invalidated_criteria_matched = v.invalidated_criteria_matched
                orig.verified_by = "llm"
                orig.verified_at = datetime.now(UTC).isoformat()
                updated_saved.append(orig)

            valid_cnt = sum(1 for f in updated_saved if f.status in ("VERIFIED", "MITIGATED"))
            tot_u = len(updated_saved)

            file_v_span.set_attribute("review.verified_count", valid_cnt)
            file_v_span.set_attribute("review.total_candidates", tot_u)
            file_v_span.add_event(
                "verification_completed",
                {"valid_count": valid_cnt, "total_candidates": tot_u},
            )

            thoughts_list = payload.ai_scratchpad.setdefault("thoughts", [])
            thoughts_list.append(
                f"[Verification] Verified {tot_u} finding(s) for "
                f"'{Path(payload.file_path).name}' "
                f"({len(payload.findings)} total candidate(s))"
            )

            payload.findings = updated_saved
            payload.ai_scratchpad["stage"] = "verified"

            sanitized_name = _sanitize_filename(payload.file_path) + ".json"
            json_target = self.files_dir / sanitized_name
            json_target.parent.mkdir(parents=True, exist_ok=True)
            json_target.write_text(payload.model_dump_json(indent=2), encoding="utf-8")

            handled_by = actual_backend or server_info
            try:
                sec_val = float(elapsed_sec)
                sec_str = f"{sec_val:.1f}s"
            except TypeError, ValueError:
                sec_str = "0.0s"

            print_info(
                f"[{idx}/{total_files}] Verified [bold]{fpath}[/bold] "
                f"({valid_cnt}/{tot_u} valid) [dim]handled by {handled_by} {sec_str}[/dim]",
                prefix=False,
            )

    def execute_finding_verification(
        self,
        file_payloads: list[FileReviewPayload],
        stage_flags: ReviewStageFlags | None = None,
    ) -> None:
        """Verify findings against file contents and linked files in parallel."""
        if stage_flags is not None and not stage_flags.verification:
            print_info(
                "[dim]Finding verification skipped (disabled via flag)[/dim]",
                prefix=False,
            )
            return

        total_files = len(file_payloads)
        server_info = self._get_server_info()

        with trace_span(
            "review.verification",
            attributes={"review.total_files": total_files},
        ) as s4_span:
            print_info(
                f"[dim]Verifying findings for {total_files} file(s) "
                f"-> Configured AI Server(s): {server_info}[/dim]",
                prefix=False,
            )

            payloads_with_findings = [
                (idx, p)
                for idx, p in enumerate(file_payloads, 1)
                if p.findings and p.file_path not in self.errored_files
            ]
            s4_span.set_attribute("review.files_with_findings", len(payloads_with_findings))
            if not payloads_with_findings:
                s4_span.add_event("no_findings_to_verify")
                print_info("[dim]  ✓ No findings to verify across files[/dim]", prefix=False)
                return

            config = getattr(self.llm_client, "_config", None)
            ollama_urls = _resolve_ollama_urls(config)
            raw_par = getattr(config, "ollama_max_parallel", None)
            max_par = int(raw_par) if isinstance(raw_par, int) else 2
            batch_capacity = max(1, len(ollama_urls) * max_par)
            n_workers = min(len(payloads_with_findings), batch_capacity)

            s4_span.set_attribute("review.workers", n_workers)
            s4_span.set_attribute("review.batch_capacity", batch_capacity)

            def _verify_task(arg: tuple[int, FileReviewPayload]) -> None:
                idx, payload = arg
                self._safe_verify_file_payload(idx, total_files, payload, server_info)

            if n_workers > 1:
                with ThreadPoolExecutor(max_workers=n_workers) as executor:
                    list(executor.map(_verify_task, payloads_with_findings))
            else:
                for item in payloads_with_findings:
                    _verify_task(item)

            from devops_cli.ai.review.stages.adversarial_debate import (
                run_adversarial_debate_stage,
            )

            run_adversarial_debate_stage(file_payloads)

    # ── AI Validation & Re-ranking ──────────────────────────────────────────
    def _rerank_single_file_payload(self, payload: FileReviewPayload) -> None:
        """Re-rank findings and update payload scratchpad."""
        valid_findings = [f for f in payload.findings if f.reportable and f.status != "INVALIDATED"]
        payload.reportable = any(
            f.reportable and f.status != "INVALIDATED" for f in payload.findings
        )
        payload.ai_scratchpad["stage"] = "reranked"
        payload.ai_scratchpad["reportable_count"] = len(valid_findings)

        thoughts_list = payload.ai_scratchpad.setdefault("thoughts", [])
        thoughts_list.append(
            f"[Re-ranking] Identified {len(valid_findings)} reportable "
            f"finding(s) from {len(payload.findings)} total candidate(s)"
        )

        sanitized_name = _sanitize_filename(payload.file_path) + ".json"
        json_target = self.files_dir / sanitized_name
        json_target.parent.mkdir(parents=True, exist_ok=True)
        json_target.write_text(payload.model_dump_json(indent=2), encoding="utf-8")

    def execute_finding_reranking(
        self,
        file_payloads: list[FileReviewPayload],
        stage_flags: ReviewStageFlags | None = None,
    ) -> None:
        """Validate and re-rank all findings into reportable vs non-reportable."""
        if stage_flags is not None and not stage_flags.reranking:
            print_info(
                "[dim]Finding re-ranking skipped (disabled via flag)[/dim]",
                prefix=False,
            )
            return

        n_p = len(file_payloads)
        with trace_span("review.reranking", attributes={"review.total_files": n_p}) as s5_span:
            print_info(
                f"[dim]Re-ranking and validating findings for {n_p} file(s)...[/dim]",
                prefix=False,
            )
            for payload in file_payloads:
                if payload.file_path in self.errored_files:
                    continue
                try:
                    self._rerank_single_file_payload(payload)
                except Exception as exc:
                    logger.error("Error re-ranking findings for %s: %s", payload.file_path, exc)
                    self.errored_files[payload.file_path] = f"Reranking: {exc}"

            total_reportable = sum(
                len([f for f in p.findings if f.reportable and f.status != "INVALIDATED"])
                for p in file_payloads
                if p.file_path not in self.errored_files
            )
            s5_span.set_attribute("review.total_reportable", total_reportable)
            s5_span.add_event("reranking_completed", {"total_reportable": total_reportable})
            print_info(
                f"[dim]  ✓ Re-ranked: {total_reportable} reportable finding(s) identified[/dim]",
                prefix=False,
            )

    # ── Stage 6: Consolidated Report Generation ──────────────────────────────
    def _collect_and_deduplicate_findings(
        self, file_payloads: list[FileReviewPayload]
    ) -> list[SavedFinding]:
        """Collect all reportable, non-invalidated findings and consolidate duplicates."""
        all_findings: list[SavedFinding] = []
        for payload in file_payloads:
            for f in payload.findings:
                if f.status != "INVALIDATED" and f.reportable:
                    all_findings.append(f)
        return consolidate_duplicate_findings(all_findings)

    def _collect_unique_dependencies_and_network_endpoints(
        self, file_payloads: list[FileReviewPayload]
    ) -> tuple[list[DependencySpec], list[NetworkReference]]:
        """Collect deduplicated dependencies and network endpoints across all payloads."""
        all_deps: list[DependencySpec] = []
        all_nets: list[NetworkReference] = []
        for payload in file_payloads:
            for d in payload.external_dependencies:
                if not any(
                    x.name == d.name and x.version_range == d.version_range for x in all_deps
                ):
                    all_deps.append(d)
            for n in payload.network_references:
                if not any(x.target == n.target for x in all_nets):
                    all_nets.append(n)
        return all_deps, all_nets

    def _build_consolidated_markdown_report(
        self,
        session_id: str,
        generated_at: str,
        reportable_findings: list[SavedFinding],
        all_deps: list[DependencySpec],
        all_nets: list[NetworkReference],
    ) -> str:
        """Construct full Markdown review report containing summary, details, and audits."""
        lines = [
            f"# Code Review Report (Session `{session_id}`)",
            f"*Generated at: {generated_at}*",
            "",
            "## Summary of Reportable Findings",
            f"Total Findings: **{len(reportable_findings)}**",
            "",
        ]

        if not reportable_findings:
            lines.append("✅ **No critical issues found during review.**")
        else:
            lines.append("| Severity | Location | Title | Status | Persona |")
            lines.append("|---|---|---|---|---|")
            for f in reportable_findings:
                clean_sev = f.severity.replace("|", "\\|").replace("\n", " ").strip()
                clean_loc = f.location.replace("|", "\\|").replace("\n", " ").strip()
                clean_title = f.title.replace("|", "\\|").replace("\n", " ").strip()
                clean_status = f.status.replace("|", "\\|").replace("\n", " ").strip()
                clean_persona = f.persona_title.replace("|", "\\|").replace("\n", " ").strip()
                row = (
                    f"| **{clean_sev}** | `{clean_loc}` | {clean_title} | "
                    f"{clean_status} | {clean_persona} |"
                )
                lines.append(row)

            lines.append("")
            lines.append("## Detailed Findings")
            for idx, f in enumerate(reportable_findings, 1):
                clean_title = f.title.replace("\n", " ").strip()
                lines.append(f"### {idx}. [{f.severity}] {clean_title}")
                lines.append(f"- **Location**: `{f.location}`")
                lines.append(f"- **Persona**: {f.persona_title}")
                lines.append(f"- **Status**: {f.status}")
                lines.append(f"- **Description**: {f.description}")
                if f.fix:
                    lines.append(f"- **Fix Recommendation**:\n```\n{f.fix}\n```")
                lines.append("")

        lines.append("## External Dependencies (OSV.dev & NVD)")
        if all_deps:
            lines.append(
                "| Severity | Dependency | Version Range | Ecosystem | Security Status | Location |"
            )
            lines.append("|---|---|---|---|---|---|")
            for dep in all_deps:
                sev_badge = (
                    f"**{dep.severity}**"
                    if dep.severity.upper() not in ("CLEAN", "NONE", "INFO")
                    else dep.severity
                )
                loc_str = f"`{dep.location}`" if dep.location else "—"
                lines.append(
                    f"| {sev_badge} | `{dep.name}` | `{dep.version_range}` | {dep.ecosystem} | "
                    f"{dep.security_status} | {loc_str} |"
                )
        else:
            lines.append("✅ **No external dependencies declared in review scope.**")
        lines.append("")

        lines.append("## Network References & Endpoints (Shodan InternetDB & Cloudflare Radar)")
        if all_nets:
            lines.append("| Target | Type | Scope | Security Status | Location |")
            lines.append("|---|---|---|---|---|")
            for net in all_nets:
                scope_str = "Local" if net.is_local else "External"
                loc_str = f"`{net.location}`" if net.location else "—"
                lines.append(
                    f"| `{net.target}` | {net.reference_type} | {scope_str} | "
                    f"{net.security_status} | {loc_str} |"
                )
        else:
            lines.append(
                "✅ **No network endpoints or remote addresses referenced in review scope.**"
            )
        lines.append("")

        if self.errored_files:
            lines.append("## Skipped / Errored Files")
            lines.append("| File Path | Stage / Error Reason |")
            lines.append("|---|---|")
            for fpath, reason in sorted(self.errored_files.items()):
                clean_f = fpath.replace("|", "\\|").replace("\n", " ").strip()
                clean_r = reason.replace("|", "\\|").replace("\n", " ").strip()
                lines.append(f"| `{clean_f}` | {clean_r} |")
            lines.append("")

        return "\n".join(lines)

    def _render_console_findings_table(
        self, console: Any, reportable_findings: list[SavedFinding]
    ) -> None:
        """Render findings table to console."""
        if not reportable_findings:
            print_success("No reportable findings across reviewed files.")
            return

        columns = [
            ("#", "dim"),
            ("Severity", "center"),
            ("Location", "bold cyan"),
            "Title",
            ("Status", "center"),
            ("Persona", "dim"),
            ("Conf", "dim"),
        ]
        rows: list[list[str]] = []
        sev_badges = {
            "CRITICAL": "[bold red]CRITICAL[/bold red]",
            "HIGH": "[red]HIGH[/red]",
            "MEDIUM": "[yellow]MEDIUM[/yellow]",
            "LOW": "[cyan]LOW[/cyan]",
            "INFO": "[green]INFO[/green]",
        }
        st_badges = {
            "VERIFIED": "[green]VERIFIED[/green]",
            "FLAGGED": "[yellow]FLAGGED[/yellow]",
            "MITIGATED": "[cyan]MITIGATED[/cyan]",
            "INVALIDATED": "[red]INVALIDATED[/red]",
        }

        for idx, f in enumerate(reportable_findings, 1):
            sev_str = sev_badges.get(f.severity.upper(), f"[white]{f.severity}[/white]")
            st_str = st_badges.get(f.status.upper(), f"[dim]{f.status}[/dim]")
            conf_str = (
                f"{int(f.confidence_score * 100)}%" if f.confidence_score is not None else "—"
            )

            rows.append(
                [
                    str(idx),
                    sev_str,
                    f.location,
                    f.title.strip(),
                    st_str,
                    f.persona_title or f.persona,
                    conf_str,
                ]
            )
        print_table(title="Code Review Findings", columns=columns, rows=rows, console=console)

        for idx, f in enumerate(reportable_findings, 1):
            sev_upper = f.severity.upper()
            sev_color = {
                "CRITICAL": "red",
                "HIGH": "orange3",
                "MEDIUM": "yellow",
                "LOW": "cyan",
                "INFO": "green",
            }.get(sev_upper, "white")

            st_badge = _get_finding_status_badge(f.status)
            title_header = f"[{sev_color} bold]Finding #{idx}: [{sev_upper}] {escape_text(f.title)}[/{sev_color} bold]  {st_badge}"
            panel_lines = [
                f"[bold]Location:[/bold] [cyan]{escape_text(f.location)}[/cyan]  |  [bold]Persona:[/bold] [magenta]{escape_text(f.persona_title or f.persona)}[/magenta]",
            ]
            if f.description:
                desc_text = format_clean_text_field(f.description).strip()
                panel_lines.extend(["", "[bold]Description:[/bold]", desc_text])
            if f.fix:
                panel_lines.extend(
                    ["", "[bold]Suggested Fix:[/bold]", format_clean_text_field(f.fix).strip()]
                )
            if f.invalidation_reason:
                inv_text = f"[bold yellow]Invalidation Reason:[/bold yellow] {f.invalidation_reason.strip()}"
                panel_lines.extend(["", inv_text])
            if f.references:
                refs_list = f.references if isinstance(f.references, list) else [str(f.references)]
                panel_lines.extend(
                    ["", f"[dim]References: {escape_text(', '.join(refs_list))}[/dim]"]
                )

            print_panel(
                "\n".join(panel_lines),
                title=title_header,
                border_style=sev_color,
                console=console,
            )

    def _render_console_dependencies_table(
        self, console: Any, all_deps: list[DependencySpec]
    ) -> None:
        """Render external dependencies security audit table to console."""
        columns = [
            ("Severity", "center"),
            ("Dependency", "bold cyan"),
            "Version Range",
            "Ecosystem",
            "Security Status",
            ("Location", "dim"),
        ]
        rows: list[list[str]] = []
        if all_deps:
            for d in all_deps:
                rows.append(_format_dependency_table_row(d))
        else:
            rows.append(
                [
                    "[green]CLEAN[/green]",
                    "No external package dependencies declared in reviewed files",
                    "—",
                    "—",
                    "[green]✓ Clean (0 dependencies)[/green]",
                    "—",
                ]
            )
        print_table(
            title="External Dependencies Security Audit (OSV.dev & NVD)",
            columns=columns,
            rows=rows,
            console=console,
        )

    def _render_console_network_table(self, console: Any, all_nets: list[NetworkReference]) -> None:
        """Render network references and endpoints audit table to console."""
        columns = [
            ("Target", "bold cyan"),
            "Type",
            "Scope",
            "Security Status",
            ("Location", "dim"),
        ]
        rows: list[list[str]] = []
        if all_nets:
            for n in all_nets:
                rows.append(_format_network_ref_table_row(n))
        else:
            rows.append(
                [
                    "No network endpoints or remote addresses referenced in reviewed files",
                    "—",
                    "—",
                    "[green]✓ Clean (0 endpoints)[/green]",
                    "—",
                ]
            )
        print_table(
            title="Network References & Endpoints Security Audit (Shodan & Cloudflare Radar)",
            columns=columns,
            rows=rows,
            console=console,
        )

    def _render_console_errored_files_table(self, console: Any) -> None:
        """Render table of skipped/errored files to console."""
        if not self.errored_files:
            return

        columns = [
            ("File Path", "bold red"),
            ("Stage / Error Details", "yellow"),
        ]
        rows = [[fpath, reason] for fpath, reason in sorted(self.errored_files.items())]
        print_table(
            title="Skipped / Errored Files During Review",
            columns=columns,
            rows=rows,
            border_style="yellow",
            console=console,
        )

    def _render_console_summary_table(
        self,
        console: Any,
        session_id: str,
        n_files: int,
        reportable_findings: list[SavedFinding],
        all_deps: list[DependencySpec],
        all_nets: list[NetworkReference],
    ) -> None:
        """Render review summary table to console."""
        crit_cnt = sum(1 for f in reportable_findings if f.severity.upper() == "CRITICAL")
        high_cnt = sum(1 for f in reportable_findings if f.severity.upper() == "HIGH")
        med_cnt = sum(1 for f in reportable_findings if f.severity.upper() == "MEDIUM")
        low_cnt = sum(1 for f in reportable_findings if f.severity.upper() == "LOW")
        info_cnt = sum(1 for f in reportable_findings if f.severity.upper() == "INFO")
        ver_cnt = sum(1 for f in reportable_findings if f.status.upper() == "VERIFIED")

        if reportable_findings:
            sev_parts: list[str] = []
            if crit_cnt:
                sev_parts.append(f"[bold red]{crit_cnt} Critical[/bold red]")
            if high_cnt:
                sev_parts.append(f"[red]{high_cnt} High[/red]")
            if med_cnt:
                sev_parts.append(f"[yellow]{med_cnt} Medium[/yellow]")
            if low_cnt:
                sev_parts.append(f"[cyan]{low_cnt} Low[/cyan]")
            if info_cnt:
                sev_parts.append(f"[green]{info_cnt} Info[/green]")
            sev_breakdown = ", ".join(sev_parts) if sev_parts else "None"
            findings_summary_str = f"{len(reportable_findings)} ({sev_breakdown})"
            ver_pct = ver_cnt / len(reportable_findings)
            ver_rate_str = f"{ver_cnt}/{len(reportable_findings)} verified ({ver_pct:.0%})"
        else:
            findings_summary_str = "[bold green]0 findings (Clean)[/bold green]"
            ver_rate_str = "[green]✓ All clean[/green]"

        vuln_deps = sum(1 for d in all_deps if d.severity.upper() not in ("CLEAN", "NONE", "INFO"))
        if all_deps:
            vuln_note = (
                f" ([red]{vuln_deps} vulnerable[/red])" if vuln_deps else " ([green]clean[/green])"
            )
            deps_str = f"{len(all_deps)} audited{vuln_note}"
        else:
            deps_str = "0 scanned"

        external_nets = [n for n in all_nets if not n.is_local]
        local_nets = [n for n in all_nets if n.is_local]
        nets_str = (
            f"{len(all_nets)} audited ({len(external_nets)} External, {len(local_nets)} Local)"
            if all_nets
            else "0 detected"
        )

        rows = [
            ["Session ID", f"[cyan]{session_id}[/cyan]"],
            ["Files Reviewed", str(n_files)],
        ]
        if self.errored_files:
            rows.append(
                [
                    "Skipped / Errored Files",
                    f"[bold red]{len(self.errored_files)} file(s) skipped[/bold red]",
                ]
            )
        rows.extend(
            [
                ["Reportable Findings", findings_summary_str],
                ["Verification Rate", ver_rate_str],
                ["Dependencies", deps_str],
                ["Network Endpoints", nets_str],
                ["Markdown Report", str(self.session_dir / "review.md")],
                ["Findings JSON", str(self.session_dir / "findings.json")],
            ]
        )

        print_table(
            title="Review Summary",
            columns=[("Metric", "bold"), "Result"],
            rows=rows,
            border_style="cyan",
            console=console,
        )

    def generate_consolidated_report(
        self,
        file_payloads: list[FileReviewPayload],
        stage_flags: ReviewStageFlags | None = None,
    ) -> tuple[dict[str, Any], str]:
        """Generate consolidated findings.json and client-facing Markdown report."""
        if stage_flags is not None and not stage_flags.reporting:
            print_info(
                "[dim]Consolidated reporting skipped (disabled via flag)[/dim]",
                prefix=False,
            )
            return {}, ""

        with trace_span(
            "review.report_generation",
            attributes={"session_id": self.session_id, "review.total_files": len(file_payloads)},
        ) as report_span:
            print_info(
                f"[dim]Generating report for session '{self.session_id}'...[/dim]",
                prefix=False,
            )
            all_findings = self._collect_and_deduplicate_findings(file_payloads)
            report_span.set_attribute("review.final_findings_count", len(all_findings))
            report_span.add_event(
                "report_findings_consolidated", {"findings_count": len(all_findings)}
            )

        all_deps, all_nets = self._collect_unique_dependencies_and_network_endpoints(file_payloads)

        payload_out = ReviewSessionPayload(
            generated_at=datetime.now(UTC).isoformat(),
            personas=["devsecops", "architect", "qa"],
            findings=all_findings,
            external_dependencies=all_deps,
            network_references=all_nets,
        )

        findings_json_path = self.session_dir / "findings.json"
        findings_json_path.write_text(payload_out.model_dump_json(indent=2), encoding="utf-8")

        reportable_findings = [
            f for f in all_findings if f.reportable and not f.is_empty and f.location.strip()
        ]

        report_md = self._build_consolidated_markdown_report(
            session_id=self.session_id,
            generated_at=payload_out.generated_at,
            reportable_findings=reportable_findings,
            all_deps=all_deps,
            all_nets=all_nets,
        )
        (self.session_dir / "review.md").write_text(report_md, encoding="utf-8")

        self._render_console_errored_files_table(None)
        self._render_console_findings_table(None, reportable_findings)
        self._render_console_dependencies_table(None, all_deps)
        self._render_console_network_table(None, all_nets)
        self._render_console_summary_table(
            console=None,
            session_id=self.session_id,
            n_files=len(file_payloads),
            reportable_findings=reportable_findings,
            all_deps=all_deps,
            all_nets=all_nets,
        )

        print_success(
            f"Consolidated review completed for session {self.session_id} "
            f"([bold]{len(all_findings)}[/bold] finding(s) saved to [dim]{self.session_dir}[/dim])"
        )
        return payload_out.model_dump(), report_md
