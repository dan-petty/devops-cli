"""Pydantic models and normalization utilities for structured code review output."""

from __future__ import annotations

import ast
import json
import re
from collections import defaultdict
from collections.abc import Hashable, Iterable, Sequence
from enum import StrEnum, auto
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from devops_cli.ai.text_utils import (
    normalize_unicode_text as normalize_unicode_text,
)
from devops_cli.ai.text_utils import (
    unique_lines as unique_lines,
)
from devops_cli.config.constants import (
    CONST_GIT_COMMIT_SHA_PATTERN,
    CONST_REVIEW_CWE_DEFECT_CLASSES,
    CONST_REVIEW_DEFECT_KEYWORDS,
    CONST_REVIEW_PROMPT_PLACEHOLDER_BASENAMES,
    CONST_REVIEW_TITLE_FILLER_WORDS,
)
from devops_cli.config.defaults import (
    DEFAULT_FINDING_STATUS,
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
from devops_cli.review.state import FindingState

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
# Report order: what verification confirmed first, what it dismissed last.
_STATUS_RANK: dict[str, int] = {"VERIFIED": 0, "UNVERIFIED": 1, "MITIGATED": 2, "INVALIDATED": 3}
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


def _safe_literal_eval(val: str) -> Any:
    """Safely evaluate Python literal suppressing SyntaxWarnings from invalid escape sequences."""
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        return ast.literal_eval(val)


def _parse_stringified_collection(s: str) -> list[Any] | None:
    """Attempt parsing a stringified Python/JSON list or tuple."""
    if not ((s.startswith("[") and s.endswith("]")) or (s.startswith("(") and s.endswith(")"))):
        return None
    for parser in (json.loads, _safe_literal_eval):
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
_TITLE_FILLER_WORDS = CONST_REVIEW_TITLE_FILLER_WORDS


def _tokenize_title(title: str) -> set[str]:
    """The words of a finding's text that tell it apart from other findings."""
    words = re.findall(r"\b[a-zA-Z0-9_]+\b", title.lower())
    return {w for w in words if len(w) > 2 and w not in _TITLE_FILLER_WORDS}


def parse_finding_references(raw_ref: Any) -> list[str]:
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

_PROMPT_PLACEHOLDER_BASENAMES: frozenset[str] = CONST_REVIEW_PROMPT_PLACEHOLDER_BASENAMES

_MARKDOWN_LINK_REGEX = re.compile(r"\[([^\]]+)\]\([^)]+\)")

# Characters a path segment may hold: letters and digits of any script, and the punctuation file
# names use (`c++`, `@scope`, `logo@2x`, `~/.config`, `100%`). A narrower class cut a path at the
# first other character and kept the fragment before it.
_SEGMENT_CHARS = r"\w\-.+@~%"
_WINDOWS_DRIVE_PREFIX = r"(?:[a-zA-Z]:[/\\])"
_PATH_CHARS = rf"{_SEGMENT_CHARS}/\\"
_LOCATION_REGEX = re.compile(
    rf"^({_WINDOWS_DRIVE_PREFIX}?[{_PATH_CHARS}]+?)(?::(\d+)(?:-(\d+))?)?$"
)
_TARGET_LOCATION_REGEX = re.compile(
    rf"^({_WINDOWS_DRIVE_PREFIX}?[{_PATH_CHARS}]+?):([{_PATH_CHARS}]+)$"
)
_EMBEDDED_LOCATION_REGEX = re.compile(
    rf"(?:^|[\s:\"'`])({_WINDOWS_DRIVE_PREFIX}?[{_PATH_CHARS}]+/[{_SEGMENT_CHARS}]+|[\w\-]+\.[\w\-]+)"
    r"(?::(\d+)(?:-(\d+))?)?"
)


def _is_structural_path_or_location(candidate: str) -> bool:
    """Validate that candidate string structurally resembles a path or location identifier."""
    cand = candidate.strip()
    if not cand or any(p in cand for p in (". ", "?", "!", ";", "\n")):
        return False
    if "/" in cand or "\\" in cand or re.match(r"^[a-zA-Z]:", cand):
        return True
    if re.search(r"\.[a-zA-Z0-9]{1,8}$", cand):
        return True
    words = cand.split()
    return len(words) <= 3 and not cand.endswith(".")


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


def _format_location_with_lines(
    file_path: str, s_str: str | None, e_str: str | None, had_leakage: bool = False
) -> str:
    """Format file path with normalized line or range boundaries."""
    norm_path = file_path.strip().replace("\\", "/")
    if not s_str:
        return f"{norm_path}:1" if had_leakage else norm_path
    s_line = int(s_str)
    e_line = int(e_str) if e_str else None
    if e_line is not None and s_line > e_line:
        s_line, e_line = e_line, s_line
    if e_line is not None and e_line != s_line:
        return f"{norm_path}:{s_line}-{e_line}"
    return f"{norm_path}:{s_line}"


def _extract_embedded_location(loc: str) -> str:
    """Extract embedded valid file location if present in conversational or scratchpad text."""
    m_embedded = _EMBEDDED_LOCATION_REGEX.search(loc)
    if not m_embedded:
        return ""
    candidate_file = m_embedded.group(1).strip().replace("\\", "/").rstrip(".")
    if (
        candidate_file.lower() in _PROMPT_PLACEHOLDER_BASENAMES
        or Path(candidate_file).name.lower() in _PROMPT_PLACEHOLDER_BASENAMES
    ):
        return ""
    return _format_location_with_lines(candidate_file, m_embedded.group(2), m_embedded.group(3))


def _pre_clean_location(location: str) -> tuple[str, bool]:
    """Clean raw location string, stripping markdown noise and prompt leakage."""
    loc = normalize_unicode_text(str(location)).strip()
    if not loc or "\n" in loc or "```" in loc:
        return "", False
    if loc.startswith("#") or not any(c.isalnum() for c in loc):
        return "", False

    m_link = _MARKDOWN_LINK_REGEX.search(loc)
    if m_link:
        loc = m_link.group(1).strip()

    loc = loc.strip("`'\"()[]*# ")
    if not loc or not any(c.isalnum() for c in loc):
        return "", False

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
    return loc, had_prompt_leakage


def _extract_base_file_path(loc: str) -> str:
    """Extract base file path from location string, preserving Windows drive letters."""
    if re.match(r"^[a-zA-Z]:[/\\]", loc):
        drive = loc[:2]
        rest = loc[2:].split(":")[0]
        return f"{drive}{rest}".strip()
    return loc.split(":")[0].strip()


def canonicalize_finding_location(location: str) -> str:
    """Canonicalize raw LLM location text into standard path/to/file.ext:start-end or path/to/file.ext:line."""
    loc, had_prompt_leakage = _pre_clean_location(location)
    if not loc:
        return ""
    if loc.startswith(":"):
        clean_suffix = loc.lstrip(":").strip()
        if clean_suffix:
            return f":{clean_suffix}"

    if " " in loc:
        embedded = _extract_embedded_location(loc)
        if embedded:
            return embedded

    loc_file = _extract_base_file_path(loc)
    if (
        loc_file.lower() in _PROMPT_PLACEHOLDER_BASENAMES
        or Path(loc_file).name.lower() in _PROMPT_PLACEHOLDER_BASENAMES
    ):
        return ""

    if m_loc := _LOCATION_REGEX.match(loc):
        return _format_location_with_lines(
            m_loc.group(1), m_loc.group(2), m_loc.group(3), had_prompt_leakage
        )

    if m_target := _TARGET_LOCATION_REGEX.match(loc):
        return f"{m_target.group(1).strip().replace('\\', '/')}:{m_target.group(2).strip()}"

    if _is_structural_path_or_location(loc_file):
        return loc

    return _extract_embedded_location(loc)


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
    # Stopped at its time limit, as opposed to run to a failing exit.
    timed_out: bool = False

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


# A finding's JSON schema is the reply format a persona agent is shown, so it lists only the
# fields a reviewer writes. The fields the pipeline owns (verdicts, criteria results, citations,
# confidence) are `SkipJsonSchema`: still parsed, so saved findings reload, but never asked of a
# reviewer, which invites it to fill them in. No docstring: pydantic would send it as the
# schema's description.
class DefectClass(StrEnum):
    """The closed set of defect classes a review groups its findings by (#948).

    A finding's `category` is the CWE it names or, naming none, the class its words name. Its
    theme, the class the report and the category metrics group it under, is always a member:
    a CWE maps here through `CONST_REVIEW_CWE_DEFECT_CLASSES`.
    """

    INJECTION = auto()
    PATH_TRAVERSAL = auto()
    SSRF = auto()
    SECRET_EXPOSURE = auto()
    INFORMATION_EXPOSURE = auto()
    ACCESS_CONTROL = auto()
    AUTHENTICATION = auto()
    CRYPTOGRAPHY = auto()
    INSECURE_TRANSPORT = auto()
    NETWORK_EXPOSURE = auto()
    SECURITY_MISCONFIGURATION = auto()
    SUPPLY_CHAIN = auto()
    RESOURCE_EXHAUSTION = auto()
    RACE_CONDITION = auto()
    ERROR_HANDLING = auto()
    INPUT_VALIDATION = auto()
    PROCESS_SAFETY = auto()
    DATA_INTEGRITY = auto()
    RELIABILITY = auto()
    SYNTAX_ERROR = auto()
    TESTING = auto()
    DOCUMENTATION = auto()
    LOGIC_ERROR = auto()
    CONFIGURATION = auto()
    CODE_QUALITY = auto()
    # Names security and no narrower class.
    SECURITY = auto()
    OTHER = auto()

    @property
    def label(self) -> str:
        """How a report names the class: `Path traversal`, `SSRF`."""
        return "SSRF" if self is DefectClass.SSRF else self.value.replace("_", " ").capitalize()


_DEFECT_CLASS_VALUES: frozenset[str] = frozenset(DefectClass)
_CWE_ID = re.compile(r"\bCWE[-_: ]?(\d{1,5})\b", re.IGNORECASE)
_CANONICAL_CWE = re.compile(r"CWE-\d+")
_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


def _cwe_number(text: str) -> int | None:
    """The number of the first CWE a text names."""
    match = _CWE_ID.search(text)
    return int(match.group(1)) if match else None


def _keyword_defect_class(text: str) -> DefectClass | None:
    """The class the first keyword found among the text's words names."""
    words = f" {_NON_ALPHANUMERIC.sub(' ', text.lower()).strip()} "
    return next(
        (DefectClass(cls) for kw, cls in CONST_REVIEW_DEFECT_KEYWORDS if f" {kw} " in words),
        None,
    )


def defect_class(*texts: str | None) -> DefectClass:
    """The class the first text naming one names; `other` when none does.

    A text names a class as its value (`path_traversal`), as a CWE the table maps (`CWE-22`,
    `CWE-22 Path Traversal`), or in its words (`Path Traversal`). Callers pass a finding's
    category, then its raw category, then its title.
    """
    for text in filter(None, texts):
        if text in _DEFECT_CLASS_VALUES:
            return DefectClass(text)
        cwe = _cwe_number(text)
        if cwe in CONST_REVIEW_CWE_DEFECT_CLASSES:
            return DefectClass(CONST_REVIEW_CWE_DEFECT_CLASSES[cwe])
        if (named := _keyword_defect_class(text)) is not None:
            return named
    return DefectClass.OTHER


def assign_category(
    category: str | None, references: Sequence[str], title: str
) -> tuple[str, str | None]:
    """A finding's category, and the raw category it replaces (#948).

    A CWE named in the category or, failing that, in the references becomes `CWE-<n>`.
    Otherwise the category's words, then the title's, name a defect class: since #951 the
    persona writes no category, so the pipeline assigns one. A category already in either form
    is kept as it is.
    """
    raw = (category or "").strip() or None
    if raw is not None and (raw in _DEFECT_CLASS_VALUES or _CANONICAL_CWE.fullmatch(raw)):
        return raw, None
    cwe = next(
        (n for text in (raw, *references) if text and (n := _cwe_number(text)) is not None),
        None,
    )
    if cwe is not None:
        return f"CWE-{cwe}", raw
    return defect_class(raw, title).value, raw


def less_severe(current: str, proposed: object) -> str:
    """The less severe of a severity and the one `proposed` names; `current` when it names none."""
    named = severity_named(proposed)
    if named is None or _SEVERITY_RANK[named] <= _SEVERITY_RANK.get(current, -1):
        return current
    return named


class Finding(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    finding_id: SkipJsonSchema[int | None] = Field(
        default=None,
        validation_alias=AliasChoices("finding_id", "id", "index"),
        description="Structural positional oracle identifier for deterministic verification binding",
    )
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
    criteria_execution_results: SkipJsonSchema[list[CriterionExecutionResult]] = Field(
        default_factory=list
    )
    verified_criteria_matched: SkipJsonSchema[list[str]] = Field(default_factory=list)
    invalidated_criteria_matched: SkipJsonSchema[list[str]] = Field(default_factory=list)
    reportable: SkipJsonSchema[bool] = True
    verified: SkipJsonSchema[bool] = False

    mitigated: SkipJsonSchema[bool] = False
    # UNVERIFIED | VERIFIED | INVALIDATED | MITIGATED
    status: SkipJsonSchema[str] = DEFAULT_FINDING_STATUS
    invalidation_reason: SkipJsonSchema[str | None] = None
    verified_by: SkipJsonSchema[str | None] = None  # "llm" | "human"
    verified_at: SkipJsonSchema[str | None] = None
    confidence_score: SkipJsonSchema[float | None] = None
    citation_line: SkipJsonSchema[int | None] = Field(
        default=None,
        validation_alias=AliasChoices("citation_line", "cited_line", "line", "refutation_line"),
    )
    mitigating_mechanism: SkipJsonSchema[str | None] = Field(
        default=None,
        validation_alias=AliasChoices("mitigating_mechanism", "mechanism", "mitigation"),
    )
    perimeter_files: SkipJsonSchema[list[str]] = Field(
        default_factory=list,
        validation_alias=AliasChoices("perimeter_files", "perimeter", "perimeters"),
    )
    regression_test: SkipJsonSchema[str | None] = Field(
        default=None,
        validation_alias=AliasChoices("regression_test", "test", "regression"),
    )
    # `CWE-<n>` or a `DefectClass` value, which validation assigns (#948).
    category: SkipJsonSchema[str | None] = Field(
        default=None,
        validation_alias=AliasChoices("category", "type", "classification", "defect_class"),
    )
    # The category a reviewer or scanner wrote, when validation replaced it.
    category_raw: SkipJsonSchema[str | None] = None
    # The severity the persona or scanner gave, when a verifier or calibration lowered it (sessions
    # saved before #1150).
    severity_raw: SkipJsonSchema[str | None] = None
    # Why advisory ids left `references`: no dependency this session scanned carries them.
    reference_note: SkipJsonSchema[str | None] = None
    observed_value: str | None = Field(
        default=None,
        validation_alias=AliasChoices("observed_value", "observed", "actual_value", "actual"),
    )
    expected_value: str | None = Field(
        default=None,
        validation_alias=AliasChoices("expected_value", "expected"),
    )
    thinking: SkipJsonSchema[str | None] = None
    properties: SkipJsonSchema[dict[str, Any]] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("properties", "props", "metadata", "meta"),
    )

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

    @field_validator("finding_id", mode="before")
    @classmethod
    def _clean_finding_id(cls, v: object) -> int | None:
        """Parse structural positional finding_id safely, ignoring non-integer identifier strings."""
        if v is None:
            return None
        if isinstance(v, int):
            return v
        try:
            return int(str(v).strip())
        except ValueError, TypeError:
            return None

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
        return parse_finding_references(v)

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
        return severity_named(v) or "MEDIUM"

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, v: object) -> str:
        return normalize_finding_status(v)

    @field_validator("confidence_score", mode="before")
    @classmethod
    def _normalize_confidence(cls, v: object) -> float | None:
        return _parse_confidence_score(v)

    @field_validator("observed_value", "expected_value", mode="before")
    @classmethod
    def _clean_polarity_value(cls, v: object) -> str | None:
        if v is None:
            return None
        text = str(v).strip()
        return text if text else None

    @model_validator(mode="after")
    def _assign_category(self) -> Finding:
        """One taxonomy for every finding: 148 free-text categories came out of one session."""
        self.category, raw = assign_category(self.category, self.references, self.title)
        self.category_raw = self.category_raw or raw
        return self

    @model_validator(mode="after")
    def _validate_polarity(self) -> Finding:
        if getattr(self, "status", None) == "INVALIDATED":
            return self
        obs = self.observed_value
        exp = self.expected_value
        if obs is None and exp is None:
            return self
        if obs is None or exp is None:
            self.observed_value = None
            self.expected_value = None
            return self
        if obs.strip().lower() == exp.strip().lower():
            self.status = "INVALIDATED"
            self.reportable = False
            self.verified = False
            self.verified_by = "deterministic:verdict_polarity"
            self.invalidation_reason = f"Observed value '{obs}' is identical to expected value '{exp}' (no defect polarity)"
            return self
        return self


