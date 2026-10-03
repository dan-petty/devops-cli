"""Step 3 finding verification pipeline, source excerpt matching, and status reconciliation."""

from __future__ import annotations

import ast
import functools
import json
import logging
import os
import re
import sys
import tempfile
import threading
import warnings
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from devops_cli.ai.client.network import limit_completion_tokens
from devops_cli.ai.review.chunker import page_line_number
from devops_cli.ai.review.construct_validator import validate_construct_location
from devops_cli.ai.review.verdicts import apply_verdict
from devops_cli.ai.review_schema import Finding, ReviewResult, extract_json_block, less_severe
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import (
    CONST_AUTH_DISPATCH_PATTERNS,
    CONST_AUTH_HEADER_CLAIM_KEYWORDS,
    CONST_AUTH_HEADER_CODE_PATTERNS,
    CONST_CACHE_DIR_NAME,
    CONST_COMPLIMENT_NEGATIONS,
    CONST_COMPLIMENT_PHRASES,
    CONST_CRITERIA_NON_DISCRIMINATING,
    CONST_FINISH_REASON_LENGTH,
    CONST_FIXTURE_CREDENTIAL_KEYWORDS,
    CONST_MASKED_SYNTAX_ERROR_PHRASES,
    CONST_MONOLOGUE_PREFIXES,
    CONST_PLACEHOLDER_VALUES,
    CONST_TYPECHECK_PROBE_CACHE_DIR_NAME,
    CONST_TYPECHECK_PROBE_MYPY_CONFIG,
    CONST_UNINITIALIZED_CLAIM_KEYWORDS,
    CONST_VERIFICATION_UNAVAILABLE,
    CONST_VERIFIER_FINDING_FIELDS,
    CONST_VERIFIER_INCONCLUSIVE,
    CONST_VERIFIER_NO_VERDICT,
    CONST_VERIFIER_REPLY_CUT,
    CONST_VERIFIER_REPLY_UNPARSED,
    CONST_VERIFIER_SELF_REFUTATION,
)
from devops_cli.config.defaults import (
    DEFAULT_DIFF_CONTEXT_LINES,
    DEFAULT_MAX_RELATED_FILES,
    DEFAULT_RELATED_FILE_MAX_CHARS,
    DEFAULT_REVIEW_VERIFICATION_REPLY_BASE_TOKENS,
    DEFAULT_REVIEW_VERIFICATION_REPLY_MAX_TOKENS,
    DEFAULT_REVIEW_VERIFICATION_REPLY_TOKENS_PER_FINDING,
    DEFAULT_TYPECHECK_PROBE_TIMEOUT_SECONDS,
)
from devops_cli.security.sanitizer import (
    mask_secrets,
    sanitize_prompt_boundary_tags,
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


def _parse_location(location: str) -> tuple[str, tuple[int, int] | None]:
    """A finding location's file and line range, when it names one."""
    file_part = location.split(":")[0].strip()
    if ":" not in location:
        return file_part, None
    try:
        nums = [int(x) for x in location.split(":", 1)[1].replace("-", " ").split()]
    except ValueError:
        return file_part, None
    return file_part, (nums[0], nums[-1]) if nums else None


def _file_header_indexes(segment: str, file_part: str) -> list[int]:
    """Offsets of the `### File:` headers of every part of one file in the segment.

    The file is matched by path, or failing that by the first header containing its name.
    """
    headers = [
        (m.start(), m[1].split(" (part ", 1)[0].strip())
        for m in re.finditer(r"^### File: (.*)$", segment, re.MULTILINE)
    ]
    labels = [label for _, label in headers]
    basename = Path(file_part).name
    label = file_part if file_part in labels else next((x for x in labels if basename in x), None)
    return [idx for idx, x in headers if x == label]


def _fenced_code(segment: str, header_idx: int) -> str:
    """The code inside the fence that follows a file header."""
    fence_open = segment.find("```", header_idx)
    if fence_open == -1:
        return segment[header_idx : header_idx + 2000]
    code_start = segment.find("\n", fence_open) + 1
    fence_close = segment.find("\n```", code_start)
    return segment[code_start : fence_close if fence_close != -1 else code_start + 4000]


def _extract_location_context(
    segment: str, location: str, context_lines: int = DEFAULT_DIFF_CONTEXT_LINES
) -> str:
    """Extract the referenced file+line range from a segment's markdown code blocks.

    Page lines carry their line numbers in the file, so the range is found by number across
    every part of the file in the segment. Code without numbers is counted from its first line.
    """
    file_part, line_range = _parse_location(location)
    codes = [_fenced_code(segment, idx) for idx in _file_header_indexes(segment, file_part)]
    if not codes or line_range is None:
        return codes[0] if codes else ""

    lo, hi = line_range[0] - context_lines, line_range[1] + context_lines
    numbered = [
        (number, line)
        for code in codes
        for line in code.splitlines()
        if (number := page_line_number(line)) is not None
    ]
    if numbered:
        # Overlapping parts repeat lines; each is shown once, in file order.
        return "\n".join(dict(sorted(p for p in numbered if lo <= p[0] <= hi)).values())
    lines = codes[0].splitlines()
    return "\n".join(lines[max(0, lo - 1) : min(len(lines), hi)])


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
        from devops_cli.core.paths import safe_resolve_subpath

        resolved = safe_resolve_subpath(repo_root, rel_path, must_exist=True)
        if not resolved.is_file():
            return None
        raw_text = resolved.read_text(encoding="utf-8", errors="replace")[:max_chars]
        clean_text = sanitize_prompt_boundary_tags(mask_secrets(raw_text))
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


def _extract_finding_excerpt(finding: Finding, all_segments: list[str]) -> str | None:
    """Extract and sanitize relevant snippet for a finding from diff segments."""
    for segment in all_segments:
        ctx = _extract_location_context(segment, finding.location)
        if ctx:
            clean_ctx = sanitize_prompt_boundary_tags(ctx)
            return f"### Finding: {finding.title} ({finding.location})\n```\n{clean_ctx}\n```"
    return None


def _collect_related_metadata_blocks(
    findings: list[Finding],
    analysis_metas: dict[str, Any],
    repo_root: Path | None,
) -> list[str]:
    """Collect related file metadata and context blocks for findings."""
    related_blocks: list[str] = []
    for finding in findings:
        loc_file = finding.location.split(":")[0].strip()
        for rmeta in _find_related_file_metas(finding, loc_file, analysis_metas):
            block = _format_related_file_block(rmeta, repo_root)
            if block:
                related_blocks.append(block)
    return list(dict.fromkeys(related_blocks))


def _collect_rag_verification_blocks(findings: list[Finding]) -> list[str]:
    """Query semantic RAG context for findings."""
    rag_blocks: list[str] = []
    try:
        from devops_cli.ai.rag.investigator import investigate_rag_context

        for finding in findings:
            query = f"{finding.title} {finding.description}"
            rag_ctx = investigate_rag_context(query, top_k=2)
            if rag_ctx and rag_ctx.has_results:
                rag_blocks.append(
                    f"### Context for Finding {finding.title}:\n{rag_ctx.formatted_text}"
                )
    except Exception:
        pass
    return rag_blocks


def _build_validation_prompt(
    findings: list[Finding],
    all_segments: list[str],
    analysis_metas: dict[str, Any] | None = None,
    repo_root: Path | None = None,
    conventions: str = "",
) -> str:
    excerpts: list[str] = []
    for finding in findings:
        excerpt = _extract_finding_excerpt(finding, all_segments)
        if excerpt:
            excerpts.append(excerpt)

    if excerpts:
        code_section = "\n\n".join(excerpts)
    else:
        full_code = "\n\n---\n\n".join(all_segments)
        code_section = sanitize_prompt_boundary_tags(mask_secrets(full_code))

    related_section = ""
    if analysis_metas:
        related_file_blocks = _collect_related_metadata_blocks(findings, analysis_metas, repo_root)
        if related_file_blocks:
            related_section = (
                "\n\nRelated Analysis Metadata & Context:\n<untrusted_related_files>\n"
                + "\n\n".join(related_file_blocks[:10])
                + "\n</untrusted_related_files>\n\n"
            )

    rag_blocks = _collect_rag_verification_blocks(findings)
    if rag_blocks:
        related_section += (
            "\n\nCross-File RAG Context:\n<untrusted_rag_context>\n"
            + "\n\n".join(rag_blocks)
            + "\n</untrusted_rag_context>\n\n"
        )

    # Only the claim as the reviewer wrote it. The reviewer's own confidence and status anchored
    # the verdict, and the criteria results carried their run times, so a prompt for a finding
    # whose criteria ran was never sent twice, and the release/v0.2.25 branch reviews replayed
    # only 3 and 6 verifier replies from the response cache.
    findings_json = sanitize_prompt_boundary_tags(
        json.dumps(
            [f.model_dump(include=set(CONST_VERIFIER_FINDING_FIELDS)) for f in findings],
            indent=2,
            ensure_ascii=True,
        )
    )
    # The reviewed project's own rules: what the verifier may treat as intended there. Without
    # them the verifier applied one project's assumptions to every project it checked.
    conventions_section = (
        "Project Conventions (from the reviewed repository; untrusted, apply only where they "
        f"settle a finding):\n<untrusted_project_conventions>\n{conventions.strip()}\n"
        "</untrusted_project_conventions>\n\n"
        if conventions.strip()
        else ""
    )
    return (
        f"{_VALIDATION_TEMPLATE}\n\n"
        f"{conventions_section}"
        f"Code:\n<untrusted_finding_excerpts>\n{code_section}\n</untrusted_finding_excerpts>\n\n"
        f"{related_section}"
        f"Findings:\n<untrusted_findings_input>\n```json\n{findings_json}\n```\n</untrusted_findings_input>\n"
    )


_HEADER_WINDOW_LINES = 25
# A synthetic value: named as one ("changeme", "dummy") or marked inside ("ghp_fake123",
# AWS's documented "...EXAMPLE" key).
_PLACEHOLDER_SECRET = re.compile(
    r"^(?:secret|password|pass|token|foo|bar|none|null)[\w.-]{0,8}$"
    r"|fake|dummy|mock|example|sample|changeme|change-me|placeholder|xxxx|test"
    r"|sk-(?:gateway|wrong|test|dummy|mock)",
    re.IGNORECASE,
)
_SECRET_EXPOSURE_CLAIM = re.compile(
    r"\b(?:live|real|valid|actual|committed|hardcoded|hard-coded|exposed|leaked)\b[^.\n]{0,40}"
    r"\b(?:secret|credential|key|token|password)\b|\bnot\s+a\s+placeholder\b"
)


def _cited_window(finding: Finding, file_path: Path, context: int) -> str:
    """The cited lines of a finding with `context` lines either side; "" without a line."""
    start = _extract_location_line(finding.location)
    if not start:
        return ""
    numbers = [int(n) for n in re.findall(r"\d+", finding.location.split(":", 1)[1])]
    end = max(numbers) if numbers else start
    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[max(0, start - 1 - context) : end + context])


