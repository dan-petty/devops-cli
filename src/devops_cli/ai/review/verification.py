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

from devops_cli.ai.review_schema import _SEVERITY_RANK, Finding, ReviewResult, extract_json_block
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.defaults import (
    DEFAULT_DIFF_CONTEXT_LINES,
    DEFAULT_MAX_RELATED_FILES,
    DEFAULT_RELATED_FILE_MAX_CHARS,
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
    return (
        f"{_VALIDATION_TEMPLATE}\n\n"
        f"Code:\n<untrusted_finding_excerpts>\n{code_section}\n</untrusted_finding_excerpts>\n\n"
        f"{related_section}"
        f"Findings:\n<untrusted_findings_input>\n```json\n{findings_json}\n```\n</untrusted_findings_input>\n"
    )


_SYNTAX_CLAIM_PATTERNS: tuple[str, ...] = (
    "syntax",
    "parse error",
    "syntaxerror",
    "invalid syntax",
    "except clause",
    "exception clause",
    "except statement",
    "cannot be imported",
    "fails to import",
    "prevents module import",
    "breaks import",
    "python 2 syntax",
    "python 2 style",
    "deprecated syntax",
)


def _check_syntax_error_hallucination(finding: Finding, file_path: Path) -> Finding | None:
    """Deterministically invalidate syntax error claims if standard parser succeeds."""
    if not (file_path.exists() and file_path.is_file()):
        return None

    title_lower = finding.title.lower()
    desc_lower = (finding.description or "").lower()
    is_syntax_claim = any(kw in title_lower or kw in desc_lower for kw in _SYNTAX_CLAIM_PATTERNS)
    if not is_syntax_claim:
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


def _check_missing_symbol_hallucination(finding: Finding, file_path: Path) -> Finding | None:
    """Deterministically invalidate false missing symbol or ImportError claims if symbol exists."""
    if not (file_path.exists() and file_path.is_file() and file_path.suffix.lower() == ".py"):
        return None
    title_lower = finding.title.lower()
    desc_lower = (finding.description or "").lower()
    claim_indicators = (
        "importerror",
        "missing",
        "not defined",
        "undefined",
        "never defined",
    )
    if not any(kw in title_lower or kw in desc_lower for kw in claim_indicators):
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
        content = file_path.read_text(encoding="utf-8", errors="replace")
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
            res = finding.model_copy(
                update={
                    "verified": False,
                    "mitigated": False,
                    "reportable": False,
                    "status": "INVALIDATED",
                    "invalidation_reason": f"Line {target_line} exceeds total file lines ({total_lines})",
                }
            )
            try:
                from devops_cli.ai.review.common_hallucinations import (
                    auto_record_invalidated_finding,
                )

                auto_record_invalidated_finding(
                    res, file_path=file_path, reason=res.invalidation_reason
                )
            except Exception:
                pass
            return res
    except Exception:
        pass
    return None


def _check_pathlib_resolve_hallucination(finding: Finding) -> Finding | None:
    """Invalidate claims that Path.resolve() raises FileNotFoundError on non-existent paths."""
    text = (finding.title + " " + (finding.description or "")).lower()
    if "filenotfounderror" in text and "resolve" in text:
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


def _check_unsupported_runtime_hallucination(finding: Finding) -> Finding | None:
    """Invalidate a compatibility claim about a Python the project does not support.

    `requires-python` is the declared support floor. A finding that a module breaks on an
    interpreter below it describes a configuration that cannot occur: the installer refuses
    it before any import runs.
    """
    text = f"{finding.title} {finding.description or ''}".lower()
    if not any(word in text for word in ("incompatible", "compatib", "importerror", "raises")):
        return None

    floor = _declared_python_floor()
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


@functools.lru_cache(maxsize=1)
def _declared_python_floor() -> int | None:
    """Return the minor version of this project's `requires-python` floor."""
    root = Path(__file__).resolve().parents[3].parent
    try:
        raw = (root / "pyproject.toml").read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r'requires-python\s*=\s*"[^"]*?3\.(\d+)', raw)
    return int(match.group(1)) if match else None


def _is_health_endpoint_version_claim(title_desc: str, loc: str) -> bool:
    return "version" in title_desc and any(
        k in loc or k in title_desc for k in ("health", "healthz", "health.py")
    )


