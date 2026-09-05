"""Pydantic models and normalization utilities for structured code review output."""

from __future__ import annotations

import ast
import json
import re
import unicodedata
from collections.abc import Hashable, Iterable
from typing import Any

import json_repair
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from devops_cli.config import (
    DEFAULT_REVIEW_LINE_OVERLAP_TOLERANCE,
    DEFAULT_REVIEW_MAX_SUMMARY_PREVIEW_LENGTH,
    DEFAULT_REVIEW_MAX_TITLE_LENGTH,
    DEFAULT_REVIEW_TITLE_SIMILARITY_THRESHOLD,
)
from devops_cli.models.ai import FileAnalysisMeta
from devops_cli.models.vulnerability import (
    DependencySpec,
    NetworkReference,
    NetworkReputationRecord,
    VulnerabilityRecord,
)

# Constants & Configuration
_SEVERITY_RANK: dict[str, int] = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
    "INFO": 4,
}

VALID_SEVERITIES: frozenset[str] = frozenset(_SEVERITY_RANK.keys())
VALID_STATUSES: frozenset[str] = frozenset({"UNVERIFIED", "VERIFIED", "INVALIDATED", "MITIGATED"})
VALID_RECOMMENDATIONS: frozenset[str] = frozenset({"APPROVE", "REQUEST CHANGES", "BLOCK"})

LINE_OVERLAP_TOLERANCE: int = DEFAULT_REVIEW_LINE_OVERLAP_TOLERANCE
TITLE_SIMILARITY_THRESHOLD: float = DEFAULT_REVIEW_TITLE_SIMILARITY_THRESHOLD
MAX_TITLE_LENGTH: int = DEFAULT_REVIEW_MAX_TITLE_LENGTH
MAX_SUMMARY_PREVIEW_LENGTH: int = DEFAULT_REVIEW_MAX_SUMMARY_PREVIEW_LENGTH

_RECOMMENDATION_ALIASES: dict[str, str] = {
    "approve": "APPROVE",
    "request changes": "REQUEST CHANGES",
    "request_changes": "REQUEST CHANGES",
    "block": "BLOCK",
    "compliant": "APPROVE",
    "non-compliant": "BLOCK",
    "non_compliant": "BLOCK",
    "requires remediation": "REQUEST CHANGES",
    "requires_remediation": "REQUEST CHANGES",
}

_UNICODE_REPLACEMENTS: dict[str, str] = {
    "\u202f": " ",  # narrow no-break space
    "\u00a0": " ",  # no-break space
    "\u200b": "",  # zero-width space
    "\u2009": " ",  # thin space
    "\u200a": " ",  # hair space
    "\u2002": " ",  # en space
    "\u2003": " ",  # em space
    "\u3000": " ",  # ideographic space
    "\ufeff": "",  # zero-width no-break space / BOM
    "\u2011": "-",  # non-breaking hyphen
    "\u2010": "-",  # hyphen
    "\u2012": "-",  # figure dash
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2018": "'",  # left single quote
    "\u2019": "'",  # right single quote
    "\u201c": '"',  # left double quote
    "\u201d": '"',  # right double quote
    "\u201a": "'",  # single low-9 quote
    "\u201e": '"',  # double low-9 quote
    "\u2032": "'",  # prime
    "\u2033": '"',  # double prime
    "\u2026": "...",  # ellipsis
}

_TRANSLATE_TABLE = str.maketrans(_UNICODE_REPLACEMENTS)


