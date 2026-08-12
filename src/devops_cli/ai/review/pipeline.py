"""Multi-Agent Pipeline Orchestrator for Code Reviews."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from devops_cli.ai.agents.pipeline import MultiAgentPipeline
from devops_cli.ai.agents.pydantic_agent import PydanticAgent
from devops_cli.ai.analyze.cache import load_cached_analysis
from devops_cli.ai.analyze.scanner import scan_directory
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
from devops_cli.config.constants import CONST_DATA_DIR
from devops_cli.models.ai import FileAnalysisMeta

logger = logging.getLogger(__name__)


class ReviewPipelineOrchestrator:
    """Orchestrates 6-stage multi-agent code reviews with per-file payloads and AI scratchpads."""

    def __init__(self, session_id: str | None = None, llm_client: LLMClient | None = None) -> None:
        self.session_id = session_id or datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        self.session_dir = CONST_DATA_DIR / "reviews" / self.session_id
        self.files_dir = self.session_dir / "files"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self.llm_client = llm_client or LLMClient()

    # ── Stage 1: Pre-Analysis & Metadata Refresh ──────────────────────────────
    def run_pre_analysis_refresh(self, target_dir: Path = Path(".")) -> dict[str, FileAnalysisMeta]:
        """Scan workspace and refresh metadata if files were edited since last analysis."""
        from devops_cli.dry_run.state import is_dry_run

        if is_dry_run():
            return {}

        metadata_by_path: dict[str, FileAnalysisMeta] = {}
        cached_meta = load_cached_analysis(target_dir)
        if cached_meta:
            for fmeta in cached_meta.files:
                metadata_by_path[fmeta.path] = fmeta
            return metadata_by_path

        if target_dir.resolve() == Path.cwd().resolve():
            return metadata_by_path

        file_metas = scan_directory(target_dir)
        for fm in file_metas:
            rel = fm.path
            existing = metadata_by_path.get(rel)
            is_outdated = bool(
                existing
                and existing.last_analyzed
                and existing.last_updated
                and existing.last_updated > existing.last_analyzed
            )
            if not existing or is_outdated:
                fm.last_analyzed = datetime.now(UTC).isoformat()
                metadata_by_path[rel] = fm

        return metadata_by_path

    # ── Stage 2: Per-File Review Session JSON Initialization ──────────────────
    def init_per_file_payloads(
        self, file_paths: list[str], metadata_by_path: dict[str, FileAnalysisMeta]
    ) -> list[FileReviewPayload]:
        """Initialize per-file JSON payloads under session files directory."""
        payloads: list[FileReviewPayload] = []

        for fpath in file_paths:
            fmeta = metadata_by_path.get(fpath) or FileAnalysisMeta(path=fpath)
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

            payload = FileReviewPayload(
                file_path=fpath,
                metadata=fmeta,
                linked_files=linked,
                findings=[],
                ai_scratchpad={
                    "initialized_at": datetime.now(UTC).isoformat(),
                    "stage": "initialized",
                    "thoughts": [f"Tracking findings for {fpath}"],
                },
            )

            json_file.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
            payloads.append(payload)

        return payloads

    # ── Stage 3: Multi-Persona Code Content Review ─────────────────────────────
    def execute_multi_persona_review(
        self,
        file_payloads: list[FileReviewPayload],
        diff_text_by_file: dict[str, str],
        personas: list[str] | None = None,
    ) -> None:
        """Run multi-persona review pipeline per file and update per-file JSON payloads."""
        active_personas = personas or ["devsecops", "architect", "qa"]

        for payload in file_payloads:
            fpath = payload.file_path
            content_or_diff = diff_text_by_file.get(fpath, "")
            if not content_or_diff and Path(fpath).exists():
                try:
                    code_raw = Path(fpath).read_text(encoding="utf-8", errors="replace")
                    content_or_diff = code_raw[:10000]
                except Exception:
                    pass

            if not content_or_diff:
                continue

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
                    f"You are {p_def.title}.\n{p_def.system_prompt}\n"
                    "Review code and provide confidence_score (0.0 to 1.0, default null)."
                )
                agent = PydanticAgent[ReviewResult](
                    client=self.llm_client,
                    name=p_def.title,
                    system_prompt=sys_prompt,
                    output_schema=ReviewResult,
                )
                pipeline.add_agent(agent)

            symbols = ", ".join(payload.metadata.key_symbols if payload.metadata else [])
            prompt = (
                f"Review File: {fpath}\n"
                f"Key Symbols: {symbols}\n\n"
                f"Code Content / Diff:\n{content_or_diff}"
            )

            result = pipeline.run(prompt, max_turns_per_agent=1, enable_thinking=False)
            for step in result.steps:
                parsed = parse_review_result(step.content)
                if parsed:
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

            sanitized_name = _sanitize_filename(fpath) + ".json"
            json_target = self.files_dir / sanitized_name
            json_target.write_text(payload.model_dump_json(indent=2), encoding="utf-8")

    # ── Stage 4: Cross-Referencing Verification & Reasoning ─────────────────
    def execute_finding_verification(self, file_payloads: list[FileReviewPayload]) -> None:
        """Verify findings against file contents and linked files, setting confidence_score."""
        for payload in file_payloads:
            if not payload.findings:
                continue

            target_file = Path(payload.file_path)
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

            review_res, _ = _validate_segment_findings(
                result=ReviewResult(findings=findings_to_verify),
                all_segments=[context],
                client=self.llm_client,
            )
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

    # ── Stage 5: AI Validation & Re-ranking ──────────────────────────────────
    def execute_finding_reranking(self, file_payloads: list[FileReviewPayload]) -> None:
        """Validate and re-rank all findings into reportable vs non-reportable."""
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

    # ── Stage 6: Consolidated Report Generation ──────────────────────────────
    def generate_consolidated_report(
        self, file_payloads: list[FileReviewPayload]
    ) -> tuple[dict[str, Any], str]:
        """Generate consolidated findings.json and client-facing Markdown report."""
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

        return payload_out.model_dump(), report_md
