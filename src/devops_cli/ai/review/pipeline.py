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

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from rich import print as rprint

from devops_cli.ai.agents.pipeline import MultiAgentPipeline
from devops_cli.ai.agents.pydantic_agent import PydanticAgent
from devops_cli.ai.analyze.cache import load_cached_analysis
from devops_cli.ai.client import LLMClient
from devops_cli.ai.personas import PERSONAS
from devops_cli.ai.review.sanitization import _sanitize_filename
from devops_cli.ai.review.verification import _validate_segment_findings
from devops_cli.ai.review_schema import (
    FileReviewPayload,
    Finding,
    ReviewResult,
    ReviewSessionPayload,
    SavedFinding,
    parse_review_result,
)
from devops_cli.config.constants import (
    CONST_DATA_DIR,
    CONST_MAX_FILE_SIZE_BYTES,
    CONST_REVIEWS_DATA_DIR,
)
from devops_cli.models.ai import FileAnalysisMeta

logger = logging.getLogger(__name__)


class ReviewPipelineOrchestrator:
    """Orchestrates 6-stage multi-agent code reviews with per-file payloads and AI scratchpads."""

    def __init__(self, session_id: str | None = None, llm_client: LLMClient | None = None) -> None:
        self.session_id = session_id or datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        base_dir = (
            CONST_DATA_DIR / "reviews"
            if CONST_DATA_DIR != CONST_REVIEWS_DATA_DIR.parent
            else CONST_REVIEWS_DATA_DIR
        )
        self.session_dir = base_dir / self.session_id
        self.files_dir = self.session_dir / "files"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self.llm_client = llm_client or LLMClient()

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
        target_dir: Path = Path("."),
        target_type: Literal["branch", "pr", "path"] = "path",
        target_ref: str = ".",
        force_refresh: bool = False,
    ) -> dict[str, FileAnalysisMeta]:
        """Scan workspace and refresh metadata if files were edited or missing."""
        from devops_cli.ai.analyze.cache import save_analysis_metadata
        from devops_cli.ai.analyze.outlines import analyze_single_file
        from devops_cli.core.repo import find_repo_root, list_repo_files
        from devops_cli.dry_run.state import is_dry_run

        if is_dry_run():
            return {}

        repo = find_repo_root(target_dir)
        target_abs = (
            target_dir.resolve() if target_dir.is_absolute() else (repo / target_dir).resolve()
        )
        rprint(f"[dim]Stage 1/6: Scanning pre-analysis metadata for '{target_ref}'...[/dim]")

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

        for p in collected_paths:
            if p.stat().st_size > CONST_MAX_FILE_SIZE_BYTES:
                continue
            rel_str = str(p.relative_to(repo)) if p.is_relative_to(repo) else str(p)
            try:
                file_mtime = datetime.fromtimestamp(p.stat().st_mtime, UTC)
                if not force_refresh and rel_str in existing_file_metas:
                    old_meta = existing_file_metas[rel_str]
                    if old_meta.last_analyzed and old_meta.pseudocode:
                        try:
                            analyzed_dt = datetime.fromisoformat(old_meta.last_analyzed)
                            if file_mtime <= analyzed_dt:
                                reused_meta = old_meta.model_copy(
                                    update={"last_analyzed": datetime.now(UTC).isoformat()}
                                )
                                file_metas.append(reused_meta)
                                metadata_by_path[rel_str] = reused_meta
                                continue
                        except Exception:
                            pass

                content = p.read_text(encoding="utf-8", errors="replace")
                meta = analyze_single_file(
                    rel_str,
                    content,
                    p.stat().st_size,
                    enhanced=True,
                    repo_root=repo,
                    ai_client=self.llm_client,
                )
                file_metas.append(meta)
                metadata_by_path[rel_str] = meta
                updated_any = True
            except Exception:
                continue

        if file_metas:
            title = f"{repo.name} pre-analysis: {target_ref}"
            save_analysis_metadata(target_type, target_ref, title, file_metas, repo, enhanced=True)

        n_meta = len(metadata_by_path)
        status_msg = "refreshed with AI metadata" if updated_any else "up to date"
        rprint(f"[dim]  ✓ Pre-analysis metadata {status_msg} for {n_meta} file(s)[/dim]")
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
    def init_per_file_payloads(
        self, file_paths: list[str], metadata_by_path: dict[str, FileAnalysisMeta]
    ) -> list[FileReviewPayload]:
        """Initialize per-file JSON payloads under session files directory."""
        n_paths = len(file_paths)
        rprint(f"[dim]Stage 2/6: Initializing payload tracking for {n_paths} file(s)...[/dim]")
        payloads: list[FileReviewPayload] = []

        static_findings_by_file: dict[str, list[SavedFinding]] = {}
        try:
            from devops_cli.security.kubelinter import run_kubelinter_scan
            from devops_cli.security.trivy import run_trivy_scan

            for fpath in file_paths:
                p_obj = Path(fpath)
                if fpath.endswith((".yaml", ".yml")):
                    kl_findings = run_kubelinter_scan(p_obj)
                    if kl_findings:
                        sf_list = [
                            SavedFinding(
                                **f.model_dump(),
                                persona="devsecops",
                                persona_title="Principal DevSecOps Engineer",
                            )
                            for f in kl_findings
                        ]
                        static_findings_by_file.setdefault(fpath, []).extend(sf_list)
                t_findings = run_trivy_scan(p_obj, scan_type="fs")
                if t_findings:
                    sf_list = [
                        SavedFinding(
                            **f.model_dump(),
                            persona="devsecops",
                            persona_title="Principal DevSecOps Engineer",
                        )
                        for f in t_findings
                    ]
                    static_findings_by_file.setdefault(fpath, []).extend(sf_list)
        except Exception:
            pass

        for fpath in file_paths:
            fmeta = self._find_matching_metadata(fpath, metadata_by_path) or FileAnalysisMeta(
                path=fpath
            )
            linked: list[FileAnalysisMeta] = []

            for other_path, other_meta in metadata_by_path.items():
                if other_path == fpath:
                    continue
                sym_match = any(sym in other_meta.key_symbols for sym in fmeta.key_symbols if sym)
                dep_match = any(dep in other_meta.dependencies for dep in fmeta.dependencies if dep)
                if sym_match or dep_match:
                    linked.append(other_meta)

            sanitized_name = _sanitize_filename(fpath) + ".json"
            json_file = self.files_dir / sanitized_name
            initial_findings = static_findings_by_file.get(fpath, [])

            payload = FileReviewPayload(
                file_path=fpath,
                metadata=fmeta,
                linked_files=linked,
                findings=initial_findings,
                ai_scratchpad={
                    "initialized_at": datetime.now(UTC).isoformat(),
                    "stage": "initialized",
                    "thoughts": [
                        f"Tracking findings for {fpath}",
                        *(
                            [f"Injected {len(initial_findings)} static security scan finding(s)"]
                            if initial_findings
                            else []
                        ),
                    ],
                },
            )

            json_file.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
            payloads.append(payload)

        rprint(f"[dim]  ✓ Initialized {len(payloads)} file review payload tracking file(s)[/dim]")
        return payloads

    # ── Stage 3: Multi-Persona Code Content Review ─────────────────────────────
    def execute_multi_persona_review(
        self,
        file_payloads: list[FileReviewPayload],
        diff_text_by_file: dict[str, str],
        personas: list[str] | None = None,
    ) -> None:
        """Run multi-persona review pipeline per file in parallel across configured AI nodes."""
        active_personas = personas or ["devsecops", "architect", "qa"]
        total_files = len(file_payloads)
        server_info = self._get_server_info()

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

        rprint(
            f"[dim]Stage 3/6: {persona_label} review for {total_files} file(s) "
            f"-> Configured AI Server(s): {server_info}[/dim]"
        )

        config = getattr(self.llm_client, "_config", None)
        ollama_urls = getattr(config, "get_ollama_urls", []) if config else []
        n_workers = min(total_files, max(len(ollama_urls) * 2, 4)) if total_files > 0 else 1

        def _review_single_file(arg: tuple[int, FileReviewPayload]) -> None:
            idx, payload = arg
            fpath = payload.file_path
            content_or_diff = diff_text_by_file.get(fpath, "")
            if not content_or_diff and Path(fpath).exists():
                try:
                    code_raw = Path(fpath).read_text(encoding="utf-8", errors="replace")
                    content_or_diff = code_raw[:10000]
                except Exception:
                    pass

            if not content_or_diff:
                rprint(
                    f"[dim]  [{idx}/{total_files}] Skipping empty/unreadable file: {fpath}[/dim]"
                )
                return

            file_findings: list[SavedFinding] = []
            pipeline = MultiAgentPipeline[ReviewResult](output_schema=ReviewResult)

            from devops_cli.ai.personas import Persona

            for p_key in active_personas:
                try:
                    persona_enum = Persona(p_key) if isinstance(p_key, str) else p_key
                except ValueError:
                    persona_enum = Persona.DEVSECOPS
                p_def = PERSONAS[persona_enum]
                sys_prompt = (
                    f"You are {p_def.title}.\n{p_def.system_prompt}\n\n"
                    "CRITICAL: Examine code carefully for flaws and security vulnerabilities.\n"
                    "Report all findings in 'findings' JSON array with severity, location, title, "
                    "description, fix, verification, and confidence_score."
                )
                agent = PydanticAgent[ReviewResult](
                    client=self.llm_client,
                    name=p_def.title,
                    system_prompt=sys_prompt,
                    output_schema=ReviewResult,
                )
                pipeline.add_agent(agent)

            symbols = ", ".join(payload.metadata.key_symbols if payload.metadata else [])
            rag_context_str = ""
            try:
                from devops_cli.ai.rag.embeddings import EmbeddingsEngine
                from devops_cli.ai.rag.qdrant import QdrantClient
                from devops_cli.ai.rag.retriever import SemanticRetriever
                from devops_cli.config.settings import get_ai_api_key, load_settings

                st = load_settings()
                if st.ai.rag.enabled:
                    q_client = QdrantClient(
                        base_url=st.qdrant.url or "http://localhost:6333",
                        allow_private_network=st.ai.allow_private_network,
                    )
                    if q_client.is_alive():
                        emb_engine = EmbeddingsEngine(ai_config=st.ai, api_key=get_ai_api_key(st))
                        retriever = SemanticRetriever(
                            qdrant=q_client,
                            embedder=emb_engine,
                            code_collection=f"{st.qdrant.collection_prefix}_code",
                            docs_collection=f"{st.qdrant.collection_prefix}_docs",
                            default_top_k=3,
                        )
                        ctx = retriever.retrieve_context(f"{fpath} {symbols}")
                        if ctx.has_results:
                            rag_context_str = (
                                f"\n\nCross-File Architecture & Context:\n{ctx.formatted_text}"
                            )
            except Exception:
                pass

            prompt = (
                f"Review File: {fpath}\n"
                f"Key Symbols: {symbols}"
                f"{rag_context_str}\n\n"
                f"Code Content / Diff:\n{content_or_diff}"
            )

            t_start = time.monotonic()
            actual_servers: list[str] = []
            try:
                result = pipeline.run(prompt, max_turns_per_agent=1, enable_thinking=False)
                for step in result.steps:
                    if step.backend_info and step.backend_info not in actual_servers:
                        actual_servers.append(step.backend_info)

                    parsed: ReviewResult | None = None
                    if step.parsed_data and isinstance(step.parsed_data, ReviewResult):
                        parsed = step.parsed_data
                    else:
                        parsed = parse_review_result(step.content)

                    if parsed and parsed.findings:
                        for f in parsed.findings:
                            saved = SavedFinding(
                                **f.model_dump(),
                                persona=step.agent_name,
                                persona_title=step.agent_name,
                            )
                            file_findings.append(saved)

                payload.findings = file_findings
                payload.ai_scratchpad["stage"] = "reviewed"
                payload.ai_scratchpad["persona_turn_count"] = len(result.steps)
            except Exception as exc:
                payload.findings = []
                payload.ai_scratchpad["stage"] = "failed"
                payload.ai_scratchpad["error"] = str(exc)

            sanitized_name = _sanitize_filename(fpath) + ".json"
            json_target = self.files_dir / sanitized_name
            json_target.write_text(payload.model_dump_json(indent=2), encoding="utf-8")

            elapsed_sec = time.monotonic() - t_start
            n_findings = len(file_findings)
            handled_by = ", ".join(actual_servers) if actual_servers else server_info
            try:
                sec_val = float(elapsed_sec)
                sec_str = f"{sec_val:.1f}s"
            except (TypeError, ValueError):
                sec_str = "0.0s"

            rprint(
                f"[cyan][{idx}/{total_files}][/cyan] Reviewed [bold]{fpath}[/bold] "
                f"({n_findings} finding(s)) [dim]handled by {handled_by} {sec_str}[/dim]"
            )

        if n_workers > 1:
            with ThreadPoolExecutor(max_workers=n_workers) as executor:
                list(executor.map(_review_single_file, list(enumerate(file_payloads, 1))))
        else:
            for item in enumerate(file_payloads, 1):
                _review_single_file(item)

    # ── Stage 4: Cross-Referencing Verification & Reasoning ─────────────────
    def execute_finding_verification(self, file_payloads: list[FileReviewPayload]) -> None:
        """Verify findings against file contents and linked files in parallel."""
        total_files = len(file_payloads)
        server_info = self._get_server_info()
        rprint(
            f"[dim]Stage 4/6: Verifying findings for {total_files} file(s) "
            f"-> Configured AI Server(s): {server_info}[/dim]"
        )

        payloads_with_findings = [(idx, p) for idx, p in enumerate(file_payloads, 1) if p.findings]
        if not payloads_with_findings:
            rprint("[dim]  ✓ No findings to verify across files[/dim]")
            return

        config = getattr(self.llm_client, "_config", None)
        ollama_urls = getattr(config, "get_ollama_urls", []) if config else []
        n_workers = min(len(payloads_with_findings), max(len(ollama_urls) * 2, 4))

        def _verify_single_file(arg: tuple[int, FileReviewPayload]) -> None:
            idx, payload = arg
            fpath = payload.file_path
            target_file = Path(fpath)
            file_code = ""
            if target_file.exists():
                try:
                    file_code = target_file.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass

            linked_snippets: list[str] = []
            for lmeta in payload.linked_files:
                lpath = Path(lmeta.path)
                if lpath.exists():
                    try:
                        snippet = lpath.read_text(encoding="utf-8", errors="replace")[:2000]
                        linked_snippets.append(f"Linked File ({lmeta.path}):\n{snippet}")
                    except Exception:
                        pass

            linked_str = "\n\n".join(linked_snippets) if linked_snippets else ""
            context = file_code + ("\n\n" + linked_str if linked_str else "")
            findings_to_verify = [Finding(**f.model_dump()) for f in payload.findings]

            t_start = time.monotonic()
            review_res, proc_sec, actual_backend = _validate_segment_findings(
                result=ReviewResult(findings=findings_to_verify),
                all_segments=[context],
                client=self.llm_client,
            )
            elapsed_sec = proc_sec if proc_sec is not None else (time.monotonic() - t_start)
            verified_list = review_res.findings

            updated_saved: list[SavedFinding] = []
            for orig, v in zip(payload.findings, verified_list):
                orig.status = v.status
                orig.verified = v.verified
                orig.mitigated = v.mitigated
                orig.invalidation_reason = v.invalidation_reason
                orig.confidence_score = v.confidence_score
                orig.verified_by = "llm"
                orig.verified_at = datetime.now(UTC).isoformat()
                updated_saved.append(orig)

            payload.findings = updated_saved
            payload.ai_scratchpad["stage"] = "verified"

            sanitized_name = _sanitize_filename(payload.file_path) + ".json"
            json_target = self.files_dir / sanitized_name
            json_target.write_text(payload.model_dump_json(indent=2), encoding="utf-8")

            valid_cnt = sum(1 for f in updated_saved if f.status in ("VERIFIED", "MITIGATED"))
            tot_u = len(updated_saved)
            handled_by = actual_backend or server_info
            try:
                sec_val = float(elapsed_sec)
                sec_str = f"{sec_val:.1f}s"
            except (TypeError, ValueError):
                sec_str = "0.0s"

            rprint(
                f"[cyan][{idx}/{total_files}][/cyan] Verified [bold]{fpath}[/bold] "
                f"({valid_cnt}/{tot_u} valid) [dim]handled by {handled_by} {sec_str}[/dim]"
            )

        if n_workers > 1:
            with ThreadPoolExecutor(max_workers=n_workers) as executor:
                list(executor.map(_verify_single_file, payloads_with_findings))
        else:
            for item in payloads_with_findings:
                _verify_single_file(item)

    # ── Stage 5: AI Validation & Re-ranking ──────────────────────────────────
    def execute_finding_reranking(self, file_payloads: list[FileReviewPayload]) -> None:
        """Validate and re-rank all findings into reportable vs non-reportable."""
        n_p = len(file_payloads)
        rprint(f"[dim]Stage 5/6: Re-ranking and validating findings for {n_p} file(s)...[/dim]")
        for payload in file_payloads:
            valid_findings = [
                f for f in payload.findings if f.status in ("VERIFIED", "UNVERIFIED", "MITIGATED")
            ]
            for f in payload.findings:
                payload.reportable = f.status != "INVALIDATED"
            payload.ai_scratchpad["stage"] = "reranked"
            payload.ai_scratchpad["reportable_count"] = len(valid_findings)

            sanitized_name = _sanitize_filename(payload.file_path) + ".json"
            json_target = self.files_dir / sanitized_name
            json_target.write_text(payload.model_dump_json(indent=2), encoding="utf-8")

        total_reportable = sum(
            len([f for f in p.findings if f.status != "INVALIDATED"]) for p in file_payloads
        )
        rprint(f"[dim]  ✓ Re-ranked: {total_reportable} reportable finding(s) identified[/dim]")

    # ── Stage 6: Consolidated Report Generation ──────────────────────────────
    def generate_consolidated_report(
        self, file_payloads: list[FileReviewPayload]
    ) -> tuple[dict[str, Any], str]:
        """Generate consolidated findings.json and client-facing Markdown report."""
        rprint(f"[dim]Stage 6/6: Generating report for session '{self.session_id}'...[/dim]")
        all_findings: list[SavedFinding] = []
        for payload in file_payloads:
            for f in payload.findings:
                if f.status != "INVALIDATED":
                    all_findings.append(f)

        payload_out = ReviewSessionPayload(
            generated_at=datetime.now(UTC).isoformat(),
            personas=["devsecops", "architect", "qa"],
            findings=all_findings,
        )

        findings_json_path = self.session_dir / "findings.json"
        findings_json_path.write_text(payload_out.model_dump_json(indent=2), encoding="utf-8")

        lines = [
            f"# Code Review Report (Session `{self.session_id}`)",
            f"*Generated at: {payload_out.generated_at}*",
            "",
            "## Summary of Reportable Findings",
            f"Total Findings: **{len(all_findings)}**",
            "",
        ]

        if not all_findings:
            lines.append("✅ **No critical issues found during review.**")
        else:
            lines.append("| Severity | Location | Title | Status | Confidence |")
            lines.append("|---|---|---|---|---|")
            for f in all_findings:
                conf = f"{f.confidence_score:.2f}" if f.confidence_score is not None else "N/A"
                lines.append(
                    f"| **{f.severity}** | `{f.location}` | {f.title} | {f.status} | {conf} |"
                )

            lines.append("")
            lines.append("## Detailed Findings")
            for idx, f in enumerate(all_findings, 1):
                lines.append(f"### {idx}. [{f.severity}] {f.title}")
                lines.append(f"- **Location**: `{f.location}`")
                lines.append(f"- **Persona**: {f.persona_title}")
                lines.append(f"- **Status**: {f.status}")
                if f.confidence_score is not None:
                    lines.append(f"- **Confidence Score**: {f.confidence_score:.2f}")
                lines.append(f"- **Description**: {f.description}")
                if f.fix:
                    lines.append(f"- **Fix Recommendation**:\n```\n{f.fix}\n```")
                lines.append("")

        report_md = "\n".join(lines)
        (self.session_dir / "review.md").write_text(report_md, encoding="utf-8")

        rprint(
            f"[green]✓ Consolidated review completed for session {self.session_id}[/green] "
            f"([bold]{len(all_findings)}[/bold] finding(s) saved to [dim]{self.session_dir}[/dim])"
        )
        return payload_out.model_dump(), report_md
