"""Pydantic models and normalization utilities for structured code review output."""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Hashable, Iterable
from pathlib import PurePosixPath
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from devops_cli.ai.text_utils import (
    normalize_unicode_text as normalize_unicode_text,
)
from devops_cli.ai.text_utils import (
    unique_lines as unique_lines,
)
from devops_cli.config import (
    DEFAULT_FINDING_STATUS,
    DEFAULT_REVIEW_LINE_OVERLAP_TOLERANCE,
    DEFAULT_REVIEW_MAX_SUMMARY_PREVIEW_LENGTH,
    DEFAULT_REVIEW_MAX_TITLE_LENGTH,
    DEFAULT_REVIEW_TITLE_SIMILARITY_THRESHOLD,
)
from devops_cli.config.constants import (
    REVIEW_DESCRIPTION_SIMILARITY_THRESHOLD,
    REVIEW_GENERIC_SYMBOL_STOPWORDS,
    REVIEW_STRONG_SYMBOL_MIN_LENGTH,
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
# Severity names models use outside the schema. Folding them all into MEDIUM turned a BLOCKER
# into a request for changes and a suggestion into one.
_SEVERITY_SYNONYMS: dict[str, str] = {
    "BLOCKER": "CRITICAL",
    "SEVERE": "CRITICAL",
    "P0": "CRITICAL",
    "P1": "HIGH",
    "MAJOR": "HIGH",
    "P2": "MEDIUM",
    "MODERATE": "MEDIUM",
    "P3": "LOW",
    "MINOR": "LOW",
    "TRIVIAL": "LOW",
    "SUGGESTION": "INFO",
    "INFORMATIONAL": "INFO",
    "NOTE": "INFO",
}
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
        items = [
            str(item).strip()
            for item in val
            if str(item).strip() and str(item).strip() not in ("**", "*", "---")
        ]
        return "\n".join(items)
    if isinstance(val, str):
        s = val.strip()
        coll = _parse_stringified_collection(s)
        if coll is not None:
            items = [
                str(item).strip()
                for item in coll
                if str(item).strip() and str(item).strip() not in ("**", "*", "---")
            ]
            return "\n".join(items)
        lines = [line for line in s.splitlines() if line.strip() not in ("**", "*", "---")]
        return "\n".join(lines).strip()
    return str(val)


# Words that open many unrelated findings ("Missing timeout", "Missing authorization check").
# Counting them as shared words merges different defects.
_TITLE_FILLER_WORDS = frozenset(
    {
        "missing",
        "lack",
        "lacks",
        "lacking",
        "absent",
        "potential",
        "possible",
        "possibly",
        "insecure",
        "unsafe",
        "improper",
        "improperly",
        "incorrect",
        "inadequate",
        "insufficient",
        "weak",
        "issue",
        "issues",
        "risk",
        "risks",
        "vulnerability",
        "vulnerable",
        "problem",
        "use",
        "uses",
        "using",
        "usage",
        "without",
        "not",
        "the",
        "and",
        "for",
        "with",
        "from",
        "via",
        "into",
        "when",
        "may",
        "can",
        "could",
        "due",
        "are",
        "has",
        "have",
        "does",
        "should",
    }
)


def _tokenize_title(title: str) -> set[str]:
    """The words of a finding's text that tell it apart from other findings."""
    words = re.findall(r"\b[a-zA-Z0-9_]+\b", title.lower())
    return {w for w in words if len(w) > 2 and w not in _TITLE_FILLER_WORDS}


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


# A leaked prompt section ("Verification criteria: ..."), not a finding about criteria.
_PROMPT_CRITERIA_SPLIT_REGEX = re.compile(
    r"(?:(?:Verification|Invalidation)\s+criteria\s*:|:\s*line\s+where)",
    re.IGNORECASE,
)

_INSTRUCTION_HEADER_PREFIX_REGEX = re.compile(
    r"^(?:\*\*)?(?:Provide\s+(?:fix|remediation|patch|verification|invalidation)|Title|Issue|Defect|Finding|Problem|Observation|Description|Fix|Location)(?:\*\*)?:\s*(?:\*\*)?\s*",
    re.IGNORECASE,
)

_PROMPT_PLACEHOLDER_BASENAMES: frozenset[str] = frozenset(
    {"file.ext", "filename.ext", "path/to/file.ext", "src/file.py", "path/to/file.py", "example.py"}
)

_MARKDOWN_LINK_REGEX = re.compile(r"\[([^\]]+)\]\([^)]+\)")

# Characters a path segment may hold: letters and digits of any script, and the punctuation file
# names use (`c++`, `@scope`, `logo@2x`, `~/.config`, `100%`). A narrower class cut a path at the
# first other character and kept the fragment before it.
_SEGMENT_CHARS = r"\w\-.+@~%"
_PATH_CHARS = rf"{_SEGMENT_CHARS}/\\"
_LOCATION_REGEX = re.compile(rf"^([{_PATH_CHARS}]+)(?::(\d+)(?:-(\d+))?)?$")
_TARGET_LOCATION_REGEX = re.compile(rf"^([{_PATH_CHARS}]+):([{_PATH_CHARS}]+)$")
_EMBEDDED_LOCATION_REGEX = re.compile(
    rf"(?:^|[\s:\"'`])([{_PATH_CHARS}]+/[{_SEGMENT_CHARS}]+|[\w\-]+\.[\w\-]+)"
    r"(?::(\d+)(?:-(\d+))?)?"
)


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


def strip_outer_markdown_bold(text: str) -> str:
    """Strip paired outer markdown bold markers (**text**) while preserving legitimate prefixes like **kwargs."""
    val = text.strip()
    if val.startswith("**") and val.endswith("**") and len(val) >= 4:
        inner = val[2:-2].strip()
        # Verify outer bold is not prematurely closed by an un-backticked `**` inside
        non_code = re.sub(r"`[^`]*`", "", inner)
        if "**" not in non_code:
            return inner
    return val


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

    # Strip leading chain-of-thought scratchpad sentences, but never the only sentence:
    # "Checking of token expiry is missing." is the finding itself.
    while (m := _SCRATCHPAD_PREFIX_REGEX.match(val)) and val[m.end() :].strip():
        val = val[m.end() :].strip()
    # Strip trailing prompt criteria leakage
    if _PROMPT_CRITERIA_SPLIT_REGEX.search(val):
        val = _PROMPT_CRITERIA_SPLIT_REGEX.split(val)[0].strip()

    # Check for pure praise / no-issue confirmation; "Looks good overall, but the token is
    # logged in plaintext" is a finding.
    if _PRAISE_PREFIX_REGEX.match(val) and not _DEFECT_KEYWORD_REGEX.search(val):
        return ""
    if val.endswith(
        ("Good.", "Good", "Looks good.", "Looks solid.")
    ) and not _DEFECT_KEYWORD_REGEX.search(val):
        return ""

    # Strip paired outer markdown bold markers while preserving legitimate prefixes like **kwargs
    val = strip_outer_markdown_bold(val)

    return val.strip()


def unique_items[T: Hashable](items: Iterable[T]) -> list[T]:
    """Preserve only the first instance of each item in a collection using a set."""
    seen: set[T] = set()
    result: list[T] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


# A bare file name: a name with an extension, which only the file under review may carry.
_FILE_NAME = re.compile(r"\.[A-Za-z0-9]{1,8}$")
# The name a bare location starts with, and a line range after a space when it has no colon:
# `getBodySize:18-24`, `nvm_alias_path() { 1368-1374`.
_BARE_NAME = re.compile(r"\s*([\w.$-]+)")
_SPACED_LINES = re.compile(r"\s(\d+(?:-\d+)?)\s*$")


def anchor_location(location: str, file_path: str, page_text: str = "") -> str:
    """Tie a location that names no directory to the file under review, keeping its lines.

    A model may name the file alone (`Dockerfile:7`) or a function in it (`getBodySize:18-24`).
    The location becomes the reviewed file's path when it names that file, or a symbol the page
    under review shows. Otherwise it is left as it is: it may name another file.
    """
    loc = location.strip()
    if not loc:
        return file_path
    head, _, tail = loc.partition(":")
    name_match = _BARE_NAME.match(head)
    if "/" in head or "\\" in head or not name_match:
        return loc
    name = name_match.group(1)
    if _FILE_NAME.search(name) or name.lower() == PurePosixPath(file_path).name.lower():
        names_this_file = name.lower() == PurePosixPath(file_path).name.lower()
    else:
        names_this_file = bool(
            page_text and re.search(rf"(?<![\w$]){re.escape(name)}(?![\w$])", page_text)
        )
    if not names_this_file:
        return loc
    if tail.strip():
        return f"{file_path}:{tail.strip()}"
    lines = _SPACED_LINES.search(head)
    return f"{file_path}:{lines.group(1)}" if lines else file_path


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

    m_loc = _LOCATION_REGEX.match(loc)
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
    m_target = _TARGET_LOCATION_REGEX.match(loc)
    if m_target:
        return f"{m_target.group(1).replace('\\', '/')}:{m_target.group(2)}"

    # Extract embedded valid file location if present in conversational or scratchpad text
    m_embedded = _EMBEDDED_LOCATION_REGEX.search(loc)
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


class VerificationCriterion(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    command: str | None = Field(
        default=None,
        description="Read-only allowlisted command to execute for verification or invalidation.",
    )
    description: str = Field(
        default="",
        description="Human-readable description of the condition or rationale if unexecutable.",
    )
    executable: bool = Field(
        default=False,
        description="Whether this criterion is an executable command from the allowlist.",
    )

    def __str__(self) -> str:
        return self.command if (self.executable and self.command) else self.description

    def __hash__(self) -> int:
        return hash((self.command, self.description, self.executable))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return other in (self.command, self.description)
        if isinstance(other, VerificationCriterion):
            return (self.command, self.description, self.executable) == (
                other.command,
                other.description,
                other.executable,
            )
        return False

    @model_validator(mode="before")
    @classmethod
    def _normalize_criterion(cls, data: Any) -> Any:
        if isinstance(data, str):
            text = data.strip()
            from devops_cli.ai.review.review_environment import validate_criteria_command

            is_valid, _, _ = validate_criteria_command(text)
            if is_valid:
                return {"command": text, "description": text, "executable": True}
            return {"command": None, "description": text, "executable": False}
        if isinstance(data, dict):
            cmd = data.get("command")
            cmd_str = str(cmd).strip() if cmd else None
            desc = data.get("description") or (cmd_str if cmd_str else "")
            is_exec = bool(data.get("executable", False))
            if is_exec:
                if not cmd_str:
                    raise ValueError("Executable criterion requires a non-empty command")
                from devops_cli.ai.review.review_environment import validate_criteria_command

                is_valid, reason, _ = validate_criteria_command(cmd_str)
                if not is_valid:
                    raise ValueError(
                        f"Criterion marked executable but command is not in closed read-only allowlist: {reason}"
                    )
            return {
                "command": cmd_str,
                "description": str(desc).strip(),
                "executable": is_exec,
            }
        return data


class CriterionExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    command: str | None = None
    description: str = ""
    executable: bool = False
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    passed: bool = False
    error: str | None = None

    def __hash__(self) -> int:
        return hash((self.command, self.exit_code, self.passed, self.error))


def _parse_single_criterion(raw: Any) -> VerificationCriterion | None:
    if isinstance(raw, VerificationCriterion):
        return raw
    try:
        return VerificationCriterion.model_validate(raw)
    except Exception:
        if isinstance(raw, dict):
            desc = str(raw.get("description") or raw.get("command") or "").strip()
            return VerificationCriterion(command=None, description=desc, executable=False)
        if isinstance(raw, str) and raw.strip():
            return VerificationCriterion(command=None, description=raw.strip(), executable=False)
        return None


def _parse_finding_criteria(raw: Any) -> list[VerificationCriterion]:
    """Parse criteria from list, stringified collection, or string."""
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, str):
        coll = _parse_stringified_collection(raw.strip())
        items = coll if coll is not None else [raw.strip()]
    else:
        return []

    result: list[VerificationCriterion] = []
    for item in items:
        crit = _parse_single_criterion(item)
        if crit is not None and (crit.command or crit.description):
            result.append(crit)
    return result


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
    verification_criteria: list[VerificationCriterion] = Field(
        default_factory=list, validation_alias=AliasChoices("verification_criteria", "verification")
    )
    invalidation_criteria: list[VerificationCriterion] = Field(
        default_factory=list, validation_alias=AliasChoices("invalidation_criteria", "invalidation")
    )
    criteria_execution_results: list[CriterionExecutionResult] = Field(default_factory=list)
    verified_criteria_matched: list[str] = Field(default_factory=list)
    invalidated_criteria_matched: list[str] = Field(default_factory=list)
    reportable: bool = True
    verified: bool = False

    mitigated: bool = False
    status: str = DEFAULT_FINDING_STATUS  # UNVERIFIED | VERIFIED | INVALIDATED | MITIGATED
    invalidation_reason: str | None = None
    verified_by: str | None = None  # "llm" | "human"
    verified_at: str | None = None
    confidence_score: float | None = None
    # Why this finding carries no verdict, when the reason is that verification could not
    # run at all. Set only by the verification pipeline; `parse_review_response` clears
    # whatever a model supplies, because a model that could write here could announce its
    # own verification outage and tell a reader to discard the findings below.
    verification_note: str | None = None
    relocated_from: str | None = None
    category: str | None = Field(
        default=None,
        validation_alias=AliasChoices("category", "type", "classification", "defect_class"),
    )
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
        "verified_criteria_matched",
        "invalidated_criteria_matched",
        mode="before",
    )
    @classmethod
    def _clean_references(cls, v: object) -> list[str]:
        return _parse_finding_references(v)

    @field_validator(
        "verification_criteria",
        "invalidation_criteria",
        mode="before",
    )
    @classmethod
    def _clean_criteria(cls, v: object) -> list[VerificationCriterion]:
        return _parse_finding_criteria(v)

    @field_validator("severity", mode="before")
    @classmethod
    def _normalize_severity(cls, v: object) -> str:
        s = str(v).upper().replace("SEVERITY", "").strip(" :-_")
        if s in VALID_SEVERITIES:
            return s
        return _SEVERITY_SYNONYMS.get(s, "MEDIUM")

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, v: object) -> str:
        s = str(v).upper().strip()
        return s if s in VALID_STATUSES else DEFAULT_FINDING_STATUS

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