def _is_stream_event_timestamp_claim(title_desc: str, loc: str) -> bool:
    return "timestamp" in title_desc and any(
        k in loc or k in title_desc for k in ("sse", "stream", "websocket", "stream.py")
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
    if any(kw in title_lower or kw in desc_lower for kw in keywords):
        return finding.model_copy(
            update={
                "verified": False,
                "mitigated": False,
                "reportable": False,
                "status": "INVALIDATED",
                "invalidation_reason": (
                    "Matches verified common hallucination [HALLUCINATION-TEST-MOCK-CRED]: "
                    "Test fixtures and mock suites legitimately use synthetic credentials"
                ),
            }
        )
    return None


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
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fn_start = getattr(node, "lineno", 0)
            fn_end = getattr(node, "end_lineno", fn_start + 1000)
            if fn_start <= target_line <= fn_end:
                assign_line = _is_var_assigned_before(node, var_name, target_line)
                if assign_line is not None:
                    return assign_line
    return None


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


def _check_conversational_monologue(title_lower: str, finding: Finding) -> Finding | None:
    phrases = (
        "we need to",
        "let's check",
        "let's verify",
        "first, let's",
        "i need to",
        "looking at the code",
        "based on the above",
    )
    if any(phrase in title_lower for phrase in phrases):
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
    phrases = (
        "looks solid",
        "properly implemented",
        "no vulnerabilities found",
        "clean code",
        "well structured",
        "all clear",
    )
    if any(phrase in title_lower for phrase in phrases):
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
    phrases = (
        "syntax error",
        "invalid syntax",
        "undefined variable",
        "nameerror",
        "placeholder",
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


_NONE_DEREFERENCE_CLAIM_PATTERNS: tuple[str, ...] = (
    "attributeerror",
    "nonetype",
    "none dereference",
    "null dereference",
    "null pointer",
    "is none",
    "when none",
    "if none",
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

    haystack = f"{finding.title} {finding.description or ''}".lower()
    if not any(pattern in haystack for pattern in _NONE_DEREFERENCE_CLAIM_PATTERNS):
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
        _check_line_boundaries,
        _check_syntax_error_hallucination,
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
        _check_unsupported_runtime_hallucination(finding),
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

    code_res = _check_code_file_hallucinations(finding, file_path)
    if code_res:
        return code_res

    return _check_catalog_hallucination(finding, file_path)


def _apply_single_finding_verification(
    f: Finding, item: dict[str, Any] | None, now_iso: str
) -> Finding:
    """Apply parsed LLM verification metadata to a single Finding."""
    if not isinstance(item, dict):
        return f

    ver_matched = [str(x) for x in item.get("verified_criteria_matched", []) if str(x)]
    inv_matched = [str(x) for x in item.get("invalidated_criteria_matched", []) if str(x)]
    is_v = bool(item.get("verified", False))
    is_m = bool(item.get("mitigated", False))

    if inv_matched:
        is_v = False
        is_m = True
        status_val = "INVALIDATED"
        is_rep = False
        try:
            from devops_cli.ai.review.common_hallucinations import auto_record_invalidated_finding

            auto_record_invalidated_finding(f, reason="; ".join(inv_matched))
        except Exception:
            pass
    elif is_m:
        status_val = "MITIGATED"
        is_rep = False
    elif is_v:
        status_val = "VERIFIED"
        is_rep = bool(item.get("reportable", True))
    else:
        status_val = "UNVERIFIED"
        is_rep = False

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
    claimed: set[int] = set()

    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").lower().strip()
        location = str(item.get("location") or "").lower().strip()
        if not title and not location:
            continue
        for index, finding in enumerate(unresolved):
            if index in claimed:
                continue
            if _is_matching_finding(finding, title, location):
                bound[index] = item
                claimed.add(index)
                break
        else:
            logger.debug("Verification verdict matched no finding: %r / %r", title, location)
    return bound


def _validate_segment_findings(
    result: ReviewResult,
    all_segments: list[str],
    client: Any,
    analysis_metas: dict[str, Any] | None = None,
    repo_root: Path | None = None,
    enable_thinking: bool = True,
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
        unresolved_findings, all_segments, analysis_metas=analysis_metas, repo_root=repo_root
    )
    proc_sec: float | None = None
    b_info: str | None = None
    try:
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


def _is_matching_finding(candidate: Finding, target_title: str, target_location: str) -> bool:
    """Check if candidate finding matches the target finding by title or location."""
    candidate_title = candidate.title.lower().strip()
    candidate_loc = candidate.location.lower().strip()
    return (
        candidate_title == target_title
        or bool(target_location and candidate_loc == target_location)
        or (len(target_title) > 5 and candidate_title in target_title)
        or (len(candidate_title) > 5 and target_title in candidate_title)
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
