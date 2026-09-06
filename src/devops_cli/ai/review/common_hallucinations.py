"""Common AI Hallucinations catalog, similarity matching, and autonomous management.

Provides centralized tracking of recurring AI false positives (such as Python 3.14 PEP 758
bracketless except clauses, masked secret placeholders, and synthetic test mock credentials),
automatic learning from invalidated findings, and prioritized scrutiny during review verification.

SAFETY INVARIANT:
No common English words (such as 'secret', 'token', 'test', 'error', 'syntax', 'code') may
be used to flag findings as hallucinations. Real defects and security vulnerabilities must NEVER
be invalidated without concrete ground-truth proof in the target source file.
"""

from __future__ import annotations

import ast
import json
import logging
import os
import re
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.ai.review_schema import Finding
from devops_cli.config.constants import CONST_HALLUCINATIONS_FILE_NAME
from devops_cli.config.defaults import DEFAULT_HALLUCINATIONS_FILE_PATH

logger = logging.getLogger(__name__)

# Common generic words that MUST NEVER contribute to hallucination classification
_FORBIDDEN_COMMON_WORDS: frozenset[str] = frozenset(
    {
        "secret",
        "secrets",
        "token",
        "tokens",
        "key",
        "keys",
        "password",
        "passwords",
        "credential",
        "credentials",
        "api",
        "auth",
        "test",
        "tests",
        "mock",
        "mocks",
        "error",
        "errors",
        "syntax",
        "code",
        "file",
        "line",
        "python",
        "pydantic",
        "default",
        "defaults",
        "mutable",
        "leak",
        "leaks",
        "vulnerability",
        "vulnerabilities",
        "security",
        "issue",
        "issues",
        "bug",
        "bugs",
        "doc",
        "docs",
        "documentation",
        "example",
        "examples",
        "sample",
        "samples",
        "rule",
        "rules",
        "clause",
        "clauses",
        "import",
        "imports",
        "package",
        "packages",
        "dependency",
        "dependencies",
        "found",
        "missing",
        "invalid",
        "statement",
        "argument",
        "arguments",
        "function",
        "method",
        "class",
        "module",
        "string",
        "variable",
        "value",
        "hardcoded",
        "exposed",
        "warning",
        "info",
        "general",
        "critical",
        "high",
        "medium",
        "low",
        # Stop words & structural descriptors
        "this",
        "that",
        "these",
        "those",
        "which",
        "what",
        "who",
        "whom",
        "whose",
        "will",
        "would",
        "shall",
        "should",
        "can",
        "could",
        "may",
        "might",
        "must",
        "from",
        "with",
        "without",
        "about",
        "above",
        "below",
        "into",
        "through",
        "during",
        "before",
        "after",
        "over",
        "under",
        "again",
        "further",
        "then",
        "once",
        "here",
        "there",
        "their",
        "theirs",
        "them",
        "they",
        "when",
        "where",
        "why",
        "how",
        "all",
        "any",
        "both",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "time",
        "pipeline",
        "runtime",
        "leading",
        "crash",
        "blocks",
        "causing",
        "potential",
        "entire",
        "occur",
        "occurs",
        "occurring",
        "occurred",
        "lead",
        "leads",
        "causes",
        "caused",
        "cause",
        "call",
        "calls",
        "called",
        "calling",
        "prevent",
        "prevents",
        "preventing",
        "prevented",
        "fail",
        "fails",
        "failed",
        "failing",
        "failure",
        "failures",
        "pass",
        "passes",
        "passed",
        "passing",
        "check",
        "checks",
        "checked",
        "checking",
        "use",
        "uses",
        "used",
        "using",
        "make",
        "makes",
        "made",
        "making",
        "get",
        "gets",
        "got",
        "getting",
        "set",
        "sets",
        "setting",
        "have",
        "has",
        "had",
        "having",
        "do",
        "does",
        "did",
        "doing",
        "be",
        "been",
        "being",
        "is",
        "are",
        "was",
        "were",
    }
)


