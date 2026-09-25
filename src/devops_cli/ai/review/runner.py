"""Multi-persona review execution runner, model warming, and session management."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import Counter
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from devops_cli.ai.analyze.cache import _load_file_analysis_metas
from devops_cli.ai.client import AIClientError, LLMClient
from devops_cli.ai.client.network import limit_completion_tokens
from devops_cli.ai.personas import PERSONAS, Persona, PersonaDefinition
from devops_cli.ai.review.chunker import (
    _extract_header_filenames,
    _split_source_file_blocks,
)
from devops_cli.ai.review.classification import _persona_system_prompt
from devops_cli.ai.review.flags import ReviewStageFlags
from devops_cli.ai.review.profile import (
    ReviewProfile,
    ReviewProfiler,
    active_profiler,
    profiling,
    report_profile,
    review_stage,
)
from devops_cli.ai.review.review_environment import (
    _get_reviews_base_dir as _get_reviews_base_dir,
)
from devops_cli.ai.review.review_environment import (
    _read_candidate_conventions_file as _read_candidate_conventions_file,
)
from devops_cli.ai.review.verification import (
    _merge_segment_results,
    _reconcile_verified,
    _validate_segment_findings,
)
from devops_cli.ai.review_schema import (
    Finding,
    ReviewResult,
    ReviewSessionPayload,
    SavedFinding,
    compute_verdict_distributions,
    consolidate_duplicate_findings,
    parse_review_response,
)
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import (
    CONST_GIT_MAIN_BRANCH,
    CONST_REVIEW_GENERATED_FILES,
)
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_REVIEW_MAX_DIFF_CHARS,
    DEFAULT_REVIEW_PERSONA_REPLY_MAX_TOKENS,
    DEFAULT_REVIEW_TIMEOUT_SECONDS,
)
from devops_cli.config.settings import Settings, get_ai_api_key, load_settings
from devops_cli.core.process import run_subprocess as _run_subprocess
from devops_cli.core.repo import find_repo_root, is_ignored_by_git, is_safe_subpath
from devops_cli.dry_run import is_dry_run
from devops_cli.models.ai import FileAnalysisMeta
from devops_cli.output import (
    format_duration,
    print_error,
    print_info,
    print_markdown,
    print_muted,
    print_section,
    print_table,
    print_warning,
    render_review_result,
)
from devops_cli.security.sanitizer import (
    redact_text,
    sanitize_prompt_boundary_tags,
)
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)

_MAX_DIFF_CHARS = DEFAULT_REVIEW_MAX_DIFF_CHARS
_MAX_SEGMENT_RETRIES = 2
_DEFAULT_CONTEXT_LINES = 2

_PAGINATED_REVIEW_PROTOCOL = load_task_prompt("paginated_review_protocol.md")
_REVIEW_OUTPUT_INSTRUCTION = "\n" + load_task_prompt("review_output_instruction.md")
_PATH_REVIEW_PROMPT_TEMPLATE = load_task_prompt("path_review_prompt.md")


class ReviewClients(BaseModel):
    """LLM clients resolved per review task, each potentially using a different model.

    ``verification`` checks the findings ``analysis`` produced. It defaults to the analysis
    client, so generation and verification share a model unless verification is configured.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    analysis: Any
    compose: Any
    verification: Any = None

    @model_validator(mode="after")
    def _verify_with_analysis_by_default(self) -> ReviewClients:
        if self.verification is None:
            self.verification = self.analysis
        return self


def _personas_to_run(all_personas: bool, persona: Persona | None) -> list[PersonaDefinition]:
    if all_personas:
        return list(PERSONAS.values())
    return [PERSONAS[persona or Persona.DEVSECOPS]]


def _debug_block(title: str, payload: dict[str, Any]) -> None:
    from devops_cli.output import print_dry_run_result

    print_warning(f"[dry-run] {title}", prefix=False)
    print_dry_run_result(payload)


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