def severity_named(value: object) -> str | None:
    """The finding severity a spelling names, `informational` or `Severity: Major` among them;
    None for one it does not name."""
    name = str(value).upper().replace("SEVERITY", "").strip(" :-_")
    return name if name in VALID_SEVERITIES else _SEVERITY_SYNONYMS.get(name)


def normalize_finding_status(value: object) -> str:
    """A finding status in upper case; the default status for one that is not a known status."""
    status = str(value).upper().strip()
    return status if status in VALID_STATUSES else DEFAULT_FINDING_STATUS


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


def _parse_location(
    location: str, preserve_case: bool = True
) -> tuple[str, int | None, int | None]:
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
        raw_part = loc.replace("\\", "/")
        return (raw_part if preserve_case else raw_part.lower()), None, None

    raw_file = (m.group(1) or "").strip().replace("\\", "/")
    file_part = raw_file if preserve_case else raw_file.lower()
    s_line_str = m.group(2)
    e_line_str = m.group(3)

    s_line = int(s_line_str) if s_line_str else None
    e_line = int(e_line_str) if e_line_str else s_line

    if s_line is not None and e_line is not None and s_line > e_line:
        s_line, e_line = e_line, s_line

    return file_part, s_line, e_line


def _location_key(location: str) -> tuple[str, int]:
    """A location as its file and first line, so line 9 sorts before line 12."""
    file_part, start, _ = _parse_location(location)
    return file_part, start or 0