class HallucinationCategory(StrEnum):
    """Classification of common AI review hallucinations and false-positive patterns."""

    SYNTAX_GRAMMAR = "syntax_grammar"
    SECRET_SCANNING = "secret_scanning"
    DEPENDENCY_ECOSYSTEM = "dependency_ecosystem"
    TEST_MOCKS = "test_mocks"
    DOCUMENTATION_CONTEXT = "documentation_context"
    MUTABLE_DEFAULTS = "mutable_defaults"
    BOUNDARY_ERRORS = "boundary_errors"
    GENERAL = "general"


class CommonHallucinationEntry(BaseModel):
    """Definition and metadata for a recurring AI review hallucination pattern."""

    model_config = ConfigDict(frozen=False)

    id: str
    name: str
    category: HallucinationCategory
    description: str
    signature_patterns: list[str] = Field(default_factory=list)
    pattern_keywords: list[str] = Field(default_factory=list)
    file_patterns: list[str] = Field(default_factory=list)
    resolution: str
    occurrence_count: int = 1
    last_seen: str = Field(default_factory=lambda: datetime.now().isoformat())
    source: str = "builtin"  # "builtin" | "auto_learned" | "custom"


class HallucinationMatch(BaseModel):
    """Result of evaluating a Finding against a known CommonHallucinationEntry."""

    model_config = ConfigDict(frozen=True)

    hallucination: CommonHallucinationEntry
    similarity_score: float
    matched_keywords: list[str] = Field(default_factory=list)
    reason: str


# ── Built-in Catalog of Common Hallucinations ────────────────────────────────


_BUILTIN_HALLUCINATIONS_FILE = Path(__file__).resolve().parent / "common_hallucinations.json"


