"""Step 3 finding verification pipeline, source excerpt matching, and status reconciliation."""

from __future__ import annotations

import ast
import functools
import json
import logging
import re
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from devops_cli.ai.client.network import limit_completion_tokens
from devops_cli.ai.review.chunker import page_line_number
from devops_cli.ai.review_schema import _SEVERITY_RANK, Finding, ReviewResult, extract_json_block
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import CONST_VERIFICATION_UNAVAILABLE
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

    findings_json = sanitize_prompt_boundary_tags(
        json.dumps(
            [
                {k: v for k, v in f.model_dump().items() if k not in {"verified", "mitigated"}}
                for f in findings
            ],
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
    r"|fake|dummy|mock|example|sample|changeme|change-me|placeholder|xxxx|test",
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

        res = finding.model_copy(
            update={
                "verified": False,
                "mitigated": False,
                "reportable": False,
                "status": "INVALIDATED",
                "invalidation_reason": "Syntax validation passed cleanly via language parser (valid Python 3.14+ syntax)",
            }
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
        tree = ast.parse(content)
        from devops_cli.ai.review.common_hallucinations import (
            _verify_symbol_defined_in_ast_or_module,
            auto_record_invalidated_finding,
        )

        if _verify_symbol_defined_in_ast_or_module(finding, tree, file_path):
            res = finding.model_copy(
                update={
                    "verified": False,
                    "mitigated": False,
                    "reportable": False,
                    "status": "INVALIDATED",
                    "invalidation_reason": "Ground-truth AST and cross-module inspection confirmed symbol is defined in module or exports",
                }
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


def _check_missing_header_hallucination(finding: Finding, file_path: Path) -> Finding | None:
    """Deterministically invalidate claims of missing Authorization headers if set in the module."""
    if not (file_path.exists() and file_path.is_file()):
        return None
    title_lower = finding.title.lower()
    desc_lower = (finding.description or "").lower()
    header_claim = any(
        kw in title_lower or kw in desc_lower
        for kw in (
            "missing authorization header",
            "missing auth header",
            "sent without authentication",
            "without including an authorization header",
            "missing header in",
        )
    )
    if not header_claim:
        return None

    try:
        # The header has to be set where the request is made, not anywhere in the module:
        # a client whose other methods authenticate can still send one request without it.
        content = _cited_window(finding, file_path, _HEADER_WINDOW_LINES)
        if not content:
            return None
        has_auth = any(
            pattern in content
            for pattern in (
                'headers["Authorization"]',
                "headers['Authorization']",
                '"Authorization":',
                "'Authorization':",
            )
        )
        has_dispatch = any(
            dispatch in content
            for dispatch in (
                "headers=headers",
                "headers = headers",
                "headers=self._headers",
                "headers=default_headers",
            )
        )
        if has_auth and has_dispatch:
            from devops_cli.ai.review.common_hallucinations import auto_record_invalidated_finding

            res = finding.model_copy(
                update={
                    "verified": False,
                    "mitigated": False,
                    "reportable": False,
                    "status": "INVALIDATED",
                    "invalidation_reason": "Source code inspection confirmed Authorization header is dynamically configured before request dispatch",
                }
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
    logger.debug(
        "Dropping line %d past the end of %s (%d lines)", target_line, file_path, total_lines
    )
    return finding.model_copy(update={"location": finding.location.split(":", 1)[0]})


def _check_pathlib_resolve_hallucination(finding: Finding) -> Finding | None:
    """Invalidate claims that Path.resolve() raises FileNotFoundError on non-existent paths."""
    text = (finding.title + " " + (finding.description or "")).lower()
    # resolve(strict=True) does raise FileNotFoundError; only the non-strict claim is false.
    if "filenotfounderror" in text and "resolve(" in text and "strict" not in text:
        return finding.model_copy(
            update={
                "verified": False,
                "mitigated": False,
                "reportable": False,
                "status": "INVALIDATED",
                "invalidation_reason": (
                    "Matches verified common hallucination [HALLUCINATION-PATHLIB-RESOLVE-FILENOTFOUND]: "
                    "In Python 3.6+, Path.resolve(strict=False) safely resolves non-existent paths without FileNotFoundError"
                ),
            }
        )
    return None


# A real advisory identifier is all digits after the year. A finding that cites
# `CVE-2023-xxxx` has named no advisory at all -- the model wrote the shape of evidence
# where the evidence belongs. Matching the placeholder is cheaper and more certain than
# asking a second model whether the vulnerability is real.
_PLACEHOLDER_ADVISORY_PATTERN = re.compile(
    r"\b(?:CVE-\d{4}-|GHSA-)[0-9a-z]*[xn?]{3,}", re.IGNORECASE
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
        or str(getattr(dep, "severity", "CLEAN")).upper() != "CLEAN"
        for dep in named
    ):
        return None

    listed = ", ".join(sorted(str(dep.name) for dep in named))
    return finding.model_copy(
        update={
            "verified": False,
            "mitigated": False,
            "reportable": False,
            "status": "INVALIDATED",
            "invalidation_reason": (
                f"This run's own advisory scan reports {listed} CLEAN with no advisory "
                "records at the pinned versions"
            ),
        }
    )


def _check_placeholder_advisory_hallucination(finding: Finding) -> Finding | None:
    """Invalidate a vulnerability claim whose only evidence is a placeholder advisory id.

    A dependency finding stands on the advisory it names. When the identifier is a
    placeholder, there is nothing to look up, and the surrounding claim was produced by the
    same step that could not name it.
    """
    text = f"{finding.title} {finding.description or ''} {' '.join(finding.references or [])}"
    match = _PLACEHOLDER_ADVISORY_PATTERN.search(text)
    if match is None:
        return None
    return finding.model_copy(
        update={
            "verified": False,
            "mitigated": False,
            "reportable": False,
            "status": "INVALIDATED",
            "invalidation_reason": (
                f"Cites the placeholder advisory identifier {match.group(0)!r}, which names "
                "no published advisory; a dependency claim must cite a real one"
            ),
        }
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

    return finding.model_copy(
        update={
            "verified": False,
            "mitigated": False,
            "reportable": False,
            "status": "INVALIDATED",
            "invalidation_reason": (
                f"Describes a failure on Python 3.{max(cited)}, below the declared "
                f"`requires-python` floor of 3.{floor}, which cannot be installed"
            ),
        }
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
        return finding.model_copy(
            update={
                "verified": False,
                "mitigated": False,
                "reportable": False,
                "status": "INVALIDATED",
                "invalidation_reason": (
                    "Matches verified common hallucination [HALLUCINATION-HEALTH-ENDPOINT-VERSION]: "
                    "Health and liveness endpoints standardly provide service version for cluster orchestration"
                ),
            }
        )
    if _is_stream_event_timestamp_claim(text, loc):
        return finding.model_copy(
            update={
                "verified": False,
                "mitigated": False,
                "reportable": False,
                "status": "INVALIDATED",
                "invalidation_reason": (
                    "Matches verified common hallucination [HALLUCINATION-STREAM-EVENT-TIMESTAMP]: "
                    "Real-time event streams require timestamps for event sequencing and client synchronization"
                ),
            }
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
    keywords = (
        "hardcoded secret",
        "hardcoded token",
        "hardcoded credential",
        "plaintext secret",
        "exposed vault token",
        "hardcoded vault token",
        "hardcoded password",
    )
    if not any(kw in title_lower or kw in desc_lower for kw in keywords):
        return None
    # A real credential committed to a test directory is still a leak. Only a cited value that
    # is plainly synthetic ("test-token", "changeme", "dummy") is a fixture.
    window = _cited_window(finding, file_path, 2)
    values = re.findall(r"[\"']([^\"'\n]{3,})[\"']", window)
    if not values or not all(_PLACEHOLDER_SECRET.search(value) for value in values):
        return None
    return finding.model_copy(
        update={
            "verified": False,
            "mitigated": False,
            "reportable": False,
            "status": "INVALIDATED",
            "invalidation_reason": (
                "Matches verified common hallucination [HALLUCINATION-TEST-MOCK-CRED]: "
                "the cited test credential is a synthetic placeholder"
            ),
        }
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
    return any(
        kw in title_lower or kw in desc_lower for kw in ("uninitialized", "unboundlocalerror")
    )


def _try_find_var_assignment(file_path: Path, var_name: str, target_line: int) -> int | None:
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
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
        return finding.model_copy(
            update={
                "verified": False,
                "mitigated": False,
                "reportable": False,
                "status": "INVALIDATED",
                "invalidation_reason": (
                    f"Matches verified common hallucination "
                    f"[HALLUCINATION-UNINITIALIZED-VARIABLE-ABOVE-LOOP]: "
                    f"Variable '{var_name}' is explicitly initialized at line {assign_line} before reference"
                ),
            }
        )
    return None


# Reasoning that opens a title; inside a title the same words describe a defect ("Clients of
# the API need to send the token in the query"). Praise counts anywhere unless negated ("Rate
# limiter not properly implemented").
_MONOLOGUE_TITLE = re.compile(
    r"^(?:we need to|let's check|let's verify|first, let's|i need to|looking at the code|"
    r"based on the above)\b"
)
_COMPLIMENT_PHRASE = re.compile(
    r"\b(?:looks solid|properly implemented|no vulnerabilities found|clean code|well structured|"
    r"all clear)\b"
)
# A negation or defect word turns praise wording into a finding.
_COMPLIMENT_NEGATION = re.compile(
    r"\b(?:not|never|isn't|aren't|no longer|improperly|but|however|except|missing|fails?|"
    r"lacks?|without)\b"
)


def _check_conversational_monologue(title_lower: str, finding: Finding) -> Finding | None:
    if _MONOLOGUE_TITLE.match(title_lower.strip()):
        return finding.model_copy(
            update={
                "verified": False,
                "mitigated": False,
                "reportable": False,
                "status": "INVALIDATED",
                "invalidation_reason": "Conversational scratchpad chain-of-thought monologue leaked into finding title",
            }
        )
    return None


def _check_benign_compliment(title_lower: str, finding: Finding) -> Finding | None:
    if _COMPLIMENT_PHRASE.search(title_lower) and not _COMPLIMENT_NEGATION.search(title_lower):
        return finding.model_copy(
            update={
                "verified": False,
                "mitigated": False,
                "reportable": False,
                "status": "INVALIDATED",
                "invalidation_reason": "Conversational praise or benign observation without a concrete defect",
            }
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
    # A claim that the redacted value is a live secret is about the value behind the marker,
    # which the source still holds; only a claim about the marker's own syntax is false.
    if _SECRET_EXPOSURE_CLAIM.search(f"{title_lower} {desc_lower}"):
        return None
    phrases = (
        "syntax error",
        "invalid syntax",
        "undefined variable",
        "nameerror",
        "unquoted placeholder",
        "unresolved identifier",
    )
    if any(phrase in title_lower or phrase in desc_lower for phrase in phrases):
        return finding.model_copy(
            update={
                "verified": False,
                "mitigated": False,
                "reportable": False,
                "status": "INVALIDATED",
                "invalidation_reason": (
                    "Sanitization marker '<masked-*>' or '***redacted***' is a prompt redaction indicator, "
                    "not an invalid identifier, undefined placeholder, or runtime defect"
                ),
            }
        )
    return None


# A claim about Python's None, spelled as code. English "if none of the roles match" is not.
_NONE_DEREFERENCE_CLAIM = re.compile(
    r"\bNoneType\b|\bNone\b[^\n]{0,60}\b(?:attribute|dereference|access|AttributeError)"
    r"|\b(?:AttributeError|[Dd]ereferenc\w*|access\w*)\b[^\n]{0,80}\bNone\b"
    r"|(?i:\bnull\s+(?:pointer|dereference)\b)"
)


@functools.lru_cache(maxsize=256)
def _module_typechecks_clean(path_str: str, mtime: float) -> bool:
    """Report whether a module passes strict type checking.

    Cached on path and mtime: verification examines many findings against the same few
    files, and a type check per finding would dominate the run.
    """
    from devops_cli.core.process import run_subprocess

    try:
        result = run_subprocess(
            ["uv", "run", "mypy", "--strict", path_str],
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
    types, and this repository already runs `mypy --strict` over the whole package. If the
    cited module passes, the attribute is not Optional and the runtime failure described
    cannot occur; if mypy cannot type check it cleanly for any reason, nothing is claimed
    and the finding proceeds to the model verifier as before.

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

    res = finding.model_copy(
        update={
            "verified": False,
            "mitigated": False,
            "reportable": False,
            "status": "INVALIDATED",
            "invalidation_reason": (
                "Module passes `mypy --strict`, so the attribute is not Optional and the "
                "described None dereference is not reachable"
            ),
        }
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

        match = is_common_hallucination(finding, threshold=0.8, file_path=file_path)
        if match and verify_ground_truth_hallucination(finding, match.hallucination, file_path):
            entry = match.hallucination
            auto_record_invalidated_finding(finding, file_path=file_path, reason=entry.resolution)
            return finding.model_copy(
                update={
                    "verified": False,
                    "mitigated": False,
                    "reportable": False,
                    "status": "INVALIDATED",
                    "invalidation_reason": f"Matches verified common hallucination [{entry.id}]: {entry.resolution}",
                }
            )
    except Exception:
        pass
    return finding


def _deterministic_pre_verification(
    finding: Finding,
    repo_root: Path | None = None,
    target_dir: Path | None = None,
    dependencies: Sequence[Any] | None = None,
    **kwargs: Any,
) -> Finding:
    """Run local deterministic parser, line boundary, and hallucination checks to invalidate obvious false positives."""
    title_lower = finding.title.lower()
    desc_lower = (finding.description or "").lower()

    early_results = [
        _check_pathlib_resolve_hallucination(finding),
        _check_operational_protocol_hallucination(finding),
        _check_conversational_monologue(title_lower, finding),
        _check_benign_compliment(title_lower, finding),
        _check_masked_placeholder_syntax_error(finding, title_lower, desc_lower),
        _check_placeholder_advisory_hallucination(finding),
        _check_scanned_clean_dependency(finding, dependencies or ()),
    ]
    for res in early_results:
        if res:
            return res

    loc_file = finding.location.split(":")[0].strip()
    if not loc_file or _is_secret_path(loc_file):
        return finding

    effective_root = repo_root or target_dir
    file_path = _resolve_target_file(loc_file, effective_root)
    if file_path is None:
        return finding

    finding = _drop_out_of_range_lines(finding, file_path)
    code_res = _check_code_file_hallucinations(finding, file_path)
    if code_res:
        return code_res

    finding = _check_catalog_hallucination(finding, file_path)
    if finding.status in {"INVALIDATED", "MITIGATED"}:
        return finding

    if effective_root and effective_root.is_dir():
        from devops_cli.ai.review.review_environment import execute_finding_criteria

        finding = execute_finding_criteria(finding, effective_root)

    return finding


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


def _verdict_status(item: dict[str, Any], inv_matched: list[str]) -> tuple[str, bool]:
    """The status and reportability a verdict supports.

    Only clear evidence removes a finding. A verdict that both confirms and refutes it, or that
    declines to confirm it without naming invalidating evidence, leaves it unverified and in
    the report, as a finding with no verdict is.
    """
    verified = _verdict_bool(item.get("verified"))
    status = str(item.get("status") or "").strip().upper()
    refuted = bool(inv_matched) or _verdict_bool(item.get("invalidated")) or status == "INVALIDATED"
    confirmed = verified is True or status == "VERIFIED"
    if refuted and confirmed:
        return "UNVERIFIED", True
    if refuted:
        return "INVALIDATED", False
    if _verdict_bool(item.get("mitigated")) or status == "MITIGATED":
        # A mitigation is a claim about the code too: without a reason naming the mechanism it
        # proves nothing. With one, the finding stays in the report beside it, and the reader
        # judges whether it holds; mitigated findings do not drive the recommendation.
        if not str(item.get("reason") or "").strip():
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


def _without_self_refutation(f: Finding, item: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """The verdict with its invalidation withdrawn when it rests only on the finding's own claim.

    An invalidation whose matched criteria all restate the defect or its fix, or whose reason
    confirms the claimed condition, names no evidence against the finding; it leaves the
    finding unverified and in the report.
    """
    inv_matched = _verdict_list(item.get("invalidated_criteria_matched"))
    genuine = [c for c in inv_matched if not _restates_the_finding(c, f)]
    reason = str(item.get("reason") or "").strip()
    if genuine and not _reason_confirms(reason, f):
        return item, inv_matched
    if not inv_matched and not _reason_confirms(reason, f):
        return item, inv_matched
    withdrawn = {**item, "invalidated": False}
    if str(item.get("status") or "").strip().upper() == "INVALIDATED":
        withdrawn["status"] = ""
    return withdrawn, []


def _apply_single_finding_verification(
    f: Finding, item: dict[str, Any] | None, now_iso: str
) -> Finding:
    """Apply parsed LLM verification metadata to a single Finding."""
    if not isinstance(item, dict):
        return f

    ver_matched = _verdict_list(item.get("verified_criteria_matched"))
    item, inv_matched = _without_self_refutation(f, item)
    status_val, is_rep = _verdict_status(item, inv_matched)
    is_v = status_val == "VERIFIED"
    # A model's invalidation does not teach the hallucinations catalog: it is the judgement
    # under test, and a real defect it wrongly dismissed would be learned as a false alarm.

    # A confidence derived from `len(verified_criteria_matched) / len(verification_criteria)`
    # divides the model's claim about its criteria by the criteria the model wrote. It
    # measures self-agreement and reads as evidence, which is how findings reached 0.95
    # while being refutable by reading one file. AGENTS.md requires a score to come from a
    # tool's native rating or a structured model response, and to be absent otherwise --
    # so an absent score stays absent rather than being computed into existence.
    conf_val = item.get("confidence_score")
    conf: float | None = f.confidence_score
    if conf_val is not None:
        try:
            conf = max(0.0, min(1.0, float(conf_val)))
        except ValueError, TypeError:
            conf = f.confidence_score

    merged_ver_matched = list(dict.fromkeys(f.verified_criteria_matched + ver_matched))
    merged_inv_matched = list(dict.fromkeys(f.invalidated_criteria_matched + inv_matched))

    updates: dict[str, object] = {
        "verified": is_v,
        "mitigated": status_val == "MITIGATED",
        "status": status_val,
        "reportable": is_rep,
        "confidence_score": conf,
        "verified_criteria_matched": merged_ver_matched,
        "invalidated_criteria_matched": merged_inv_matched,
        "criteria_execution_results": f.criteria_execution_results,
        "verified_by": "llm",
        "verified_at": now_iso,
    }
    reason = str(item.get("reason") or "").strip()
    if status_val in {"MITIGATED", "INVALIDATED"} and reason:
        updates["invalidation_reason"] = reason
    new_sev = str(item.get("severity", "")).upper().strip()
    if new_sev and new_sev in _SEVERITY_RANK:
        updates["severity"] = new_sev
    new_loc = str(item.get("location", "")).strip()
    if new_loc and new_loc != f.location:
        updates["location"] = new_loc
    return f.model_copy(update=updates)


def _bind_verdicts_to_findings(
    unresolved: list[Finding], items: list[Any]
) -> dict[int, dict[str, Any]]:
    """Match each model verdict to the finding it describes, by identity.

    Verdicts were bound by list position, across two incompatible index spaces: the
    response covers only the unresolved findings, but the fallback indexed it with a
    position from the *whole* list including findings deterministically invalidated before
    the model ever saw them. Any count mismatch -- a model merging, dropping or adding an
    item, which is routine -- shifted every verdict onto the wrong finding.

    Measured across this repository's 59 recorded sessions: 35 findings carry an
    `invalidation_reason` while reporting `verified=true` and `status=VERIFIED`, 23 of them
    in a single session. Several of those reasons are verbatim the *title of a different
    finding*, which is what a shifted verdict looks like from the outside. A finding cannot
    be both withdrawn and confirmed.

    An item that matches nothing is dropped rather than applied to whatever sits at its
    index, and a finding that matches nothing keeps the status it already had.
    """
    bound: dict[int, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").lower().strip()
        location = str(item.get("location") or "").lower().strip()
        index = _best_verdict_target(unresolved, bound, title, location)
        if index is None:
            logger.debug("Verification verdict matched no finding: %r / %r", title, location)
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


def _validate_segment_findings(
    result: ReviewResult,
    all_segments: list[str],
    client: Any,
    analysis_metas: dict[str, Any] | None = None,
    repo_root: Path | None = None,
    enable_thinking: bool = True,
    conventions: str = "",
) -> tuple[ReviewResult, float | None, str | None]:
    """Ask the LLM to verify each finding using enhanced analysis metadata of related files."""
    if not result.findings:
        return result, None, None

    # Apply deterministic static rules first
    pre_validated_findings = [
        _deterministic_pre_verification(
            f, repo_root=repo_root, dependencies=result.external_dependencies
        )
        for f in result.findings
    ]
    result = result.model_copy(update={"findings": pre_validated_findings})

    # If all candidate findings are already deterministically invalidated or mitigated, bypass LLM
    unresolved_findings = [
        f for f in pre_validated_findings if f.status not in {"INVALIDATED", "MITIGATED"}
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
        # Uncapped, one runaway reply held a review for over ten minutes.
        with limit_completion_tokens(_verification_reply_cap(len(unresolved_findings))):
            res_obj = client.chat(
                system=_VALIDATION_SYSTEM, user=prompt, enable_thinking=enable_thinking
            )
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
            bound = _bind_verdicts_to_findings(unresolved_findings, data)
            validated: list[Finding] = []
            now_iso = datetime.now().isoformat()
            unresolved_idx = 0
            for f in result.findings:
                if f.status in {"INVALIDATED", "MITIGATED"}:
                    validated.append(f)
                    continue
                item = bound.get(unresolved_idx)
                unresolved_idx += 1
                validated.append(_apply_single_finding_verification(f, item, now_iso))
            return result.model_copy(update={"findings": validated}), proc_sec, b_info
    except Exception as exc:
        # An infrastructure failure, a malformed response and a genuine refusal to verify
        # all produced the same page of `*(unverified)*` findings, so a reader could not
        # tell whether the verifier disagreed or never ran. The reason is recorded on the
        # findings themselves rather than on `ReviewResult`, which is parsed straight from
        # model output -- a field there would let a model write its own outage banner.
        logger.warning("Verification did not complete: %s: %s", type(exc).__name__, exc)
        reason = f"{CONST_VERIFICATION_UNAVAILABLE}: {type(exc).__name__}"
        degraded = [
            f.model_copy(update={"verification_note": reason})
            if f.status not in {"INVALIDATED", "MITIGATED"}
            else f
            for f in result.findings
        ]
        return result.model_copy(update={"findings": degraded}), proc_sec, b_info
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

    if any(_is_matching_finding(uf, target_title, target_loc) for uf in unverified_findings):
        updates["verified"] = False
        updates["status"] = "UNVERIFIED"
        updates["reportable"] = False

    if any(_is_matching_finding(mf, target_title, target_loc) for mf in mitigated_findings):
        updates["mitigated"] = True
        updates["status"] = "MITIGATED"
        updates["reportable"] = False

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
    positive = recomposed.positive_observations or (
        merged_seg.positive_observations if merged_seg else []
    )

    return recomposed.model_copy(
        update={
            "findings": updated,
            "summary": summary,
            "positive_observations": positive,
        }
    )