def normalize_unicode_text(text: str) -> str:
    """Normalize non-standard Unicode spaces, hyphens, and quotes to standard ASCII."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    return normalized.translate(_TRANSLATE_TABLE)


def _parse_stringified_collection(s: str) -> list[Any] | None:
    """Attempt parsing a stringified Python/JSON list or tuple."""
    if not ((s.startswith("[") and s.endswith("]")) or (s.startswith("(") and s.endswith(")"))):
        return None
    for parser in (ast.literal_eval, json.loads):
        try:
            parsed = parser(s)
            if isinstance(parsed, (list, tuple, set)):
                return list(parsed)
        except Exception:
            continue
    return None


def format_clean_text_field(val: Any) -> str:
    """Normalize strings, lists, or stringified Python/JSON lists into clean, readable text."""
    if val is None:
        return ""
    if isinstance(val, (list, tuple, set)):
        return "\n".join(str(item).strip() for item in val if str(item).strip())
    if isinstance(val, str):
        s = val.strip()
        coll = _parse_stringified_collection(s)
        if coll is not None:
            return "\n".join(str(item).strip() for item in coll if str(item).strip())
        return s
    return str(val)


def _tokenize_title(title: str) -> set[str]:
    """Tokenize finding title into lowercase word tokens."""
    words = re.findall(r"\b[a-zA-Z0-9_]+\b", title.lower())
    return {w for w in words if len(w) > 2}


def _parse_finding_references(raw_ref: Any) -> list[str]:
    """Parse references from list, string, or literal representation."""
    if isinstance(raw_ref, list):
        return [normalize_unicode_text(str(r)).strip() for r in raw_ref if str(r).strip()]
    if not isinstance(raw_ref, str):
        return []
    cleaned = normalize_unicode_text(raw_ref).strip()
    coll = _parse_stringified_collection(cleaned)
    if coll is not None:
        return [normalize_unicode_text(str(r)).strip() for r in coll if str(r).strip()]
    return [r.strip() for r in cleaned.split(",") if r.strip()]


_PROMPT_CRITERIA_SPLIT_REGEX = re.compile(
    r"(?:Verification\s+criteria|Invalidation\s+criteria|:\s*line\s+where)",
    re.IGNORECASE,
)

_INSTRUCTION_HEADER_PREFIX_REGEX = re.compile(
    r"^(?:Provide\s+(?:fix|remediation|patch|verification|invalidation)|Title|Issue|Defect|Finding|Problem|Observation):\s*",
    re.IGNORECASE,
)

_PROMPT_PLACEHOLDER_BASENAMES: frozenset[str] = frozenset(
    {"file.ext", "filename.ext", "path/to/file.ext", "src/file.py", "path/to/file.py", "example.py"}
)

_MARKDOWN_LINK_REGEX = re.compile(r"\[([^\]]+)\]\([^)]+\)")


_SCRATCHPAD_PREFIX_REGEX = re.compile(
    r"^(?:(?:We|I)\s+(?:need to|must|should|will|have to)\b|Let's\b|Looking at\b|Reviewing\b|Checking\b|Based on\b)[^.\n]*[.?!:]\s*",
    re.IGNORECASE,
)

_APPROVAL_PREFIX_REGEX = re.compile(
    r"^(?:Good|Looks\s+good|Great)\.\s*But\s+",
    re.IGNORECASE,
)

_PRAISE_PREFIX_REGEX = re.compile(
    r"^(?:No issues(?:\s+found)?|Looks\s+solid|Looks\s+good|All\s+good|Clean\s+implementation|Properly\s+implemented|Correctly\s+handled)\b.*$",
    re.IGNORECASE,
)

_DEFECT_KEYWORD_REGEX = re.compile(
    r"\b(?:but|however|although|except|potential|issue|risk|bug|vulnerability|flaw|leak|fail|race|error|insecure|missing|unhandled|unvalidated)\b",
    re.IGNORECASE,
)


def sanitize_finding_text(text: str) -> str:
    """Scrub prompt criteria leakage, instruction headers, scratchpad prefixes, and markdown noise from text."""
    val = normalize_unicode_text(str(text)).strip()
    # Strip leading instruction headers first (e.g., 'Provide fix:', 'Title:', 'Issue:')
    val = _INSTRUCTION_HEADER_PREFIX_REGEX.sub("", val).strip()

    # Strip conversational approval prefix (e.g., 'Good. But potential...' -> 'Potential...')
    m_app = _APPROVAL_PREFIX_REGEX.match(val)
    if m_app:
        val = val[m_app.end() :].strip()
        if val:
            val = val[0].upper() + val[1:]

    # Strip leading chain-of-thought scratchpad sentences
    while True:
        m = _SCRATCHPAD_PREFIX_REGEX.match(val)
        if not m:
            break
        val = val[m.end() :].strip()
    # Strip trailing prompt criteria leakage
    if _PROMPT_CRITERIA_SPLIT_REGEX.search(val):
        val = _PROMPT_CRITERIA_SPLIT_REGEX.split(val)[0].strip()

    # Check for pure praise / no-issue confirmation
    if _PRAISE_PREFIX_REGEX.match(val):
        return ""
    if val.endswith(
        ("Good.", "Good", "Looks good.", "Looks solid.")
    ) and not _DEFECT_KEYWORD_REGEX.search(val):
        return ""

    return val


def unique_items[T: Hashable](items: Iterable[T]) -> list[T]:
    """Preserve only the first instance of each item in a collection using a set."""
    seen: set[T] = set()
    result: list[T] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def unique_lines(text: str) -> str:
    """Preserve only the first instance of each line or string in text or thinking responses using a set."""
    if not text:
        return ""
    seen: set[str] = set()
    result: list[str] = []
    for line in text.splitlines():
        trimmed = line.strip()
        if not trimmed:
            if result and result[-1] != "":
                result.append("")
            continue
        if trimmed not in seen:
            seen.add(trimmed)
            result.append(line)
    return "\n".join(result)


def canonicalize_finding_location(location: str) -> str:
    """Canonicalize raw LLM location text into standard path/to/file.ext:start-end or path/to/file.ext:line."""
    loc = normalize_unicode_text(str(location)).strip()
    if not loc or "\n" in loc or "```" in loc:
        return ""

    if loc.startswith("#") or not any(c.isalnum() for c in loc):
        return ""

    m_link = _MARKDOWN_LINK_REGEX.search(loc)
    if m_link:
        loc = m_link.group(1).strip()

    loc = loc.strip("`'\"()[]*# ")
    if not loc or not any(c.isalnum() for c in loc):
        return ""

    had_prompt_leakage = False
    if _PROMPT_CRITERIA_SPLIT_REGEX.search(loc):
        loc = _PROMPT_CRITERIA_SPLIT_REGEX.split(loc)[0].strip()
        had_prompt_leakage = True

    loc = re.sub(r"#L?(\d+)(?:-L?(\d+))?", r":\1-\2", loc).rstrip("-")
    loc = re.sub(
        r"[,:]\s*lines?\s*(\d+)(?:\s*[-–—:]\s*(\d+))?",
        r":\1-\2",
        loc,
        flags=re.IGNORECASE,
    ).rstrip("-")
    loc = re.sub(r"\s*:\s*", ":", loc)
    loc = re.sub(r"(\d+)\s*[-–—]\s*(\d+)", r"\1-\2", loc)

    loc_file = loc.split(":")[0].strip()
    from pathlib import Path

    if (
        loc_file.lower() in _PROMPT_PLACEHOLDER_BASENAMES
        or Path(loc_file).name.lower() in _PROMPT_PLACEHOLDER_BASENAMES
    ):
        return ""

    m_loc = re.match(r"^([a-zA-Z0-9_\-./\\]+)(?::(\d+)(?:-(\d+))?)?$", loc)
    if m_loc:
        file_path = m_loc.group(1).replace("\\", "/")
        s_str = m_loc.group(2)
        e_str = m_loc.group(3)

        if not s_str:
            return f"{file_path}:1" if had_prompt_leakage else file_path

        s_line = int(s_str)
        e_line = int(e_str) if e_str else None

        if e_line is not None and s_line > e_line:
            s_line, e_line = e_line, s_line

        if e_line is not None and e_line != s_line:
            return f"{file_path}:{s_line}-{e_line}"
        return f"{file_path}:{s_line}"

    # Match general target specifiers without spaces, e.g. uv.lock:jinja2, Dockerfile:cve-1, k8s/app.yaml:Deployment/app
    m_target = re.match(r"^([a-zA-Z0-9_\-./\\]+):([a-zA-Z0-9_\-./\\]+)$", loc)
    if m_target:
        return f"{m_target.group(1).replace('\\', '/')}:{m_target.group(2)}"

    # Extract embedded valid file location if present in conversational or scratchpad text
    m_embedded = re.search(
        r"(?:^|[\s:\"'`])([a-zA-Z0-9_\-./\\]+/[a-zA-Z0-9_\-.]+|[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+)(?::(\d+)(?:-(\d+))?)?",
        loc,
    )
    if m_embedded:
        candidate_file = m_embedded.group(1).replace("\\", "/").rstrip(".")
        if (
            candidate_file.lower() not in _PROMPT_PLACEHOLDER_BASENAMES
            and Path(candidate_file).name.lower() not in _PROMPT_PLACEHOLDER_BASENAMES
        ):
            s_str = m_embedded.group(2)
            e_str = m_embedded.group(3)
            if s_str:
                s_line = int(s_str)
                e_line = int(e_str) if e_str else None
                if e_line is not None and s_line > e_line:
                    s_line, e_line = e_line, s_line
                if e_line is not None and e_line != s_line:
                    return f"{candidate_file}:{s_line}-{e_line}"
                return f"{candidate_file}:{s_line}"
            return candidate_file

    # Reject conversational scratchpad or prompt instruction leakage
    has_scratchpad_phrase = bool(
        re.search(
            r"\b(?:file path and line numbers|we need to|let's|where the vulnerability occurs)\b",
            loc,
            re.IGNORECASE,
        )
    )
    is_conversational_sentence = len(loc.split()) > 3 and any(p in loc for p in (".", "!", "?"))
    if has_scratchpad_phrase or is_conversational_sentence:
        return ""

    return loc


class Finding(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    severity: str = Field(
        default="MEDIUM", validation_alias=AliasChoices("severity", "level", "priority")
    )
    location: str = Field(
        default="",
        validation_alias=AliasChoices("location", "file", "path", "target", "line", "lines"),
    )
    title: str = Field(
        default="",
        validation_alias=AliasChoices(
            "title", "issue", "problem", "name", "summary", "heading", "finding"
        ),
    )
    description: str = Field(
        default="",
        validation_alias=AliasChoices(
            "description", "details", "detail", "impact", "explanation", "message", "body"
        ),
    )
    fix: str = Field(
        default="",
        validation_alias=AliasChoices(
            "fix", "remediation", "recommendation", "suggested_fix", "solution", "patch"
        ),
    )
    references: list[str] = Field(default_factory=list)
    verification_criteria: list[str] = Field(
        default_factory=list, validation_alias=AliasChoices("verification_criteria", "verification")
    )
    invalidation_criteria: list[str] = Field(
        default_factory=list, validation_alias=AliasChoices("invalidation_criteria", "invalidation")
    )
    verified_criteria_matched: list[str] = Field(default_factory=list)
    invalidated_criteria_matched: list[str] = Field(default_factory=list)
    reportable: bool = True
    verified: bool = False

    mitigated: bool = False
    status: str = "UNVERIFIED"  # UNVERIFIED | VERIFIED | INVALIDATED | MITIGATED
    invalidation_reason: str | None = None
    verified_by: str | None = None  # "llm" | "human"
    verified_at: str | None = None
    confidence_score: float | None = None
    thinking: str | None = None

    @property
    def is_empty(self) -> bool:
        """Check if finding is blank or lacks a valid target location."""
        clean_title = sanitize_finding_text(self.title).strip()
        clean_loc = canonicalize_finding_location(self.location).strip()
        if not clean_title or not clean_loc:
            return True
        if "\n" in clean_loc or "```" in clean_loc:
            return True
        if clean_loc in {"**", "*", "---", "##", "###"} or not any(c.isalnum() for c in clean_loc):
            return True

        file_part, _, _ = _parse_location(clean_loc)
        if not file_part or file_part in {"none", "n/a", "na", "null", "undefined"}:
            return True
        return False

    @field_validator("description", "fix", mode="before")
    @classmethod
    def _clean_body_fields(cls, v: object) -> str:
        text = format_clean_text_field(v)
        sanitized = sanitize_finding_text(text)
        return unique_lines(sanitized)

    @field_validator("thinking", mode="before")
    @classmethod
    def _clean_thinking(cls, v: object) -> str | None:
        if not v:
            return None
        cleaned = unique_lines(normalize_unicode_text(str(v)))
        return cleaned if cleaned.strip() else None

    @field_validator("location", mode="before")
    @classmethod
    def _clean_location(cls, v: object) -> str:
        return canonicalize_finding_location(str(v))

    @field_validator("title", mode="before")
    @classmethod
    def _clean_title(cls, v: object) -> str:
        if isinstance(v, (list, tuple, set)):
            text = " ".join(str(item).strip() for item in v if str(item).strip())
        else:
            text = format_clean_text_field(v)
        text = sanitize_finding_text(text)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return ""
        first_line = re.sub(r"^(?:#+\s*|\d+\.\s*|\*\s*|-\s*)", "", lines[0]).strip()
        collapsed = re.sub(r"\s+", " ", first_line)
        return collapsed[:MAX_TITLE_LENGTH]

    @field_validator(
        "references",
        "verification_criteria",
        "invalidation_criteria",
        "verified_criteria_matched",
        "invalidated_criteria_matched",
        mode="before",
    )
    @classmethod
    def _clean_references(cls, v: object) -> list[str]:
        return _parse_finding_references(v)

    @field_validator("severity", mode="before")
    @classmethod
    def _normalize_severity(cls, v: object) -> str:
        s = str(v).upper().strip()
        return s if s in VALID_SEVERITIES else "MEDIUM"

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, v: object) -> str:
        s = str(v).upper().strip()
        return s if s in VALID_STATUSES else "UNVERIFIED"

    @field_validator("confidence_score", mode="before")
    @classmethod
    def _normalize_confidence(cls, v: object) -> float | None:
        return _parse_confidence_score(v)


def _parse_confidence_score(v: object) -> float | None:
    """Parse and clamp confidence score between 0.0 and 1.0."""
    if v is None or str(v).lower() in ("null", "none", ""):
        return None
    try:
        val = float(str(v))
        return max(0.0, min(1.0, val))
    except ValueError, TypeError:
        return None


def _filter_non_empty_findings[T: (Finding, SavedFinding)](v: list[T]) -> list[T]:
    """Filter out empty finding records from lists."""
    return [f for f in v if not f.is_empty]


def _parse_location(location: str) -> tuple[str, int | None, int | None]:
    """Extract normalized (filepath, start_line, end_line) from a location string."""
    loc = location.strip()
    if not loc:
        return "", None, None

    m = re.search(
        r"^(.*?)(?:[#:]\s*(?:lines?\s*)?(?:L)?(\d+)(?:\s*[-–—:]\s*(?:L)?(\d+))?)?$",
        loc,
        re.IGNORECASE,
    )
    if not m:
        return loc.lower().replace("\\", "/"), None, None

    file_part = (m.group(1) or "").strip().lower().replace("\\", "/")
    s_line_str = m.group(2)
    e_line_str = m.group(3)

    s_line = int(s_line_str) if s_line_str else None
    e_line = int(e_line_str) if e_line_str else s_line

    if s_line is not None and e_line is not None and s_line > e_line:
        s_line, e_line = e_line, s_line

    return file_part, s_line, e_line


def _are_findings_duplicate(f1: Finding, f2: Finding) -> bool:
    """Determine if two findings describe the same underlying issue across personas or segments."""
    file1, s1, e1 = _parse_location(f1.location)
    file2, s2, e2 = _parse_location(f2.location)
    t1 = f1.title.strip().lower()
    t2 = f2.title.strip().lower()

    if not file1 or not file2 or file1 != file2:
        return False

    if t1 == t2:
        return True

    tokens1 = _tokenize_title(t1)
    tokens2 = _tokenize_title(t2)

    intersection = tokens1 & tokens2
    union = tokens1 | tokens2
    jaccard = len(intersection) / len(union) if union else 0.0

    same_line_range = (
        s1 is not None
        and e1 is not None
        and s2 is not None
        and e2 is not None
        and max(s1, s2) <= min(e1, e2) + LINE_OVERLAP_TOLERANCE
    )

    if (s1 == s2 and e1 == e2) or (s1 is None and s2 is None):
        if jaccard >= TITLE_SIMILARITY_THRESHOLD or (
            tokens1 and tokens2 and len(intersection) / min(len(tokens1), len(tokens2)) >= 0.6
        ):
            return True
    elif same_line_range:
        if jaccard >= 0.4 or (
            tokens1 and tokens2 and len(intersection) / min(len(tokens1), len(tokens2)) >= 0.5
        ):
            return True

    return False


def _merge_two_findings[F: Finding](base: F, other: F) -> F:
    """Merge duplicate finding `other` into `base`, taking highest severity and confidence."""
    sev1 = base.severity.upper().strip()
    sev2 = other.severity.upper().strip()
    best_sev = sev1 if _SEVERITY_RANK.get(sev1, 99) <= _SEVERITY_RANK.get(sev2, 99) else sev2

    c1 = base.confidence_score
    c2 = other.confidence_score
    best_conf: float | None = None
    if c1 is not None and c2 is not None:
        best_conf = max(c1, c2)
    elif c1 is not None:
        best_conf = c1
    else:
        best_conf = c2

    status_order = {"VERIFIED": 0, "UNVERIFIED": 1, "MITIGATED": 2, "INVALIDATED": 3}
    best_status = (
        base.status
        if status_order.get(base.status, 99) <= status_order.get(other.status, 99)
        else other.status
    )
    verified = base.verified or other.verified
    mitigated = (base.mitigated or other.mitigated) if not verified else False

    desc = (
        base.description if len(base.description) >= len(other.description) else other.description
    )
    fix = base.fix if len(base.fix) >= len(other.fix) else other.fix
    refs = list(dict.fromkeys(base.references + other.references))
    ver_crit = list(dict.fromkeys(base.verification_criteria + other.verification_criteria))
    inv_crit = list(dict.fromkeys(base.invalidation_criteria + other.invalidation_criteria))
    ver_match = list(
        dict.fromkeys(base.verified_criteria_matched + other.verified_criteria_matched)
    )
    inv_match = list(
        dict.fromkeys(base.invalidated_criteria_matched + other.invalidated_criteria_matched)
    )
    if not verified and (base.mitigated or other.mitigated):
        reportable = base.reportable and other.reportable
    else:
        reportable = base.reportable or other.reportable

    updates: dict[str, Any] = {
        "severity": best_sev,
        "confidence_score": best_conf,
        "status": best_status,
        "verified": verified,
        "mitigated": mitigated,
        "description": desc,
        "fix": fix,
        "references": refs,
        "verification_criteria": ver_crit,
        "invalidation_criteria": inv_crit,
        "verified_criteria_matched": ver_match,
        "invalidated_criteria_matched": inv_match,
        "reportable": reportable,
    }

    if isinstance(base, SavedFinding):
        base_personas = [p.strip() for p in base.persona.split(",") if p.strip()]
        other_personas = (
            [p.strip() for p in other.persona.split(",") if p.strip()]
            if isinstance(other, SavedFinding)
            else []
        )
        for p in other_personas:
            if p and p not in base_personas:
                base_personas.append(p)
        updates["persona"] = ", ".join(base_personas)

        base_titles = [t.strip() for t in base.persona_title.split(",") if t.strip()]
        other_titles = (
            [t.strip() for t in other.persona_title.split(",") if t.strip()]
            if isinstance(other, SavedFinding)
            else []
        )
        for t in other_titles:
            if t and t not in base_titles:
                base_titles.append(t)
        updates["persona_title"] = ", ".join(base_titles)

    return base.model_copy(update=updates)


def consolidate_duplicate_findings[F: Finding](findings: list[F]) -> list[F]:
    """Consolidate duplicate findings across personas, merging metadata and scores."""
    if not findings:
        return []

    consolidated: list[F] = []
    for f in findings:
        matched = False
        for idx, existing in enumerate(consolidated):
            if _are_findings_duplicate(existing, f):
                consolidated[idx] = _merge_two_findings(existing, f)
                matched = True
                break
        if not matched:
            consolidated.append(f)

    return sort_findings(consolidated)


def sort_findings[F: Finding](findings: list[F]) -> list[F]:
    """Sort findings by reportability, severity rank, confidence score descending, then verified."""
    return sorted(
        findings,
        key=lambda f: (
            not f.reportable,
            _SEVERITY_RANK.get(f.severity.upper().strip(), 99),
            -(f.confidence_score if f.confidence_score is not None else -1.0),
            not f.verified,
        ),
    )


class SavedFinding(Finding):
    persona: str = ""
    persona_title: str = ""
    recommendation: str = "REQUEST CHANGES"


class FileReviewPayload(BaseModel):
    file_path: str
    metadata: FileAnalysisMeta | None = None
    linked_files: list[FileAnalysisMeta] = Field(default_factory=list)
    findings: list[SavedFinding] = Field(default_factory=list)
    ai_scratchpad: dict[str, Any] = Field(default_factory=dict)
    thinking_traces: dict[str, str] = Field(default_factory=dict)
    external_dependencies: list[DependencySpec] = Field(default_factory=list)
    network_references: list[NetworkReference] = Field(default_factory=list)
    reportable: bool = True

    @field_validator("findings", mode="after")
    @classmethod
    def _filter_valid_findings(cls, v: list[SavedFinding]) -> list[SavedFinding]:
        return _filter_non_empty_findings(v)


class ReviewSessionPayload(BaseModel):
    generated_at: str = ""
    personas: list[str] = Field(default_factory=list)
    findings: list[SavedFinding] = Field(default_factory=list)
    external_dependencies: list[DependencySpec] = Field(default_factory=list)
    dependency_vulnerabilities: list[VulnerabilityRecord] = Field(default_factory=list)
    network_references: list[NetworkReference] = Field(default_factory=list)
    network_reputations: list[NetworkReputationRecord] = Field(default_factory=list)

    @field_validator("findings", mode="after")
    @classmethod
    def _filter_valid_findings(cls, v: list[SavedFinding]) -> list[SavedFinding]:
        return _filter_non_empty_findings(v)

    @property
    def sorted_findings(self) -> list[SavedFinding]:
        return consolidate_duplicate_findings(self.findings)


def derive_recommendation(findings: list[Finding]) -> str:
    """Deterministically derive merge recommendation based on verified and reportable findings."""
    reportable = [
        f
        for f in findings
        if not f.is_empty
        and f.reportable
        and f.status not in {"INVALIDATED", "MITIGATED"}
        and f.severity in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
    ]
    if not reportable:
        return "APPROVE"
    if any(f.severity == "CRITICAL" for f in reportable):
        return "BLOCK"
    return "REQUEST CHANGES"


class ReviewResult(BaseModel):
    findings: list[Finding] = Field(default_factory=list)
    positive_observations: list[str] = Field(default_factory=list)
    recommendation: str = "REQUEST CHANGES"
    summary: str = ""
    thinking: str | None = None
    confidence_score: float | None = None
    external_dependencies: list[DependencySpec] = Field(default_factory=list)
    network_references: list[NetworkReference] = Field(default_factory=list)

    @field_validator("findings", mode="after")
    @classmethod
    def _filter_valid_findings(cls, v: list[Finding]) -> list[Finding]:
        return _filter_non_empty_findings(v)

    @model_validator(mode="after")
    def _sync_recommendation(self) -> ReviewResult:
        self.recommendation = derive_recommendation(self.findings)
        return self

    @field_validator("summary", mode="before")
    @classmethod
    def _clean_summary(cls, v: object) -> str:
        return normalize_unicode_text(str(v)).strip()

    @field_validator("thinking", mode="before")
    @classmethod
    def _clean_thinking(cls, v: object) -> str | None:
        if not v:
            return None
        cleaned = unique_lines(normalize_unicode_text(str(v)))
        return cleaned if cleaned.strip() else None

    @field_validator("positive_observations", mode="before")
    @classmethod
    def _clean_positive_observations(cls, v: object) -> list[str]:
        if isinstance(v, list):
            return [normalize_unicode_text(str(r)).strip() for r in v if str(r).strip()]
        return []

    @field_validator("recommendation", mode="before")
    @classmethod
    def _normalize_recommendation(cls, v: object) -> str:
        s = str(v).strip()
        return _RECOMMENDATION_ALIASES.get(s.lower(), s.upper())

    @field_validator("confidence_score", mode="before")
    @classmethod
    def _normalize_confidence(cls, v: object) -> float | None:
        return _parse_confidence_score(v)

    @property
    def sorted_findings(self) -> list[Finding]:
        return consolidate_duplicate_findings(self.findings)

    def merge(self, other: ReviewResult) -> ReviewResult:
        """Merge another ReviewResult, deduplicating and consolidating findings."""
        merged_findings = consolidate_duplicate_findings(self.findings + other.findings)
        recommendation = derive_recommendation(merged_findings)
        scores = [s for s in (self.confidence_score, other.confidence_score) if s is not None]
        merged_conf = round(sum(scores) / len(scores), 2) if scores else None
        return ReviewResult(
            findings=merged_findings,
            positive_observations=list(
                dict.fromkeys(self.positive_observations + other.positive_observations)
            ),
            recommendation=recommendation,
            summary=self.summary or other.summary,
            confidence_score=merged_conf,
        )


def extract_json_block(text: str) -> Any:
    """Extract and repair the first parseable JSON object or array from text using json-repair."""
    if not text or not text.strip():
        return None

    try:
        data = json_repair.loads(text)
        if data != "" and data is not None:
            return data
    except Exception:
        pass

    for pattern in (r"```(?:json)?\s*([\s\S]*?)```",):
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                data = json_repair.loads(m.group(1))
                if data != "" and data is not None:
                    return data
            except Exception:
                pass
    return None


def _validate_raw_findings_list(data: list[Any]) -> list[Finding]:
    """Validate and filter list of raw dictionary findings."""
    parsed_findings: list[Finding] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            f = Finding.model_validate(item)
            if not f.is_empty:
                parsed_findings.append(f)
        except Exception:
            pass
    return parsed_findings


def parse_review_response(response: str | Any) -> ReviewResult | None:
    """Parse review LLM response, prioritizing standard Pydantic and pydantic_ai.messages structured output."""
    from devops_cli.ai.response_repair import fix_llm_response

    fixed = fix_llm_response(response, schema=ReviewResult)
    if fixed.parsed_model is not None and isinstance(fixed.parsed_model, ReviewResult):
        if fixed.thinking and not fixed.parsed_model.thinking:
            fixed.parsed_model.thinking = fixed.thinking
        return fixed.parsed_model

    data = fixed.json_data or extract_json_block(fixed.content)
    if isinstance(data, list):
        parsed_findings = _validate_raw_findings_list(data)
        if parsed_findings:
            return ReviewResult(
                findings=parsed_findings,
                recommendation="APPROVE" if not parsed_findings else "REQUEST CHANGES",
                summary=f"Extracted {len(parsed_findings)} finding(s)",
                thinking=fixed.thinking,
            )
    elif isinstance(data, dict):
        try:
            res = ReviewResult.model_validate(data)
            if fixed.thinking and not res.thinking:
                res.thinking = fixed.thinking
            return res
        except Exception:
            pass

    return None