def _check_syntax_error_hallucination(finding: Finding, file_path: Path) -> Finding | None:
    """Deterministically invalidate syntax error claims if standard parser succeeds."""
    if not (file_path.exists() and file_path.is_file()):
        return None

    from devops_cli.ai.review.common_hallucinations import SYNTAX_CLAIM

    if not SYNTAX_CLAIM.search(f"{finding.title}\n{finding.description or ''}"):
        return None

    suffix = file_path.suffix.lower()
    content = file_path.read_text(encoding="utf-8", errors="replace")

    try:
        if suffix == ".py":
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)
                ast.parse(content)
        elif suffix == ".json":
            json.loads(content)
        elif suffix in {".yaml", ".yml"}:
            import yaml

            yaml.safe_load(content)
        elif suffix == ".toml":
            import tomllib

            tomllib.loads(content)
        else:
            return None

        res = apply_verdict(
            finding,
            "INVALIDATED",
            by="deterministic:syntax_error",
            reason="Syntax validation passed cleanly via language parser (valid Python 3.14+ syntax)",
        )

        try:
            from devops_cli.ai.review.common_hallucinations import auto_record_invalidated_finding

            auto_record_invalidated_finding(
                res, file_path=file_path, reason=res.invalidation_reason
            )
        except Exception:
            pass
        return res
    except Exception as exc:
        logger.debug("Failed syntax error hallucination check for %s: %s", file_path, exc)
        return None


# A claim that a name does not exist: an import or name error, or a symbol said to be undefined
# or unimportable. The word "missing" alone is not one: a finding about a missing check, limit or
# validation names the function that lacks it, and that function exists.
_UNDEFINED_SYMBOL_CLAIM = re.compile(
    r"\b(?:import|name|modulenotfound)error\b"
    r"|\b(?:is|are|was|were)\s+(?:not|never)\s+(?:defined|declared|imported|exported)\b"
    r"|\b(?:is|are)\s+undefined\b(?!\s+behaviou?r)"
    r"|\bnot\s+defined\s+in\b"
    r"|\b(?:does\s+not|doesn't|do\s+not)\s+(?:define|export)\b"
    r"|\b(?:cannot|can't|could\s+not)\s+(?:be\s+)?import(?:ed)?\b"
    r"|\b(?:missing|undefined|unresolved)\s+(?:import|symbol|name)s?\b"
    # "missing `x` variable", "missing _helper import": the name must look like code.
    r"|\b(?:missing|undefined|unresolved)\s+(?:`[\w.]+`|\w*_\w*)\s+"
    r"(?:import|symbol|variable|function|class|constant|name|attribute|module)s?\b",
    re.IGNORECASE,
)


def _claims_undefined_symbol(finding: Finding) -> bool:
    return bool(_UNDEFINED_SYMBOL_CLAIM.search(f"{finding.title}\n{finding.description or ''}"))


def _check_missing_symbol_hallucination(finding: Finding, file_path: Path) -> Finding | None:
    """Deterministically invalidate a claim that a name is undefined, when the name is defined."""
    if not (file_path.exists() and file_path.is_file() and file_path.suffix.lower() == ".py"):
        return None
    if not _claims_undefined_symbol(finding):
        return None

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(content)
        from devops_cli.ai.review.common_hallucinations import (
            _verify_symbol_defined_in_ast_or_module,
            auto_record_invalidated_finding,
        )

        if _verify_symbol_defined_in_ast_or_module(finding, tree, file_path):
            res = apply_verdict(
                finding,
                "INVALIDATED",
                by="deterministic:missing_symbol",
                reason="Ground-truth AST and cross-module inspection confirmed symbol is defined in module or exports",
            )

            try:
                auto_record_invalidated_finding(
                    res, file_path=file_path, reason=res.invalidation_reason
                )
            except Exception:
                pass
            return res
    except Exception:
        pass
    return None


def _has_auth_header_claim(finding: Finding) -> bool:
    """Check if finding claims a missing authorization header."""
    title_lower = finding.title.lower()
    desc_lower = (finding.description or "").lower()
    return any(kw in title_lower or kw in desc_lower for kw in CONST_AUTH_HEADER_CLAIM_KEYWORDS)


def _content_has_auth_and_dispatch(content: str) -> bool:
    """Verify code content configures auth header and dispatches HTTP request."""
    has_auth = any(pattern in content for pattern in CONST_AUTH_HEADER_CODE_PATTERNS)
    has_dispatch = any(dispatch in content for dispatch in CONST_AUTH_DISPATCH_PATTERNS)
    return has_auth and has_dispatch


def _build_invalidated_auth_header_finding(finding: Finding, file_path: Path) -> Finding:
    """Construct invalidated finding for verified authorization header presence."""
    from devops_cli.ai.review.common_hallucinations import auto_record_invalidated_finding

    res = apply_verdict(
        finding,
        "INVALIDATED",
        by="deterministic:missing_header",
        reason="Source code inspection confirmed Authorization header is dynamically configured before request dispatch",
    )

    try:
        auto_record_invalidated_finding(res, file_path=file_path, reason=res.invalidation_reason)
    except Exception:
        pass
    return res


def _check_missing_header_hallucination(finding: Finding, file_path: Path) -> Finding | None:
    """Deterministically invalidate claims of missing Authorization headers if set in the module."""
    if not (file_path.exists() and file_path.is_file()):
        return None
    if not _has_auth_header_claim(finding):
        return None

    try:
        content = _cited_window(finding, file_path, _HEADER_WINDOW_LINES)
        if content and _content_has_auth_and_dispatch(content):
            return _build_invalidated_auth_header_finding(finding, file_path)
    except Exception:
        pass
    return None


def _check_candidate_paths(base_dir: Path, rel_path: Path) -> Path | None:
    """Check direct relative path and src-prefixed path under base directory."""
    cand = (base_dir / rel_path).resolve()
    if cand.is_file():
        return cand
    cand_src = (base_dir / "src" / rel_path).resolve()
    if cand_src.is_file():
        return cand_src
    return None


def _resolve_target_file(loc_file: str, repo_root: Path | None) -> Path | None:
    """Resolve finding location file path against repo_root or current working directory."""
    if not loc_file:
        return None
    p = Path(loc_file)
    if p.is_absolute() and p.is_file():
        return p.resolve()

    if repo_root is not None:
        resolved_root = repo_root.resolve()
        if cand := _check_candidate_paths(resolved_root, p):
            return cand
        try:
            from devops_cli.core.repo import find_repo_root

            repo = find_repo_root(resolved_root).resolve()
            if cand_repo := _check_candidate_paths(repo, p):
                return cand_repo
        except Exception:
            pass
        if len(p.parts) > 1 and p.parts[0] == resolved_root.name:
            cand_sub = (resolved_root / Path(*p.parts[1:])).resolve()
            if cand_sub.is_file():
                return cand_sub

    cwd = Path.cwd().resolve()
    if cand_cwd := _check_candidate_paths(cwd, p):
        return cand_cwd
    try:
        from devops_cli.core.repo import find_repo_root

        cwd_repo = find_repo_root(cwd).resolve()
        if cand_cwd_repo := _check_candidate_paths(cwd_repo, p):
            return cand_cwd_repo
    except Exception:
        pass

    return None