def _extract_code_symbols(text: str) -> set[str]:
    """Extract the distinctive code identifiers named in a piece of review prose."""
    symbols: set[str] = set()

    # Backtick-quoted identifiers and dotted paths.
    for raw in re.findall(r"`([^`\n]{2,80})`", text):
        symbols.update(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", raw))
    # Bare identifiers written in call form, or carrying an underscore.
    symbols.update(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(\)", text))
    symbols.update(re.findall(r"\b(_[A-Za-z0-9_]+|[A-Za-z0-9]+_[A-Za-z0-9_]+)\b", text))

    return {
        s.lower()
        for s in symbols
        if len(s) > 2 and s.lower() not in REVIEW_GENERIC_SYMBOL_STOPWORDS
    }


def _is_distinctive_symbol_overlap(shared: set[str]) -> bool:
    """Report whether a shared symbol set is specific enough to identify one defect."""
    if not shared:
        return False
    # A single shared symbol only counts when it is specific (private, snake_case, or
    # long); otherwise require corroboration from a second shared symbol.
    strong = any("_" in s or len(s) >= REVIEW_STRONG_SYMBOL_MIN_LENGTH for s in shared)
    return strong or len(shared) > 1


def _share_distinctive_symbol(primary: Finding, candidate: Finding) -> bool:
    """Report whether two findings describe the same defect in the same code symbol.

    A symbol named in both *titles* is strong evidence on its own. A symbol shared only
    in the bodies is usually just the enclosing function both findings happen to sit
    inside, so it additionally requires the two descriptions to tell a similar story;
    otherwise genuinely different defects sharing one call site would be collapsed.
    """
    if _is_distinctive_symbol_overlap(
        _extract_code_symbols(primary.title) & _extract_code_symbols(candidate.title)
    ):
        return True

    body_shared = _extract_code_symbols(primary.description) & _extract_code_symbols(
        candidate.description
    )
    if not _is_distinctive_symbol_overlap(body_shared):
        return False

    primary_body = _tokenize_title(primary.description)
    candidate_body = _tokenize_title(candidate.description)
    union = primary_body | candidate_body
    if not union:
        return False
    overlap = len(primary_body & candidate_body) / len(union)
    return overlap >= REVIEW_DESCRIPTION_SIMILARITY_THRESHOLD


_DISMISSED_STATUSES = frozenset({"INVALIDATED", "MITIGATED"})


def _title_similarity(primary: Finding, candidate: Finding) -> tuple[float, float]:
    """Jaccard and overlap coefficients of two findings' distinguishing title words."""
    primary_terms = _tokenize_title(primary.title)
    candidate_terms = _tokenize_title(candidate.title)
    if not primary_terms or not candidate_terms:
        return 0.0, 0.0
    shared = len(primary_terms & candidate_terms)
    return (
        shared / len(primary_terms | candidate_terms),
        shared / min(len(primary_terms), len(candidate_terms)),
    )


def _are_findings_duplicate(primary: Finding, candidate: Finding) -> bool:
    """Determine if two findings describe the same underlying issue across personas or segments.

    A missed merge leaves a duplicate in the report; a wrong merge loses a defect, so merging
    needs positive evidence. Findings at overlapping lines merge when their distinguishing title
    words agree. Findings far apart merge only with near-identical titles naming the same code
    symbol: personas do cite one defect at different lines, but two hardcoded secrets or two
    unbounded requests in one file are separate defects.
    """
    primary_file, primary_start, primary_end = _parse_location(primary.location)
    candidate_file, candidate_start, candidate_end = _parse_location(candidate.location)
    if not primary_file or primary_file != candidate_file:
        return False
    if (primary.status in _DISMISSED_STATUSES) != (candidate.status in _DISMISSED_STATUSES):
        return False

    same_title = primary.title.strip().lower() == candidate.title.strip().lower()
    jaccard, overlap = _title_similarity(primary, candidate)
    if (
        primary_start is None
        or primary_end is None
        or candidate_start is None
        or candidate_end is None
    ):
        # Without lines to compare, the code each finding names is the only other evidence:
        # "Hardcoded secret: `AWS_KEY`" and "Hardcoded secret: `DB_PASSWORD`" are two findings,
        # even after verification has dropped a miscounted line from one of them.
        if _name_different_symbols(primary, candidate):
            return False
        return same_title or jaccard >= TITLE_SIMILARITY_THRESHOLD or overlap >= 0.6

    overlapping = (
        max(primary_start, candidate_start)
        <= min(primary_end, candidate_end) + LINE_OVERLAP_TOLERANCE
    )
    if overlapping:
        return (
            same_title
            or jaccard >= 0.4
            or overlap >= 0.5
            or _share_title_symbol_and_word(primary, candidate)
        )
    return (same_title or jaccard >= 0.8) and _share_distinctive_symbol(primary, candidate)


def _name_different_symbols(primary: Finding, candidate: Finding) -> bool:
    """Both findings name code symbols, and none of them in common."""
    primary_symbols = _extract_code_symbols(f"{primary.title} {primary.description}")
    candidate_symbols = _extract_code_symbols(f"{candidate.title} {candidate.description}")
    return bool(primary_symbols and candidate_symbols) and not primary_symbols & candidate_symbols


def _share_title_symbol_and_word(primary: Finding, candidate: Finding) -> bool:
    """Both titles name the same code symbol and share one more distinguishing symbol or word.

    "Uninitialized _watcher leads to ineffective stop()" and "`_watcher` never set, `stop()` may
    not terminate" are one defect; "`parse_config` swallows exceptions" and "`parse_config`
    reads without a size limit" are two defects in one function.
    """
    shared_symbols = _extract_code_symbols(primary.title) & _extract_code_symbols(candidate.title)
    if not _is_distinctive_symbol_overlap(shared_symbols):
        return False
    shared_words = _tokenize_title(primary.title) & _tokenize_title(candidate.title)
    return len(shared_words | shared_symbols) >= 2


def _merge_two_findings[F: Finding](base: F, other: F) -> F:
    """Merge duplicate finding `other` into `base`, taking highest severity and confidence."""
    base_sev = base.severity.upper().strip()
    other_sev = other.severity.upper().strip()
    best_sev = (
        base_sev
        if _SEVERITY_RANK.get(base_sev, 99) <= _SEVERITY_RANK.get(other_sev, 99)
        else other_sev
    )

    base_conf = base.confidence_score
    other_conf = other.confidence_score
    best_conf: float | None = None
    if base_conf is not None and other_conf is not None:
        best_conf = max(base_conf, other_conf)
    elif base_conf is not None:
        best_conf = base_conf
    else:
        best_conf = other_conf

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
    crit_results = list(
        dict.fromkeys(base.criteria_execution_results + other.criteria_execution_results)
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
        "criteria_execution_results": crit_results,
        "verified_criteria_matched": ver_match,
        "invalidated_criteria_matched": inv_match,
        "reportable": reportable,
        "relocated_from": base.relocated_from or other.relocated_from,
        "category": base.category or other.category,
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
    """Extract and repair the first parseable JSON object or array from text."""
    from devops_cli.core.serialization import extract_json_block as _core_extract

    return _core_extract(text, default=None)


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


def reset_verification_state[F: Finding](finding: F) -> F:
    """A copy of a model-written finding with every field only verification may set cleared.

    A reviewer's reply is untrusted text parsed into the full finding schema, so it can mark
    its own finding INVALIDATED or MITIGATED, which skips verification and drops the finding
    from the report, or VERIFIED, which reports it unchecked.
    """
    return finding.model_copy(
        update={
            "status": DEFAULT_FINDING_STATUS,
            "reportable": True,
            "verified": False,
            "mitigated": False,
            "invalidation_reason": None,
            "verified_criteria_matched": [],
            "invalidated_criteria_matched": [],
            "verified_by": None,
            "verified_at": None,
            "verification_note": None,
        }
    )


def _strip_model_set_verification_state(result: ReviewResult) -> ReviewResult:
    """Clear any verification note a model supplied in its own output.

    `ReviewResult` is parsed directly from untrusted model text, so every field on it is
    model-writable. `verification_note` exists to tell a reader the verifier never ran; a
    model able to set it could announce a fabricated outage over findings that were
    verified normally. Only the verification pipeline may write it, so it is cleared here
    on the way in.
    """
    for finding in result.findings:
        finding.verification_note = None
    return result


# Keys models use for the findings list when they do not follow the schema exactly.
_FINDINGS_KEYS = ("findings", "issues", "results", "vulnerabilities", "problems")


def _findings_list(data: dict[str, Any]) -> list[Any] | None:
    """The findings list of a reply, under the schema's key, a synonym, or one level down."""
    for key in _FINDINGS_KEYS:
        if isinstance(value := data.get(key), list):
            return value
    for value in data.values():
        if isinstance(value, dict):
            nested = next((v for k in _FINDINGS_KEYS if isinstance(v := value.get(k), list)), None)
            if nested is not None:
                return nested
    return None


def _review_result_from_dict(data: dict[str, Any]) -> ReviewResult | None:
    """Validate a reply object, keeping every valid finding when other fields are malformed."""
    if "findings" in data:
        try:
            return ReviewResult.model_validate(data)
        except Exception:
            pass
    raw_findings = _findings_list(data)
    if raw_findings is None:
        try:
            return ReviewResult.model_validate(data)
        except Exception:
            return None
    summary = data.get("summary")
    return ReviewResult(
        findings=_validate_raw_findings_list(raw_findings),
        summary=summary if isinstance(summary, str) else "",
    )


def parse_review_response(response: str | Any) -> ReviewResult | None:
    """Parse a review reply into its findings.

    One malformed field must not cost the reply's valid findings: a reply whose object fails
    validation keeps each finding that validates on its own, and findings under a synonym key
    (`issues`, `results`) or one level down are found.
    """
    from devops_cli.ai.response_repair import fix_llm_response

    fixed = fix_llm_response(response, schema=ReviewResult)
    data = fixed.json_data or extract_json_block(fixed.content)
    result: ReviewResult | None = None
    if isinstance(data, dict):
        result = _review_result_from_dict(data)
    elif isinstance(fixed.parsed_model, ReviewResult):
        result = fixed.parsed_model
    elif isinstance(data, list) and (findings := _validate_raw_findings_list(data)):
        result = ReviewResult(findings=findings, summary=f"Extracted {len(findings)} finding(s)")
    if result is None:
        return None
    if fixed.thinking and not result.thinking:
        result.thinking = fixed.thinking
    return _strip_model_set_verification_state(result)