def _llm_request_preview(client: Any, system: str, user: str) -> dict[str, Any]:
    config = getattr(client, "_config", None)
    provider = getattr(config, "provider", "unknown")
    model = getattr(config, "model", "unknown")

    if provider == "ollama":
        urls = _resolve_ollama_urls(config)
        base = urls[0] if urls else "http://localhost:11434"
        return {
            "provider": provider,
            "endpoint": f"{str(base).rstrip('/')}/api/chat",
            "method": "POST",
            "json": {
                "model": model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        }

    if provider == "claude":
        base = getattr(config, "api_base_url", "https://api.anthropic.com")
        return {
            "provider": provider,
            "endpoint": f"{str(base).rstrip('/')}/v1/messages",
            "method": "POST",
            "headers": {
                "x-api-key": "***REDACTED***",
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            "json": {
                "model": model,
                "max_tokens": 8192,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        }

    base = getattr(config, "api_base_url", "")
    if provider == "copilot" and not base:
        base = "https://api.githubcopilot.com"
    if provider == "openai" and not base:
        base = "https://api.openai.com/v1"
    return {
        "provider": provider,
        "endpoint": f"{str(base).rstrip('/')}/chat/completions",
        "method": "POST",
        "headers": {
            "Authorization": "Bearer ***REDACTED***",
            "Content-Type": "application/json",
        },
        "json": {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
    }


def _persona_format_section(persona: PersonaDefinition) -> str:
    """Extract the output-format specification from the persona's system prompt."""
    marker = "Respond in this exact format:"
    if marker not in persona.system_prompt:
        return ""
    return marker + persona.system_prompt.split(marker, 1)[1].rstrip()


def _resolve_relevant_analysis_metas(
    filenames: list[str], analysis_metas: dict[str, FileAnalysisMeta]
) -> dict[str, Any]:
    """Filter analysis metadata for filenames present in the segment."""
    relevant = {
        path: fmeta.model_dump(exclude_none=True)
        for path, fmeta in analysis_metas.items()
        if not filenames or path in filenames or any(f in path for f in filenames)
    }
    if not relevant and filenames:
        return {
            fn: {"path": fn, "primary_purpose": f"Source file review for {fn}"} for fn in filenames
        }
    if not relevant:
        return {
            path: fmeta.model_dump(exclude_none=True)
            for path, fmeta in list(analysis_metas.items())[:15]
        }
    return relevant


def _query_segment_rag_section(
    filenames: list[str],
    relevant_metas: dict[str, Any],
    title: str,
    persona: PersonaDefinition,
) -> str:
    """Perform RAG investigation for cross-file architecture context."""
    try:
        from devops_cli.ai.rag.investigator import (
            format_rag_investigation_for_prompt,
            investigate_rag_context,
        )

        symbols: list[str] = []
        for meta_dict in relevant_metas.values():
            if isinstance(meta_dict, dict) and isinstance(meta_dict.get("key_symbols"), list):
                symbols.extend([str(s) for s in meta_dict["key_symbols"][:3]])

        rag_query = f"{' '.join(filenames)} {' '.join(symbols)}".strip() or title
        rag_ctx = investigate_rag_context(rag_query, persona=persona.name, top_k=3)
        return format_rag_investigation_for_prompt(
            rag_ctx, "Cross-File Architecture & Semantic Context"
        )
    except Exception:
        return ""


def _build_segment_review_prompt(
    segment: str,
    title: str,
    index: int,
    total: int,
    analysis_metas: dict[str, FileAnalysisMeta],
    build_base: Callable[[str, str], str],
    persona: PersonaDefinition,
) -> str:
    fns = _extract_header_filenames(segment)
    relevant_metas = _resolve_relevant_analysis_metas(fns, analysis_metas)
    all_files_list = list(analysis_metas.keys()) if analysis_metas else fns
    context_meta = {
        "title": title,
        "total_files": total,
        "current_file_index": index,
        "all_files": all_files_list,
        "file_metadata": relevant_metas,
    }
    meta_json = sanitize_prompt_boundary_tags(json.dumps(context_meta, indent=2, ensure_ascii=True))
    part_title = title if total == 1 else f"{title} — file {index}/{total}"
    format_section = _persona_format_section(persona)
    rag_section = _query_segment_rag_section(fns, relevant_metas, title, persona)

    return (
        f"You are performing a code review as: {persona.title}.\n\n"
        f"Analysis metadata for review context:\n"
        f"<review_metadata_context>\n```json\n{meta_json}\n```\n</review_metadata_context>\n\n"
        f"{_PAGINATED_REVIEW_PROTOCOL}\n"
        f"{build_base(segment, part_title)}"
        + (f"\n\n{rag_section}" if rag_section else "")
        + (f"\n\n{format_section}" if format_section else "")
        + _REVIEW_OUTPUT_INSTRUCTION
    )


def _build_recompose_prompt(
    title: str,
    analysis_metas: dict[str, FileAnalysisMeta],
    responses: list[str],
    persona: PersonaDefinition,
    segment_results: list[ReviewResult | None],
) -> str:
    summary_map = {
        path: {
            "purpose": fmeta.primary_purpose,
            "symbols": fmeta.key_symbols,
            "dependencies": fmeta.dependencies,
            "complexity": fmeta.complexity_score,
            **({"pseudocode": fmeta.pseudocode} if fmeta.pseudocode else {}),
        }
        for path, fmeta in analysis_metas.items()
    }
    context_meta = {
        "title": title,
        "total_files": len(analysis_metas),
        "file_summaries": summary_map,
    }
    meta_json = sanitize_prompt_boundary_tags(json.dumps(context_meta, indent=2, ensure_ascii=True))
    parsed_findings = [f for r in segment_results if r for f in r.sorted_findings]
    if parsed_findings:
        findings_json = sanitize_prompt_boundary_tags(
            json.dumps([f.model_dump() for f in parsed_findings], indent=2, ensure_ascii=True)
        )
        findings_block = (
            f"Structured findings from {len(parsed_findings)} validated finding(s):\n"
            f"<untrusted_segment_outputs>\n```json\n{findings_json}\n```\n</untrusted_segment_outputs>"
        )
    else:
        non_empty = [(i + 1, r) for i, r in enumerate(responses) if r.strip()]
        total = len(responses)
        parts = "\n\n".join(f"## Segment {i}/{total}\n{r}" for i, r in non_empty)
        clean_parts = sanitize_prompt_boundary_tags(parts)
        findings_block = (
            f"Per-segment review outputs ({len(non_empty)} of {total} segments had content):\n"
            f"<untrusted_segment_outputs>\n{clean_parts}\n</untrusted_segment_outputs>"
        )
    format_section = _persona_format_section(persona)
    return (
        f"You are performing a code review as: {persona.title}.\n\n"
        "Consolidate the findings below into one final review. "
        "Deduplicate, keeping the strongest description of each. "
        "Do not add findings absent from the provided data.\n"
        f"{_PAGINATED_REVIEW_PROTOCOL}"
        f"Review title: {title}\n\n"
        "Review metadata:\n"
        f"<review_metadata_context>\n```json\n{meta_json}\n```\n</review_metadata_context>\n\n"
        f"{findings_block}"
        + (f"\n\n{format_section}" if format_section else "")
        + _REVIEW_OUTPUT_INSTRUCTION
    )


def _fallback_join(reviews: list[str]) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for r in reviews:
        for line in r.splitlines():
            key = line.strip().lower()
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            lines.append(line)
        lines.append("")
    return "\n".join(lines).strip()


def _find_session_dir(session_arg: str | None) -> Path | None:
    reviews_dir = _get_reviews_base_dir()
    if not reviews_dir.exists():
        return None
    if session_arg:
        safe_arg = Path(session_arg).name
        target = (reviews_dir / safe_arg).resolve()
        if target.exists() and target.is_dir() and target.is_relative_to(reviews_dir.resolve()):
            return target
        matches = [d for d in reviews_dir.iterdir() if d.is_dir() and safe_arg in d.name]
        if matches:
            return sorted(matches)[-1]
        return None

    sessions = [d for d in reviews_dir.iterdir() if d.is_dir() and (d / "findings.json").exists()]
    return max(sessions, key=lambda p: p.stat().st_mtime) if sessions else None


def _review_session_dir(label: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = _get_reviews_base_dir()
    d = base / f"{stamp}-{label}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_segments(pages: list[str], session_dir: Path) -> None:
    for i, page in enumerate(pages, 1):
        target = session_dir / f"segment-{i}.md"
        target.write_text(page, encoding="utf-8")
        target.chmod(0o600)


def _save_findings_json(
    completed: list[tuple[PersonaDefinition, ReviewResult | str]],
    session_dir: Path,
    show_status: bool = False,
) -> bool:
    target = session_dir / "findings.json"
    findings: list[SavedFinding] = []
    for pd, review in completed:
        if not isinstance(review, ReviewResult):
            continue
        for f in review.sorted_findings:
            findings.append(
                SavedFinding(
                    persona=pd.name,
                    persona_title=pd.title,
                    recommendation=review.recommendation,
                    **f.model_dump(),
                )
            )
    findings = consolidate_duplicate_findings(findings)
    payload = ReviewSessionPayload(
        generated_at=datetime.now().isoformat(),
        personas=[pd.name for pd, _ in completed],
        findings=findings,
    )
    try:
        target.write_text(
            payload.model_dump_json(indent=2),
            encoding="utf-8",
        )
        target.chmod(0o600)
        if show_status:
            print_muted(f"  ✓ findings saved → {target}")
        return True
    except OSError as exc:
        print_warning(f"Warning: failed to write findings.json: {exc}")
        return False


def _review_to_markdown(review: ReviewResult | str) -> str:
    if isinstance(review, str):
        from devops_cli.ai.thinking_stream import strip_think_blocks

        clean_text = strip_think_blocks(review)
        parsed = parse_review_response(clean_text)
        return _review_to_markdown(parsed) if parsed else clean_text
    lines: list[str] = [f"**Recommendation: {review.recommendation}**\n"]
    if review.findings:
        lines.append("## Findings\n")
        for f in review.sorted_findings:
            verified = (
                ""
                if f.verified and not f.mitigated
                else " *(mitigated)*"
                if f.mitigated
                else " *(unverified)*"
            )
            lines.append(f"### [{f.severity}] {f.title}{verified}")
            lines.append(f"**Location:** `{f.location}`\n")
            if f.description:
                lines.append(f.description + "\n")
            if f.fix:
                lines.append(f"**Fix:** {f.fix}\n")
            if f.references:
                lines.append(f"**References:** {', '.join(f.references)}\n")
    if review.positive_observations:
        lines.append("## Positive Observations\n")
        lines.extend(f"- {obs}" for obs in review.positive_observations)
        lines.append("")
    if review.summary:
        lines.append("## Summary\n")
        lines.append(review.summary)
    return "\n".join(lines)


def _save_persona_review(
    pd: PersonaDefinition,
    review: ReviewResult | str,
    session_dir: Path,
) -> Path:
    filename = f"{pd.name}-review.md"
    content = f"# {pd.title}\n\n{_review_to_markdown(review)}\n"
    dest = session_dir / filename
    dest.write_text(content, encoding="utf-8")
    dest.chmod(0o600)
    return dest


def _write_summary(
    title: str,
    session_dir: Path,
    pages: list[str],
    completed: list[tuple[PersonaDefinition, ReviewResult | str]],
    analysis_metas: dict[str, FileAnalysisMeta] | None = None,
) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    if completed:
        _save_findings_json(completed, session_dir, show_status=True)
    lines: list[str] = [
        f"# Review: {title}",
        f"**Date:** {now}  ",
        f"**Files/Segments:** {len(pages)}  ",
        f"**Session:** `{session_dir}`\n",
    ]
    if analysis_metas:
        lines.append("## Analysis Metadata\n")
        lines.append(f"**Files analyzed:** {len(analysis_metas)}  \n")
        lines.append("### File Summaries\n")
        for path, fmeta in analysis_metas.items():
            lines.append(
                f"**{path}** — purpose: {fmeta.primary_purpose}"
                f"{', complexity: ' + fmeta.complexity_score if fmeta.complexity_score else ''}"
            )
            if fmeta.key_symbols:
                lines.append(f"> Symbols: {', '.join(fmeta.key_symbols[:10])}")
        lines.append("| File Path | Language | Purpose | Complexity |")
        lines.append("|---|---|---|---|")
        for path, fmeta in analysis_metas.items():
            clean_p = path.replace("|", "\\|").replace("\n", " ").strip()
            clean_purp = (
                (fmeta.primary_purpose or "—").replace("|", "\\|").replace("\n", " ").strip()
            )
            clean_comp = (
                (fmeta.complexity_score or "—").replace("|", "\\|").replace("\n", " ").strip()
            )
            lines.append(f"| `{clean_p}` | {fmeta.language} | {clean_purp} | {clean_comp} |")
        lines.append("")
    if completed:
        lines.append("## Personas\n")
        lines.append("| Persona | Recommendation | Report |")
        lines.append("|---|---|---|")
        for pd, rev in completed:
            rec = rev.recommendation if isinstance(rev, ReviewResult) else "—"
            clean_title = pd.title.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")
            clean_rec = rec.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")
            lines.append(
                f"| {clean_title} | {clean_rec} | [{pd.name}-review.md]({pd.name}-review.md) |"
            )
        lines.append("")
    if pages:
        lines.append("## Segments\n")
        lines.append("| # | File |")
        lines.append("|---|------|")
        for i in range(1, len(pages) + 1):
            lines.append(f"| {i} | [segment-{i}.md](segment-{i}.md) |")
        lines.append("")
    summary_path = session_dir / "summary.md"
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    summary_path.chmod(0o600)
    if completed:
        print_info(f"[dim]Review saved → {session_dir}[/dim]", prefix=False)


def _build_dry_run_segment_result(file_label: str, title: str) -> ReviewResult:
    """Construct mock ReviewResult for dry-run simulation of a segment."""
    return ReviewResult(
        findings=[
            Finding(
                severity="INFO",
                location=title,
                title=f"[dry-run] {file_label} Analysis",
                description=f"Dry run analysis performed for {file_label}.",
                fix="No action required (dry-run mode).",
                verified=True,
                status="VERIFIED",
            )
        ],
        positive_observations=["Segment code passed dry-run analysis."],
        recommendation="APPROVE",
        summary=f"Dry run {file_label} review simulation.",
    )


def _log_segment_error(
    file_label: str, seg_elapsed: float, fail_backend: str, attempt: int
) -> None:
    """Log segment failure or retry message."""
    if attempt <= _MAX_SEGMENT_RETRIES:
        print_warning(
            f"  ✗ {file_label} error in {format_duration(seg_elapsed)}"
            f"{fail_backend} (attempt {attempt}), retrying...",
            prefix=False,
        )
    else:
        print_warning(
            f"  ✗ {file_label} failed in {format_duration(seg_elapsed)} after "
            f"{_MAX_SEGMENT_RETRIES + 1} attempt(s); skipping.{fail_backend}",
            prefix=False,
        )


def _log_segment_empty(
    file_label: str, seg_elapsed: float, req_backend_str: str, attempt: int
) -> None:
    """Log empty segment response or retry message."""
    if attempt <= _MAX_SEGMENT_RETRIES:
        print_warning(
            f"  ✗ {file_label} empty in {format_duration(seg_elapsed)}"
            f"{req_backend_str} (attempt {attempt}), retrying...",
            prefix=False,
        )
    else:
        print_warning(
            f"Warning: {file_label} still empty in {format_duration(seg_elapsed)} "
            f"after {_MAX_SEGMENT_RETRIES + 1} attempt(s).{req_backend_str}",
            prefix=False,
        )


def _build_dry_run_persona_result(title: str, persona_name: str, total: int) -> ReviewResult:
    """Construct mock ReviewResult for dry-run simulation of a persona."""
    return ReviewResult(
        findings=[
            Finding(
                severity="INFO",
                location=title,
                title="[dry-run] Simulated Review Execution",
                description=(
                    f"Dry run analysis performed for persona {persona_name} "
                    f"across {total} segment(s)."
                ),
                fix="No changes required (dry-run mode).",
                verified=True,
                status="VERIFIED",
            )
        ],
        positive_observations=["Dry run command execution completed successfully."],
        recommendation="APPROVE",
        summary=f"Dry run execution of review for {title}.",
    )


def _prepare_review_metadata(
    pages: list[str],
    prebuilt_metadata: dict[str, FileAnalysisMeta] | None,
    analysis_suffix: str,
) -> dict[str, FileAnalysisMeta]:
    """Resolve AST and AI metadata for files in scope."""
    total = len(pages)
    if prebuilt_metadata is not None:
        count = len(prebuilt_metadata)
        print_info(
            f"[dim]Step 1/4: Reusing pre-computed analysis metadata for {count} file(s).[/dim]",
            prefix=False,
        )
        return prebuilt_metadata

    try:
        from devops_cli.core.repo import find_repo_root

        repo_target = find_repo_root(Path.cwd())
    except Exception:
        repo_target = None

    all_files = sorted(list({fn for page in pages for fn in _extract_header_filenames(page)}))
    print_info(
        f"[dim]Step 1/4: Loading analysis metadata for {total} file(s)...{analysis_suffix}[/dim]",
        prefix=False,
    )
    return _load_file_analysis_metas(all_files, repo_root=repo_target)


def _execute_review_segment_attempt(
    clients: ReviewClients,
    analysis_system: str,
    user_prompt: str,
    file_label: str,
    analysis_suffix: str,
) -> str:
    """Execute LLM call for a single review segment with retries."""
    result_text = ""
    for attempt in range(1, _MAX_SEGMENT_RETRIES + 2):
        seg_start = time.monotonic()
        proc_sec: float | None = None
        try:
            with limit_completion_tokens(DEFAULT_REVIEW_PERSONA_REPLY_MAX_TOKENS):
                res_obj = clients.analysis.chat(
                    system=analysis_system,
                    user=user_prompt,
                    validator=lambda text: parse_review_response(text) is not None,
                )
            result_text = str(res_obj)
            proc_sec = getattr(res_obj, "processing_seconds", None)
            res_backend = getattr(res_obj, "backend_info", None) or getattr(
                clients.analysis, "backend_info", ""
            )
        except AIClientError, OSError:
            seg_elapsed = time.monotonic() - seg_start
            fail_info = getattr(clients.analysis, "backend_info", "")
            fail_backend = f" [{fail_info}]" if fail_info else analysis_suffix
            _log_segment_error(file_label, seg_elapsed, fail_backend, attempt)
            if attempt <= _MAX_SEGMENT_RETRIES:
                continue
            break

        seg_elapsed = (
            float(proc_sec)
            if isinstance(proc_sec, (int, float))
            else (time.monotonic() - seg_start)
        )
        req_backend_str = f" [{res_backend}]" if res_backend else analysis_suffix
        if not result_text.strip():
            _log_segment_empty(file_label, seg_elapsed, req_backend_str, attempt)
            if attempt <= _MAX_SEGMENT_RETRIES:
                continue
        else:
            retry_note = f" (attempt {attempt})" if attempt > 1 else ""
            print_info(
                f"[dim]  ✓ {file_label} in {format_duration(seg_elapsed)}{req_backend_str}{retry_note}[/dim]",
                prefix=False,
            )
        break
    return result_text


def _execute_review_segments(
    pages: list[str],
    title: str,
    metadata: dict[str, FileAnalysisMeta],
    persona: PersonaDefinition,
    clients: ReviewClients,
    build_prompt: Callable[[str, str], str],
    analysis_system: str,
    analysis_suffix: str,
) -> list[str]:
    """Execute Step 2: review each segment across parallel or serial workers."""
    total = len(pages)
    print_info(f"[dim]Step 2/4: Reviewing {total} file(s)...{analysis_suffix}[/dim]", prefix=False)
    t_review = time.monotonic()

    def _review_segment(i: int, page: str) -> tuple[int, str]:
        fns = _extract_header_filenames(page)
        file_label = (
            f"{', '.join(fns)} ({i}/{total})"
            if fns and total > 1
            else (fns[0] if fns else f"segment {i}/{total}")
        )
        user_prompt = _build_segment_review_prompt(
            page, title, i, total, metadata, build_prompt, persona
        )
        if is_dry_run():
            _debug_block(
                f"Would send LLM review request for {file_label}",
                _llm_request_preview(clients.analysis, analysis_system, user_prompt),
            )
            dry_seg = _build_dry_run_segment_result(file_label, title)
            return (i, dry_seg.model_dump_json(indent=2))

        result_text = _execute_review_segment_attempt(
            clients, analysis_system, user_prompt, file_label, analysis_suffix
        )
        return (i, result_text)

    if total > 1 and not is_dry_run():
        from devops_cli.ai.review.pool import ReviewWorkerPool

        workers = _calculate_parallel_review_workers(clients, total)
        pool = ReviewWorkerPool.create(concurrency=workers)

        def _worker_task(item: tuple[int, str]) -> tuple[int, str]:
            i, page = item
            return _review_segment(i, page)

        raw_results = pool.run_sync_all(
            _worker_task, list(enumerate(pages, 1)), return_exceptions=True
        )
        indexed_results: list[tuple[int, str]] = []
        for idx, res in enumerate(raw_results, 1):
            if isinstance(res, tuple) and len(res) == 2:
                indexed_results.append((res[0], str(res[1])))
            elif isinstance(res, Exception):
                logger.error("Segment %d review error (%s)", idx, type(res).__name__)
                indexed_results.append((idx, ""))
            else:
                indexed_results.append((idx, str(res or "")))
        responses = [res for _, res in sorted(indexed_results, key=lambda x: x[0])]
    else:
        responses = [_review_segment(i, page)[1] for i, page in enumerate(pages, 1)]

    if not is_dry_run():
        print_info(
            f"[dim]  total {format_duration(time.monotonic() - t_review)}[/dim]", prefix=False
        )
    return responses


def _validate_single_segment_findings(
    index: int,
    page: str,
    parsed: ReviewResult | None,
    total: int,
    pages: list[str],
    clients: ReviewClients,
    file_analysis_metas: dict[str, FileAnalysisMeta],
    repo_target: Path | None,
    analysis_suffix: str,
) -> tuple[int, ReviewResult | None]:
    """Verify findings for a single review segment."""
    fns = _extract_header_filenames(page)
    file_label = (
        f"{', '.join(fns)} ({index}/{total})"
        if fns and total > 1
        else (fns[0] if fns else f"segment {index}/{total}")
    )
    if parsed is None or not parsed.findings:
        print_info(f"[dim]  ✓ {file_label}: 0 finding(s) to verify[/dim]", prefix=False)
        return (index, parsed)

    val_start = time.monotonic()
    validated, proc_sec, _ = _validate_segment_findings(
        parsed,
        pages,
        clients.verification,
        analysis_metas=file_analysis_metas,
        repo_root=repo_target,
    )
    val_elapsed = proc_sec if proc_sec is not None else (time.monotonic() - val_start)
    n_verified = sum(1 for f in validated.findings if f.verified)
    v_count = f"{n_verified}/{len(validated.findings)} finding(s) verified"
    print_info(
        f"[dim]  ✓ {file_label} in {format_duration(val_elapsed)}: {v_count}{analysis_suffix}[/dim]",
        prefix=False,
    )
    return (index, validated)


def _execute_findings_validation(
    pages: list[str],
    segment_results: list[ReviewResult | None],
    clients: ReviewClients,
    analysis_suffix: str,
) -> list[ReviewResult | None]:
    """Execute Step 3: Validate and filter hallucinated findings."""
    total = len(pages)
    if is_dry_run():
        return segment_results

    print_info(
        f"[dim]Step 3/4: Validating findings for {total} file(s)...{analysis_suffix}[/dim]",
        prefix=False,
    )
    t3 = time.monotonic()
    try:
        from devops_cli.core.repo import find_repo_root

        repo_target = find_repo_root(Path.cwd())
    except Exception:
        repo_target = None
    file_analysis_metas = _load_file_analysis_metas(None, repo_root=repo_target)

    validated_results = list(segment_results)
    if total > 1 and not is_dry_run():
        from devops_cli.ai.review.pool import ReviewWorkerPool

        workers = _calculate_parallel_review_workers(clients, total)
        val_items = list(enumerate(zip(pages, segment_results), 1))
        pool = ReviewWorkerPool.create(concurrency=workers)

        def _val_task(
            item: tuple[int, tuple[str, ReviewResult | None]],
        ) -> tuple[int, ReviewResult | None]:
            i, (page, parsed) = item
            return _validate_single_segment_findings(
                i,
                page,
                parsed,
                total,
                pages,
                clients,
                file_analysis_metas,
                repo_target,
                analysis_suffix,
            )

        val_results = pool.run_sync_all(_val_task, val_items, return_exceptions=True)
        for (idx_val, _), res_entry in zip(val_items, val_results):
            if isinstance(res_entry, tuple) and len(res_entry) == 2:
                _, val_obj = res_entry
                validated_results[idx_val - 1] = val_obj
            elif isinstance(res_entry, Exception):
                logger.error(
                    "Findings validation error for segment %d (%s)",
                    idx_val,
                    type(res_entry).__name__,
                )
                validated_results[idx_val - 1] = None
    else:
        for i, (page, parsed) in enumerate(zip(pages, segment_results), 1):
            try:
                _, single_res = _validate_single_segment_findings(
                    i,
                    page,
                    parsed,
                    total,
                    pages,
                    clients,
                    file_analysis_metas,
                    repo_target,
                    analysis_suffix,
                )
                validated_results[i - 1] = single_res
            except Exception as exc:
                logger.error(
                    "Findings validation error for segment %d (%s)",
                    i,
                    type(exc).__name__,
                )
                validated_results[i - 1] = None

    print_info(f"[dim]  total {format_duration(time.monotonic() - t3)}[/dim]", prefix=False)
    return validated_results


def _execute_final_recompose(
    title: str,
    metadata: dict[str, FileAnalysisMeta],
    responses: list[str],
    segment_results: list[ReviewResult | None],
    persona: PersonaDefinition,
    clients: ReviewClients,
    compose_system: str,
    compose_suffix: str,
    total: int,
) -> ReviewResult | str:
    """Execute Step 4: Recompose and synthesize multi-segment review findings."""
    print_info(f"[dim]Step 4/4: Composing final review...{compose_suffix}[/dim]", prefix=False)
    recompose_prompt = _build_recompose_prompt(title, metadata, responses, persona, segment_results)
    if is_dry_run():
        _debug_block(
            "Would send LLM recompose request",
            _llm_request_preview(clients.compose, compose_system, recompose_prompt),
        )
        merged = _merge_segment_results(segment_results)
        if isinstance(merged, ReviewResult):
            return merged
        return _build_dry_run_persona_result(title, persona.name, total)

    non_empty = [r for r in responses if r.strip()]
    try:
        t4 = time.monotonic()
        raw = str(
            clients.compose.chat(
                system=compose_system,
                user=recompose_prompt,
                validator=lambda text: parse_review_response(text) is not None,
            )
        )
        print_info(
            f"[dim]  ✓ {format_duration(time.monotonic() - t4)}{compose_suffix}[/dim]", prefix=False
        )
        if not raw.strip():
            return _merge_segment_results(segment_results) or _fallback_join(non_empty)
        parsed = parse_review_response(raw)
        if parsed is not None:
            return _reconcile_verified(parsed, segment_results)
        return raw
    except Exception:
        return _merge_segment_results(segment_results) or _fallback_join(non_empty)


def _run_review(
    pages: list[str],
    title: str,
    persona: PersonaDefinition,
    clients: ReviewClients,
    agents_md: str,
    build_prompt: Callable[[str, str], str],
    context_lines: int = _DEFAULT_CONTEXT_LINES,
    prebuilt_metadata: dict[str, FileAnalysisMeta] | None = None,
    session_dir: Path | None = None,
) -> ReviewResult | str:
    total = len(pages)
    analysis_system = _persona_system_prompt(persona, agents_md)
    compose_system = persona.compose_prompt

    analysis_info = getattr(clients.analysis, "backend_info", "")
    analysis_suffix = f" [{analysis_info}]" if analysis_info else ""
    compose_info = getattr(clients.compose, "backend_info", "")
    compose_suffix = f" [{compose_info}]" if compose_info else ""

    metadata = _prepare_review_metadata(pages, prebuilt_metadata, analysis_suffix)
    responses = _execute_review_segments(
        pages,
        title,
        metadata,
        persona,
        clients,
        build_prompt,
        analysis_system,
        analysis_suffix,
    )

    non_empty = [r for r in responses if r.strip()]
    if not non_empty:
        return ""

    segment_results = [parse_review_response(r) for r in responses]
    segment_results = _execute_findings_validation(pages, segment_results, clients, analysis_suffix)

    if total == 1:
        return segment_results[0] if segment_results[0] is not None else responses[0]

    return _execute_final_recompose(
        title,
        metadata,
        responses,
        segment_results,
        persona,
        clients,
        compose_system,
        compose_suffix,
        total,
    )


def _maybe_preload_ollama_models(clients: ReviewClients) -> None:
    """Preload Ollama models across available nodes if provider is ollama."""
    config = getattr(clients.analysis, "_config", None)
    if getattr(config, "provider", None) != "ollama" or is_dry_run():
        return
    model_name = getattr(config, "model", "ollama")
    ollama_urls = _resolve_ollama_urls(config)
    if ollama_urls:
        n_nodes = len(ollama_urls)
        print_info(
            f"[dim]Warming up model '{model_name}' in background across {n_nodes} Ollama node(s)...[/dim]",
            prefix=False,
        )
        clients.analysis.preload_models(blocking=False)


def _load_shared_metadata_for_pages(pages: list[str]) -> dict[str, FileAnalysisMeta]:
    """Load AST / AI analysis metadata for all files referenced in pages."""
    try:
        from devops_cli.core.repo import find_repo_root

        repo_target = find_repo_root(Path.cwd())
    except Exception:
        repo_target = None
    all_files = sorted(list({fn for page in pages for fn in _extract_header_filenames(page)}))
    return _load_file_analysis_metas(all_files, repo_root=repo_target)


def _calculate_parallel_review_workers(
    clients: ReviewClients, num_tasks: int, concurrency: int | None = None
) -> int:
    """Calculate worker pool capacity for parallel review execution."""
    from devops_cli.config.defaults import (
        DEFAULT_REVIEW_CONCURRENCY,
        DEFAULT_REVIEW_MAX_CONCURRENCY,
    )

    if concurrency is not None:
        return min(num_tasks, max(1, concurrency))
    config = getattr(clients.analysis, "_config", None)
    ollama_urls = _resolve_ollama_urls(config)
    raw_par = getattr(config, "ollama_max_parallel", None)
    max_par = int(raw_par) if isinstance(raw_par, int) else 2
    capacity = max(DEFAULT_REVIEW_CONCURRENCY, len(ollama_urls) * max_par)
    return min(num_tasks, capacity, DEFAULT_REVIEW_MAX_CONCURRENCY)


def _run_persona_loop(
    pages: list[str],
    title: str,
    build_prompt: Callable[[str, str], str],
    clients: ReviewClients,
    agents_md: str,
    all_personas: bool,
    persona: Persona | None,
) -> list[tuple[PersonaDefinition, ReviewResult | str]]:
    """Run full persona review loop using analysis metadata exclusively."""
    personas = _personas_to_run(all_personas, persona)
    session_dir = _review_session_dir(title) if not is_dry_run() else None
    if session_dir:
        _save_segments(pages, session_dir)

    _maybe_preload_ollama_models(clients)

    analysis_info = getattr(clients.analysis, "backend_info", "")
    analysis_suffix = f" [{analysis_info}]" if analysis_info else ""
    n_files = len(pages)
    print_info(
        f"[dim]Step 1/4: Loading analysis metadata for {n_files} file(s)...{analysis_suffix}[/dim]",
        prefix=False,
    )

    shared_meta = _load_shared_metadata_for_pages(pages)
    if session_dir and shared_meta:
        _write_summary(title, session_dir, pages, [], shared_meta)

    completed: list[tuple[PersonaDefinition, ReviewResult | str]] = []
    try:

        def _execute_persona(pd: PersonaDefinition) -> tuple[PersonaDefinition, ReviewResult | str]:
            print_info(f"Reviewing as [bold magenta]{pd.title}[/bold magenta]...", prefix=False)
            review_text = _run_review(
                pages,
                title,
                pd,
                clients,
                agents_md,
                build_prompt,
                prebuilt_metadata=shared_meta,
                session_dir=session_dir,
            )
            return (pd, review_text)

        def _record_result(pd: PersonaDefinition, review_text: ReviewResult | str) -> None:
            _print_review(pd, review_text)
            completed.append((pd, review_text))
            if session_dir:
                _save_persona_review(pd, review_text, session_dir)
                _write_summary(title, session_dir, pages, completed, shared_meta)

        if len(personas) > 1 and not is_dry_run():
            from devops_cli.ai.review.pool import ReviewWorkerPool

            workers = _calculate_parallel_review_workers(clients, len(personas))
            pool = ReviewWorkerPool.create(concurrency=workers)
            persona_results = pool.run_sync_all(_execute_persona, personas, return_exceptions=True)
            for item in persona_results:
                if isinstance(item, tuple) and len(item) == 2:
                    pd, review_text = item
                    _record_result(pd, review_text)
                elif isinstance(item, Exception):
                    logger.error("Persona review execution error (%s)", type(item).__name__)
        else:
            for pd in personas:
                pd, review_text = _execute_persona(pd)
                _record_result(pd, review_text)
    except AIClientError as exc:
        print_error(f"AI provider error: {exc}")
        raise
    except KeyboardInterrupt:
        print_error("Review cancelled by user.", prefix=False)
    finally:
        if session_dir and completed:
            _write_summary(title, session_dir, pages, completed, shared_meta)

    return completed


def _print_review(persona: PersonaDefinition, review: ReviewResult | str) -> None:
    print_section(f"{persona.title}", style="bold magenta")
    if isinstance(review, ReviewResult):
        render_review_result(persona, review)
        return
    if not review.strip():
        print_warning("No review content returned by the model.", prefix=False)
        return
    parsed = parse_review_response(review)
    if parsed:
        render_review_result(persona, parsed)
        return

    print_markdown(review)


def _nearest_conventions(start: Path) -> str:
    """Return the nearest project conventions file, from the start directory up to its repo root."""
    from devops_cli.ai.review.review_environment import nearest_conventions

    return nearest_conventions(start)


def _load_agents_md(start: Path) -> str:
    """Return the sanitized nearest project conventions for a review target."""
    raw_content = _nearest_conventions(start)
    if not raw_content:
        return ""

    from devops_cli.security.sanitizer import (
        redact_text,
        sanitize_prompt_boundary_tags,
    )

    return sanitize_prompt_boundary_tags(redact_text(raw_content))


def _git_repo_root(path: Path) -> Path | None:
    root = find_repo_root(path)
    return root if (root / ".git").exists() else None


def _list_git_tracked_candidates(
    root: Path, repo_root: Path | None
) -> tuple[list[Path], bool, bool]:
    """Retrieve git-tracked candidate file paths when inside a repository."""
    if repo_root is None:
        return [p for p in sorted(root.rglob("*")) if p.is_file()], False, False

    try:
        rel_to_repo = root.relative_to(repo_root)
        rel_str = str(rel_to_repo) if str(rel_to_repo) != "." else "."
    except ValueError:
        rel_str = "."

    root_ignored = (
        is_ignored_by_git(repo_root, root) if root.resolve() != repo_root.resolve() else False
    )
    if not root_ignored:
        result = _run_subprocess(
            [
                "git",
                "-C",
                str(repo_root),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
                "--",
                rel_str,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout:
            candidates = [repo_root / Path(item) for item in result.stdout.split("\0") if item]
            return candidates, True, root_ignored

    fallback_candidates = [p for p in sorted(root.rglob("*")) if p.is_file()]
    return fallback_candidates, False, root_ignored


def _is_candidate_file_included(
    candidate_path: Path,
    root: Path,
    repo_root: Path | None,
    is_from_git: bool,
    root_ignored: bool,
    pattern: str,
) -> bool:
    """Predicate determining if candidate file should be included in review scope."""
    if not candidate_path.is_file():
        return False
    if candidate_path.name in CONST_REVIEW_GENERATED_FILES:
        return False
    effective_root = repo_root or find_repo_root(candidate_path)
    if not is_from_git and not root_ignored and is_ignored_by_git(effective_root, candidate_path):
        return False

    try:
        rel = candidate_path.relative_to(root)
    except ValueError:
        rel = candidate_path
    return rel.match(pattern)


def _review_candidate_files(root: Path, pattern: str) -> list[Path]:
    """The files under root that a path review reads, in review order."""
    repo_root = _git_repo_root(root)
    candidates, is_from_git, root_ignored = _list_git_tracked_candidates(root, repo_root)
    return [
        p
        for p in sorted(candidates)
        if _is_candidate_file_included(p, root, repo_root, is_from_git, root_ignored, pattern)
    ]


def _collect_file_blocks(root: Path, pattern: str) -> list[str]:
    blocks: list[str] = []
    repo_root = _git_repo_root(root)

    for p in _review_candidate_files(root, pattern):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        try:
            rel = p.relative_to(root)
        except ValueError:
            rel = p
        file_label = (
            p.relative_to(repo_root)
            if repo_root is not None and p.is_relative_to(repo_root)
            else rel
        )
        suffix = rel.suffix.lstrip(".") or "text"
        blocks.extend(_split_source_file_blocks(file_label, suffix, text, _MAX_DIFF_CHARS))
    return blocks


def _corpus_digest(targets: list[Path], pattern: str) -> str:
    """Fingerprint the files a path review reads, so benchmarks of the same corpus can be matched."""
    digest = hashlib.sha256()
    for target in targets:
        resolved = target.resolve()
        if resolved.is_file():
            digest.update(resolved.read_bytes())
            continue
        for block in _collect_file_blocks(resolved, pattern):
            digest.update(block.encode())
    return digest.hexdigest()[:16]


def _collect_files(root: Path, pattern: str) -> str:
    """Join collected file blocks into a single string."""
    return "\n\n".join(_collect_file_blocks(root, pattern))


def _build_path_prompt(content: str, title: str) -> str:
    clean_content = sanitize_prompt_boundary_tags(content)
    return _PATH_REVIEW_PROMPT_TEMPLATE.format(title=title, clean_content=clean_content)


def _print_analysis_metadata(analysis_metas: dict[str, FileAnalysisMeta], title: str) -> None:
    """Render a summary table of file analysis metadata."""
    print_section(f"Analysis Metadata — {title}", style="bold cyan")
    if not analysis_metas:
        print_warning("No analysis metadata found for files in scope.", prefix=False)
        return
    columns = [
        ("File Path", "cyan"),
        ("Language", "green"),
        ("Purpose", "white"),
        ("Complexity", "magenta"),
    ]
    rows = [
        [
            path,
            fmeta.language or "text",
            fmeta.primary_purpose or "—",
            fmeta.complexity_score or "—",
        ]
        for path, fmeta in analysis_metas.items()
    ]
    print_table(columns=columns, rows=rows)


def _make_review_clients(
    settings: Any,
    *,
    cache_enabled: bool | None = None,
    append_cache: bool | None = None,
) -> ReviewClients:
    """Build LLM clients for the analysis, compose and verification review tasks.

    Verification overrides apply on top of the analysis task, so `ai.tasks.verification` need only
    name what differs, such as a stronger model on the same gateway.
    """
    api_key = get_ai_api_key(settings)
    analysis_config = settings.ai.for_task("analysis")
    analysis = LLMClient(
        analysis_config,
        api_key=api_key,
        request_timeout_seconds=DEFAULT_REVIEW_TIMEOUT_SECONDS,
        cache_enabled=cache_enabled,
        append_cache=append_cache,
    )
    verification = (
        LLMClient(
            analysis_config.for_task("verification"),
            api_key=api_key,
            request_timeout_seconds=DEFAULT_REVIEW_TIMEOUT_SECONDS,
            cache_enabled=cache_enabled,
            append_cache=append_cache,
        )
        if settings.ai.tasks.verification.model_dump(exclude_none=True)
        else analysis
    )
    return ReviewClients(
        analysis=analysis,
        verification=verification,
        compose=LLMClient(
            settings.ai.for_task("compose"),
            api_key=api_key,
            request_timeout_seconds=DEFAULT_REVIEW_TIMEOUT_SECONDS,
            cache_enabled=cache_enabled,
            append_cache=append_cache,
        ),
    )


def _is_allowed_review_boundary(target: Path, settings: Settings) -> bool:
    target_resolved = target.resolve()
    allowed_roots: list[Path] = [Path.cwd().resolve()]
    if (cwd_repo := _git_repo_root(Path.cwd())) is not None:
        allowed_roots.append(cwd_repo.resolve())
    if (target_repo := _git_repo_root(target_resolved)) is not None:
        allowed_roots.append(target_repo.resolve())

    repos_base = settings.repos.base_dir.resolve()
    allowed_roots.append(repos_base)

    return any(is_safe_subpath(root, target_resolved) for root in allowed_roots)


def _detect_remote_default_branch(repo_path: Path) -> str:
    """Detect origin default branch from symbolic-ref or HEAD."""
    res_sym = _run_subprocess(
        ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        capture_output=True,
        text=True,
        cwd=repo_path,
        check=False,
    )
    if res_sym.returncode == 0 and res_sym.stdout:
        if target_str := res_sym.stdout.strip().removeprefix("origin/"):
            return target_str

    head_proc = _run_subprocess(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        cwd=repo_path,
        check=False,
    )
    if (
        head_proc.returncode == 0
        and (head_name := str(head_proc.stdout).strip())
        and head_name != "HEAD"
    ):
        return head_name

    return ""


def _detect_base_branch(repo_path: Path, preferred_base: str = CONST_GIT_MAIN_BRANCH) -> str:
    """Return preferred_base if it exists, otherwise detect master/main/origin default."""
    res = _run_subprocess(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{preferred_base}"],
        capture_output=True,
        text=True,
        cwd=repo_path,
        check=False,
    )
    if res.returncode == 0:
        return preferred_base

    branches_proc = _run_subprocess(
        ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads/"],
        capture_output=True,
        text=True,
        cwd=repo_path,
        check=False,
    )
    local_branches = (
        [b.strip() for b in branches_proc.stdout.splitlines() if b.strip()]
        if branches_proc.returncode == 0
        else []
    )

    if preferred_base in local_branches:
        return preferred_base

    for alt in ("main", "master", "trunk"):
        if alt in local_branches:
            return alt

    if remote_branch := _detect_remote_default_branch(repo_path):
        return remote_branch

    return str(preferred_base)


def _prepare_path_content(target: Path, pattern: str) -> tuple[list[str], str, str]:
    """Prepare paginated pages, title, and agents_md for path review target."""
    import typer

    from devops_cli.config.constants import CONST_MAX_FILE_SIZE_BYTES
    from devops_cli.lang import MESSAGES

    settings = load_settings()
    target_resolved = target.resolve()
    if not _is_allowed_review_boundary(target, settings):
        err_msg = MESSAGES.review.outside_boundary.format(target=target_resolved)
        print_error(err_msg, prefix=False)
        raise typer.Exit(1)
    if target_resolved.is_file():
        if target_resolved.stat().st_size > CONST_MAX_FILE_SIZE_BYTES:
            max_mb = CONST_MAX_FILE_SIZE_BYTES // (1024 * 1024)
            err_size = MESSAGES.review.exceeds_max_size.format(
                target=target_resolved, max_mb=max_mb
            )
            print_error(err_size, prefix=False)
            raise typer.Exit(0)
        repo_root = _git_repo_root(target_resolved)
        file_label = (
            str(target_resolved.relative_to(repo_root))
            if repo_root and target_resolved.is_relative_to(repo_root)
            else target_resolved.name
        )
        suffix = target_resolved.suffix.lstrip(".") or "text"
        content = target_resolved.read_text(encoding="utf-8", errors="replace")
        blocks = _split_source_file_blocks(Path(file_label), suffix, content, _MAX_DIFF_CHARS)
        title = str(file_label)
    else:
        collecting_msg = MESSAGES.review.collecting_files.format(
            pattern=f"[cyan]{pattern}[/cyan]", target=f"[dim]{target_resolved}[/dim]"
        )
        print_info(collecting_msg, prefix=False)
        blocks = _collect_file_blocks(target_resolved, pattern)
        title = str(target_resolved)

    if not blocks:
        print_warning(MESSAGES.review.no_files_found, prefix=False)
        raise typer.Exit(0)

    pages = [redact_text(p) for p in blocks]
    agents_md = _load_agents_md(
        target_resolved if target_resolved.is_dir() else target_resolved.parent
    )
    return pages, title, agents_md


def _get_current_git_branch(repo_path: Path) -> str:
    """Return active git branch name if HEAD is attached, otherwise empty string."""
    proc = _run_subprocess(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        cwd=repo_path,
        check=False,
    )
    if proc.returncode == 0 and (name := proc.stdout.strip()) and name != "HEAD":
        return name
    return ""


def _has_uncommitted_working_tree_changes(repo_path: Path) -> bool:
    """Return True if working tree has staged or unstaged modifications."""
    proc = _run_subprocess(
        ["git", "diff", "HEAD"],
        capture_output=True,
        text=True,
        cwd=repo_path,
        check=False,
    )
    return proc.returncode == 0 and bool(proc.stdout.strip())


def _resolve_main_branch_fallback_base(repo_path: Path, branch_name: str) -> str:
    """Find appropriate comparison base when reviewing main/primary branch."""
    from devops_cli.git.operations import get_latest_git_tag

    tag = get_latest_git_tag(repo_path)
    if tag:
        tag_diff = _run_subprocess(
            ["git", "diff", f"{tag}...{branch_name}"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            check=False,
        )
        if tag_diff.returncode == 0 and tag_diff.stdout.strip():
            return tag

    parent_proc = _run_subprocess(
        ["git", "rev-parse", "--verify", "--quiet", f"{branch_name}~1"],
        capture_output=True,
        text=True,
        cwd=repo_path,
        check=False,
    )
    if parent_proc.returncode == 0:
        return f"{branch_name}~1"

    return "HEAD"


def _resolve_branch_targets(
    repo_path: Path, branch_name: str | None, base: str
) -> tuple[str, str, bool]:
    """Resolve target branch and comparison base, handling main branch review edge cases."""
    current_branch = _get_current_git_branch(repo_path)
    target_branch = branch_name or current_branch
    if not target_branch:
        return "", "", False

    effective_base = _detect_base_branch(repo_path, base)

    # When target branch equals effective base (e.g. both are 'main')
    if target_branch == effective_base:
        if current_branch and current_branch != target_branch:
            # User passed base branch while on another branch (e.g. 'devops review branch main' from release/v0.2.20)
            return current_branch, effective_base, False

        # User is reviewing main branch directly
        if _has_uncommitted_working_tree_changes(repo_path):
            return target_branch, "HEAD", True

        fallback_base = _resolve_main_branch_fallback_base(repo_path, target_branch)
        return target_branch, fallback_base, False

    return target_branch, effective_base, False


def _prepare_branch_content(
    branch_name: str | None, base: str, repo_path: Path
) -> tuple[list[str], str, str, str]:
    """Prepare paginated diff pages, title, agents_md, and resolved target_branch."""
    import typer

    from devops_cli.ai.review.chunker import diff_pages
    from devops_cli.lang import MESSAGES

    settings = load_settings()
    repo_resolved = repo_path.resolve()
    if not _is_allowed_review_boundary(repo_resolved, settings):
        err_msg = MESSAGES.review.outside_boundary.format(target=repo_resolved)
        print_error(err_msg, prefix=False)
        raise typer.Exit(1)

    target_branch, effective_base, is_working_tree = _resolve_branch_targets(
        repo_path, branch_name, base
    )
    if not target_branch:
        print_error(MESSAGES.review.detect_branch_failed, prefix=False)
        raise typer.Exit(1)

    diffing_msg = MESSAGES.review.diffing_branches.format(
        branch=f"[cyan]{target_branch}[/cyan]", base=f"[cyan]{effective_base}[/cyan]"
    )
    print_info(diffing_msg, prefix=False)

    if is_working_tree:
        diff_proc = _run_subprocess(
            ["git", "diff", "HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_path,
        )
    else:
        diff_proc = _run_subprocess(
            ["git", "diff", f"{effective_base}...{target_branch}"],
            capture_output=True,
            text=True,
            cwd=repo_path,
        )
        if diff_proc.returncode != 0:
            diff_proc = _run_subprocess(
                ["git", "diff", effective_base, target_branch],
                capture_output=True,
                text=True,
                cwd=repo_path,
            )
    if diff_proc.returncode != 0:
        diff_err = MESSAGES.review.git_diff_failed.format(error=diff_proc.stderr.strip())
        print_error(diff_err, prefix=False)
        raise typer.Exit(1)
    if not diff_proc.stdout.strip():
        print_warning(MESSAGES.review.no_diff_found, prefix=False)
        raise typer.Exit(0)

    title = f"Branch `{target_branch}` vs `{effective_base}`"
    agents_md = _load_agents_md(repo_path)
    pages = [redact_text(p) for p in diff_pages(diff_proc.stdout, _MAX_DIFF_CHARS)]
    return pages, title, agents_md, target_branch


def _prepare_pr_content(
    number: int,
    repo_arg: str | None = None,
    auth: str | None = None,
    **kwargs: Any,
) -> tuple[list[str], str, str, Any, str]:
    """Fetch PR details, diff pages, title, and agents_md for PR review target."""
    import typer

    from devops_cli.ai.review.chunker import diff_pages
    from devops_cli.github.client import GitHubClient
    from devops_cli.lang import MESSAGES

    repo = repo_arg
    if repo is None:
        from devops_cli.core.repo import get_repo_origin_name

        repo = get_repo_origin_name()
        if not repo:
            parse_err = MESSAGES.review.github_repo_parse_failed.format(raw="")
            print_error(parse_err, prefix=False)
            raise typer.Exit(1)

    fetch_msg = MESSAGES.review.fetching_pr.format(number=number, repo=f"[cyan]{repo}[/cyan]")
    print_info(fetch_msg, prefix=False)
    effective_auth = auth or kwargs.get("token") or ""
    gh = GitHubClient(effective_auth)
    pull = gh.get_pull(repo, number)
    diff = gh.get_pr_diff(repo, number)
    title = f"PR #{number}: {pull.title}"
    head_dir: Path | None = kwargs.get("head_dir")
    if head_dir is not None:
        _materialize_pr_head(gh, repo, pull, head_dir)
    agents_md = _load_agents_md(head_dir or Path.cwd())
    pages = [redact_text(p) for p in diff_pages(diff, _MAX_DIFF_CHARS)]
    return pages, title, agents_md, pull, repo


def _materialize_pr_head(gh: Any, repo: str, pull: Any, dest: Path) -> int:
    """Write the PR head's version of each changed file, and its conventions, under `dest`.

    A PR review's pages come from the PR's diff, but verification, the scanners and dependency
    extraction read files from the review's target directory. That was the local checkout, which
    holds another version of those files, or none, or another repository's under `--repo`.
    Returns the number of files written.
    """
    from devops_cli.ai.review.review_environment import _TARGET_CONVENTIONS_CANDIDATES
    from devops_cli.config.constants import CONST_REVIEW_CONVENTIONS_FILE

    head_repo = getattr(getattr(pull.head, "repo", None), "full_name", None) or repo
    changed = [f.filename for f in pull.get_files() if getattr(f, "status", "") != "removed"]
    root = dest.resolve()
    written = 0
    for rel in dict.fromkeys(
        [*changed, *_TARGET_CONVENTIONS_CANDIDATES, CONST_REVIEW_CONVENTIONS_FILE]
    ):
        target = (root / rel).resolve()
        if not target.is_relative_to(root):
            continue
        text = gh.get_file_at(head_repo, rel, pull.head.sha)
        if text is None:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        written += 1
    return written


def _record_profile_findings(payloads: list[Any], candidates: int) -> None:
    """Record candidate, verified and reported finding counts on the active review profile."""
    profiler = active_profiler()
    if profiler is None:
        return
    findings = [f for p in payloads for f in p.findings]
    profiler.set_findings(
        candidates=candidates,
        verified=sum(1 for f in findings if f.verified),
        reported=sum(1 for f in findings if f.reportable),
        verdict_distributions=compute_verdict_distributions(findings),
    )
    if not profiler._persona_replies:
        for p in payloads:
            for r in getattr(p, "ai_scratchpad", {}).get("persona_replies", []):
                profiler.record_persona_reply(
                    file=getattr(p, "file_path", ""),
                    persona=r.get("persona", "unknown"),
                    outcome=r.get("outcome", "unparsed"),
                    persona_title=r.get("persona_title", ""),
                    page=r.get("page", 1),
                )


def _write_review_profile(
    profiler: ReviewProfiler, orchestrator: Any, target: str, files: int
) -> ReviewProfile:
    """Write the session's profile.json and summarise where the time went."""
    profile = profiler.build(session_id=orchestrator.session_id, target=target, files=files)
    path = profile.write(orchestrator.session_dir)
    report_profile(profile)
    stages = ", ".join(
        f"{s.name} {format_duration(s.wall_seconds)} ({s.llm_calls} calls)"
        for s in profile.stages
        if s.wall_seconds >= 1 or s.llm_calls
    )
    print_info(
        f"[dim]Profile: {format_duration(profile.total_wall_seconds)}, "
        f"{profile.llm_calls} LLM calls; {stages} -> {path}[/dim]",
        prefix=False,
    )
    return profile


def _record_review_metrics(
    results: list[tuple[PersonaDefinition, ReviewResult | str]],
    seconds: float,
    target_type: str,
) -> None:
    """Send the review's wall time, and its findings by persona, severity and status."""
    from devops_cli.telemetry.instruments import FINDINGS_TOTAL, REVIEW_DURATION, emit

    emit(REVIEW_DURATION, seconds, {"target_type": target_type})
    counts = Counter(
        (persona.name, finding.severity.upper(), finding.status.upper())
        for persona, result in results
        if isinstance(result, ReviewResult)
        for finding in result.findings
    )
    for (persona, severity, status), count in counts.items():
        emit(FINDINGS_TOTAL, count, {"persona": persona, "severity": severity, "status": status})


def _run_profiled_session(
    orchestrator: Any,
    all_files: list[str],
    target_dir: Path,
    pages: list[str],
    active_p: list[str],
    persona: Persona | None,
    target_type: Literal["branch", "pr", "path"],
    target_ref: str,
    stage_flags: ReviewStageFlags | None,
) -> list[tuple[PersonaDefinition, ReviewResult | str]] | None:
    """Run the orchestrated review under a profiler; None when there are no files to review."""
    with profiling() as profiler:
        with review_stage("pre_analysis"):
            metadata_by_path = orchestrator.run_pre_analysis_refresh(
                target_dir=target_dir,
                target_type=target_type,
                target_ref=target_ref,
                stage_flags=stage_flags,
            )
        if not all_files:
            return None
        results = _run_orchestrator_review(
            orchestrator,
            all_files,
            metadata_by_path,
            target_dir,
            pages,
            active_p,
            persona,
            stage_flags=stage_flags,
        )
        if not is_dry_run():
            profile = _write_review_profile(profiler, orchestrator, target_ref, len(all_files))
            _record_review_metrics(results, profile.total_wall_seconds, target_type)
        return results


def _run_orchestrator_review(
    orchestrator: Any,
    all_files: list[str],
    metadata_by_path: dict[str, FileAnalysisMeta],
    target_dir: Path | None,
    pages: list[str],
    active_p: list[str],
    persona: Persona | None,
    stage_flags: ReviewStageFlags | None = None,
) -> list[tuple[PersonaDefinition, ReviewResult | str]]:
    """Execute orchestrator pipeline review for all files."""
    with review_stage("payloads"):
        payloads = orchestrator.init_per_file_payloads(
            all_files, metadata_by_path, target_dir=target_dir, stage_flags=stage_flags
        )
    if not is_dry_run():
        # Each file gets the pages whose headers name it; a substring match gave `a.py` the
        # pages of `data.py` as well.
        diff_map = {
            f: "\n".join(p for p in pages if f in _extract_header_filenames(p)) for f in all_files
        }
        with review_stage("persona_review"):
            orchestrator.execute_multi_persona_review(
                payloads, diff_text_by_file=diff_map, personas=active_p, stage_flags=stage_flags
            )
        candidates = sum(len(p.findings) for p in payloads)
        with review_stage("verification"):
            orchestrator.execute_finding_verification(payloads, stage_flags=stage_flags)
        with review_stage("reranking"):
            orchestrator.execute_finding_reranking(payloads, stage_flags=stage_flags)
        _record_profile_findings(payloads, candidates)

    with review_stage("report"):
        _, report_md = orchestrator.generate_consolidated_report(payloads, stage_flags=stage_flags)
    p_def = PERSONAS[persona or Persona.DEVSECOPS]
    return [(p_def, report_md)]


def _execute_review_workflow(
    pages: list[str],
    title: str,
    prompt_builder: Callable[..., str],
    agents_md: str,
    all_personas: bool,
    persona: Persona | None,
    summary_only: bool,
    clients: ReviewClients,
    target_type: Literal["branch", "pr", "path"] = "path",
    target_ref: str = ".",
    target_dir: Path = DEFAULT_CURRENT_PATH,
    stage_flags: ReviewStageFlags | None = None,
    concurrency: int | None = None,
    parallel: bool = True,
    ground_contracts: bool = True,
) -> list[tuple[PersonaDefinition, ReviewResult | str]]:
    """Common review execution workflow for path, branch, and PR reviews."""
    from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
    from devops_cli.lang import MESSAGES

    if len(pages) > 1:
        spans_msg = MESSAGES.review.spans_pages.format(count=len(pages))
        print_info(f"[dim]{spans_msg}[/dim]", prefix=False)

    all_files = sorted(list({fn for page in pages for fn in _extract_header_filenames(page)}))
    orchestrator = ReviewPipelineOrchestrator(
        llm_client=clients.analysis,
        verification_client=clients.verification,
        target_dir=target_dir,
        concurrency=concurrency,
        parallel=parallel,
        ground_contracts=ground_contracts,
    )

    if type(clients.analysis).__name__ == "LLMClient":
        server_info = orchestrator._get_server_info()
        n_af = len(all_files)
        all_p = ["devsecops", "architect", "qa", "auditor", "pm"]
        active_p = [persona.value] if persona else (all_p if all_personas else ["devsecops"])
        with trace_span(
            "review.session",
            attributes={
                "session_id": orchestrator.session_id,
                "target_type": target_type,
                "target_ref": target_ref,
                "file_count": n_af,
                "personas": ", ".join(active_p),
            },
        ):
            print_info(
                f"[bold cyan]Initializing review pipeline session '{orchestrator.session_id}' "
                f"for {n_af} file(s) via {server_info}...[/bold cyan]",
                prefix=False,
            )
            results = _run_profiled_session(
                orchestrator,
                all_files,
                target_dir,
                pages,
                active_p,
                persona,
                target_type,
                target_ref,
                stage_flags,
            )
            if results is not None:
                return results

    if summary_only:
        print_info(f"[dim]{MESSAGES.review.generating_metadata}[/dim]", prefix=False)
        try:
            from devops_cli.core.repo import find_repo_root

            repo_target = find_repo_root(Path.cwd())
        except Exception:
            repo_target = None
        analysis_metas = _load_file_analysis_metas(all_files, repo_root=repo_target)
        _print_analysis_metadata(analysis_metas, title)
        return []

    return _run_persona_loop(
        pages, title, prompt_builder, clients, agents_md, all_personas, persona
    )