def sort_findings[F: Finding](findings: list[F]) -> list[F]:
    """Sort reportable findings first, then VERIFIED, UNVERIFIED and MITIGATED, then by severity,
    location and title.

    A model's confidence plays no part: ranked before verification, it put UNVERIFIED findings
    at 1.0 above VERIFIED ones at 0.95 (#948).
    """
    return sorted(
        findings,
        key=lambda f: (
            not f.reportable,
            _STATUS_RANK.get(f.status, len(_STATUS_RANK)),
            _SEVERITY_RANK.get((f.severity or "").upper().strip(), 99),
            _location_key(f.location),
            f.title,
        ),
    )


class CitedCode(BaseModel):
    """The code a finding's location cites, as the review read it when it saved the session (#950).

    `ai/review/cited_code.py` records it; `devops review score`, review history and the feedback
    export read it.
    """

    model_config = ConfigDict(frozen=True)

    # The repository the code belongs to, and the file relative to the checkout holding it.
    project: str
    file: str
    # The first line the location cites, and the lines it cites, with secrets masked.
    line: int
    excerpt: str


class SavedFinding(Finding):
    state: FindingState = FindingState.OPEN
    confirmed_by: str | None = None
    fingerprint: str = ""
    producer: str = Field(default="", validation_alias=AliasChoices("producer", "persona"))
    recommendation: str = "REQUEST CHANGES"

    @field_validator("state", mode="before")
    @classmethod
    def _coerce_state(cls, v: Any) -> Any:
        if v is None:
            return FindingState.OPEN
        if isinstance(v, str):
            clean = v.upper().strip()
            if clean in FindingState.__members__:
                return FindingState(clean)
        return v

    @property
    def persona(self) -> str:
        return self.producer

    # On a finding a VERIFIED or MITIGATED verdict moved into findings.json, the number of the
    # candidate in candidates.json it was moved from, which later verdicts on either keep in step.
    moved_from_candidate: int | None = None
    # The code the location cites, when it cites a line of a file in the reviewed checkout (#950).
    cited_code: CitedCode | None = None
    # False when admission found the finding's fingerprint at the base revision (#871, #1295),
    # so review.md lists it under pre-existing findings rather than introduced ones.
    introduced: bool = True


