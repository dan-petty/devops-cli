"""Pydantic models for structured code review output."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from devops_cli.models.ai import FileAnalysisMeta

_SEVERITY_RANK: dict[str, int] = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
    "INFO": 4,
}

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


class Finding(BaseModel):
    severity: str = "MEDIUM"
    location: str = ""
    title: str = ""
    description: str = ""
    fix: str = ""
    references: list[str] = Field(default_factory=list)
    verified: bool = False

    mitigated: bool = False
    status: str = "UNVERIFIED"  # UNVERIFIED | VERIFIED | INVALIDATED | MITIGATED
    invalidation_reason: str | None = None
    verified_by: str | None = None  # "llm" | "human"
    verified_at: str | None = None
    confidence_score: float | None = None

    @field_validator("severity", mode="before")
    @classmethod
    def _normalize_severity(cls, v: object) -> str:
        s = str(v).upper().strip()
        return s if s in _SEVERITY_RANK else "MEDIUM"

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, v: object) -> str:
        s = str(v).upper().strip()
        valid = {"UNVERIFIED", "VERIFIED", "INVALIDATED", "MITIGATED"}
        return s if s in valid else "UNVERIFIED"

    @field_validator("confidence_score", mode="before")
    @classmethod
    def _normalize_confidence(cls, v: object) -> float | None:
        if v is None or str(v).lower() in ("null", "none", ""):
            return None
        try:
            val = float(str(v))
            return max(0.0, min(1.0, val))
        except ValueError, TypeError:
            return None


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
    reportable: bool = True


class ReviewSessionPayload(BaseModel):
    generated_at: str = ""
    personas: list[str] = Field(default_factory=list)
    findings: list[SavedFinding] = Field(default_factory=list)


class ReviewResult(BaseModel):
    findings: list[Finding] = Field(default_factory=list)
    positive_observations: list[str] = Field(default_factory=list)
    recommendation: str = "REQUEST CHANGES"
    summary: str = ""
    confidence_score: float | None = None

    @field_validator("recommendation", mode="before")
    @classmethod
    def _normalize_recommendation(cls, v: object) -> str:
        s = str(v).strip()
        return _RECOMMENDATION_ALIASES.get(s.lower(), s.upper())

    @field_validator("confidence_score", mode="before")
    @classmethod
    def _normalize_confidence(cls, v: object) -> float | None:
        if v is None or str(v).lower() in ("null", "none", ""):
            return None
        try:
            val = float(str(v))
            return max(0.0, min(1.0, val))
        except ValueError, TypeError:
            return None

    @property
    def sorted_findings(self) -> list[Finding]:
        return sorted(
            self.findings,
            key=lambda f: (_SEVERITY_RANK.get(f.severity, 99), not f.verified),
        )

    def merge(self, other: ReviewResult) -> ReviewResult:
        """Merge another ReviewResult, deduplicating findings by (title, location)."""
        seen: set[tuple[str, str]] = {(f.title.lower(), f.location.lower()) for f in self.findings}
        new_findings: list[Finding] = []
        for f in other.findings:
            key = (f.title.lower(), f.location.lower())
            if key not in seen:
                seen.add(key)
                new_findings.append(f)

        rec_order = {"BLOCK": 0, "REQUEST CHANGES": 1, "APPROVE": 2}
        recommendation = min(
            (self.recommendation, other.recommendation),
            key=lambda r: rec_order.get(r, 99),
        )
        c1 = self.confidence_score if self.confidence_score is not None else 0.8
        c2 = other.confidence_score if other.confidence_score is not None else 0.8
        merged_conf = round((c1 + c2) / 2.0, 2)
        return ReviewResult(
            findings=self.findings + new_findings,
            positive_observations=list(
                dict.fromkeys(self.positive_observations + other.positive_observations)
            ),
            recommendation=recommendation,
            summary=self.summary or other.summary,
            confidence_score=merged_conf,
        )


def extract_json_block(text: str) -> Any:
    """Extract the first parseable JSON object or array from text."""
    for pattern in (r"```json\s*([\s\S]*?)```", r"```\s*([\s\S]*?)```"):
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
    decoder = json.JSONDecoder()
    for m in re.finditer(r"[\{\[]", text):
        try:
            obj, _ = decoder.raw_decode(text, idx=m.start())
            return obj
        except json.JSONDecodeError:
            continue
    return None


def _parse_markdown_review_findings(text: str) -> list[Finding]:
    """Fallback parser to extract Finding objects from Markdown-formatted review text."""
    findings: list[Finding] = []
    blocks = re.split(r"\n(?=###?\s*Finding|\n\d+\.\s+|\n\*\*Location\*\*|\nLocation:)", text)
    for block in blocks:
        loc_m = re.search(r"(?:Location|File):\s*`?([^`\n]+)`?", block, re.IGNORECASE)
        if not loc_m:
            continue
        loc = loc_m.group(1).strip()
        sev_m = re.search(r"Severity:\s*\*?(CRITICAL|HIGH|MEDIUM|LOW)\*?", block, re.IGNORECASE)
        sev = (
            sev_m.group(1).upper()
            if (sev_m and sev_m.group(1).upper() in ("CRITICAL", "HIGH", "MEDIUM", "LOW"))
            else "MEDIUM"
        )
        title_m = re.search(
            r"(?:###?\s*(?:Finding\s*\d*:?\s*)?|\d+\.\s+|\*\*Title\*\*:\s*)([^\n]+)", block
        )
        title = title_m.group(1).strip("* ") if title_m else f"Issue at {loc}"
        desc_m = re.search(
            r"(?:Description|Impact):\s*(.+?)(?=\n\s*(?:Fix|Verification|Severity|Location):|\Z)",
            block,
            re.DOTALL | re.IGNORECASE,
        )
        desc = desc_m.group(1).strip() if desc_m else block[:200]
        fix_m = re.search(
            r"(?:Fix|Remediation):\s*(.+?)(?=\n\s*(?:Verification|Severity|Location):|\Z)",
            block,
            re.DOTALL | re.IGNORECASE,
        )
        fix = fix_m.group(1).strip() if fix_m else ""

        findings.append(
            Finding(
                severity=sev,
                location=loc,
                title=title,
                description=desc,
                fix=fix,
                confidence_score=0.8,
            )
        )

    return findings


def parse_review_result(text: str) -> ReviewResult | None:
    """Parse LLM output into a ReviewResult. Returns None if parsing fails."""
    data = extract_json_block(text)
    if isinstance(data, dict):
        try:
            return ReviewResult.model_validate(data)
        except Exception:
            pass

    md_findings = _parse_markdown_review_findings(text)
    if md_findings:
        return ReviewResult(findings=md_findings, summary=text[:300])

    return None
