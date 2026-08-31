"""Step 3 finding verification pipeline, source excerpt matching, and status reconciliation."""

from __future__ import annotations

import ast
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from devops_cli.ai.review.sanitization import (
    _mask_secrets_in_content,
    _sanitize_prompt_boundary_tags,
)
from devops_cli.ai.review_schema import _SEVERITY_RANK, Finding, ReviewResult, extract_json_block
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.defaults import (
    DEFAULT_DIFF_CONTEXT_LINES,
    DEFAULT_MAX_RELATED_FILES,
    DEFAULT_RELATED_FILE_MAX_CHARS,
)

logger = logging.getLogger(__name__)

_VALIDATION_TEMPLATE = load_task_prompt("verify_finding.md")
_VALIDATION_SYSTEM = load_task_prompt("verify_finding_system.md")


def _is_secret_path(path_str: str) -> bool:
    """Check if file path indicates sensitive secrets or credential files."""
    p = Path(path_str)
    name_lower = p.name.lower()
    return (
        name_lower.startswith(".env")
        or name_lower.startswith("id_")
        or p.suffix.lower() in {".pem", ".key", ".pfx", ".p12"}
        or any(part in {"secrets", "credentials", ".ssh"} for part in p.parts)
    )


def _extract_location_context(
    segment: str, location: str, context_lines: int = DEFAULT_DIFF_CONTEXT_LINES
) -> str:
    """Extract the referenced file+line range from a segment's markdown code blocks."""
    file_part = location.split(":")[0].strip()
    line_range: tuple[int, int] | None = None
    if ":" in location:
        try:
            nums = [int(x) for x in location.split(":", 1)[1].replace("-", " ").split()]
            if nums:
                line_range = (nums[0], nums[-1])
        except ValueError:
            pass

    header = f"### File: {file_part}"
    header_idx = segment.find(header)
    if header_idx == -1:
        basename = Path(file_part).name
        for seg_line in segment.splitlines():
            if seg_line.startswith("### File: ") and basename in seg_line:
                header_idx = segment.find(seg_line)
                break
    if header_idx == -1:
        return ""

    fence_open = segment.find("```", header_idx)
    if fence_open == -1:
        return segment[header_idx : header_idx + 2000]
    code_start = segment.find("\n", fence_open) + 1
    fence_close = segment.find("\n```", code_start)
    code = segment[code_start : fence_close if fence_close != -1 else code_start + 4000]

    if line_range is None:
        return code

    lines = code.splitlines()
    lo = max(0, line_range[0] - 1 - context_lines)
    hi = min(len(lines), line_range[1] + context_lines)
    return "\n".join(lines[lo:hi])


def _match_dep_to_filepath(dep: str, all_paths: set[str]) -> str | None:
    """Map Python import path or module name to a relative repository file path."""
    clean_dep = dep.replace(".", "/")
    for path in all_paths:
        path_no_ext = str(Path(path).with_suffix(""))
        if path_no_ext == clean_dep or path_no_ext.endswith(f"/{clean_dep}"):
            return path
    return None


def _find_related_file_metas(
    finding: Finding,
    finding_file: str,
    analysis_metas: dict[str, Any],
    max_related: int = DEFAULT_MAX_RELATED_FILES,
) -> list[Any]:
    """Identify files in analysis_metas related to target finding for cross-file verification."""
    related: list[Any] = []
    seen: set[str] = {finding_file}
    all_paths = set(analysis_metas.keys())

    target_meta = analysis_metas.get(finding_file)

    if target_meta and getattr(target_meta, "dependencies", None):
        for dep in target_meta.dependencies:
            match = _match_dep_to_filepath(dep, all_paths)
            if match and match not in seen:
                meta = analysis_metas[match]
                related.append(meta)
                seen.add(match)
            if len(related) >= max_related:
                return related

    target_stem = Path(finding_file).stem
    target_mod = target_stem.replace("/", ".")
    for rel_path, meta in analysis_metas.items():
        if rel_path in seen:
            continue
        deps = getattr(meta, "dependencies", []) or []
        for dep in deps:
            if dep and (dep in target_mod or target_mod in dep):
                related.append(meta)
                seen.add(rel_path)
                break
        if len(related) >= max_related:
            return related

    return related


def _read_and_mask_related_file(
    repo_root: Path,
    rel_path: str,
    max_chars: int = DEFAULT_RELATED_FILE_MAX_CHARS,
) -> str | None:
    """Read a related file safely from repo_root, masking secrets and boundary tags."""
    if _is_secret_path(rel_path):
        return None
    try:
        candidate = repo_root / rel_path
        resolved = candidate.resolve()
        if not resolved.is_relative_to(repo_root.resolve()) or not resolved.is_file():
            return None
        raw_text = resolved.read_text(encoding="utf-8", errors="replace")[:max_chars]
        clean_text = _sanitize_prompt_boundary_tags(_mask_secrets_in_content(raw_text))
        return f"```\n{clean_text}\n```"
    except Exception as exc:
        logger.debug("Failed reading related file %s: %s", rel_path, exc)
        return None