def _drop_out_of_range_lines(finding: Finding, file_path: Path) -> Finding:
    """Remove a line range that points past the end of the file, keeping the finding.

    Review pages carry no line numbers (#499), so a cited line is the model's own count and
    can overshoot on a long file. That is a wrong location, not a wrong finding.
    """
    target_line = _extract_location_line(finding.location)
    if not target_line:
        return finding
    try:
        total_lines = len(file_path.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return finding
    if target_line <= max(1, total_lines):
        return finding
    updates: dict[str, Any] = {"location": finding.location.split(":", 1)[0]}
    if finding.relocated_from is None:
        updates["relocated_from"] = finding.location
    return finding.model_copy(update=updates)


def _check_pathlib_resolve_hallucination(finding: Finding) -> Finding | None:
    """Invalidate claims that Path.resolve() raises FileNotFoundError on non-existent paths."""
    text = (finding.title + " " + (finding.description or "")).lower()
    # resolve(strict=True) does raise FileNotFoundError; only the non-strict claim is false.
    if "filenotfounderror" in text and "resolve(" in text and "strict" not in text:
        return apply_verdict(
            finding,
            "INVALIDATED",
            by="deterministic:pathlib_resolve",
            reason=(
                "Matches verified common hallucination [HALLUCINATION-PATHLIB-RESOLVE-FILENOTFOUND]: "
                "In Python 3.6+, Path.resolve(strict=False) safely resolves non-existent paths without FileNotFoundError"
            ),
        )

    return None


# An advisory id as written: `CVE-<year>-<number>` or `GHSA-xxxx-xxxx-xxxx`, placeholder
# characters included, so a placeholder is caught as the id it pretends to be.
_ADVISORY_ID = re.compile(
    r"\b(?:CVE-\d{4}-[0-9a-z?]+|GHSA-[0-9a-z?]+(?:-[0-9a-z?]+)*)", re.IGNORECASE
)
_ADVISORY_PLACEHOLDER_RUN = re.compile(r"[xn?]{3,}", re.IGNORECASE)
_ASCENDING_DIGITS = "0123456789"
_MIN_SEQUENTIAL_ADVISORY_DIGITS = 4


def _is_placeholder_advisory(advisory: str) -> bool:
    """Whether an advisory id is written as a placeholder: an `x`, `n` or `?` run, or a run of
    ascending digits.

    A model that cites `CVE-2023-xxxx`, or the sequence `CVE-2023-1234`, has written the shape of
    evidence where the evidence belongs. A sequence can still be a published id (CVE-2016-1234
    is a glibc advisory), so the check spares one this session's scan carries.
    """
    number = advisory.split("-", 2)[-1] if advisory.upper().startswith("CVE-") else advisory[5:]
    sequential = len(number) >= _MIN_SEQUENTIAL_ADVISORY_DIGITS and (
        _ASCENDING_DIGITS.startswith(number) or _ASCENDING_DIGITS[1:].startswith(number)
    )
    return sequential or _ADVISORY_PLACEHOLDER_RUN.search(number) is not None


def _backed_advisories(dependencies: Sequence[Any]) -> frozenset[str]:
    """Every advisory id, and every alias of one, this session's dependency scan found."""
    return frozenset(
        advisory.upper()
        for dep in dependencies
        for vulnerability in getattr(dep, "vulnerabilities", None) or ()
        for advisory in (vulnerability.id, *getattr(vulnerability, "aliases", ()))
    )


def _strip_unbacked_advisories(finding: Finding, dependencies: Sequence[Any]) -> Finding:
    """The finding without the advisories in its references no scanned dependency carries.

    The CVEs a model cites come from its training, not from the code: session
    `20261001-224227` cited Log4j, polkit and OpenSSH advisories against a Python CLI whose
    dependencies the same run scanned clean, and the report headlined one. An advisory stays
    only when a vulnerability record of this session carries it, by id or alias; a note says
    which left. A finding left with no reference had that advisory as its only evidence.
    """
    backed = _backed_advisories(dependencies)

    def unbacked_in(reference: str) -> set[str]:
        return {advisory.upper() for advisory in _ADVISORY_ID.findall(reference)} - backed

    unbacked = sorted(set().union(*map(unbacked_in, finding.references)))
    if not unbacked:
        return finding
    listed = ", ".join(unbacked)
    stripped = finding.model_copy(
        update={
            "references": [ref for ref in finding.references if not unbacked_in(ref)],
            "reference_note": f"Removed {listed}: no dependency this session scanned carries it",
        }
    )
    if stripped.references:
        return stripped
    return apply_verdict(
        stripped,
        "INVALIDATED",
        by="deterministic:unbacked_advisory",
        reason=f"Its only evidence was {listed}, which no dependency this session scanned carries",
    )


def _check_scanned_clean_dependency(
    finding: Finding, dependencies: Sequence[Any]
) -> Finding | None:
    """Invalidate a vulnerability claim against a dependency this run already scanned clean.

    The pipeline resolves advisories for every pinned dependency and writes the verdicts
    into the same artifact as the findings. When a claim names a package the scan reports
    `CLEAN` with no advisory records, the artifact contradicts itself, and the scan is the
    side with a source.

    Session `20260922-034125` reported FastAPI and Uvicorn as carrying unpatched CVEs while
    its own `external_dependencies` listed both `CLEAN` with an empty vulnerability list.
    """
    if not dependencies:
        return None

    text = f"{finding.title} {finding.description or ''}".lower()
    if not any(word in text for word in ("vulnerab", "cve", "advisory", "outdated", "unpatched")):
        return None

    named = [
        dep
        for dep in dependencies
        if getattr(dep, "name", "") and re.search(rf"\b{re.escape(str(dep.name).lower())}\b", text)
    ]
    if not named or any(
        getattr(dep, "vulnerabilities", None)
        or str(getattr(dep, "severity", "UNCHECKED")).upper() != "CLEAN"
        for dep in named
    ):
        return None

    listed = ", ".join(sorted(str(dep.name) for dep in named))
    return apply_verdict(
        finding,
        "INVALIDATED",
        by="deterministic:scanned_clean_dependency",
        reason=(
            f"This run's own advisory scan reports {listed} CLEAN with no advisory "
            "records at the pinned versions"
        ),
    )


def _check_placeholder_advisory_hallucination(
    finding: Finding, dependencies: Sequence[Any] = ()
) -> Finding | None:
    """Invalidate a vulnerability claim whose only evidence is a placeholder advisory id.

    Dependency advisories come from the scanners, which look them up. When the identifier is
    a placeholder, nothing was looked up, and the surrounding claim was produced by the same
    step that could not name it. An id a record of `dependencies`, this session's scan, carries
    was looked up, whatever its digits: the check invalidated Trivy's own finding of
    CVE-2020-11111 (#948).
    """
    text = f"{finding.title} {finding.description or ''} {' '.join(finding.references or [])}"
    backed = _backed_advisories(dependencies)
    placeholder = next(
        (
            advisory
            for advisory in _ADVISORY_ID.findall(text)
            if _is_placeholder_advisory(advisory) and advisory.upper() not in backed
        ),
        None,
    )
    if placeholder is None:
        return None
    return apply_verdict(
        finding,
        "INVALIDATED",
        by="deterministic:placeholder_advisory",
        reason=(
            f"Cites {placeholder!r}, an advisory id written as a placeholder that no dependency "
            "this session scanned carries; dependency advisories come from the scanners"
        ),
    )


_UNSUPPORTED_RUNTIME_PATTERN = re.compile(
    r"python\s*(?:<|below|before|earlier than|older than)?\s*3\.(\d+)", re.IGNORECASE
)


def _check_unsupported_runtime_hallucination(finding: Finding, file_path: Path) -> Finding | None:
    """Invalidate a compatibility claim about a Python the reviewed project does not support.

    `requires-python` is the declared support floor. A finding that a module breaks on an
    interpreter below it describes a configuration that cannot occur: the installer refuses
    it before any import runs. The floor is the reviewed project's, found from the file.
    """
    text = f"{finding.title} {finding.description or ''}".lower()
    if not any(word in text for word in ("incompatible", "compatib", "importerror", "raises")):
        return None

    floor = _declared_python_floor(_nearest_pyproject(file_path))
    if floor is None:
        return None

    cited = [int(m.group(1)) for m in _UNSUPPORTED_RUNTIME_PATTERN.finditer(text)]
    if not cited or max(cited) >= floor:
        return None

    return apply_verdict(
        finding,
        "INVALIDATED",
        by="deterministic:unsupported_runtime",
        reason=(
            f"Describes a failure on Python 3.{max(cited)}, below the declared "
            f"`requires-python` floor of 3.{floor}, which cannot be installed"
        ),
    )


def _nearest_pyproject(file_path: Path) -> Path | None:
    """The pyproject.toml of the project a file belongs to."""
    for directory in file_path.resolve().parents:
        candidate = directory / "pyproject.toml"
        if candidate.is_file():
            return candidate
        if (directory / ".git").exists():
            return None
    return None


@functools.lru_cache(maxsize=32)
def _declared_python_floor(pyproject: Path | None) -> int | None:
    """Return the minor version of a project's `requires-python` floor."""
    if pyproject is None:
        return None
    try:
        raw = pyproject.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r'requires-python\s*=\s*"[^"]*?3\.(\d+)', raw)
    return int(match.group(1)) if match else None


# Whole words: "sse" inside "processed" or "health" inside "healthy" is not a protocol.
_HEALTH_ENDPOINT = re.compile(r"\bhealth(?:z|check)?\b|\bliveness\b|\breadiness\b")
_EVENT_STREAM = re.compile(r"\bsse\b|\bserver-sent\b|\bevent[- ]stream\b|\bwebsockets?\b")


def _is_health_endpoint_version_claim(title_desc: str, loc: str) -> bool:
    return bool(re.search(r"\bversion\b", title_desc)) and bool(
        _HEALTH_ENDPOINT.search(loc) or _HEALTH_ENDPOINT.search(title_desc)
    )


def _is_stream_event_timestamp_claim(title_desc: str, loc: str) -> bool:
    return bool(re.search(r"\btimestamps?\b", title_desc)) and bool(
        _EVENT_STREAM.search(loc) or _EVENT_STREAM.search(title_desc)
    )


def _check_operational_protocol_hallucination(finding: Finding) -> Finding | None:
    """Invalidate claims that health probe versions or stream event timestamps are leaks."""
    text = (finding.title + " " + (finding.description or "")).lower()
    loc = finding.location.lower()
    if _is_health_endpoint_version_claim(text, loc):
        return apply_verdict(
            finding,
            "INVALIDATED",
            by="deterministic:operational_protocol",
            reason=(
                "Matches verified common hallucination [HALLUCINATION-HEALTH-ENDPOINT-VERSION]: "
                "Health and liveness endpoints standardly provide service version for cluster orchestration"
            ),
        )
    if _is_stream_event_timestamp_claim(text, loc):
        return apply_verdict(
            finding,
            "INVALIDATED",
            by="deterministic:operational_protocol",
            reason=(
                "Matches verified common hallucination [HALLUCINATION-STREAM-EVENT-TIMESTAMP]: "
                "Real-time event streams require timestamps for event sequencing and client synchronization"
            ),
        )
    return None


def _check_test_fixture_credential_hallucination(
    finding: Finding, file_path: Path
) -> Finding | None:
    """Invalidate claims of hardcoded secrets or credentials in test fixtures or mock test files."""
    loc_file = finding.location.split(":")[0].strip()
    p = Path(loc_file)
    is_test = any(part in {"tests", "test", "fixtures"} for part in p.parts) or p.name.startswith(
        ("test_", "mock_")
    )
    if not is_test:
        return None
    title_lower = finding.title.lower()
    desc_lower = (finding.description or "").lower()
    if not any(kw in title_lower or kw in desc_lower for kw in CONST_FIXTURE_CREDENTIAL_KEYWORDS):
        return None
    # A real credential committed to a test directory is still a leak. Only a cited value that
    # is plainly synthetic ("test-token", "changeme", "dummy") is a fixture.
    window = _cited_window(finding, file_path, 2)
    values = re.findall(r"[\"']([^\"'\n]{3,})[\"']", window)
    finding_text = f"{title_lower} {desc_lower}"
    has_placeholder = any(_PLACEHOLDER_SECRET.search(v) for v in values) or bool(
        re.search(
            r"\b(?:sk-(?:gateway|wrong|test|dummy|mock)|example\.com|00000000)\b", finding_text
        )
    )
    if not has_placeholder:
        return None
    return apply_verdict(
        finding,
        "INVALIDATED",
        by="deterministic:test_fixture_credential",
        reason=(
            "Matches verified common hallucination [HALLUCINATION-TEST-MOCK-CRED]: "
            "the cited test credential is a synthetic placeholder"
        ),
    )


def _is_var_assigned_before(
    node: ast.FunctionDef | ast.AsyncFunctionDef, var_name: str, target_line: int
) -> int | None:
    """Check if variable is assigned in function body before target line."""
    for stmt in node.body:
        stmt_line = getattr(stmt, "lineno", 0)
        if stmt_line < target_line and isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == var_name:
                    return stmt_line
    return None


def _extract_uninitialized_var_name(title: str, desc: str) -> str | None:
    import re

    match = re.search(r"['\"`]([a-zA-Z0-9_]+)['\"`]", title) or re.search(
        r"['\"`]([a-zA-Z0-9_]+)['\"`]", desc
    )
    return match.group(1) if match else None


