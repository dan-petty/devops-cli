"""Multi-persona review execution runner, model warming, and session management."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from concurrent.futures import as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from devops_cli.ai.analyze.cache import _load_file_analysis_metas
from devops_cli.ai.client import AIClientError, LLMClient
from devops_cli.ai.personas import PERSONAS, Persona, PersonaDefinition
from devops_cli.ai.review.chunker import (
    _extract_segment_filenames,
    _split_source_file_blocks,
)
from devops_cli.ai.review.rendering import _render_review_result
from devops_cli.ai.review.sanitization import (
    _mask_secrets_in_content,
    _sanitize_prompt_boundary_tags,
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
    consolidate_duplicate_findings,
    parse_review_response,
)
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import (
    CONST_AGENTS_MD_FILENAME,
    CONST_GIT_MAIN_BRANCH,
    CONST_GITIGNORE_DIRS,
    CONST_REVIEW_GENERATED_FILES,
    CONST_REVIEW_MAX_DIFF_CHARS,
)
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_DATA_DIR,
    DEFAULT_REVIEW_TIMEOUT_SECONDS,
)
from devops_cli.config.settings import Settings, get_ai_api_key, load_settings
from devops_cli.core.process import run_subprocess as _run_subprocess
from devops_cli.core.repo import find_repo_root, is_ignored_by_git, is_safe_subpath
from devops_cli.dry_run import is_dry_run
from devops_cli.models.ai import FileAnalysisMeta
from devops_cli.output import (
    print_error,
    print_info,
    print_markdown,
    print_muted,
    print_section,
    print_table,
    print_warning,
)
from devops_cli.telemetry import ContextPropagatingThreadPoolExecutor as ThreadPoolExecutor
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)

_MAX_DIFF_CHARS = CONST_REVIEW_MAX_DIFF_CHARS
_MAX_SEGMENT_RETRIES = 2
_DEFAULT_CONTEXT_LINES = 2

_PAGINATED_REVIEW_PROTOCOL = load_task_prompt("paginated_review_protocol.md")
_REVIEW_OUTPUT_INSTRUCTION = "\n" + load_task_prompt("review_output_instruction.md")
_GUARDRAILS_PROMPT = "\n\n" + load_task_prompt("guardrails_isolation.md")
_PATH_REVIEW_PROMPT_TEMPLATE = load_task_prompt("path_review_prompt.md")


class ReviewClients(BaseModel):
    """LLM clients resolved per review task, each potentially using a different model."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    analysis: Any
    compose: Any


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


def _persona_system_prompt(persona: PersonaDefinition, agents_md: str) -> str:
    """Compose the per-file/segment system prompt for this persona."""
    if not agents_md:
        return persona.system_prompt + _GUARDRAILS_PROMPT

    clean_agents = _sanitize_prompt_boundary_tags(agents_md)
    return (
        f"{persona.system_prompt}\n\n"
        "## Target Project Conventions & Reference Instructions (AGENTS.md)\n"
        "<project_conventions_context>\n"
        f"{clean_agents}\n"
        "</project_conventions_context>\n\n"
        "Adhere to target project conventions. Do not raise findings that merely "
        "restate or contradict the conventions explicitly documented above."
        f"{_GUARDRAILS_PROMPT}"
    )


def _persona_format_section(persona: PersonaDefinition) -> str:
    """Extract the output-format specification from the persona's system prompt."""
    marker = "Respond in this exact format:"
    if marker not in persona.system_prompt:
        return ""
    return marker + persona.system_prompt.split(marker, 1)[1].rstrip()