def _format_related_file_block(rmeta: Any, repo_root: Path | None) -> str | None:
    """Format single related file analysis metadata block."""
    if _is_secret_path(rmeta.path):
        return None
    r_lines: list[str] = [
        f"### Related File: `{rmeta.path}`",
        f"- **Purpose**: {rmeta.primary_purpose or 'N/A'}",
    ]
    if rmeta.key_symbols:
        r_lines.append(f"- **Key Symbols**: {', '.join(rmeta.key_symbols[:10])}")
    if rmeta.dependencies:
        r_lines.append(f"- **Dependencies**: {', '.join(rmeta.dependencies[:10])}")
    if rmeta.pseudocode:
        r_lines.append("- **Pseudocode Outline**:")
        r_lines.extend(f"  {step}" for step in rmeta.pseudocode[:15])

    if repo_root:
        masked_block = _read_and_mask_related_file(repo_root, rmeta.path)
        if masked_block:
            r_lines.append(masked_block)
    return "\n".join(r_lines)


def _build_validation_prompt(
    findings: list[Finding],
    all_segments: list[str],
    analysis_metas: dict[str, Any] | None = None,
    repo_root: Path | None = None,
) -> str:
    excerpts: list[str] = []
    related_file_blocks: list[str] = []

    if analysis_metas is None:
        analysis_metas = {}

    for f in findings:
        primary = ""
        additional: list[str] = []
        for seg in all_segments:
            ctx = _extract_location_context(seg, f.location)
            if not ctx:
                continue
            if not primary:
                primary = ctx
            elif ctx != primary:
                additional.append(ctx)
        parts: list[str] = []
        if primary:
            clean_prim = _sanitize_prompt_boundary_tags(_mask_secrets_in_content(primary[:1500]))
            parts.append(f"```\n{clean_prim}\n```")
        for extra in additional[:2]:
            clean_extra = _sanitize_prompt_boundary_tags(_mask_secrets_in_content(extra[:800]))
            parts.append(f"```\n{clean_extra}\n```")
            if ctx:
                clean_ctx = _sanitize_prompt_boundary_tags(ctx)
                excerpts.append(f"### Finding: {f.title} ({f.location})\n```\n{clean_ctx}\n```")
                break

        # Grounding with file analysis metadata if available
        loc_file = f.location.split(":")[0].strip()
        if analysis_metas:
            for rmeta in _find_related_file_metas(f, loc_file, analysis_metas):
                block = _format_related_file_block(rmeta, repo_root)
                if block:
                    related_file_blocks.append(block)

    if excerpts:
        code_section = "\n\n".join(excerpts)
    else:
        full_code = "\n\n---\n\n".join(all_segments)
        code_section = _sanitize_prompt_boundary_tags(_mask_secrets_in_content(full_code))

    related_section = ""
    if related_file_blocks:
        dedup_related = list(dict.fromkeys(related_file_blocks))
        related_section = (
            "\n\nRelated Analysis Metadata & Context:\n<untrusted_related_files>\n"
            + "\n\n".join(dedup_related[:10])
            + "\n</untrusted_related_files>\n\n"
        )

    # Augment validation with semantic RAG investigation across indexed codebase
    rag_verification_blocks: list[str] = []
    try:
        from devops_cli.ai.rag.investigator import investigate_rag_context

        for f in findings:
            f_query = f"{f.title} {f.description}"
            rag_ctx = investigate_rag_context(f_query, top_k=2)
            if rag_ctx and rag_ctx.has_results:
                rag_verification_blocks.append(
                    f"### Context for Finding {f.title}:\n{rag_ctx.formatted_text}"
                )
    except Exception:
        pass

    if rag_verification_blocks:
        related_section += (
            "\n\nCross-File RAG Context:\n<untrusted_rag_context>\n"
            + "\n\n".join(rag_verification_blocks)
            + "\n</untrusted_rag_context>\n\n"
        )

    findings_json = _sanitize_prompt_boundary_tags(
        json.dumps(
            [
                {k: v for k, v in f.model_dump().items() if k not in {"verified", "mitigated"}}
                for f in findings
            ],
            indent=2,
            ensure_ascii=True,
        )
    )
    return (
        f"{_VALIDATION_TEMPLATE}\n\n"
        f"Code:\n<untrusted_finding_excerpts>\n{code_section}\n</untrusted_finding_excerpts>\n\n"
        f"{related_section}"
        f"Findings:\n<untrusted_findings_input>\n```json\n{findings_json}\n```\n</untrusted_findings_input>\n"
    )