def _extract_location_line(location: str) -> int:
    if ":" not in location:
        return 0
    try:
        line_part = location.split(":", 1)[1].strip()
        nums = [int(x) for x in line_part.replace("-", " ").split() if x.isdigit()]
        return nums[0] if nums else 0
    except ValueError, IndexError:
        return 0


def _find_enclosing_fn_assignment(tree: ast.AST, var_name: str, target_line: int) -> int | None:
    """An assignment before the line in the innermost function containing it.

    An outer function's assignment does not bind the name in a nested one: `count += 1` in a
    closure without `nonlocal count` raises UnboundLocalError.
    """
    enclosing = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.lineno <= target_line <= (node.end_lineno or node.lineno)
    ]
    if not enclosing:
        return None
    innermost = max(enclosing, key=lambda node: node.lineno)
    return _is_var_assigned_before(innermost, var_name, target_line)


def _is_uninitialized_claim(title_lower: str, desc_lower: str) -> bool:
    return any(kw in title_lower or kw in desc_lower for kw in CONST_UNINITIALIZED_CLAIM_KEYWORDS)


def _try_find_var_assignment(file_path: Path, var_name: str, target_line: int) -> int | None:
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(content, filename=str(file_path))
        return _find_enclosing_fn_assignment(tree, var_name, target_line)
    except (SyntaxError, OSError) as exc:
        logger.debug("Failed checking variable assignment in %s: %s", file_path, exc)
        return None


def _check_uninitialized_variable_hallucination(
    finding: Finding, file_path: Path
) -> Finding | None:
    """Check if variable claimed as uninitialized is actually initialized in enclosing function."""
    if not (file_path.exists() and file_path.is_file() and file_path.suffix == ".py"):
        return None
    if not _is_uninitialized_claim(finding.title.lower(), (finding.description or "").lower()):
        return None

    var_name = _extract_uninitialized_var_name(finding.title, finding.description or "")
    if not var_name:
        return None

    target_line = _extract_location_line(finding.location)
    assign_line = _try_find_var_assignment(file_path, var_name, target_line)
    if assign_line is not None:
        return apply_verdict(
            finding,
            "INVALIDATED",
            by="deterministic:uninitialized_variable",
            reason=(
                f"Matches verified common hallucination "
                f"[HALLUCINATION-UNINITIALIZED-VARIABLE-ABOVE-LOOP]: "
                f"Variable '{var_name}' is explicitly initialized at line {assign_line} before reference"
            ),
        )
    return None


# Reasoning that opens a title; inside a title the same words describe a defect ("Clients of
# the API need to send the token in the query"). Praise counts anywhere unless negated ("Rate
# limiter not properly implemented").
_MONOLOGUE_TITLE = re.compile(CONST_MONOLOGUE_PREFIXES)
_COMPLIMENT_PHRASE = re.compile(CONST_COMPLIMENT_PHRASES)
# A negation or defect word turns praise wording into a finding.
_COMPLIMENT_NEGATION = re.compile(CONST_COMPLIMENT_NEGATIONS)


def _check_conversational_monologue(title_lower: str, finding: Finding) -> Finding | None:
    if _MONOLOGUE_TITLE.match(title_lower.strip()):
        return apply_verdict(
            finding,
            "INVALIDATED",
            by="deterministic:conversational_monologue",
            reason="Conversational scratchpad chain-of-thought monologue leaked into finding title",
        )
    return None


def _check_benign_compliment(title_lower: str, finding: Finding) -> Finding | None:
    desc_lower = (finding.description or "").lower()
    is_doc_narrative = title_lower.startswith(
        (
            "documentation of ",
            "documentation explains ",
            "documentation introduces ",
            "documentation provides ",
            "documentation clarification ",
            "documentation context ",
        )
    ) or desc_lower.startswith(
        (
            "the documentation correctly ",
            "the documentation explains ",
            "the documentation introduces ",
            "the documentation provides ",
        )
    )
    if is_doc_narrative or (
        _COMPLIMENT_PHRASE.search(title_lower) and not _COMPLIMENT_NEGATION.search(title_lower)
    ):
        return apply_verdict(
            finding,
            "INVALIDATED",
            by="deterministic:benign_compliment",
            reason="Conversational praise, narrative summary, or benign observation without a concrete defect",
        )
    return None


def _check_masked_placeholder_syntax_error(
    finding: Finding, title_lower: str, desc_lower: str
) -> Finding | None:
    has_marker = (
        "<masked-" in finding.title
        or "<masked-" in desc_lower
        or "***redacted***" in finding.title.lower()
        or "***redacted***" in desc_lower
    )
    if not has_marker:
        return None
    if "placeholder <masked-" in desc_lower or "placeholder <masked-" in title_lower:
        return apply_verdict(
            finding,
            "INVALIDATED",
            by="deterministic:masked_placeholder_syntax_error",
            reason=(
                "Matches verified common hallucination [HALLUCINATION-MASKED-SECRET]: "
                "Sanitization marker '<masked-*>' is a prompt redaction indicator, not a live secret or hardcoded credential"
            ),
        )
    if _SECRET_EXPOSURE_CLAIM.search(f"{title_lower} {desc_lower}"):
        return None
    if any(
        phrase in title_lower or phrase in desc_lower
        for phrase in CONST_MASKED_SYNTAX_ERROR_PHRASES
    ):
        return apply_verdict(
            finding,
            "INVALIDATED",
            by="deterministic:masked_placeholder_syntax_error",
            reason=(
                "Sanitization marker '<masked-*>' or '***redacted***' is a prompt redaction indicator, "
                "not an invalid identifier, undefined placeholder, or runtime defect"
            ),
        )
    return None


def _check_localhost_default_url_hallucination(finding: Finding) -> Finding | None:
    text = f"{finding.title} {finding.description or ''}".lower()
    is_localhost = "localhost" in text or "127.0.0.1" in text
    is_default = "default" in text or "config" in text
    is_ssrf = "ssrf" in text or "insecure default" in text or "arbitrary internal" in text
    if is_localhost and is_default and is_ssrf:
        return apply_verdict(
            finding,
            "INVALIDATED",
            by="deterministic:localhost_default_config",
            reason=(
                "Matches verified common hallucination [HALLUCINATION-LOCALHOST-DEFAULT-CONFIG]: "
                "Default configuration URLs pointing to localhost or 127.0.0.1 are mandated by project "
                "configuration hygiene conventions."
            ),
        )
    return None


def _check_posix_signal_zero_liveness_hallucination(finding: Finding) -> Finding | None:
    text = f"{finding.title} {finding.description or ''}".lower()
    has_signal = "os.kill" in text or "signal 0" in text or "process signal" in text
    has_race = "race condition" in text or "pid" in text or "reuse" in text or "liveness" in text
    if has_signal and has_race:
        return apply_verdict(
            finding,
            "INVALIDATED",
            by="deterministic:posix_signal_zero_liveness",
            reason=(
                "Matches verified common hallucination [HALLUCINATION-POSIX-SIGNAL-ZERO-LIVENESS]: "
                "Standard POSIX os.kill(pid, 0) process existence checking is the canonical standard library "
                "mechanism to test process liveness without delivering a signal."
            ),
        )
    return None


def _check_pre_1_0_breaking_change_hallucination(finding: Finding) -> Finding | None:
    text = f"{finding.title} {finding.description or ''}".lower()
    has_compat = "backward" in text or "backwards" in text or "breaking change" in text
    has_flag = "flag naming" in text or "cli flag" in text or "compatibility" in text
    if has_compat and has_flag:
        return apply_verdict(
            finding,
            "INVALIDATED",
            by="deterministic:pre_1_0_breaking_change",
            reason=(
                "Matches verified common hallucination [HALLUCINATION-PRE-1-0-BREAKING-CHANGE]: "
                "devops-cli is alpha software prior to release 1.0.0 with zero backwards compatibility guarantees; "
                "interface evolutions and flag alterations are explicitly permitted."
            ),
        )
    return None


def _check_structural_tuple_equality_hallucination(
    finding: Finding, file_path: Path
) -> Finding | None:
    parts = set(file_path.parts)
    is_test = bool(
        parts & {"tests", "test"}
        or file_path.name.startswith("test_")
        or file_path.name.endswith("_test.py")
    )
    if not is_test:
        return None
    text = f"{finding.title} {finding.description or ''}".lower()
    if not any(kw in text for kw in ("tuple", "assertion logic", "assertion")):
        return None
    window = _cited_window(finding, file_path, 2)
    if "assert (" in window or "assert tuple(" in window or ") == (" in window:
        return apply_verdict(
            finding,
            "INVALIDATED",
            by="deterministic:structural_tuple_equality",
            reason=(
                "Matches verified common hallucination [HALLUCINATION-STRUCTURAL-TUPLE-EQUALITY]: "
                "Consolidated structural tuple equality assertions (assert (...) == (...)) in test suites "
                "are a mandatory architectural invariant to cap McCabe cyclomatic complexity M <= 10 while "
                "preserving element-level diff diagnostics."
            ),
        )
    return None


# A claim about Python's None, spelled as code. English "if none of the roles match" is not.
_NONE_DEREFERENCE_CLAIM = re.compile(
    r"\bNoneType\b|\bNone\b[^\n]{0,60}\b(?:attribute|dereference|access|AttributeError)"
    r"|\b(?:AttributeError|[Dd]ereferenc\w*|access\w*)\b[^\n]{0,80}\bNone\b"
    r"|(?i:\bnull\s+(?:pointer|dereference)\b)"
)


# One probe at a time: concurrent verification workers would each make a cold pass over the
# same imports, where the first warms the shared cache for the rest.
_TYPECHECK_PROBE_LOCK = threading.Lock()


def _typecheck_probe_cache_dir() -> Path:
    """Where the probe keeps mypy's cache: devops-cli's cache directory, one per interpreter
    and probe config.

    A cold `mypy --strict` pass over a large module's imports takes about a minute, near the
    probe's timeout, and the cache carries it across probes and reviews. It is data mypy reads,
    never code it runs.
    """
    from devops_cli.ai.run_store import digest
    from devops_cli.config.env import ENV_DATA_DIR
    from devops_cli.config.settings import load_settings
    from devops_cli.core.repo import resolve_data_path

    env_data_dir = os.environ.get(ENV_DATA_DIR)
    cache_dir = (
        Path(env_data_dir) / CONST_CACHE_DIR_NAME
        if env_data_dir
        else load_settings().data.cache_dir
    )
    key = digest([sys.executable, CONST_TYPECHECK_PROBE_MYPY_CONFIG])
    return resolve_data_path(cache_dir) / CONST_TYPECHECK_PROBE_CACHE_DIR_NAME / key