def _build_segment_review_prompt(
    segment: str,
    title: str,
    index: int,
    total: int,
    analysis_metas: dict[str, FileAnalysisMeta],
    build_base: Callable[[str, str], str],
    persona: PersonaDefinition,
) -> str:
    fns = _extract_segment_filenames(segment)
    relevant_metas = {
        path: fmeta.model_dump(exclude_none=True)
        for path, fmeta in analysis_metas.items()
        if not fns or path in fns or any(f in path for f in fns)
    }
    if not relevant_metas and fns:
        relevant_metas = {
            fn: {"path": fn, "primary_purpose": f"Source file review for {fn}"} for fn in fns
        }
    elif not relevant_metas:
        relevant_metas = {
            path: fmeta.model_dump(exclude_none=True)
            for path, fmeta in list(analysis_metas.items())[:15]
        }

    all_files_list = list(analysis_metas.keys()) if analysis_metas else fns
    context_meta = {
        "title": title,
        "total_files": total,
        "current_file_index": index,
        "all_files": all_files_list,
        "file_metadata": relevant_metas,
    }
    meta_json = _sanitize_prompt_boundary_tags(
        json.dumps(context_meta, indent=2, ensure_ascii=True)
    )
    part_title = title if total == 1 else f"{title} — file {index}/{total}"
    format_section = _persona_format_section(persona)

    # RAG investigation step for cross-file architecture and security guidelines
    rag_section = ""
    try:
        from devops_cli.ai.rag.investigator import (
            format_rag_investigation_for_prompt,
            investigate_rag_context,
        )

        symbols: list[str] = []
        for m in relevant_metas.values():
            if isinstance(m, dict) and "key_symbols" in m and isinstance(m["key_symbols"], list):
                symbols.extend([str(s) for s in m["key_symbols"][:3]])

        rag_query = f"{' '.join(fns)} {' '.join(symbols)}".strip() or title
        rag_ctx = investigate_rag_context(rag_query, persona=persona.name, top_k=3)
        rag_section = format_rag_investigation_for_prompt(
            rag_ctx, "Cross-File Architecture & Semantic Context"
        )
    except Exception:
        pass

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
    meta_json = _sanitize_prompt_boundary_tags(
        json.dumps(context_meta, indent=2, ensure_ascii=True)
    )
    parsed_findings = [f for r in segment_results if r for f in r.sorted_findings]
    if parsed_findings:
        findings_json = _sanitize_prompt_boundary_tags(
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
        clean_parts = _sanitize_prompt_boundary_tags(parts)
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


def _get_reviews_base_dir() -> Path:
    from devops_cli.core.repo import find_top_level_repo_root

    settings = load_settings()
    d = (
        settings.data.reviews_dir
        if settings.data.dir == DEFAULT_DATA_DIR
        else settings.data.dir / "reviews"
    )
    if not d.is_absolute():
        d = (find_top_level_repo_root() / d).resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


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
        (session_dir / f"segment-{i}.md").write_text(page, encoding="utf-8")


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
        if show_status:
            print_muted(f"  ✓ findings saved → {target}")
        return True
    except OSError as exc:
        print_warning(f"Warning: failed to write findings.json: {exc}")
        return False


def _review_to_markdown(review: ReviewResult | str) -> str:
    if isinstance(review, str):
        parsed = parse_review_response(review)
        return _review_to_markdown(parsed) if parsed else review
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
    (session_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")
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
            f"  ✗ {file_label} error in {seg_elapsed:.1f}s"
            f"{fail_backend} (attempt {attempt}), retrying...",
            prefix=False,
        )
    else:
        print_warning(
            f"  ✗ {file_label} failed in {seg_elapsed:.1f}s after "
            f"{_MAX_SEGMENT_RETRIES + 1} attempt(s); skipping.{fail_backend}",
            prefix=False,
        )


def _log_segment_empty(
    file_label: str, seg_elapsed: float, req_backend_str: str, attempt: int
) -> None:
    """Log empty segment response or retry message."""
    if attempt <= _MAX_SEGMENT_RETRIES:
        print_warning(
            f"  ✗ {file_label} empty in {seg_elapsed:.1f}s"
            f"{req_backend_str} (attempt {attempt}), retrying...",
            prefix=False,
        )
    else:
        print_warning(
            f"Warning: {file_label} still empty in {seg_elapsed:.1f}s "
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

    try:
        from devops_cli.core.repo import find_repo_root

        repo_target = find_repo_root(Path.cwd())
    except Exception:
        repo_target = None

    if prebuilt_metadata is not None:
        count = len(prebuilt_metadata)
        print_info(
            f"[dim]Step 1/4: Reusing pre-computed analysis metadata for {count} file(s).[/dim]",
            prefix=False,
        )
        metadata = prebuilt_metadata
    else:
        all_files = sorted(list({fn for page in pages for fn in _extract_segment_filenames(page)}))
        print_info(
            f"[dim]Step 1/4: Loading analysis metadata for {total} file(s)..."
            f"{analysis_suffix}[/dim]",
            prefix=False,
        )
        metadata = _load_file_analysis_metas(all_files, repo_root=repo_target)

    print_info(f"[dim]Step 2/4: Reviewing {total} file(s)...{analysis_suffix}[/dim]", prefix=False)
    t2 = time.monotonic()
    responses: list[str] = []

    def _review_segment(i: int, page: str) -> tuple[int, str]:
        fns = _extract_segment_filenames(page)
        if fns:
            fn_str = ", ".join(fns)
            file_label = f"{fn_str} ({i}/{total})" if total > 1 else fn_str
        else:
            file_label = f"segment {i}/{total}"

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

        result_text = ""
        res_backend: str | None = None
        for attempt in range(1, _MAX_SEGMENT_RETRIES + 2):
            seg_start = time.monotonic()
            proc_sec: float | None = None
            try:
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
                    f"[dim]  ✓ {file_label} in {seg_elapsed:.1f}s"
                    f"{req_backend_str}{retry_note}[/dim]",
                    prefix=False,
                )
            break
        return (i, result_text)

    if total > 1 and not is_dry_run():
        config = getattr(clients.analysis, "_config", None)
        ollama_urls = _resolve_ollama_urls(config)
        raw_par = getattr(config, "ollama_max_parallel", None)
        max_par = int(raw_par) if isinstance(raw_par, int) else 2
        workers = min(total, max(len(ollama_urls) * max_par, 1))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(_review_segment, i, page) for i, page in enumerate(pages, 1)]
            indexed_results = [f.result() for f in futures]
            responses = [res for _, res in sorted(indexed_results, key=lambda x: x[0])]
    else:
        for i, page in enumerate(pages, 1):
            _, res = _review_segment(i, page)
            responses.append(res)
    if not is_dry_run():
        print_info(f"[dim]  total {time.monotonic() - t2:.1f}s[/dim]", prefix=False)

    non_empty = [r for r in responses if r.strip()]
    if not non_empty:
        return ""

    segment_results: list[ReviewResult | None] = [parse_review_response(r) for r in responses]
    if not is_dry_run():
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

        def _validate_single_segment(
            arg: tuple[int, str, ReviewResult | None],
        ) -> tuple[int, ReviewResult | None]:
            i, page, parsed = arg
            fns = _extract_segment_filenames(page)
            if fns:
                fn_str = ", ".join(fns)
                file_label = f"{fn_str} ({i}/{total})" if total > 1 else fn_str
            else:
                file_label = f"segment {i}/{total}"

            if parsed is None or not parsed.findings:
                print_info(f"[dim]  ✓ {file_label}: 0 finding(s) to verify[/dim]", prefix=False)
                return (i, parsed)
            val_start = time.monotonic()
            validated, proc_sec, _ = _validate_segment_findings(
                parsed,
                pages,
                clients.analysis,
                analysis_metas=file_analysis_metas,
                repo_root=repo_target,
            )
            val_elapsed = proc_sec if proc_sec is not None else (time.monotonic() - val_start)
            n_verified = sum(1 for f in validated.findings if f.verified)
            v_count = f"{n_verified}/{len(validated.findings)} finding(s) verified"
            print_info(
                f"[dim]  ✓ {file_label} in {val_elapsed:.1f}s: {v_count}{analysis_suffix}[/dim]",
                prefix=False,
            )
            return (i, validated)

        if total > 1:
            config = getattr(clients.analysis, "_config", None)
            ollama_urls = _resolve_ollama_urls(config)
            raw_par = getattr(config, "ollama_max_parallel", None)
            max_par = int(raw_par) if isinstance(raw_par, int) else 2
            workers = min(total, max(len(ollama_urls) * max_par, 1))
            val_items = list(enumerate(zip(pages, segment_results), 1))
            with ThreadPoolExecutor(max_workers=workers) as val_executor:
                val_futures = [
                    val_executor.submit(_validate_single_segment, (i, page, parsed))
                    for i, (page, parsed) in val_items
                ]
                for val_fut in val_futures:
                    idx_val, val_res = val_fut.result()
                    segment_results[idx_val - 1] = val_res
        else:
            for i, (page, parsed) in enumerate(zip(pages, segment_results), 1):
                _, val_res = _validate_single_segment((i, page, parsed))
                segment_results[i - 1] = val_res

        print_info(f"[dim]  total {time.monotonic() - t3:.1f}s[/dim]", prefix=False)

    if total == 1:
        return segment_results[0] if segment_results[0] is not None else responses[0]

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
    try:
        t4 = time.monotonic()
        raw = str(
            clients.compose.chat(
                system=compose_system,
                user=recompose_prompt,
                validator=lambda text: parse_review_response(text) is not None,
            )
        )
        print_info(f"[dim]  ✓ {time.monotonic() - t4:.1f}s{compose_suffix}[/dim]", prefix=False)
        if not raw.strip():
            return _merge_segment_results(segment_results) or _fallback_join(non_empty)
        parsed = parse_review_response(raw)
        if parsed is not None:
            return _reconcile_verified(parsed, segment_results)
        return raw
    except Exception:
        return _merge_segment_results(segment_results) or _fallback_join(non_empty)


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

    config = getattr(clients.analysis, "_config", None)
    if getattr(config, "provider", None) == "ollama" and not is_dry_run():
        model_name = getattr(config, "model", "ollama")
        ollama_urls = _resolve_ollama_urls(config)
        if ollama_urls:
            n = len(ollama_urls)
            print_info(
                f"[dim]Warming up model '{model_name}' in background across "
                f"{n} Ollama node(s)...[/dim]",
                prefix=False,
            )
            clients.analysis.preload_models(blocking=False)

    analysis_info = getattr(clients.analysis, "backend_info", "")
    analysis_suffix = f" [{analysis_info}]" if analysis_info else ""
    n_files = len(pages)
    print_info(
        f"[dim]Step 1/4: Loading analysis metadata for {n_files} file(s)...{analysis_suffix}[/dim]",
        prefix=False,
    )
    try:
        from devops_cli.core.repo import find_repo_root

        repo_target = find_repo_root(Path.cwd())
    except Exception:
        repo_target = None
    all_files = sorted(list({fn for page in pages for fn in _extract_segment_filenames(page)}))
    shared_meta: dict[str, FileAnalysisMeta] = _load_file_analysis_metas(
        all_files, repo_root=repo_target
    )
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
            config = getattr(clients.analysis, "_config", None)
            ollama_urls = _resolve_ollama_urls(config)
            raw_par = getattr(config, "ollama_max_parallel", None)
            max_par = int(raw_par) if isinstance(raw_par, int) else 2
            workers = min(len(personas), max(len(ollama_urls) * max_par, 1))
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_map = {executor.submit(_execute_persona, pd): pd for pd in personas}
                for future in as_completed(future_map):
                    pd, review_text = future.result()
                    _record_result(pd, review_text)
        else:
            for pd in personas:
                pd, review_text = _execute_persona(pd)
                _record_result(pd, review_text)
    except AIClientError as exc:
        print_error(f"AI provider error: {exc}")
        raise
    finally:
        if session_dir and completed:
            _write_summary(title, session_dir, pages, completed, shared_meta)

    return completed