def _build_builtin_hallucinations() -> list[CommonHallucinationEntry]:
    """Load baseline verified common hallucinations catalog from JSON file."""
    if _BUILTIN_HALLUCINATIONS_FILE.exists() and _BUILTIN_HALLUCINATIONS_FILE.is_file():
        try:
            data = json.loads(_BUILTIN_HALLUCINATIONS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [
                    CommonHallucinationEntry.model_validate(item)
                    for item in data
                    if isinstance(item, dict)
                ]
        except Exception as exc:
            logger.debug(
                "Failed loading builtin hallucinations from %s: %s",
                _BUILTIN_HALLUCINATIONS_FILE,
                exc,
            )
    return []


# ── File Path & Storage Helpers ──────────────────────────────────────────────


def get_common_hallucinations_file_path() -> Path:
    """Resolve the persistent storage file path for common hallucinations catalog.

    Respects DEVOPS_CLI_DATA_DIR environment override.
    """
    env_dir = os.environ.get("DEVOPS_CLI_DATA_DIR")
    if env_dir:
        target = Path(env_dir) / CONST_HALLUCINATIONS_FILE_NAME
    else:
        target = DEFAULT_HALLUCINATIONS_FILE_PATH

    if not target.is_absolute():
        from devops_cli.core.repo import find_top_level_repo_root

        try:
            target = (find_top_level_repo_root() / target).resolve()
        except Exception:
            target = target.resolve()

    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def load_common_hallucinations(
    target_file: Path | None = None, include_builtin: bool = True
) -> list[CommonHallucinationEntry]:
    """Load common hallucinations from disk, merging with built-ins when requested."""
    fpath = target_file or get_common_hallucinations_file_path()
    entries_by_id: dict[str, CommonHallucinationEntry] = {}

    if include_builtin:
        for b in _build_builtin_hallucinations():
            entries_by_id[b.id] = b

    if fpath.exists() and fpath.is_file():
        try:
            raw_data = json.loads(fpath.read_text(encoding="utf-8"))
            if isinstance(raw_data, list):
                for item in raw_data:
                    if isinstance(item, dict):
                        entry = CommonHallucinationEntry.model_validate(item)
                        entries_by_id[entry.id] = entry
        except Exception as exc:
            logger.debug("Failed reading common hallucinations from %s: %s", fpath, exc)

    return list(entries_by_id.values())


def save_common_hallucinations(
    entries: list[CommonHallucinationEntry], target_file: Path | None = None
) -> None:
    """Persist common hallucinations list to disk in JSON format."""
    fpath = target_file or get_common_hallucinations_file_path()
    fpath.parent.mkdir(parents=True, exist_ok=True)

    data = [entry.model_dump() for entry in entries]
    temp_path = fpath.with_suffix(f".tmp-{uuid4().hex[:6]}")
    temp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temp_path.replace(fpath)


def register_common_hallucination(
    entry: CommonHallucinationEntry, target_file: Path | None = None
) -> CommonHallucinationEntry:
    """Register or update a common hallucination entry in the persistent catalog."""
    file_entries = load_common_hallucinations(target_file=target_file, include_builtin=False)
    by_id = {e.id: e for e in file_entries}

    builtins = {b.id: b for b in _build_builtin_hallucinations()}
    existing = by_id.get(entry.id) or builtins.get(entry.id)

    if existing:
        safe_keywords = [
            kw
            for kw in (existing.pattern_keywords + entry.pattern_keywords)
            if kw.lower() not in _FORBIDDEN_COMMON_WORDS
        ]
        combined_keywords = list(dict.fromkeys(safe_keywords))[:30]
        combined_signatures = list(
            dict.fromkeys(existing.signature_patterns + entry.signature_patterns)
        )[:20]
        updated = existing.model_copy(
            update={
                "occurrence_count": max(existing.occurrence_count + 1, entry.occurrence_count),
                "last_seen": datetime.now().isoformat(),
                "pattern_keywords": combined_keywords,
                "signature_patterns": combined_signatures,
                "resolution": entry.resolution or existing.resolution,
            }
        )
        by_id[entry.id] = updated
        entry = updated
    else:
        # Sanitize any forbidden words from new entry
        safe_kw = [kw for kw in entry.pattern_keywords if kw.lower() not in _FORBIDDEN_COMMON_WORDS]
        entry = entry.model_copy(update={"pattern_keywords": safe_kw})
        by_id[entry.id] = entry

    save_common_hallucinations(list(by_id.values()), target_file=target_file)
    return entry


# ── Text & Pattern Signature Matching ────────────────────────────────────────


def _check_file_pattern_match(file_name: str, patterns: list[str]) -> bool:
    """Evaluate whether a file name matches any glob patterns in the entry."""
    if not patterns or "*" in patterns:
        return True
    from fnmatch import fnmatch

    return any(
        fnmatch(file_name, pat) or fnmatch(file_name.lower(), pat.lower()) for pat in patterns
    )


def _check_signature_match(finding_text: str, signatures: list[str]) -> list[str]:
    """Evaluate if finding text matches any of the explicit signature regexes, returning matched text."""
    matches: list[str] = []
    for pattern in signatures:
        try:
            m = re.search(pattern, finding_text, re.IGNORECASE)
            if m:
                matches.append(m.group(0))
        except re.error:
            if pattern.lower() in finding_text.lower():
                matches.append(pattern)
    return matches


def _check_keyword_compound_match(finding_text: str, keywords: list[str]) -> list[str]:
    """Find matching non-common distinctive keywords in finding text."""
    clean_text = finding_text.lower()
    matches: list[str] = []
    for kw in keywords:
        clean_kw = kw.lower().strip()
        if clean_kw in _FORBIDDEN_COMMON_WORDS or len(clean_kw) <= 3:
            continue
        if clean_kw in clean_text:
            matches.append(kw)
    return matches


def _extract_defined_ast_names(tree: ast.AST) -> set[str]:
    """Extract all function, class, and assignment symbol names defined in an AST."""
    defined_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined_names.add(node.name)
        elif isinstance(node, ast.Assign):
            defined_names.update(
                target.id for target in node.targets if isinstance(target, ast.Name)
            )
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defined_names.add(node.target.id)
    return defined_names


def _verify_symbol_defined_in_ast_or_module(
    finding: Finding, tree: ast.AST, file_path: Path
) -> bool:
    """Verify whether a symbol claimed as missing actually exists in the file AST or exports."""
    finding_text = f"{finding.title} {finding.description or ''}"
    symbols = re.findall(r"\b[A-Z0-9_]{3,}\b", finding_text)
    if not symbols:
        return True

    defined_names = _extract_defined_ast_names(tree)
    raw_text = file_path.read_text(encoding="utf-8", errors="replace")
    for sym in symbols:
        if sym in defined_names or f"{sym} =" in raw_text or f"def {sym}" in raw_text:
            return True

    return False


def verify_ground_truth_hallucination(
    finding: Finding, entry: CommonHallucinationEntry, file_path: Path | None
) -> bool:
    """Verify ground truth in the actual target file before allowing hallucination invalidation.

    Guarantees that real defects, syntax errors, or plaintext secrets are NEVER invalidated.
    """
    if file_path is None or not file_path.exists() or not file_path.is_file():
        return False

    if entry.category == HallucinationCategory.SYNTAX_GRAMMAR:
        if file_path.suffix.lower() != ".py":
            return False
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            # Genuinely broken syntax! NEVER invalidate a real syntax error.
            return False

        if "missing" in entry.id.lower() or "symbol" in entry.id.lower():
            return _verify_symbol_defined_in_ast_or_module(finding, tree, file_path)

        return True

    if entry.category == HallucinationCategory.SECRET_SCANNING:
        # Check if finding explicitly points to masked/redacted placeholder
        finding_text = f"{finding.title} {finding.description or ''}"
        has_masked_token = bool(
            re.search(r"<masked-[a-zA-Z0-9_\-]+>|\*{3,}redacted\*{3,}", finding_text, re.IGNORECASE)
        )
        if not has_masked_token:
            return False
        # Read target line if location specified
        content = file_path.read_text(encoding="utf-8", errors="replace")
        loc = finding.location
        if ":" in loc:
            try:
                line_str = loc.split(":", 1)[1]
                num = int(re.split(r"[\s\-]", line_str.strip())[0])
                lines = content.splitlines()
                if 1 <= num <= len(lines):
                    target_line = lines[num - 1]
                    # Verify target line actually contains masked placeholder
                    return bool(
                        re.search(
                            r"<masked-[a-zA-Z0-9_\-]+>|\*{3,}redacted\*{3,}",
                            target_line,
                            re.IGNORECASE,
                        )
                    )
            except Exception:
                pass
        return bool(
            re.search(r"<masked-[a-zA-Z0-9_\-]+>|\*{3,}redacted\*{3,}", content, re.IGNORECASE)
        )

    if entry.category == HallucinationCategory.MUTABLE_DEFAULTS:
        # Verify target file actually uses default_factory on that line
        content = file_path.read_text(encoding="utf-8", errors="replace")
        return "default_factory" in content

    return False


def calculate_hallucination_similarity(
    finding: Finding, entry: CommonHallucinationEntry, file_path: Path | None = None
) -> HallucinationMatch:
    """Calculate similarity between a finding and a known common hallucination.

    ENFORCES SAFETY:
    1. Generic words (secret, token, error, etc.) are strictly excluded.
    2. Explicit signature regex matching is required.
    3. If target file is present for syntax claims, real syntax errors yield 0.0 score.
    """
    finding_text = f"{finding.title} {finding.description or ''}"
    loc_file = finding.location.split(":")[0].strip()
    file_matched = _check_file_pattern_match(Path(loc_file).name, entry.file_patterns)

    # Check explicit signature patterns first
    sig_matches = _check_signature_match(finding_text, entry.signature_patterns)
    matched_kws = _check_keyword_compound_match(finding_text, entry.pattern_keywords)

    if not (sig_matches or matched_kws):
        return HallucinationMatch(
            hallucination=entry,
            similarity_score=0.0,
            matched_keywords=[],
            reason="No signature pattern or distinctive compound keyword match",
        )

    finding_text_lower = finding_text.lower()

    # Category-specific domain validation guards
    if entry.category == HallucinationCategory.SYNTAX_GRAMMAR:
        syntax_indicators = (
            "syntax",
            "grammar",
            "except",
            "exception clause",
            "bracketless",
            "parentheses",
            "unparenthesized",
            "pep758",
            "python 2",
            "nameerror",
            "importerror",
            "undefined",
            "placeholder",
            "symbol",
            "import",
            "missing",
            "identifier",
        )
        if not any(si in finding_text_lower for si in syntax_indicators):
            return HallucinationMatch(
                hallucination=entry,
                similarity_score=0.0,
                matched_keywords=[],
                reason="Finding does not describe a syntax or grammar issue",
            )

        if file_path and file_path.exists() and file_path.suffix.lower() == ".py":
            try:
                ast.parse(file_path.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                # Real syntax error in source! Never match as hallucination.
                return HallucinationMatch(
                    hallucination=entry,
                    similarity_score=0.0,
                    matched_keywords=[],
                    reason="Target file has genuine SyntaxError; real defect confirmed",
                )

    if entry.category == HallucinationCategory.SECRET_SCANNING:
        secret_indicators = (
            "secret",
            "token",
            "key",
            "password",
            "credential",
            "masked",
            "redacted",
        )
        if not any(si in finding_text_lower for si in secret_indicators):
            return HallucinationMatch(
                hallucination=entry,
                similarity_score=0.0,
                matched_keywords=[],
                reason="Finding does not describe a secret, token, or credential issue",
            )

        # If it's a secret finding, it MUST match a masked placeholder pattern specifically
        has_masked_sig = bool(
            re.search(
                r"<masked-[a-zA-Z0-9_\-]+>|\*{3,}redacted\*{3,}|<secret-placeholder>",
                finding_text,
                re.IGNORECASE,
            )
        )
        if not has_masked_sig:
            return HallucinationMatch(
                hallucination=entry,
                similarity_score=0.0,
                matched_keywords=[],
                reason="Finding does not reference a verified masked/redacted placeholder",
            )

    # Require minimum 2 compound keywords if no explicit regex signature matched
    if not sig_matches and len(matched_kws) < 2:
        return HallucinationMatch(
            hallucination=entry,
            similarity_score=0.0,
            matched_keywords=matched_kws,
            reason="Insufficient compound keywords matched without signature pattern",
        )

    all_matched = list(dict.fromkeys(sig_matches + matched_kws))
    total_expected = max(1, len(entry.pattern_keywords))
    keyword_overlap = len(matched_kws) / total_expected

    if sig_matches:
        # Regex signature match represents structural pattern match (>= 0.70 confidence)
        # Scaled by keyword overlap for bonus confidence up to 1.0
        score = round(min(1.0, 0.70 + 0.30 * keyword_overlap), 3)
    else:
        # Without regex signature, score reflects normalized keyword overlap capped at 0.65
        score = round(min(0.65, keyword_overlap), 3)

    if not file_matched:
        score = round(score * 0.5, 3)

    return HallucinationMatch(
        hallucination=entry,
        similarity_score=score,
        matched_keywords=all_matched,
        reason=f"Matched signature/keywords for [{entry.id}]",
    )


def find_similar_hallucinations(
    finding: Finding,
    threshold: float = 0.5,
    file_path: Path | None = None,
    target_file: Path | None = None,
) -> list[HallucinationMatch]:
    """Find all catalogued hallucinations matching the candidate finding."""
    entries = load_common_hallucinations(target_file=target_file, include_builtin=True)
    matches: list[HallucinationMatch] = []

    for entry in entries:
        m = calculate_hallucination_similarity(finding, entry, file_path=file_path)
        if m.similarity_score >= threshold:
            matches.append(m)

    matches.sort(key=lambda x: x.similarity_score, reverse=True)
    return matches


def is_common_hallucination(
    finding: Finding,
    threshold: float = 0.6,
    file_path: Path | None = None,
    target_file: Path | None = None,
) -> HallucinationMatch | None:
    """Return top hallucination match if finding exceeds similarity threshold, else None."""
    matches = find_similar_hallucinations(
        finding, threshold=threshold, file_path=file_path, target_file=target_file
    )
    return matches[0] if matches else None


# ── Autonomous Management from Invalidation ──────────────────────────────────


def _infer_hallucination_category(title: str, reason: str) -> HallucinationCategory:
    """Map distinctive non-common terms in title and reason to HallucinationCategory."""
    combined = f"{title} {reason}".lower()
    dispatch_rules: list[tuple[set[str], HallucinationCategory]] = [
        (
            {"pep758", "bracketless", "unparenthesized", "grammar"},
            HallucinationCategory.SYNTAX_GRAMMAR,
        ),
        ({"masked", "redacted", "sanitization_marker"}, HallucinationCategory.SECRET_SCANNING),
        (
            {"dummy_token", "rfc2606", "example.com", "fake_credential"},
            HallucinationCategory.TEST_MOCKS,
        ),
        ({"typosquat", "httpx2"}, HallucinationCategory.DEPENDENCY_ECOSYSTEM),
        ({"anti-pattern", "educational"}, HallucinationCategory.DOCUMENTATION_CONTEXT),
        ({"default_factory", "pydantic_field"}, HallucinationCategory.MUTABLE_DEFAULTS),
        ({"eof", "out_of_bounds"}, HallucinationCategory.BOUNDARY_ERRORS),
    ]
    for keywords, category in dispatch_rules:
        if any(kw in combined for kw in keywords):
            return category
    return HallucinationCategory.GENERAL


def auto_record_invalidated_finding(
    finding: Finding,
    file_path: Path | None = None,
    reason: str | None = None,
    target_file: Path | None = None,
) -> CommonHallucinationEntry | None:
    """Automatically record an invalidated finding into the common hallucinations catalog."""
    effective_reason = reason or finding.invalidation_reason or ""
    matches = find_similar_hallucinations(
        finding, threshold=0.5, file_path=file_path, target_file=target_file
    )

    if matches:
        top_match = matches[0]
        entry = top_match.hallucination
        safe_hints = [
            h for h in _extract_keyword_hints(finding) if h not in _FORBIDDEN_COMMON_WORDS
        ]
        new_keywords = list(dict.fromkeys(entry.pattern_keywords + safe_hints))[:30]
        # Never overwrite canonical resolution of builtin entries
        resolution_to_use = entry.resolution
        if entry.source != "builtin" and effective_reason:
            resolution_to_use = effective_reason

        updated_entry = entry.model_copy(
            update={
                "occurrence_count": entry.occurrence_count + 1,
                "last_seen": datetime.now().isoformat(),
                "pattern_keywords": new_keywords,
                "resolution": resolution_to_use,
            }
        )
        return register_common_hallucination(updated_entry, target_file=target_file)

    # Synthesize new auto-learned entry if distinctive non-common reason or title is available
    if not (effective_reason or finding.title):
        return None

    safe_keywords = [
        kw
        for kw in _extract_keyword_hints(finding, effective_reason)
        if kw not in _FORBIDDEN_COMMON_WORDS and len(kw) > 4
    ]
    if not safe_keywords:
        return None

    cat = _infer_hallucination_category(finding.title, effective_reason)
    loc_file = finding.location.split(":")[0].strip()
    file_pat = [f"*{Path(loc_file).suffix}"] if loc_file and Path(loc_file).suffix else ["*"]

    # Synthesize a safe signature pattern from distinctive keywords
    sig = [re.escape(safe_keywords[0])]

    new_entry = CommonHallucinationEntry(
        id=f"HALLUCINATION-AUTO-{uuid4().hex[:8].upper()}",
        name=f"Auto-learned: {finding.title[:50]}",
        category=cat,
        description=finding.description or finding.title,
        signature_patterns=sig,
        pattern_keywords=safe_keywords[:15],
        file_patterns=file_pat,
        resolution=effective_reason or "Invalidated during review verification",
        occurrence_count=1,
        last_seen=datetime.now().isoformat(),
        source="auto_learned",
    )
    return register_common_hallucination(new_entry, target_file=target_file)


def _extract_keyword_hints(finding: Finding, extra_text: str = "") -> list[str]:
    """Extract notable distinctive keyword hints, strictly filtering all forbidden common words."""
    raw = f"{finding.title} {finding.description or ''} {extra_text}".lower()
    words = re.findall(r"[a-z0-9_\-\*]{4,}", raw)
    filtered = [w for w in words if w not in _FORBIDDEN_COMMON_WORDS and not w.isdigit()]
    return list(dict.fromkeys(filtered))