@functools.lru_cache(maxsize=256)
def _module_typechecks_clean(path_str: str, mtime: float) -> bool:
    """Report whether a module passes strict type checking.

    The module belongs to the tree under review, which is untrusted, so nothing of that tree
    may run (#946). `uv run` would sync the target's project and run its build backend, mypy
    would load the config and plugins of the directory it starts in, and `python -m` would
    import from there, or from a `PYTHONPATH` naming the target. So this interpreter's own mypy
    checks the module in isolated mode (`-I`, which ignores `PYTHON*` variables and keeps the
    working directory off `sys.path`), from an empty temporary directory, with devops-cli's
    own config and its own cache.

    Cached on path and mtime: verification examines many findings against the same few
    files, and a type check per finding would dominate the run.
    """
    from devops_cli.core.process import run_subprocess

    module = str(Path(path_str).absolute())
    try:
        with (
            _TYPECHECK_PROBE_LOCK,
            tempfile.TemporaryDirectory(prefix="devops-typecheck-") as probe_dir,
        ):
            config = Path(probe_dir) / "mypy.ini"
            config.write_text(CONST_TYPECHECK_PROBE_MYPY_CONFIG, encoding="utf-8")
            result = run_subprocess(
                [
                    sys.executable,
                    "-I",
                    "-m",
                    "mypy",
                    "--strict",
                    "--config-file",
                    str(config),
                    "--cache-dir",
                    str(_typecheck_probe_cache_dir()),
                    module,
                ],
                cwd=Path(probe_dir),
                check=False,
                quiet=True,
                timeout=DEFAULT_TYPECHECK_PROBE_TIMEOUT_SECONDS,
            )
    except Exception as exc:
        logger.debug("Type check probe failed for %s: %s", path_str, exc)
        return False
    return result.returncode == 0


def _check_none_dereference_hallucination(finding: Finding, file_path: Path) -> Finding | None:
    """Invalidate a claimed None dereference in a module that type checks strictly.

    A finding asserting an AttributeError on a possibly-None attribute is a claim about
    types. If the cited module passes `mypy --strict`, the attribute is not Optional and the
    runtime failure described cannot occur; if mypy cannot type check it cleanly for any
    reason, such as a target whose imports this interpreter cannot resolve, nothing is
    claimed and the finding proceeds to the model verifier as before.

    This exists because two findings of exactly this shape were marked VERIFIED at 0.94
    confidence against fields the schema declares as plain `str`.
    """
    if not (file_path.exists() and file_path.is_file() and file_path.suffix.lower() == ".py"):
        return None

    if not _NONE_DEREFERENCE_CLAIM.search(f"{finding.title} {finding.description or ''}"):
        return None

    try:
        mtime = file_path.stat().st_mtime
    except OSError:
        return None
    if not _module_typechecks_clean(str(file_path), mtime):
        return None

    res = apply_verdict(
        finding,
        "INVALIDATED",
        by="deterministic:none_dereference",
        reason=(
            "Module passes `mypy --strict`, so the attribute is not Optional and the "
            "described None dereference is not reachable"
        ),
    )
    try:
        from devops_cli.ai.review.common_hallucinations import auto_record_invalidated_finding

        auto_record_invalidated_finding(res, file_path=file_path, reason=res.invalidation_reason)
    except Exception:
        pass
    return res


def _check_code_file_hallucinations(finding: Finding, file_path: Path) -> Finding | None:
    """Run deterministic checks against resolved target code file."""
    for checker in (
        _check_test_fixture_credential_hallucination,
        _check_structural_tuple_equality_hallucination,
        _check_uninitialized_variable_hallucination,
        _check_syntax_error_hallucination,
        _check_unsupported_runtime_hallucination,
        _check_missing_symbol_hallucination,
        _check_missing_header_hallucination,
        _check_none_dereference_hallucination,
    ):
        res = checker(finding, file_path)
        if res:
            return res
    return None


def _check_catalog_hallucination(finding: Finding, file_path: Path) -> Finding:
    """Check finding against dynamic common hallucinations catalog."""
    try:
        from devops_cli.ai.review.common_hallucinations import (
            auto_record_invalidated_finding,
            is_common_hallucination,
            verify_ground_truth_hallucination,
        )

        match = is_common_hallucination(finding, threshold=0.7, file_path=file_path)
        if match and verify_ground_truth_hallucination(finding, match.hallucination, file_path):
            entry = match.hallucination
            auto_record_invalidated_finding(finding, file_path=file_path, reason=entry.resolution)
            return apply_verdict(
                finding,
                "INVALIDATED",
                by="deterministic:catalog_hallucination",
                reason=f"Matches verified common hallucination [{entry.id}]: {entry.resolution}",
            )
    except Exception:
        pass
    return finding


def _check_verdict_polarity_hallucination(finding: Finding) -> Finding | None:
    """Invalidate findings where observed and expected concrete values match."""
    obs = finding.observed_value
    exp = finding.expected_value
    if obs is not None and exp is not None and obs.strip().lower() == exp.strip().lower():
        return apply_verdict(
            finding,
            "INVALIDATED",
            by="deterministic:verdict_polarity",
            reason=(
                f"Observed value '{obs}' is identical to expected value '{exp}' (no defect polarity)"
            ),
        )
    return None


def _check_early_hallucinations(
    finding: Finding, dependencies: Sequence[Any] | None
) -> Finding | None:
    title_lower = finding.title.lower()
    desc_lower = (finding.description or "").lower()
    early_results = [
        _check_verdict_polarity_hallucination(finding),
        _check_pathlib_resolve_hallucination(finding),
        _check_operational_protocol_hallucination(finding),
        _check_localhost_default_url_hallucination(finding),
        _check_posix_signal_zero_liveness_hallucination(finding),
        _check_pre_1_0_breaking_change_hallucination(finding),
        _check_conversational_monologue(title_lower, finding),
        _check_benign_compliment(title_lower, finding),
        _check_masked_placeholder_syntax_error(finding, title_lower, desc_lower),
        _check_placeholder_advisory_hallucination(finding, dependencies or ()),
        _check_scanned_clean_dependency(finding, dependencies or ()),
    ]
    for res in early_results:
        if res:
            return res
    return None


def _run_file_level_deterministic_checks(
    finding: Finding,
    file_path: Path,
    effective_root: Path | None,
    removed_symbols: set[str] | None,
    diff_hunks: list[tuple[int, int]] | None,
) -> Finding:
    finding = _drop_out_of_range_lines(finding, file_path)
    if code_res := _check_code_file_hallucinations(finding, file_path):
        return code_res

    finding = validate_construct_location(
        finding, file_path, removed_symbols=removed_symbols, diff_hunks=diff_hunks
    )
    if finding.status in {"INVALIDATED", "MITIGATED"}:
        return finding

    finding = _check_catalog_hallucination(finding, file_path)
    if finding.status in {"INVALIDATED", "MITIGATED"}:
        return finding

    if effective_root and effective_root.is_dir():
        from devops_cli.ai.review.review_environment import execute_finding_criteria

        finding = execute_finding_criteria(finding, effective_root)

    return finding


def _deterministic_pre_verification(
    finding: Finding,
    repo_root: Path | None = None,
    target_dir: Path | None = None,
    dependencies: Sequence[Any] | None = None,
    removed_symbols: set[str] | None = None,
    diff_hunks: list[tuple[int, int]] | None = None,
    **kwargs: Any,
) -> Finding:
    """Run local deterministic parser, line boundary, and hallucination checks to invalidate obvious false positives."""
    early_res = _check_early_hallucinations(finding, dependencies)
    if early_res:
        return early_res
    if finding.status == "UNVERIFIED":
        finding = _strip_unbacked_advisories(finding, dependencies or ())
        if finding.status == "INVALIDATED":
            return finding

    loc_file = finding.location.split(":")[0].strip()
    if not loc_file or _is_secret_path(loc_file):
        return finding

    effective_root = repo_root or target_dir
    file_path = _resolve_target_file(loc_file, effective_root)
    if file_path is None:
        return finding

    return _run_file_level_deterministic_checks(
        finding, file_path, effective_root, removed_symbols, diff_hunks
    )


_NO_VALUES = frozenset({"", "none", "null", "n/a", "na", "[]", "-"})


