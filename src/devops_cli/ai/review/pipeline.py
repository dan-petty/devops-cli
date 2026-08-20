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
    consolidate_duplicate_findings,
    parse_review_result,
)
from devops_cli.ai.thinking import extract_think_blocks
from devops_cli.config.constants import (
    CONST_DATA_DIR,
    CONST_MAX_FILE_SIZE_BYTES,
    CONST_REVIEWS_DATA_DIR,
)
from devops_cli.models.ai import FileAnalysisMeta
from devops_cli.security.intelligence import (
    CloudflareRadarClient,
    DependencySpec,
    NetworkReference,
    NetworkReputationRecord,
    OSVClient,
    ShodanInternetDBClient,
    VulnerabilityRecord,
    extract_dependencies_from_text,
    extract_network_references,
)

logger = logging.getLogger(__name__)


class ReviewPipelineOrchestrator:
    """Orchestrates 6-stage multi-agent code reviews with per-file payloads and AI scratchpads."""

    def __init__(
        self,
        session_id: str | None = None,
        llm_client: LLMClient | None = None,
        target_dir: Path = Path("."),
    ) -> None:
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
        self.target_dir = target_dir

    def _resolve_file_path(self, fpath: str) -> Path:
        """Resolve fpath to an existing filesystem Path, prioritizing target_dir."""
        p_fpath = Path(fpath)
        if p_fpath.is_absolute() and p_fpath.exists():
            return p_fpath

        candidates = [
            self.target_dir.resolve() / fpath,
            Path.cwd().resolve() / fpath,
            p_fpath,
        ]
        for c in candidates:
            if c.exists() and c.is_file():
                return c
        return candidates[0]

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

        self.target_dir = target_dir
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
        self,
        file_paths: list[str],
        metadata_by_path: dict[str, FileAnalysisMeta],
        target_dir: Path | None = None,
    ) -> list[FileReviewPayload]:
        """Initialize per-file JSON payloads under session files directory."""
        if target_dir is not None:
            self.target_dir = target_dir

        n_paths = len(file_paths)
        rprint(f"[dim]Stage 2/6: Initializing payload tracking for {n_paths} file(s)...[/dim]")
        payloads: list[FileReviewPayload] = []

        static_findings_by_file: dict[str, list[SavedFinding]] = {}
        try:
            from devops_cli.security.bandit import run_bandit_scan
            from devops_cli.security.kubelinter import run_kubelinter_scan
            from devops_cli.security.pluto import run_pluto_scan
            from devops_cli.security.trivy import run_trivy_scan

            def _scan_file_static(fpath: str) -> tuple[str, list[SavedFinding]]:
                p_obj = self._resolve_file_path(fpath)
                p_name = Path(fpath).name.lower()
                findings: list[SavedFinding] = []

                # 1. Kube-linter & Pluto scan for K8s manifests
                if fpath.endswith((".yaml", ".yml")):
                    kl_findings = run_kubelinter_scan(p_obj)
                    if kl_findings:
                        findings.extend(
                            [
                                SavedFinding(
                                    **f.model_dump(),
                                    persona="devsecops",
                                    persona_title="Principal DevSecOps Engineer",
                                )
                                for f in kl_findings
                            ]
                        )

                    pluto_findings = run_pluto_scan(p_obj)
                    if pluto_findings:
                        findings.extend(
                            [
                                SavedFinding(
                                    **f.model_dump(),
                                    persona="devsecops",
                                    persona_title="Principal DevSecOps Engineer",
                                )
                                for f in pluto_findings
                            ]
                        )

                # 2. Bandit static security scanner for Python files
                if fpath.endswith(".py"):
                    bandit_findings = run_bandit_scan(p_obj)
                    if bandit_findings:
                        findings.extend(
                            [
                                SavedFinding(
                                    **f.model_dump(),
                                    persona="devsecops",
                                    persona_title="Principal DevSecOps Engineer",
                                )
                                for f in bandit_findings
                            ]
                        )

                # 3. Aqua Trivy scan for Dockerfiles and lockfiles
                if p_name in ("dockerfile", "containerfile") or p_name.endswith(
                    (".lock", ".lockb")
                ):
                    t_findings = run_trivy_scan(
                        p_obj,
                        scan_type="config" if "docker" in p_name else "fs",
                    )
                    if t_findings:
                        findings.extend(
                            [
                                SavedFinding(
                                    **f.model_dump(),
                                    persona="devsecops",
                                    persona_title="Principal DevSecOps Engineer",
                                )
                                for f in t_findings
                            ]
                        )

                return fpath, findings

            with ThreadPoolExecutor(max_workers=8) as executor:
                for fpath, f_findings in executor.map(_scan_file_static, file_paths):
                    if f_findings:
                        static_findings_by_file.setdefault(fpath, []).extend(f_findings)
        except Exception:
            pass

        osv_client = OSVClient()
        shodan_client = ShodanInternetDBClient()
        radar_client = CloudflareRadarClient()

        # 1. Parse dependencies and network references across target files
        raw_file_data: dict[str, tuple[list[DependencySpec], list[NetworkReference]]] = {}
        all_unique_deps: set[tuple[str, str, str]] = set()
        all_unique_nets: set[tuple[str, str]] = set()

        for fpath in file_paths:
            file_deps: list[DependencySpec] = []
            file_nets: list[NetworkReference] = []
            p_target = self._resolve_file_path(fpath)
            if p_target.exists() and p_target.is_file():
                try:
                    f_content = p_target.read_text(encoding="utf-8", errors="replace")
                    file_deps = extract_dependencies_from_text(f_content, fpath)
                    file_nets = extract_network_references(f_content, fpath)
                except Exception:
                    pass
            raw_file_data[fpath] = (file_deps, file_nets)
            for d in file_deps:
                all_unique_deps.add((d.name, d.version_range, d.ecosystem))
            for n in file_nets:
                all_unique_nets.add((n.target, n.reference_type))

        # 2. Concurrently pre-fetch unique dependency vulnerabilities and network reputations
        dep_cache: dict[tuple[str, str, str], list[VulnerabilityRecord]] = {}
        net_cache: dict[str, NetworkReputationRecord] = {}

        def _fetch_dep(
            d_key: tuple[str, str, str],
        ) -> tuple[tuple[str, str, str], list[VulnerabilityRecord]]:
            name, ver, eco = d_key
            try:
                vulns = osv_client.check_vulnerability(name, ver, eco)
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

        if all_unique_deps or all_unique_nets:
            with ThreadPoolExecutor(max_workers=8) as executor:
                if all_unique_deps:
                    for d_key, vulns in executor.map(_fetch_dep, list(all_unique_deps)):
                        dep_cache[d_key] = vulns
                if all_unique_nets:
                    for target, rep in executor.map(_fetch_net, list(all_unique_nets)):
                        net_cache[target] = rep

        # 3. Assemble FileReviewPayload objects
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

            file_deps, file_nets = raw_file_data.get(fpath, ([], []))
            initial_findings = list(static_findings_by_file.get(fpath, []))

            # Apply audited dependency results
            for dep in file_deps:
                d_key = (dep.name, dep.version_range, dep.ecosystem)
                vulns = dep_cache.get(d_key, [])
                if vulns:
                    dep.vulnerabilities = vulns
                    dep.security_status = f"⚠️ {len(vulns)} Known Vuln(s)"
                else:
                    dep.security_status = "✓ Clean"

                for v in vulns:
                    initial_findings.append(
                        SavedFinding(
                            severity=v.severity,
                            location=f"{fpath}:1",
                            title=f"Vulnerable Dependency: {dep.name} ({v.id})",
                            description=(
                                f"Dependency '{dep.name}' ({dep.version_range}) is affected by "
                                f"{v.id}: {v.summary}"
                            ),
                            fix=f"Upgrade '{dep.name}' to a patched release.",
                            references=[v.details_url] if v.details_url else [],
                            verification_criteria=[f"Package '{dep.name}' declared in {fpath}"],
                            invalidation_criteria=["Dependency upgraded or patched in lockfile"],
                            verified_criteria_matched=[f"Package '{dep.name}' declared in {fpath}"],
                            status="VERIFIED",
                            verified=True,
                            reportable=True,
                            confidence_score=0.95,
                            persona="devsecops",
                            persona_title="Principal DevSecOps Engineer",
                        )
                    )

            # Apply audited network reference results
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
                    initial_findings.append(
                        SavedFinding(
                            severity="HIGH",
                            location=f"{fpath}:{net.line_number or 1}",
                            title=f"Suspicious / Vulnerable Network Reference: {net.target}",
                            description=(
                                f"External host '{net.target}' flagged by {rep.source}: "
                                f"{rep.reputation_summary}"
                            ),
                            fix=f"Sanitize or remove external host reference '{net.target}'.",
                            references=[f"https://internetdb.shodan.io/{rep.ip}"] if rep.ip else [],
                            verification_criteria=[f"Host '{net.target}' referenced in {fpath}"],
                            invalidation_criteria=["Internal test fixture or isolated sandbox"],
                            verified_criteria_matched=[
                                f"Host '{net.target}' referenced in {fpath}"
                            ],
                            status="VERIFIED",
                            verified=True,
                            reportable=True,
                            confidence_score=0.90,
                            persona="devsecops",
                            persona_title="Principal DevSecOps Engineer",
                        )
                    )

            sanitized_name = _sanitize_filename(fpath) + ".json"
            json_file = self.files_dir / sanitized_name

            payload = FileReviewPayload(
                file_path=fpath,
                metadata=fmeta,
                linked_files=linked,
                findings=initial_findings,
                external_dependencies=file_deps,
                network_references=file_nets,
                ai_scratchpad={
                    "initialized_at": datetime.now(UTC).isoformat(),
                    "stage": "initialized",
                    "thoughts": [
                        f"Tracking findings for {fpath}",
                        *(
                            [
                                f"Injected {len(initial_findings)} static scan / "
                                "threat intel finding(s)"
                            ]
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

            persona_lookup: dict[str, tuple[str, str]] = {}
            target_agents_path = self.target_dir / "AGENTS.md"
            target_conventions = ""
            if target_agents_path.exists() and target_agents_path.is_file():
                try:
                    c_text = target_agents_path.read_text(encoding="utf-8", errors="replace")[:3000]
                    target_conventions = (
                        f"\n\nTarget Repository Conventions ({target_agents_path.name}):\n"
                        f"{c_text}\n"
                    )
                except Exception:
                    pass

            for p_key in active_personas:
                try:
                    persona_enum = Persona(p_key) if isinstance(p_key, str) else p_key
                    p_val = (
                        persona_enum.value if hasattr(persona_enum, "value") else str(persona_enum)
                    )
                except ValueError:
                    persona_enum = Persona.DEVSECOPS
                    p_val = "devsecops"
                p_def = PERSONAS[persona_enum]
                persona_lookup[p_def.title] = (p_val, p_def.title)
                persona_lookup[p_val] = (p_val, p_def.title)
                sys_prompt = (
                    f"You are {p_def.title}.\n{p_def.system_prompt}\n\n"
                    "CRITICAL: Examine code carefully for flaws and security vulnerabilities.\n"
                    "Evaluate code objectively according to its target runtime and architecture "
                    "without enforcing host project layout.\n"
                    f"{target_conventions}"
                    "Report all findings in 'findings' JSON array with severity, location, title, "
                    "description, fix, verification_criteria, invalidation_criteria, and "
                    "confidence_score."
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
                thoughts_list: list[str] = payload.ai_scratchpad.setdefault("thoughts", [])
                for step in result.steps:
                    if step.backend_info and step.backend_info not in actual_servers:
                        actual_servers.append(step.backend_info)

                    # Extract thinking blocks from step
                    if step.thoughts:
                        for t in step.thoughts:
                            t_clean = t.strip()
                            if t_clean and t_clean not in thoughts_list:
                                thoughts_list.append(f"[{step.agent_name}] {t_clean}")
                    elif step.content:
                        thinks, _ = extract_think_blocks(step.content)
                        for t in thinks:
                            t_clean = t.strip()
                            if t_clean and t_clean not in thoughts_list:
                                thoughts_list.append(f"[{step.agent_name}] {t_clean}")

                    parsed: ReviewResult | None = None
                    if step.parsed_data and isinstance(step.parsed_data, ReviewResult):
                        parsed = step.parsed_data
                    else:
                        parsed = parse_review_result(step.content)

                    p_val, p_title = persona_lookup.get(
                        step.agent_name,
                        (step.agent_name.lower().replace(" ", "_"), step.agent_name),
                    )

                    rec_str = parsed.recommendation if parsed else "REVIEW"
                    n_findings_step = len(parsed.findings) if parsed else 0
                    thoughts_list.append(
                        f"[{p_title}] Evaluated {fpath}: {rec_str} ({n_findings_step} finding(s))"
                    )

                    if parsed and parsed.findings:
                        for f in parsed.findings:
                            saved = SavedFinding(
                                **f.model_dump(),
                                persona=p_val,
                                persona_title=p_title,
                            )
                            file_findings.append(saved)

                payload.findings = file_findings
                payload.ai_scratchpad["stage"] = "reviewed"
                payload.ai_scratchpad["persona_turn_count"] = len(result.steps)
            except Exception as exc:
                payload.findings = []
                payload.ai_scratchpad["stage"] = "failed"
                payload.ai_scratchpad["error"] = str(exc)
                payload.ai_scratchpad.setdefault("thoughts", []).append(
                    f"Review failed for {fpath}: {exc}"
                )

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
            target_file = self._resolve_file_path(fpath)
            file_code = ""
            if target_file.exists() and target_file.is_file():
                try:
                    file_code = target_file.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass

            linked_snippets: list[str] = []
            for lmeta in payload.linked_files:
                lpath = self._resolve_file_path(lmeta.path)
                if lpath.exists() and lpath.is_file():
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

            thoughts_list = payload.ai_scratchpad.setdefault("thoughts", [])
            thoughts_list.append(
                f"[Stage 4 Verification] Verified {tot_u} finding(s) for {payload.file_path}: "
                f"{valid_cnt} confirmed/mitigated, {tot_u - valid_cnt} invalidated/unverified"
            )

            payload.findings = updated_saved
            payload.ai_scratchpad["stage"] = "verified"

            sanitized_name = _sanitize_filename(payload.file_path) + ".json"
            json_target = self.files_dir / sanitized_name
            json_target.write_text(payload.model_dump_json(indent=2), encoding="utf-8")

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
                f
                for f in payload.findings
                if f.reportable and f.status in ("VERIFIED", "UNVERIFIED", "MITIGATED")
            ]
            for f in payload.findings:
                payload.reportable = f.status != "INVALIDATED" and f.reportable
            payload.ai_scratchpad["stage"] = "reranked"
            payload.ai_scratchpad["reportable_count"] = len(valid_findings)

            thoughts_list = payload.ai_scratchpad.setdefault("thoughts", [])
            thoughts_list.append(
                f"[Stage 5 Re-ranking] Identified {len(valid_findings)} reportable finding(s) "
                f"from {len(payload.findings)} total candidate(s)"
            )

            sanitized_name = _sanitize_filename(payload.file_path) + ".json"
            json_target = self.files_dir / sanitized_name
            json_target.write_text(payload.model_dump_json(indent=2), encoding="utf-8")

        total_reportable = sum(
            len([f for f in p.findings if f.reportable and f.status != "INVALIDATED"])
            for p in file_payloads
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
                if f.status != "INVALIDATED" and f.reportable:
                    all_findings.append(f)

        all_findings = consolidate_duplicate_findings(all_findings)

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

        payload_out = ReviewSessionPayload(
            generated_at=datetime.now(UTC).isoformat(),
            personas=["devsecops", "architect", "qa"],
            findings=all_findings,
            external_dependencies=all_deps,
            network_references=all_nets,
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
            lines.append("| Severity | Location | Title | Status | Persona |")
            lines.append("|---|---|---|---|---|")
            for f in all_findings:
                row = (
                    f"| **{f.severity}** | `{f.location}` | {f.title} | "
                    f"{f.status} | {f.persona_title} |"
                )
                lines.append(row)

            lines.append("")
            lines.append("## Detailed Findings")
            for idx, f in enumerate(all_findings, 1):
                lines.append(f"### {idx}. [{f.severity}] {f.title}")
                lines.append(f"- **Location**: `{f.location}`")
                lines.append(f"- **Persona**: {f.persona_title}")
                lines.append(f"- **Status**: {f.status}")
                lines.append(f"- **Description**: {f.description}")
                if f.fix:
                    lines.append(f"- **Fix Recommendation**:\n```\n{f.fix}\n```")
                lines.append("")

        if all_deps:
            lines.append("## External Dependencies (OSV.dev & NVD)")
            lines.append(
                "| Dependency | Version Range | Ecosystem | Security Status | Source File |"
            )
            lines.append("|---|---|---|---|---|")
            for dep in all_deps:
                lines.append(
                    f"| `{dep.name}` | `{dep.version_range}` | {dep.ecosystem} | "
                    f"{dep.security_status} | `{dep.source_file}` |"
                )
            lines.append("")

        if all_nets:
            lines.append("## External Network References (Shodan InternetDB & Cloudflare Radar)")
            lines.append("| Target | Type | Security Status | Source File | Line |")
            lines.append("|---|---|---|---|---|")
            for net in all_nets:
                l_str = str(net.line_number) if net.line_number else "—"
                lines.append(
                    f"| `{net.target}` | {net.reference_type} | {net.security_status} | "
                    f"`{net.source_file}` | {l_str} |"
                )
            lines.append("")

        report_md = "\n".join(lines)
        (self.session_dir / "review.md").write_text(report_md, encoding="utf-8")

        from rich.console import Console
        from rich.table import Table

        console = Console()
        if all_deps:
            dep_tbl = Table(title="External Dependencies Security Audit (OSV.dev & NVD)")
            dep_tbl.add_column("Dependency", style="bold cyan")
            dep_tbl.add_column("Version Range")
            dep_tbl.add_column("Ecosystem")
            dep_tbl.add_column("Security Status")
            dep_tbl.add_column("Source File", style="dim")
            for d in all_deps:
                color = "red" if "⚠️" in d.security_status else "green"
                dep_tbl.add_row(
                    d.name,
                    d.version_range,
                    d.ecosystem,
                    f"[{color}]{d.security_status}[/{color}]",
                    d.source_file,
                )
            console.print(dep_tbl)

        if all_nets:
            net_tbl = Table(
                title="External Network References Security Audit (Shodan & Cloudflare Radar)"
            )
            net_tbl.add_column("Target", style="bold cyan")
            net_tbl.add_column("Type")
            net_tbl.add_column("Security Status")
            net_tbl.add_column("Source File", style="dim")
            net_tbl.add_column("Line", justify="right")
            for n in all_nets:
                color = "red" if "⚠️" in n.security_status else "green"
                net_tbl.add_row(
                    n.target,
                    n.reference_type,
                    f"[{color}]{n.security_status}[/{color}]",
                    n.source_file,
                    str(n.line_number or "—"),
                )
            console.print(net_tbl)

        rprint(
            f"[green]✓ Consolidated review completed for session {self.session_id}[/green] "
            f"([bold]{len(all_findings)}[/bold] finding(s) saved to [dim]{self.session_dir}[/dim])"
        )
        return payload_out.model_dump(), report_md