_SYNTAX_INVALIDATION_REASON = "Syntax validation passed cleanly via language parser"


def _check_syntax_error_hallucination(finding: Finding, file_path: Path) -> Finding | None:
    """Deterministically invalidate syntax error claims if standard parser succeeds."""
    if not (file_path.exists() and file_path.is_file()):
        return None

    title_lower = finding.title.lower()
    desc_lower = (finding.description or "").lower()
    is_syntax_claim = any(
        kw in title_lower or kw in desc_lower
        for kw in ("syntax error", "invalid syntax", "parse error", "syntaxerror", "syntax_error")
    )
    if not is_syntax_claim:
        return None

    suffix = file_path.suffix.lower()
    content = file_path.read_text(encoding="utf-8", errors="replace")

    try:
        if suffix == ".py":
            ast.parse(content)
        elif suffix == ".json":
            import json

            json.loads(content)
        elif suffix in {".yaml", ".yml"}:
            import yaml

            yaml.safe_load(content)
        elif suffix == ".toml":
            import tomllib

            tomllib.loads(content)
        else:
            return None

        return finding.model_copy(
            update={
                "verified": False,
                "mitigated": False,
                "reportable": False,
                "status": "INVALIDATED",
                "invalidation_reason": _SYNTAX_INVALIDATION_REASON,
            }
        )
    except Exception:
        return None


def _check_line_boundaries(finding: Finding, file_path: Path) -> Finding | None:
    """Invalidate findings referencing line numbers beyond total file length."""
    if not (file_path.exists() and file_path.is_file()):
        return None
    if ":" not in finding.location:
        return None
    try:
        line_part = finding.location.split(":", 1)[1].strip()
        nums = [int(x) for x in line_part.replace("-", " ").split() if x.isdigit()]
        if not nums:
            return None
        target_line = nums[0]
        total_lines = len(file_path.read_text(encoding="utf-8", errors="replace").splitlines())
        if target_line > max(1, total_lines):
            return finding.model_copy(
                update={
                    "verified": False,
                    "mitigated": False,
                    "reportable": False,
                    "status": "INVALIDATED",
                    "invalidation_reason": f"Line {target_line} exceeds total file lines ({total_lines})",
                }
            )
    except Exception:
        pass
    return None


def _deterministic_pre_verification(finding: Finding, repo_root: Path | None = None) -> Finding:
    """Run local deterministic parser and structural checks to invalidate obvious false positives."""
    if not repo_root:
        return finding

    loc_file = finding.location.split(":")[0].strip()
    if not loc_file or _is_secret_path(loc_file):
        return finding

    try:
        resolved_file = (repo_root / loc_file).resolve()
        resolved_root = repo_root.resolve()
        if not resolved_file.is_relative_to(resolved_root):
            return finding
        file_path = resolved_file
    except ValueError, OSError:
        return finding

    line_res = _check_line_boundaries(finding, file_path)
    if line_res:
        return line_res

    syntax_res = _check_syntax_error_hallucination(finding, file_path)
    if syntax_res:
        return syntax_res

    return finding


def _apply_single_finding_verification(
    f: Finding, item: dict[str, Any] | None, now_iso: str
) -> Finding:
    """Apply parsed LLM verification metadata to a single Finding."""
    if not isinstance(item, dict):
        return f

    ver_matched = [str(x) for x in item.get("verified_criteria_matched", []) if str(x)]
    inv_matched = [str(x) for x in item.get("invalidated_criteria_matched", []) if str(x)]
    is_v = bool(item.get("verified", True))
    is_m = bool(item.get("mitigated", False))

    if inv_matched:
        is_v = False
        is_m = True
        status_val = "INVALIDATED"
        is_rep = False
    elif is_m:
        status_val = "MITIGATED"
        is_rep = False
    elif is_v:
        status_val = "VERIFIED"
        is_rep = bool(item.get("reportable", True))
    else:
        status_val = "UNVERIFIED"
        is_rep = False

    conf_val = item.get("confidence_score")
    if conf_val is not None:
        try:
            conf: float | None = max(0.0, min(1.0, float(conf_val)))
        except ValueError, TypeError:
            conf = f.confidence_score
    elif f.verification_criteria:
        conf = round(len(ver_matched) / max(1, len(f.verification_criteria)), 2)
    else:
        conf = f.confidence_score

    updates: dict[str, object] = {
        "verified": is_v,
        "mitigated": is_m,
        "status": status_val,
        "reportable": is_rep,
        "confidence_score": conf,
        "verified_criteria_matched": ver_matched,
        "invalidated_criteria_matched": inv_matched,
        "verified_by": "llm",
        "verified_at": now_iso,
    }
    new_sev = str(item.get("severity", "")).upper().strip()
    if new_sev and new_sev in _SEVERITY_RANK:
        updates["severity"] = new_sev
    new_loc = str(item.get("location", "")).strip()
    if new_loc and new_loc != f.location:
        updates["location"] = new_loc
    return f.model_copy(update=updates)