class FileReviewPayload(BaseModel):
    file_path: str
    metadata: FileAnalysisMeta | None = None
    linked_files: list[FileAnalysisMeta] = Field(default_factory=list)
    findings: list[SavedFinding] = Field(default_factory=list)
    thinking_traces: dict[str, str] = Field(default_factory=dict)
    external_dependencies: list[DependencySpec] = Field(default_factory=list)
    network_references: list[NetworkReference] = Field(default_factory=list)
    reportable: bool = True

    @field_validator("findings", mode="after")
    @classmethod
    def _filter_valid_findings(cls, v: list[SavedFinding]) -> list[SavedFinding]:
        return _filter_non_empty_findings(v)


class ReviewCheckout(BaseModel):
    """The commit of the checkout a review read, and whether its working tree was clean (#2415).

    `review.checkout` reads it when the review starts and decides from it whether the session is
    on merged code.
    """

    model_config = ConfigDict(frozen=True)

    head: str
    clean: bool

    @field_validator("head")
    @classmethod
    def _full_commit_name(cls, value: str) -> str:
        # findings.json is a file on disk, and its commit goes to git as an argument, so it is a
        # full commit name and never an option or a symbolic name.
        if not CONST_GIT_COMMIT_SHA_PATTERN.fullmatch(value):
            raise ValueError("The head of a review checkout must be a full commit name.")
        return value