def _print_review(persona: PersonaDefinition, review: ReviewResult | str) -> None:
    print_section(f"{persona.title}", style="bold magenta")
    if isinstance(review, ReviewResult):
        _render_review_result(persona, review)
        return
    if not review.strip():
        print_warning("No review content returned by the model.", prefix=False)
        return
    parsed = parse_review_response(review)
    if parsed:
        _render_review_result(persona, parsed)
        return

    print_markdown(review)


def _resolve_review_clients(settings: Settings | None = None) -> ReviewClients:
    cfg = settings or load_settings()
    api_key = get_ai_api_key(cfg)

    def _make(task: str) -> LLMClient:
        return LLMClient(
            cfg.ai,
            api_key=api_key,
            request_timeout_seconds=float(DEFAULT_REVIEW_TIMEOUT_SECONDS),
        )

    return ReviewClients(
        analysis=_make("analysis"),
        compose=_make("compose"),
    )


def _load_agents_md(start: Path) -> str:
    """Return sanitized AGENTS.md content from target repo, start dir, or CWD repo root."""
    start_resolved = start.resolve()
    raw_content = ""
    target_repo = _git_repo_root(start_resolved)
    if target_repo is not None:
        agents_file = target_repo / CONST_AGENTS_MD_FILENAME
        if agents_file.is_file():
            try:
                raw_content = agents_file.read_text(encoding="utf-8")
            except OSError:
                pass

    if not raw_content:
        agents_file = (
            start_resolved / CONST_AGENTS_MD_FILENAME
            if start_resolved.is_dir()
            else start_resolved.parent / CONST_AGENTS_MD_FILENAME
        )
        if agents_file.is_file():
            try:
                raw_content = agents_file.read_text(encoding="utf-8")
            except OSError:
                pass

    if raw_content:
        from devops_cli.ai.review.sanitization import (
            _mask_secrets_in_content,
            _sanitize_prompt_boundary_tags,
        )

        return _sanitize_prompt_boundary_tags(_mask_secrets_in_content(raw_content))

    return ""