def _validate_segment_findings(
    result: ReviewResult,
    all_segments: list[str],
    client: Any,
    analysis_metas: dict[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[ReviewResult, float | None, str | None]:
    """Ask the LLM to verify each finding using enhanced analysis metadata of related files."""
    if not result.findings:
        return result, None, None

    # Apply deterministic static rules first
    pre_validated_findings = [
        _deterministic_pre_verification(f, repo_root=repo_root) for f in result.findings
    ]
    result = result.model_copy(update={"findings": pre_validated_findings})

    # If all candidate findings are already deterministically invalidated or mitigated, bypass LLM
    unresolved_findings = [
        f for f in pre_validated_findings if f.status not in {"INVALIDATED", "MITIGATED"}
    ]
    if not unresolved_findings:
        return result, 0.0, "deterministic"

    prompt = _build_validation_prompt(
        result.findings, all_segments, analysis_metas=analysis_metas, repo_root=repo_root
    )
    proc_sec: float | None = None
    b_info: str | None = None
    try:
        res_obj = client.chat(system=_VALIDATION_SYSTEM, user=prompt, enable_thinking=False)
        response = str(res_obj)
        proc_sec = getattr(res_obj, "processing_seconds", None)
        b_info = getattr(res_obj, "backend_info", None)
        data = extract_json_block(response)

        if isinstance(data, dict):
            if "findings" in data and isinstance(data["findings"], list):
                data = data["findings"]
            elif "items" in data and isinstance(data["items"], list):
                data = data["items"]

        if isinstance(data, list) and data:
            validated: list[Finding] = []
            now_iso = datetime.now().isoformat()
            for idx, f in enumerate(result.findings):
                if f.status == "INVALIDATED":
                    validated.append(f)
                    continue
                item = data[idx] if idx < len(data) else None
                validated.append(_apply_single_finding_verification(f, item, now_iso))
            return result.model_copy(update={"findings": validated}), proc_sec, b_info
    except Exception:
        pass
    return result, proc_sec, b_info


def _merge_segment_results(results: list[ReviewResult | None]) -> ReviewResult | None:
    """Python-level merge of validated segment ReviewResults used as recompose fallback."""
    valid = [r for r in results if r is not None]
    if not valid:
        return None
    merged = valid[0]
    for other in valid[1:]:
        merged = merged.merge(other)
    return merged


def _reconcile_verified(
    recomposed: ReviewResult, segment_results: list[ReviewResult | None]
) -> ReviewResult:
    """Carry verified=False and mitigated=True from step-3 validation into the recomposed result."""
    valid_results = [r for r in segment_results if r is not None]

    merged_seg = _merge_segment_results(segment_results)
    baseline_findings = recomposed.findings
    if not baseline_findings and merged_seg and merged_seg.findings:
        baseline_findings = merged_seg.findings

    unverified_findings = [f for r in valid_results for f in r.findings if not f.verified]
    mitigated_findings = [f for r in valid_results for f in r.findings if f.mitigated]

    updated: list[Finding] = []
    for f in baseline_findings:
        f_title = f.title.lower().strip()
        f_loc = f.location.lower().strip()
        u: dict[str, object] = {}

        is_unverified = any(
            uf.title.lower().strip() == f_title
            or (f_loc and uf.location.lower().strip() == f_loc)
            or (len(f_title) > 5 and uf.title.lower().strip() in f_title)
            or (len(uf.title) > 5 and f_title in uf.title.lower().strip())
            for uf in unverified_findings
        )
        if is_unverified:
            u["verified"] = False
            u["status"] = "UNVERIFIED"
            u["reportable"] = False

        is_mitigated = any(
            mf.title.lower().strip() == f_title
            or (f_loc and mf.location.lower().strip() == f_loc)
            or (len(f_title) > 5 and mf.title.lower().strip() in f_title)
            or (len(mf.title) > 5 and f_title in mf.title.lower().strip())
            for mf in mitigated_findings
        )
        if is_mitigated:
            u["mitigated"] = True
            u["status"] = "MITIGATED"
            u["reportable"] = False

        updated.append(f.model_copy(update=u) if u else f)

    summary = recomposed.summary
    positive = recomposed.positive_observations
    if not summary and merged_seg and merged_seg.summary:
        summary = merged_seg.summary
    if not positive and merged_seg and merged_seg.positive_observations:
        positive = merged_seg.positive_observations

    return recomposed.model_copy(
        update={
            "findings": updated,
            "summary": summary,
            "positive_observations": positive,
        }
    )