class ReviewSessionPayload(BaseModel):
    generated_at: str = ""
    # What the session reviewed (`history.review_subject`); empty for a session written before
    # #607, which review history counts on its own.
    subject: dict[str, str] = Field(default_factory=dict)
    # The checkout that holds the target, as git read it when the review started; None outside
    # any checkout and for a session written before #2415.
    checkout: ReviewCheckout | None = None
    findings: list[SavedFinding] = Field(default_factory=list)
    external_dependencies: list[DependencySpec] = Field(default_factory=list)
    dependency_vulnerabilities: list[VulnerabilityRecord] = Field(default_factory=list)
    network_references: list[NetworkReference] = Field(default_factory=list)
    network_reputations: list[NetworkReputationRecord] = Field(default_factory=list)
    symbol_delta_summary: dict[str, int] = Field(default_factory=dict)
    complexity_delta: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("findings", mode="after")
    @classmethod
    def _filter_valid_findings(cls, v: list[SavedFinding]) -> list[SavedFinding]:
        return _filter_non_empty_findings(v)

    @property
    def sorted_findings(self) -> list[SavedFinding]:
        return sort_findings(self.findings)


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


# A review's reply. Its JSON schema, like `Finding`'s, holds only what a reviewer writes.
class ReviewResult(BaseModel):
    findings: list[Finding] = Field(default_factory=list)
    recommendation: SkipJsonSchema[str] = "REQUEST CHANGES"
    summary: str = ""
    thinking: SkipJsonSchema[str | None] = None
    confidence_score: SkipJsonSchema[float | None] = None
    external_dependencies: SkipJsonSchema[list[DependencySpec]] = Field(default_factory=list)
    network_references: SkipJsonSchema[list[NetworkReference]] = Field(default_factory=list)
    report_markdown: SkipJsonSchema[str | None] = None
    static_analyzers: SkipJsonSchema[dict[str, str]] = Field(default_factory=dict)

    @field_validator("findings", mode="before")
    @classmethod
    def _ensure_finding_items(cls, v: object) -> list[Any]:
        if not isinstance(v, list):
            return []
        return [item for item in v if isinstance(item, (dict, Finding))]

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
        return sort_findings(self.findings)

    def merge(self, other: ReviewResult) -> ReviewResult:
        """Merge another ReviewResult, deduplicating and consolidating findings."""
        merged_findings = sort_findings(self.findings + other.findings)
        recommendation = derive_recommendation(merged_findings)
        scores = [s for s in (self.confidence_score, other.confidence_score) if s is not None]
        merged_conf = round(sum(scores) / len(scores), 2) if scores else None
        return ReviewResult(
            findings=merged_findings,
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
    """A copy of a model-written finding with every field only a tool or a person sets cleared.

    A reviewer's reply is untrusted text parsed into the full finding schema, so it can mark
    its own finding INVALIDATED or MITIGATED, which drops it from the report, or VERIFIED, which
    reports it as confirmed. It can also bring its own confidence, citation, mitigation or
    criteria results, which would be shown as the pipeline's. Only a person's verdict
    (`devops review verify`) or a tool's evidence sets them (#1150).
    """
    return finding.model_copy(
        update={
            "finding_id": None,
            "status": DEFAULT_FINDING_STATUS,
            "reportable": True,
            "verified": False,
            "mitigated": False,
            "invalidation_reason": None,
            "verified_criteria_matched": [],
            "invalidated_criteria_matched": [],
            "criteria_execution_results": [],
            "verified_by": None,
            "verified_at": None,
            "confidence_score": None,
            "citation_line": None,
            "mitigating_mechanism": None,
            "perimeter_files": [],
            "regression_test": None,
        }
    )


def strip_model_set_state(result: ReviewResult) -> ReviewResult:
    """Clear every field only the pipeline may write that a model supplied in its own output.

    `ReviewResult` is parsed from untrusted model text, by `parse_review_response` or by the
    agent framework, so every field on it is model-writable. The dependencies and network
    references are the scans' own: a reply that declared a dependency scanned clean, or listed
    an endpoint, would be trusted by the checks that read them (#948). The raw severity and the
    reference note record what the pipeline changed.
    """
    for finding in result.findings:
        finding.severity_raw = None
        finding.reference_note = None
    result.external_dependencies = []
    result.network_references = []
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


def _review_result_from_list(data: list[Any]) -> ReviewResult | None:
    """Construct ReviewResult from a list response (empty or list of finding dicts)."""
    if not data:
        return ReviewResult(findings=[], summary="")
    if findings := _validate_raw_findings_list(data):
        return ReviewResult(findings=findings, summary=f"Extracted {len(findings)} finding(s)")
    return None


def parse_review_response(response: str | Any) -> ReviewResult | None:
    """Parse a review reply into its findings.

    One malformed field must not cost the reply's valid findings: a reply whose object fails
    validation keeps each finding that validates on its own, and findings under a synonym key
    (`issues`, `results`) or one level down are found.
    """
    from devops_cli.ai.response_repair import fix_llm_response

    fixed = fix_llm_response(response)
    data = fixed.json_data or extract_json_block(fixed.content)
    result: ReviewResult | None = None
    if isinstance(data, dict):
        result = _review_result_from_dict(data)
    elif isinstance(data, list):
        result = _review_result_from_list(data)
    if result is None:
        return None
    if fixed.thinking and not result.thinking:
        result.thinking = fixed.thinking
    return strip_model_set_state(result)


def compute_verdict_distributions(
    findings: Sequence[Finding | SavedFinding],
) -> dict[str, Any]:
    """Compute distributions for core verdict fields and per-adjudicator citation rates.

    Returns a mapping of verdict field name to value counts and citation rates across all findings.
    """
    status_counts: dict[str, int] = defaultdict(int)
    reportable_counts: dict[str, int] = {"true": 0, "false": 0}
    verified_counts: dict[str, int] = {"true": 0, "false": 0}
    mitigated_counts: dict[str, int] = {"true": 0, "false": 0}
    adj_totals: dict[str, int] = defaultdict(int)
    adj_cited: dict[str, int] = defaultdict(int)

    for f in findings:
        st_raw = getattr(f, "status", None)
        st = (
            st_raw.upper().strip()
            if isinstance(st_raw, str) and st_raw.strip()
            else DEFAULT_FINDING_STATUS
        )
        status_counts[st] += 1
        rep_key = "true" if bool(getattr(f, "reportable", False)) else "false"
        reportable_counts[rep_key] += 1
        ver_key = "true" if bool(getattr(f, "verified", False)) else "false"
        verified_counts[ver_key] += 1
        mit_key = "true" if bool(getattr(f, "mitigated", False)) else "false"
        mitigated_counts[mit_key] += 1

        adj_raw = getattr(f, "verified_by", None)
        adj = adj_raw.strip() if isinstance(adj_raw, str) and adj_raw.strip() else "unknown"
        adj_totals[adj] += 1
        if getattr(f, "citation_line", None) is not None:
            adj_cited[adj] += 1

    citation_rates: dict[str, float] = {
        adj: round(adj_cited[adj] / total, 2) for adj, total in adj_totals.items() if total > 0
    }

    return {
        "status": dict(status_counts),
        "reportable": reportable_counts,
        "verified": verified_counts,
        "mitigated": mitigated_counts,
        "citation_rates": citation_rates,
    }


def is_field_discriminating(counts: dict[str, int]) -> bool:
    """Report whether a verdict field distribution discriminates between outcomes.

    A field discriminates if at least two distinct values have non-zero counts.
    If only one value was ever observed (or total is 0), the field acts as a constant rather than a discriminator.
    """
    non_zero = sum(1 for c in counts.values() if c > 0)
    return non_zero > 1