def _git_repo_root(path: Path) -> Path | None:
    root = find_repo_root(path)
    return root if (root / ".git").exists() else None


def _is_git_ignored(repo_root: Path, path: Path) -> bool:
    return is_ignored_by_git(repo_root, path)


def _collect_file_blocks(root: Path, pattern: str) -> list[str]:
    blocks: list[str] = []
    repo_root = _git_repo_root(root)
    candidates: list[Path] = []
    root_ignored = False

    if repo_root is not None:
        try:
            rel_to_repo = root.relative_to(repo_root)
            rel_str = str(rel_to_repo) if str(rel_to_repo) != "." else "."
        except ValueError:
            rel_str = "."

        root_ignored = (
            _is_git_ignored(repo_root, root) if root.resolve() != repo_root.resolve() else False
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
                is_from_git = True
            else:
                is_from_git = False
    else:
        is_from_git = False

    if not candidates:
        candidates = [p for p in sorted(root.rglob("*")) if p.is_file()]
        is_from_git = False

    for p in sorted(candidates):
        if not p.is_file():
            continue
        if any(part in CONST_GITIGNORE_DIRS for part in p.parts):
            continue
        if p.name in CONST_REVIEW_GENERATED_FILES:
            continue
        if (
            not is_from_git
            and repo_root is not None
            and not root_ignored
            and _is_git_ignored(repo_root, p)
        ):
            continue
        try:
            rel = p.relative_to(root)
        except ValueError:
            rel = p
        if not rel.match(pattern):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        file_label = (
            p.relative_to(repo_root)
            if repo_root is not None and p.is_relative_to(repo_root)
            else rel
        )
        suffix = rel.suffix.lstrip(".") or "text"
        blocks.extend(_split_source_file_blocks(file_label, suffix, text, _MAX_DIFF_CHARS))
    return blocks


def _collect_files(root: Path, pattern: str) -> str:
    """Join collected file blocks into a single string."""
    return "\n\n".join(_collect_file_blocks(root, pattern))


def _build_path_prompt(content: str, title: str) -> str:
    clean_content = _sanitize_prompt_boundary_tags(content)
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


def _make_review_clients(settings: Any) -> ReviewClients:
    """Build unified LLM clients for analysis and compose tasks."""
    api_key = get_ai_api_key(settings)
    return ReviewClients(
        analysis=LLMClient(
            settings.ai.for_task("analysis"),
            api_key=api_key,
            request_timeout_seconds=DEFAULT_REVIEW_TIMEOUT_SECONDS,
        ),
        compose=LLMClient(
            settings.ai.for_task("compose"),
            api_key=api_key,
            request_timeout_seconds=DEFAULT_REVIEW_TIMEOUT_SECONDS,
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

    res_sym = _run_subprocess(
        ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        capture_output=True,
        text=True,
        cwd=repo_path,
        check=False,
    )
    if res_sym.returncode == 0 and res_sym.stdout:
        target_str: str = res_sym.stdout.strip().removeprefix("origin/")
        if target_str:
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
        blocks = [f"### File: {file_label}\n```{suffix}\n{content}\n```"]
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

    pages = [_mask_secrets_in_content(p) for p in blocks]
    agents_md = _load_agents_md(
        target_resolved if target_resolved.is_dir() else target_resolved.parent
    )
    return pages, title, agents_md


def _prepare_branch_content(
    branch_name: str | None, base: str, repo_path: Path
) -> tuple[list[str], str, str]:
    """Prepare paginated diff pages, title, and agents_md for branch review target."""
    import typer

    from devops_cli.ai.review.chunker import _diff_pages
    from devops_cli.lang import MESSAGES

    settings = load_settings()
    repo_resolved = repo_path.resolve()
    if not _is_allowed_review_boundary(repo_resolved, settings):
        err_msg = MESSAGES.review.outside_boundary.format(target=repo_resolved)
        print_error(err_msg, prefix=False)
        raise typer.Exit(1)

    effective_base = _detect_base_branch(repo_path, base)

    if branch_name is None:
        proc = _run_subprocess(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_path,
        )
        if (
            proc.returncode != 0
            or not (branch_name := proc.stdout.strip())
            or branch_name == "HEAD"
        ):
            print_error(MESSAGES.review.detect_branch_failed, prefix=False)
            raise typer.Exit(1)

    diffing_msg = MESSAGES.review.diffing_branches.format(
        branch=f"[cyan]{branch_name}[/cyan]", base=f"[cyan]{effective_base}[/cyan]"
    )
    print_info(diffing_msg, prefix=False)

    diff_proc = _run_subprocess(
        ["git", "diff", f"{effective_base}...{branch_name}"],
        capture_output=True,
        text=True,
        cwd=repo_path,
    )
    if diff_proc.returncode != 0:
        diff_proc = _run_subprocess(
            ["git", "diff", effective_base, branch_name],
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

    title = f"Branch `{branch_name}` vs `{effective_base}`"
    agents_md = _load_agents_md(repo_path)
    pages = [_mask_secrets_in_content(p) for p in _diff_pages(diff_proc.stdout, _MAX_DIFF_CHARS)]
    return pages, title, agents_md


def _prepare_pr_content(
    number: int, repo_arg: str | None, token: str
) -> tuple[list[str], str, str, Any, str]:
    """Fetch PR details, diff pages, title, and agents_md for PR review target."""
    import typer

    from devops_cli.ai.review.chunker import _diff_pages
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
    gh = GitHubClient(token)
    pull = gh.get_pull(repo, number)
    diff = gh.get_pr_diff(repo, number)
    title = f"PR #{number}: {pull.title}"
    agents_md = _load_agents_md(Path.cwd())
    pages = [_mask_secrets_in_content(p) for p in _diff_pages(diff, _MAX_DIFF_CHARS)]
    return pages, title, agents_md, pull, repo


def _run_orchestrator_review(
    orchestrator: Any,
    all_files: list[str],
    metadata_by_path: dict[str, FileAnalysisMeta],
    target_dir: Path | None,
    pages: list[str],
    active_p: list[str],
    persona: Persona | None,
) -> list[tuple[PersonaDefinition, ReviewResult | str]]:
    """Execute orchestrator pipeline review for all files."""
    payloads = orchestrator.init_per_file_payloads(
        all_files, metadata_by_path, target_dir=target_dir
    )
    if not is_dry_run():
        diff_map = {f: "\n".join([p for p in pages if f in p]) for f in all_files}
        orchestrator.execute_multi_persona_review(
            payloads, diff_text_by_file=diff_map, personas=active_p
        )
        orchestrator.execute_finding_verification(payloads)
        orchestrator.execute_finding_reranking(payloads)

    _, report_md = orchestrator.generate_consolidated_report(payloads)
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
) -> list[tuple[PersonaDefinition, ReviewResult | str]]:
    """Common review execution workflow for path, branch, and PR reviews."""
    from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
    from devops_cli.lang import MESSAGES

    if len(pages) > 1:
        spans_msg = MESSAGES.review.spans_pages.format(count=len(pages))
        print_info(f"[dim]{spans_msg}[/dim]", prefix=False)

    all_files = sorted(list({fn for page in pages for fn in _extract_segment_filenames(page)}))
    orchestrator = ReviewPipelineOrchestrator(llm_client=clients.analysis, target_dir=target_dir)

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
            metadata_by_path = orchestrator.run_pre_analysis_refresh(
                target_dir=target_dir,
                target_type=target_type,
                target_ref=target_ref,
            )
            if all_files:
                return _run_orchestrator_review(
                    orchestrator,
                    all_files,
                    metadata_by_path,
                    target_dir,
                    pages,
                    active_p,
                    persona,
                )

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