def _verdict_bool(value: object) -> bool | None:
    """A verdict flag as the model meant it; the string "false" is not true."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "yes", "1"}:
            return True
        if text in {"false", "no", "0"} or text in _NO_VALUES:
            return False
    return None


def _verdict_list(value: object) -> list[str]:
    """Matched criteria as a list; "none" or a bare string is not a list of characters."""
    items = value if isinstance(value, list) else [value] if isinstance(value, str) else []
    return [str(x).strip() for x in items if str(x).strip().lower() not in _NO_VALUES]


def _extract_mitigating_mechanism(item: dict[str, Any], reason: str) -> str | None:
    """Extract named mitigating mechanism from verdict item or reason."""
    for key in ("mitigating_mechanism", "mechanism", "mitigation"):
        val = item.get(key)
        if val is not None and str(val).strip() and str(val).strip().lower() not in _NO_VALUES:
            return str(val).strip()
    if reason:
        m = re.search(
            r"\b(?:mechanism|mitigated by|mitigation):\s*([^,.\n;]+)",
            reason,
            re.IGNORECASE,
        )
        if m:
            return m.group(1).strip()
    return None


def _extract_perimeter_from_keys(item: dict[str, Any]) -> list[str]:
    """Extract perimeter file paths from verdict item dictionary keys."""
    for key in ("perimeter_files", "perimeter", "perimeters"):
        val = item.get(key)
        if isinstance(val, list):
            res = [
                str(x).strip()
                for x in val
                if str(x).strip() and str(x).strip().lower() not in _NO_VALUES
            ]
            if res:
                return res
        if isinstance(val, str) and str(val).strip() and str(val).strip().lower() not in _NO_VALUES:
            return [str(val).strip()]
    return []


def _extract_perimeter_from_reason(reason: str) -> list[str]:
    """Extract perimeter file paths from reason text pattern."""
    if not reason:
        return []
    m = re.search(r"\b(?:perimeter_files|perimeter|perimeters):\s*([^;\n]+)", reason, re.IGNORECASE)
    if not m:
        return []
    parts = [p.strip().strip("`'\"[]") for p in m.group(1).split(",")]
    return [p for p in parts if p and p.lower() not in _NO_VALUES]


def _extract_perimeter_files(item: dict[str, Any], reason: str) -> list[str]:
    """Extract perimeter file paths from verdict item or reason."""
    return _extract_perimeter_from_keys(item) or _extract_perimeter_from_reason(reason)


def _extract_regression_test(item: dict[str, Any]) -> str | None:
    """Extract regression test path from verdict item."""
    for key in ("regression_test", "test", "regression"):
        val = item.get(key)
        if val is not None and str(val).strip() and str(val).strip().lower() not in _NO_VALUES:
            return str(val).strip()
    return None


def _is_placeholder(val: Any) -> bool:
    """Return True if val is None, empty, or a recognized placeholder like 'none', 'n/a'."""
    if val is None:
        return True
    if isinstance(val, (list, tuple, set)):
        return not val or all(_is_placeholder(item) for item in val)
    s = str(val).strip().lower()
    return not s or s in CONST_PLACEHOLDER_VALUES


def _refutes(item: dict[str, Any], inv_matched: list[str]) -> bool:
    """Whether a verdict refutes its finding: it matched invalidation criteria or says so."""
    status = str(item.get("status") or "").strip().upper()
    flagged = _verdict_bool(item.get("invalidated")) is True
    return bool(inv_matched) or flagged or status == "INVALIDATED"


def _verdict_status(item: dict[str, Any], inv_matched: list[str]) -> tuple[str, bool]:
    """The status and reportability a verdict supports.

    Only clear evidence removes a finding. A verdict that both confirms and refutes it, or that
    declines to confirm it without naming invalidating evidence, leaves it unverified and in
    the report, as a finding with no verdict is.
    """
    verified = _verdict_bool(item.get("verified"))
    status = str(item.get("status") or "").strip().upper()
    refuted = _refutes(item, inv_matched)
    confirmed = verified is True or status == "VERIFIED"
    if refuted and confirmed:
        return "UNVERIFIED", True
    if refuted:
        return "INVALIDATED", False
    if _verdict_bool(item.get("mitigated")) or status == "MITIGATED":
        # A mitigation is a claim about the code too: without a reason naming the mechanism
        # and perimeter files it proves nothing, degrading to UNVERIFIED (reportable=True).
        reason_str = str(item.get("reason") or "").strip()
        mech_val = item.get("mitigating_mechanism") or item.get("mechanism")
        perim_val = item.get("perimeter_files") or item.get("perimeter")
        has_mech = not _is_placeholder(mech_val) or bool(
            reason_str and not _is_placeholder(_extract_mitigating_mechanism(item, reason_str))
        )
        has_perim = not _is_placeholder(perim_val) or bool(
            reason_str and not _is_placeholder(_extract_perimeter_files(item, reason_str))
        )
        if not reason_str or not has_mech or not has_perim:
            return "UNVERIFIED", True
        return "MITIGATED", True
    if confirmed:
        return "VERIFIED", _verdict_bool(item.get("reportable")) is not False
    return "UNVERIFIED", True


# Words too common to tell one claim from another.
_CLAIM_STOPWORDS = frozenset(
    {"the", "a", "an", "of", "to", "in", "is", "are", "as", "for", "with", "that", "this"}
    | {"and", "or", "be", "it", "its", "on", "by", "at", "still", "which", "verify", "check"}
)
# A reason that negates what it quotes may be a refutation; one that does not only restates.
_NEGATION = re.compile(
    r"\b(?:not|no|never|none|cannot|without|already|isn't|doesn't|don't|aren't|wasn't)\b|n't\b"
)
_RESTATEMENT_OVERLAP = 0.6


def _claim_words(text: Any) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", str(text).lower()) if w not in _CLAIM_STOPWORDS}


def _covers(text: str, claims: list[Any]) -> float:
    """The largest share of any claim's words that the text contains."""
    words = _claim_words(text)
    shares = [len(cw & words) / len(cw) for claim in claims if (cw := _claim_words(claim))]
    return max(shares, default=0.0)


def _restates_the_finding(criterion: str, f: Finding) -> bool:
    """Whether a "matched invalidation criterion" only restates the defect or its fix.

    Models file the finding's own verification criterion, or the fix, as the invalidation they
    matched: "The FROM directive still uses 'latest' as the image tag." That confirms the
    defect. A criterion closer to the finding's invalidation criteria than to its claim and fix
    is a refutation.
    """
    ver_claims = [str(c) for c in f.verification_criteria]
    inv_claims = [str(c) for c in f.invalidation_criteria]
    claim = _covers(criterion, [*ver_claims, f.title, f.fix])
    refutation = _covers(criterion, inv_claims)
    return claim >= _RESTATEMENT_OVERLAP and claim > refutation


def _reason_confirms(reason: str, f: Finding) -> bool:
    """Whether the verdict's reason states the claimed condition without negating it."""
    ver_claims = [str(c) for c in f.verification_criteria]
    return (
        bool(reason)
        and not _NEGATION.search(reason.lower())
        and _covers(reason, [*ver_claims, f.title]) >= _RESTATEMENT_OVERLAP
    )


def _without_self_refutation(
    f: Finding, item: dict[str, Any]
) -> tuple[dict[str, Any], list[str], bool]:
    """The verdict with its invalidation withdrawn when it rests only on the finding's own claim,
    the invalidation criteria it still matches, and whether an invalidation was withdrawn.

    An invalidation whose matched criteria all restate the defect or its fix, or whose reason
    confirms the claimed condition, names no evidence against the finding; it leaves the
    finding unverified and in the report.
    """
    inv_matched = _verdict_list(item.get("invalidated_criteria_matched"))
    if not _refutes(item, inv_matched):
        return item, inv_matched, False
    genuine = [c for c in inv_matched if not _restates_the_finding(c, f)]
    reason = str(item.get("reason") or "").strip()
    if genuine and not _reason_confirms(reason, f):
        return item, inv_matched, False
    if not inv_matched and not _reason_confirms(reason, f):
        return item, inv_matched, False
    withdrawn = {**item, "invalidated": False}
    if str(item.get("status") or "").strip().upper() == "INVALIDATED":
        withdrawn["status"] = ""
    return withdrawn, [], True


def _extract_citation_line(item: dict[str, Any]) -> int | None:
    """The line a verdict cites under an explicit citation key.

    The `location` a verdict echoes is the finding's own, and a number in its reason may be any
    line, so neither cites the line that settles the claim.
    """
    for key in ("citation_line", "cited_line", "line", "refutation_line"):
        val = item.get(key)
        if val is not None:
            try:
                return int(val)
            except ValueError, TypeError:
                pass
    return None


def _check_ast_symbol_at_line(
    file_path: Path, citation_line: int, candidates: Sequence[str]
) -> bool:
    """Check if AST symbols around citation_line match candidate tokens."""
    try:
        from devops_cli.ai.ast.engine import TreeSitterEngine

        engine = TreeSitterEngine()
        file_map = engine.parse_file(file_path)
        if file_map and file_map.symbols:
            cand_lowers = {c.lower() for c in candidates}
            for sym in file_map.symbols:
                if sym.span.line_start <= citation_line <= sym.span.line_end:
                    sym_lower = sym.name.lower()
                    if any(c in sym_lower or sym_lower in c for c in cand_lowers):
                        return True
    except Exception:
        pass
    return False


def _validate_citation_line(
    f: Finding,
    citation_line: int | None,
    repo_root: Path | None,
) -> tuple[bool, int | None, str | None]:
    """Validate refutation citation line against file bounds and construct tokens."""
    if citation_line is None:
        return False, None, "Refutation missing cited line; downgraded to UNVERIFIED"
    if citation_line <= 0:
        return (
            False,
            citation_line,
            f"Refutation cited line {citation_line} is out of range; downgraded to UNVERIFIED",
        )

    loc_file = f.location.split(":")[0].strip()
    file_path = _resolve_target_file(loc_file, repo_root)
    if not (file_path and file_path.is_file()):
        return True, citation_line, None

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        if citation_line > len(lines):
            return (
                False,
                citation_line,
                f"Refutation cited line {citation_line} exceeds file length ({len(lines)} lines); downgraded to UNVERIFIED",
            )

        from devops_cli.ai.review.construct_validator import extract_finding_construct_candidates
        from devops_cli.ai.review_schema import _extract_code_symbols

        candidates = extract_finding_construct_candidates(f)
        if not candidates:
            candidates = list(_extract_code_symbols(f"{f.title} {f.description or ''}"))
        if not candidates:
            return True, citation_line, None

        cited_text = lines[citation_line - 1]
        line_matches = any(
            re.search(rf"\b{re.escape(cand)}\b", cited_text, re.IGNORECASE) for cand in candidates
        )
        if line_matches:
            return True, citation_line, None

        if _check_ast_symbol_at_line(file_path, citation_line, candidates):
            return True, citation_line, None

        return (
            False,
            citation_line,
            f"Refutation cited line {citation_line} does not contain cited construct tokens; downgraded to UNVERIFIED",
        )
    except Exception as exc:
        logger.debug("Failed citation line validation for %s: %s", file_path, exc)
        return True, citation_line, None


# A refutation of the finding's criteria ("tautological", "the criteria only check that it
# exists"), not of its claim. Without a cited line it says nothing about the code.
_REFUTES_THE_CRITERIA = re.compile(r"tautolog|criteri\w+ (?:only|merely)|only confirms", re.I)
_CRITERIA_REFUTATION_NOTE = (
    "Refutation is about the criteria, not the code, and cites no line; downgraded to UNVERIFIED"
)


def _extract_finding_confidence(conf_val: Any, default: float | None) -> float | None:
    """Normalize confidence score to bounded float in [0.0, 1.0]."""
    if conf_val is None:
        return default
    try:
        return max(0.0, min(1.0, float(conf_val)))
    except ValueError, TypeError:
        return default


def _determine_mitigated_degradation_note(
    reason: str, mech: str | None, perimeter: list[str]
) -> str:
    """Return specific reason why a claimed mitigation was degraded to UNVERIFIED."""
    if not reason:
        return "Mitigated verdict without explanation; degraded to UNVERIFIED"
    if not mech or _is_placeholder(mech):
        return "Mitigated verdict without specified mitigating mechanism; degraded to UNVERIFIED"
    if not perimeter or _is_placeholder(perimeter):
        return "Mitigated verdict without specified perimeter files; degraded to UNVERIFIED"
    return ""


