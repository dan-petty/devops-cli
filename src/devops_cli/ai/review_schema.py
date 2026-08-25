"""Pydantic models and normalization utilities for structured code review output."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

import json_repair
from pydantic import BaseModel, Field, field_validator, model_validator

from devops_cli.config.defaults import DEFAULT_FINDING_CONFIDENCE
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

LINE_OVERLAP_TOLERANCE: int = 2
TITLE_SIMILARITY_THRESHOLD: float = 0.5
MAX_TITLE_LENGTH: int = 200
MAX_SUMMARY_PREVIEW_LENGTH: int = 300

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


def _tokenize_title(title: str) -> set[str]:
    """Tokenize finding title into lowercase word tokens."""
    words = re.findall(r"\b[a-zA-Z0-9_]+\b", title.lower())
    return {w for w in words if len(w) > 2}


class Finding(BaseModel):
    severity: str = "MEDIUM"
    location: str = ""
    title: str = ""
    description: str = ""
    fix: str = ""
    references: list[str] = Field(default_factory=list)
    verification_criteria: list[str] = Field(default_factory=list)
    invalidation_criteria: list[str] = Field(default_factory=list)
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

    @model_validator(mode="before")
    @classmethod
    def _pre_validate_finding(cls, data: Any) -> Any:
        if isinstance(data, str):
            text = normalize_unicode_text(data).strip()
            if not text:
                return {"title": "", "location": "", "description": ""}
            # If string is structured as "[SEVERITY] path:line - title"
            m = re.match(
                r"^\[?(CRITICAL|HIGH|MEDIUM|LOW|INFO)\]?\s*`?([^`:\s]+(?::\d+(?:-\d+)?)?)`?\s*[-:—]\s*(.+)$",
                text,
                re.IGNORECASE,
            )
            if m:
                return {
                    "severity": m.group(1).upper(),
                    "location": m.group(2).strip(),
                    "title": m.group(3).strip(),
                    "description": text,
                }
            return {"title": "", "location": "", "description": ""}
        if isinstance(data, dict):
            d = dict(data)
            # Map alternative field names produced by varied LLM personas
            if not d.get("title"):
                d["title"] = (
                    d.get("issue")
                    or d.get("problem")
                    or d.get("name")
                    or d.get("summary")
                    or d.get("heading")
                    or d.get("finding")
                    or ""
                )
            if not d.get("description"):
                d["description"] = (
                    d.get("details")
                    or d.get("detail")
                    or d.get("impact")
                    or d.get("explanation")
                    or d.get("message")
                    or d.get("body")
                    or ""
                )
            if not d.get("location"):
                d["location"] = (
                    d.get("file")
                    or d.get("path")
                    or d.get("target")
                    or d.get("line")
                    or d.get("lines")
                    or ""
                )
            if not d.get("fix"):
                d["fix"] = (
                    d.get("remediation")
                    or d.get("recommendation")
                    or d.get("suggested_fix")
                    or d.get("solution")
                    or d.get("patch")
                    or ""
                )
            if not d.get("verification_criteria") and d.get("verification"):
                d["verification_criteria"] = d.get("verification")
            if not d.get("invalidation_criteria") and d.get("invalidation"):
                d["invalidation_criteria"] = d.get("invalidation")
            return d
        return data

    @property
    def is_empty(self) -> bool:
        """Check if finding is blank or lacks a valid target location."""
        clean_title = self.title.strip()
        clean_loc = self.location.strip()
        if not clean_title or not clean_loc:
            return True
        if "\n" in clean_loc or "```" in clean_loc:
            return True

        file_part, _, _ = _parse_location(clean_loc)
        if not file_part or file_part in {"none", "n/a", "na", "null", "undefined"}:
            return True
        return False

    @field_validator("description", "fix", mode="before")
    @classmethod
    def _clean_text_fields(cls, v: object) -> str:
        return normalize_unicode_text(str(v)).strip()

    @field_validator("location", mode="before")
    @classmethod
    def _clean_location(cls, v: object) -> str:
        loc = normalize_unicode_text(str(v)).strip()
        if "\n" in loc or "```" in loc:
            return ""
        return loc

    @field_validator("title", mode="before")
    @classmethod
    def _clean_title(cls, v: object) -> str:
        text = normalize_unicode_text(str(v)).strip()
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
        if isinstance(v, list):
            return [normalize_unicode_text(str(r)).strip() for r in v if str(r).strip()]
        if isinstance(v, str) and v.strip():
            return [normalize_unicode_text(v).strip()]
        return []

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


class ReviewResult(BaseModel):
    findings: list[Finding] = Field(default_factory=list)
    positive_observations: list[str] = Field(default_factory=list)
    recommendation: str = "REQUEST CHANGES"
    summary: str = ""
    confidence_score: float | None = None
    external_dependencies: list[DependencySpec] = Field(default_factory=list)
    network_references: list[NetworkReference] = Field(default_factory=list)

    @field_validator("findings", mode="after")
    @classmethod
    def _filter_valid_findings(cls, v: list[Finding]) -> list[Finding]:
        return _filter_non_empty_findings(v)

    @model_validator(mode="after")
    def _sync_recommendation(self) -> ReviewResult:
        if not self.findings and self.recommendation == "REQUEST CHANGES":
            self.recommendation = "APPROVE"
        return self

    @field_validator("summary", mode="before")
    @classmethod
    def _clean_summary(cls, v: object) -> str:
        return normalize_unicode_text(str(v)).strip()

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
        rec_order = {"BLOCK": 0, "REQUEST CHANGES": 1, "APPROVE": 2}
        recommendation = min(
            (self.recommendation, other.recommendation),
            key=lambda r: rec_order.get(r, 99),
        )
        c1 = (
            self.confidence_score
            if self.confidence_score is not None
            else DEFAULT_FINDING_CONFIDENCE
        )
        c2 = (
            other.confidence_score
            if other.confidence_score is not None
            else DEFAULT_FINDING_CONFIDENCE
        )
        merged_conf = round((c1 + c2) / 2.0, 2)
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


def _parse_markdown_review_findings(text: str) -> list[Finding]:
    """Fallback parser to extract Finding objects from Markdown-formatted review text."""
    findings: list[Finding] = []
    blocks = re.split(
        r"\n+(?=(?:###?\s*(?:Finding|\d+\.)|\d+\.\s+|\*{1,2}Location\*{0,2}:|Location:))",
        text,
    )
    for block in blocks:
        loc_m = re.search(r"(?:Location|File):\s*`?([^`\n]+)`?", block, re.IGNORECASE)
        if not loc_m:
            continue
        loc = loc_m.group(1).strip()
        if "\n" in loc or "```" in loc:
            continue

        sev_m = re.search(
            r"Severity:\s*\*?(CRITICAL|HIGH|MEDIUM|LOW|INFO)\*?", block, re.IGNORECASE
        )
        sev_from_block = (
            sev_m.group(1).upper()
            if (sev_m and sev_m.group(1).upper() in VALID_SEVERITIES)
            else None
        )

        title_m = re.search(
            r"(?:###?\s*(?:Finding\s*\d*:?\s*)?|\d+\.\s+|\*\*Title\*\*:\s*)([^\n]+)",
            block,
        )
        raw_title = title_m.group(1).strip("* ") if title_m else f"Issue at {loc}"

        if not sev_from_block:
            title_sev_m = re.match(
                r"^\[?(CRITICAL|HIGH|MEDIUM|LOW|INFO)\]?\s*[-:—]?\s*(.+)$",
                raw_title,
                re.IGNORECASE,
            )
            if title_sev_m:
                sev_from_block = title_sev_m.group(1).upper()
                raw_title = title_sev_m.group(2).strip()

        sev = sev_from_block or "MEDIUM"

        desc_m = re.search(
            r"(?:Description|Impact):\s*(.+?)(?=\n\s*(?:Fix|Remediation|Verification|Severity|Location):|\Z)",
            block,
            re.DOTALL | re.IGNORECASE,
        )
        desc = desc_m.group(1).strip() if desc_m else block[:MAX_TITLE_LENGTH]
        fix_m = re.search(
            r"(?:Fix|Remediation):\s*(.+?)(?=\n\s*(?:Verification|Invalidation|Severity|Location):|\Z)",
            block,
            re.DOTALL | re.IGNORECASE,
        )
        fix = fix_m.group(1).strip() if fix_m else ""

        f = Finding(
            severity=sev,
            location=loc,
            title=raw_title,
            description=desc,
            fix=fix,
            confidence_score=DEFAULT_FINDING_CONFIDENCE,
        )
        if not f.is_empty:
            findings.append(f)

    return findings


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


def parse_review_response(text: str) -> ReviewResult | None:
    """Parse review LLM response, prioritizing Pydantic structured output."""
    from devops_cli.ai.response_repair import fix_llm_response

    fixed = fix_llm_response(text, schema=ReviewResult)
    if fixed.parsed_model is not None and isinstance(fixed.parsed_model, ReviewResult):
        return fixed.parsed_model

    data = fixed.json_data or extract_json_block(text)
    if isinstance(data, list):
        parsed_findings = _validate_raw_findings_list(data)
        if parsed_findings:
            return ReviewResult(
                findings=parsed_findings,
                recommendation="APPROVE" if not parsed_findings else "REQUEST CHANGES",
                summary=f"Extracted {len(parsed_findings)} finding(s)",
            )
    elif isinstance(data, dict):
        try:
            return ReviewResult.model_validate(data)
        except Exception:
            pass

    target_text = fixed.content or text
    md_findings = _parse_markdown_review_findings(target_text)
    if md_findings:
        return ReviewResult(findings=md_findings, summary=target_text[:MAX_SUMMARY_PREVIEW_LENGTH])

    return None
