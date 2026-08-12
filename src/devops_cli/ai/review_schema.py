"""Pydantic models for structured code review output."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, field_validator

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
    references: list[str] = []
    verified: bool = False
    mitigated: bool = False
    status: str = "UNVERIFIED"  # UNVERIFIED | VERIFIED | INVALIDATED | MITIGATED
    invalidation_reason: str | None = None
    verified_by: str | None = None  # "llm" | "human"
    verified_at: str | None = None
    confidence_score: float = 0.9

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
    def _normalize_confidence(cls, v: object) -> float:
        if v is None:
            return 0.9
        try:
            val = float(str(v))
            return max(0.0, min(1.0, val))
        except ValueError, TypeError:
            return 0.9


class SavedFinding(Finding):
    persona: str = ""
    persona_title: str = ""
    recommendation: str = "REQUEST CHANGES"


class ReviewSessionPayload(BaseModel):
    generated_at: str = ""
    personas: list[str] = []
    findings: list[SavedFinding] = []


class ReviewResult(BaseModel):
    findings: list[Finding] = []
    positive_observations: list[str] = []
    recommendation: str = "REQUEST CHANGES"
    summary: str = ""
    confidence_score: float = 0.9

    @field_validator("recommendation", mode="before")
    @classmethod
    def _normalize_recommendation(cls, v: object) -> str:
        s = str(v).strip()
        return _RECOMMENDATION_ALIASES.get(s.lower(), s.upper())

    @field_validator("confidence_score", mode="before")
    @classmethod
    def _normalize_confidence(cls, v: object) -> float:
        if v is None:
            return 0.9
        try:
            val = float(str(v))
            return max(0.0, min(1.0, val))
        except ValueError, TypeError:
            return 0.9

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
        merged_conf = round((self.confidence_score + other.confidence_score) / 2.0, 2)
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


def parse_review_result(text: str) -> ReviewResult | None:
    """Parse LLM output into a ReviewResult. Returns None if parsing fails."""
    data = extract_json_block(text)
    if not isinstance(data, dict):
        return None
    try:
        return ReviewResult.model_validate(data)
    except Exception:
        return None