def _resolve_status_and_verification_note(
    f: Finding,
    item: dict[str, Any],
    status_val: str,
    reason: str,
    citation_line: int | None,
    mitigating_mechanism: str | None,
    perimeter_files: list[str],
    repo_root: Path | None,
    is_rep: bool,
) -> tuple[str, str, int | None, str | None, bool]:
    """Resolve validated status, reason, citation line, verification note, and reportability."""
    if status_val == "INVALIDATED":
        if citation_line is None and _REFUTES_THE_CRITERIA.search(reason):
            return "UNVERIFIED", "", None, _CRITERIA_REFUTATION_NOTE, True
        is_valid, cit_line, note = _validate_citation_line(f, citation_line, repo_root)
        if not is_valid:
            return "UNVERIFIED", "", None, note, True
        return "INVALIDATED", reason, cit_line, None, False

    if status_val == "MITIGATED":
        note = (
            "Mitigated verdict without specified mitigating mechanism"
            if not mitigating_mechanism or _is_placeholder(mitigating_mechanism)
            else None
        )
        return "MITIGATED", reason, citation_line, note, True

    is_mitigated = (
        _verdict_bool(item.get("mitigated")) or str(item.get("status", "")).upper() == "MITIGATED"
    )
    if is_mitigated and status_val == "UNVERIFIED":
        note = _determine_mitigated_degradation_note(reason, mitigating_mechanism, perimeter_files)
        return "UNVERIFIED", reason, citation_line, note or None, True

    return status_val, reason, citation_line, None, is_rep


def _check_finding_polarity(
    obs: str | None, exp: str | None, status_val: str, reason: str
) -> tuple[str, str | None, str]:
    """Deterministic polarity check: identical observed and expected invalidates finding."""
    if obs and exp and str(obs).strip().lower() == str(exp).strip().lower():
        return (
            "INVALIDATED",
            "deterministic:verdict_polarity",
            f"Observed value '{obs}' is identical to expected value '{exp}' (polarity check)",
        )
    by = "llm" if status_val != "UNVERIFIED" else None
    return status_val, by, reason


def _resolve_finding_attributes(
    f: Finding, item: dict[str, Any]
) -> tuple[str, str, str | None, str | None]:
    """Resolve updated severity, location, observed value, and expected value.

    The verifier may only lower a severity (#948): it raised findings it had no more evidence
    for than the persona.
    """
    sev = less_severe(f.severity, item.get("severity", ""))
    raw_loc = item.get("location")
    if raw_loc is None or str(raw_loc).strip().lower() in ("none", "null", ""):
        loc = f.location
    else:
        new_loc = str(raw_loc).strip()
        loc = new_loc if new_loc != f.location else f.location

    obs_val = item.get("observed_value") or item.get("observed")
    exp_val = item.get("expected_value") or item.get("expected")
    final_obs = str(obs_val).strip() if obs_val is not None else f.observed_value
    final_exp = str(exp_val).strip() if exp_val is not None else f.expected_value
    return sev, loc, final_obs, final_exp


def _build_finding_verdict_kwargs(
    status_val: str,
    item: dict[str, Any],
    final_reportable: bool,
) -> dict[str, Any]:
    """Build extra keyword arguments for apply_verdict."""
    extra_kw: dict[str, Any] = {}
    if status_val == "MITIGATED" and _verdict_bool(item.get("verified")) is False:
        extra_kw["verified"] = False
    if final_reportable is False:
        extra_kw["reportable"] = False
    return extra_kw


def _no_verdict_note(f: Finding, withdrawn: bool) -> str:
    """Why a finding the verifier judged has no verdict, when no check of the verdict said.

    A withdrawn self-refutation says so. Criteria that passed both ways sent the finding to the
    verifier, and when it cannot decide either, that is still why. Otherwise the verifier was
    inconclusive: it neither confirmed, refuted nor found a mitigation, or it both confirmed
    and refuted.
    """
    if withdrawn:
        return CONST_VERIFIER_SELF_REFUTATION
    if f.verification_note == CONST_CRITERIA_NON_DISCRIMINATING:
        return CONST_CRITERIA_NON_DISCRIMINATING
    return CONST_VERIFIER_INCONCLUSIVE


def _apply_single_finding_verification(
    f: Finding,
    item: dict[str, Any] | None,
    now_iso: str,
    repo_root: Path | None = None,
) -> Finding:
    """Apply parsed LLM verification metadata to a single Finding."""
    if not isinstance(item, dict):
        return f

    ver_matched = _verdict_list(item.get("verified_criteria_matched"))
    item, inv_matched, withdrawn = _without_self_refutation(f, item)
    status_val, is_rep = _verdict_status(item, inv_matched)
    conf = _extract_finding_confidence(item.get("confidence_score"), f.confidence_score)

    merged_ver_matched = list(dict.fromkeys(f.verified_criteria_matched + ver_matched))
    merged_inv_matched = list(dict.fromkeys(f.invalidated_criteria_matched + inv_matched))

    raw_reason = str(item.get("reason") or "").strip()
    raw_citation = _extract_citation_line(item)
    mitigating_mechanism = _extract_mitigating_mechanism(item, raw_reason)
    perimeter_files = _extract_perimeter_files(item, raw_reason)
    regression_test = _extract_regression_test(item)

    status_val, reason, citation_line, verification_note, final_rep = (
        _resolve_status_and_verification_note(
            f,
            item,
            status_val,
            raw_reason,
            raw_citation,
            mitigating_mechanism,
            perimeter_files,
            repo_root,
            is_rep,
        )
    )

    sev, loc, final_obs, final_exp = _resolve_finding_attributes(f, item)
    status_val, by, reason = _check_finding_polarity(final_obs, final_exp, status_val, reason)
    extra_kw = _build_finding_verdict_kwargs(status_val, item, final_rep)
    if status_val == "UNVERIFIED" and verification_note is None:
        verification_note = _no_verdict_note(f, withdrawn)

    return apply_verdict(
        f,
        status_val,
        by=by,
        reason=reason if status_val in {"INVALIDATED", "MITIGATED"} else None,
        citation_line=citation_line,
        mitigating_mechanism=mitigating_mechanism if status_val == "MITIGATED" else None,
        perimeter_files=perimeter_files if status_val == "MITIGATED" else None,
        regression_test=regression_test if status_val == "MITIGATED" else None,
        verification_note=verification_note,
        confidence_score=conf,
        verified_at=now_iso if status_val != "UNVERIFIED" else None,
        severity=sev,
        severity_raw=(f.severity_raw or f.severity) if sev != f.severity else None,
        location=loc,
        observed_value=final_obs,
        expected_value=final_exp,
        verified_criteria_matched=merged_ver_matched,
        invalidated_criteria_matched=merged_inv_matched,
        criteria_execution_results=f.criteria_execution_results,
        **extra_kw,
    )


def _extract_verdict_pos_id(item: dict[str, Any]) -> int | None:
    """Extract positional identifier from finding_id, id, or index keys."""
    for key in ("finding_id", "id", "index"):
        val = item.get(key)
        if val is not None:
            try:
                return int(val)
            except ValueError, TypeError:
                return None
    return None


def _find_by_explicit_finding_id(
    unresolved: list[Finding], bound: dict[int, dict[str, Any]], pos_id: int
) -> tuple[bool, int | None]:
    """Check for finding explicitly assigned pos_id, returning (found, available_index)."""
    for idx, f in enumerate(unresolved):
        if f.finding_id is not None and f.finding_id == pos_id:
            return True, (idx if idx not in bound else None)
    return False, None


def _is_verdict_title_compatible(f_title: str, item_title: str) -> bool:
    """Check if model verdict title is compatible with candidate finding title."""
    clean_item = item_title.strip().lower()
    clean_f = f_title.strip().lower()
    if not clean_item or not clean_f:
        return True
    if clean_item in clean_f or clean_f in clean_item:
        return True
    words_f = set(re.findall(r"[a-z0-9]+", clean_f))
    words_item = set(re.findall(r"[a-z0-9]+", clean_item))
    overlap = words_f & words_item
    return len(overlap) >= 2 or (len(overlap) == 1 and len(words_item) <= 2)


def _is_oracle_verdict_match(f: Finding, item_title: str, item_loc: str) -> bool:
    """Check if finding matches verdict by title compatibility or location equivalence."""
    if not item_title or _is_verdict_title_compatible(f.title, item_title):
        return True
    return bool(item_loc and f.location == item_loc)


def _match_verdict_by_positional_oracle(
    unresolved: list[Finding],
    bound: dict[int, dict[str, Any]],
    item: dict[str, Any],
) -> int | None:
    """Resolve finding target using structural positional identifier if provided."""
    pos_id = _extract_verdict_pos_id(item)
    if pos_id is None:
        return None

    item_title = str(item.get("title") or "").strip()
    item_loc = str(item.get("location") or "").strip()
    found_explicit, explicit_idx = _find_by_explicit_finding_id(unresolved, bound, pos_id)
    if found_explicit and explicit_idx is not None:
        if _is_oracle_verdict_match(unresolved[explicit_idx], item_title, item_loc):
            return explicit_idx

    target_idx = (pos_id - 1) if (1 <= pos_id <= len(unresolved)) else (0 if pos_id == 0 else None)
    if target_idx is not None and target_idx not in bound:
        if _is_oracle_verdict_match(unresolved[target_idx], item_title, item_loc):
            return target_idx

    return None


def _bind_verdicts_to_findings(
    unresolved: list[Finding], items: list[Any]
) -> dict[int, dict[str, Any]]:
    """Match each model verdict to the finding it describes, using structural positional oracles or identity fallback.

    Primary resolution leverages structural positional enumeration (`finding_id`),
    eliminating title-drift vulnerabilities. Fallback matches by finding identity (title + normalized location).
    An item that matches nothing is dropped, and a finding that matches nothing keeps its status.
    """
    bound: dict[int, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        index = _match_verdict_by_positional_oracle(unresolved, bound, item)
        if index is None:
            title = str(item.get("title") or "").lower().strip()
            location = str(item.get("location") or "").lower().strip()
            index = _best_verdict_target(unresolved, bound, title, location)
        if index is None:
            logger.debug("Verification verdict matched no finding: %r", item)
            continue
        bound[index] = item
    return bound


def _best_verdict_target(
    unresolved: list[Finding], bound: dict[int, dict[str, Any]], title: str, location: str
) -> int | None:
    """The unclaimed finding a verdict names: by title, with the location breaking ties.

    A location alone never binds: two findings at one line would swap verdicts, a real SQL
    injection taking the invalidation meant for a style note beside it.
    """
    best: tuple[int, int] | None = None
    for index, finding in enumerate(unresolved):
        if index in bound or not _is_matching_finding(finding, title, location):
            continue
        score = (finding.title.lower().strip() == title) * 2 + (
            bool(location) and finding.location.lower().strip() == location
        )
        if best is None or score > best[0]:
            best = (score, index)
    return best[1] if best else None


def _verification_reply_cap(finding_count: int) -> int:
    """Reply tokens a verdict on ``finding_count`` findings may take, reasoning included."""
    return min(
        DEFAULT_REVIEW_VERIFICATION_REPLY_MAX_TOKENS,
        DEFAULT_REVIEW_VERIFICATION_REPLY_BASE_TOKENS
        + finding_count * DEFAULT_REVIEW_VERIFICATION_REPLY_TOKENS_PER_FINDING,
    )


def _extract_removed_symbols_for_file(
    loc_file: str, analysis_metas: dict[str, Any] | None
) -> set[str]:
    """Retrieve set of removed symbols for a file from analysis metadata."""
    if not analysis_metas or not loc_file:
        return set()
    meta = analysis_metas.get(loc_file)
    if meta is None:
        loc_pure = PurePosixPath(loc_file)
        for path_key, m in analysis_metas.items():
            if PurePosixPath(path_key).name == loc_pure.name:
                meta = m
                break
    if meta is None:
        return set()
    removed = getattr(meta, "symbols_removed", None)
    if isinstance(removed, list):
        return set(removed)
    if isinstance(meta, dict):
        return set(meta.get("symbols_removed") or [])
    return set()


def _extract_diff_hunks_for_file(
    loc_file: str,
    file_hunks: dict[str, list[tuple[int, int]]],
    all_hunks: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Retrieve diff hunk ranges for a cited file."""
    if not loc_file:
        return all_hunks
    if loc_file in file_hunks:
        return file_hunks[loc_file]
    loc_pure = PurePosixPath(loc_file)
    for path_key, hunks in file_hunks.items():
        if PurePosixPath(path_key).name == loc_pure.name:
            return hunks
    return all_hunks


def _run_deterministic_pre_verification_on_findings(
    findings: list[Finding],
    repo_root: Path | None,
    dependencies: Sequence[Any] | None,
    analysis_metas: dict[str, Any] | None,
    diff_segments: list[str],
) -> list[Finding]:
    """Apply deterministic pre-verification with removed symbol detection and diff hunk re-anchoring."""
    from devops_cli.ai.review.chunker import extract_diff_hunks, extract_file_diff_hunks

    file_hunks = extract_file_diff_hunks(diff_segments)
    all_hunks = extract_diff_hunks("\n".join(diff_segments))
    return [
        _deterministic_pre_verification(
            f,
            repo_root=repo_root,
            dependencies=dependencies,
            removed_symbols=_extract_removed_symbols_for_file(
                f.location.split(":")[0].strip(), analysis_metas
            ),
            diff_hunks=_extract_diff_hunks_for_file(
                f.location.split(":")[0].strip(), file_hunks, all_hunks
            ),
        )
        for f in findings
    ]


def _awaits_verdict(f: Finding) -> bool:
    """Whether the verifier is shown the finding: one no deterministic check settled."""
    return f.status == "UNVERIFIED" and f.verification_note != "cites removed symbol"


def _without_verdict(findings: list[Finding], note: str) -> list[Finding]:
    """The findings, each one the verifier was shown carrying `note` for why it has no verdict."""
    return [
        f.model_copy(update={"verification_note": note}) if _awaits_verdict(f) else f
        for f in findings
    ]


def _apply_bound_verdicts_to_findings(
    findings: list[Finding],
    bound: dict[int, dict[str, Any]],
    repo_root: Path | None,
) -> list[Finding]:
    """Apply bound verification verdicts to findings in order.

    A finding the reply gave no verdict on is noted as such, apart from one the verifier
    judged and left unverified, whose note says why its verdict settled nothing.
    """
    now_iso = datetime.now().isoformat()
    validated: list[Finding] = []
    unresolved_idx = 0
    for f in findings:
        if not _awaits_verdict(f):
            validated.append(f)
            continue
        item = bound.get(unresolved_idx)
        unresolved_idx += 1
        if item is None:
            validated.append(f.model_copy(update={"verification_note": CONST_VERIFIER_NO_VERDICT}))
            continue
        validated.append(_apply_single_finding_verification(f, item, now_iso, repo_root=repo_root))
    return validated


def _parse_verifier_payload(response: str) -> list[Any] | None:
    """The verdicts of a verifier reply; None when it holds no list of verdicts."""
    data = extract_json_block(response)
    if isinstance(data, dict):
        if "findings" in data and isinstance(data["findings"], list):
            data = data["findings"]
        elif "items" in data and isinstance(data["items"], list):
            data = data["items"]
    return data if isinstance(data, list) else None


def _mark_degraded_findings(findings: list[Finding], exc: Exception) -> list[Finding]:
    """Annotate unverified findings with unavailable reason when verifier fails."""
    logger.warning("Verification did not complete: %s: %s", type(exc).__name__, exc)
    return _without_verdict(findings, f"{CONST_VERIFICATION_UNAVAILABLE}: {type(exc).__name__}")


def _validate_segment_findings(
    result: ReviewResult,
    all_segments: list[str],
    client: Any,
    analysis_metas: dict[str, Any] | None = None,
    repo_root: Path | None = None,
    enable_thinking: bool = True,
    conventions: str = "",
    diff_text: str | None = None,
) -> tuple[ReviewResult, float | None, str | None]:
    """Ask the LLM to verify each finding using enhanced analysis metadata of related files.

    `analysis_metas` is the review session's own metadata, whose removed symbols exempt a
    finding from invalidation. Hunks to re-anchor such a finding come from `diff_text` when the
    segments are not the diff itself, such as a file's numbered source.
    """
    if not result.findings:
        return result, None, None

    diff_segments = [diff_text] if diff_text is not None else all_segments
    pre_validated_findings = _run_deterministic_pre_verification_on_findings(
        result.findings, repo_root, result.external_dependencies, analysis_metas, diff_segments
    )
    result = result.model_copy(update={"findings": pre_validated_findings})

    unresolved_findings = [
        f.model_copy(update={"finding_id": i})
        for i, f in enumerate(
            (f for f in pre_validated_findings if _awaits_verdict(f)),
            start=1,
        )
    ]
    if not unresolved_findings:
        return result, 0.0, "deterministic"

    prompt = _build_validation_prompt(
        unresolved_findings,
        all_segments,
        analysis_metas=analysis_metas,
        repo_root=repo_root,
        conventions=conventions,
    )
    proc_sec: float | None = None
    b_info: str | None = None
    try:
        with limit_completion_tokens(_verification_reply_cap(len(unresolved_findings))):
            res_obj = client.chat(
                system=_VALIDATION_SYSTEM, user=prompt, enable_thinking=enable_thinking
            )
        proc_sec = getattr(res_obj, "processing_seconds", None)
        b_info = getattr(res_obj, "backend_info", None)
        if getattr(res_obj, "finish_reason", None) == CONST_FINISH_REASON_LENGTH:
            # A reply cut at its cap can still parse: JSON repair closes a verdict cut
            # mid-reason, and in session 20261002-214641 such a fragment refuted a finding.
            cut = _without_verdict(result.findings, CONST_VERIFIER_REPLY_CUT)
            return result.model_copy(update={"findings": cut}), proc_sec, b_info
        data = _parse_verifier_payload(str(res_obj))
        if data is None:
            unparsed = _without_verdict(result.findings, CONST_VERIFIER_REPLY_UNPARSED)
            return result.model_copy(update={"findings": unparsed}), proc_sec, b_info
        bound = _bind_verdicts_to_findings(unresolved_findings, data)
        validated = _apply_bound_verdicts_to_findings(result.findings, bound, repo_root)
        return result.model_copy(update={"findings": validated}), proc_sec, b_info
    except Exception as exc:
        degraded = _mark_degraded_findings(result.findings, exc)
        return result.model_copy(update={"findings": degraded}), proc_sec, b_info


def _merge_segment_results(results: list[ReviewResult | None]) -> ReviewResult | None:
    """Python-level merge of validated segment ReviewResults used as recompose fallback."""
    valid = [r for r in results if r is not None]
    if not valid:
        return None
    merged = valid[0]
    for other in valid[1:]:
        merged = merged.merge(other)
    return merged


def _is_matching_finding(candidate: Finding, target_title: str, target_location: str) -> bool:
    """Whether a finding is the one a title names; a shared location alone is not enough.

    `target_location` is accepted for callers that pass it, but it never decides a match: two
    different findings routinely share a line.
    """
    candidate_title = candidate.title.lower().strip()
    if not target_title or not candidate_title:
        return False
    return (
        candidate_title == target_title
        or (len(target_title) > 5 and target_title in candidate_title)
        or (len(candidate_title) > 5 and candidate_title in target_title)
    )


def _reconcile_single_finding(
    finding: Finding,
    unverified_findings: list[Finding],
    mitigated_findings: list[Finding],
) -> Finding:
    """Compute verification status updates for a single finding."""
    target_title = finding.title.lower().strip()
    target_loc = finding.location.lower().strip()
    updates: dict[str, object] = {}

    uf = next(
        (f for f in unverified_findings if _is_matching_finding(f, target_title, target_loc)), None
    )
    if uf is not None:
        updates["verified"] = False
        updates["status"] = "UNVERIFIED"
        updates["reportable"] = False
        if uf.verification_note:
            updates["verification_note"] = uf.verification_note

    mf = next(
        (f for f in mitigated_findings if _is_matching_finding(f, target_title, target_loc)), None
    )
    if mf is not None:
        updates["mitigated"] = True
        updates["status"] = "MITIGATED"
        updates["reportable"] = True
        updates["mitigating_mechanism"] = mf.mitigating_mechanism
        updates["perimeter_files"] = mf.perimeter_files
        updates["regression_test"] = mf.regression_test
        updates["invalidation_reason"] = mf.invalidation_reason
        if mf.verification_note:
            updates["verification_note"] = mf.verification_note

    return finding.model_copy(update=updates) if updates else finding


def _reconcile_verified(
    recomposed: ReviewResult, segment_results: list[ReviewResult | None]
) -> ReviewResult:
    """Carry verified=False and mitigated=True from step-3 validation into the recomposed result."""
    valid_results = [r for r in segment_results if r is not None]
    merged_seg = _merge_segment_results(segment_results)
    baseline_findings = recomposed.findings or (merged_seg.findings if merged_seg else [])

    unverified_findings = [f for r in valid_results for f in r.findings if not f.verified]
    mitigated_findings = [f for r in valid_results for f in r.findings if f.mitigated]

    updated = [
        _reconcile_single_finding(f, unverified_findings, mitigated_findings)
        for f in baseline_findings
    ]

    summary = recomposed.summary or (merged_seg.summary if merged_seg else "")

    return recomposed.model_copy(
        update={
            "findings": updated,
            "summary": summary,
        }
    )
