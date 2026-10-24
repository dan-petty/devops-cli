"""Domain models for upstream maturity and capability survey."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DependencyPin(BaseModel):
    """Pinned runtime dependency name and version."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: str


class DependencyMaturity(BaseModel):
    """Mechanical signals and maintenance score for a pinned dependency."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    last_commit_date: str
    release_cadence: str
    archival_status: str
    is_archived: bool
    licence: str
    maintenance_score: float
    source_url: str = ""


class CapabilityStatus(StrEnum):
    """Assessment status of a system capability."""

    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"


class CapabilityComparison(BaseModel):
    """Capability assessment row comparing devops-cli against a comparable tool."""

    model_config = ConfigDict(frozen=True)

    capability: str
    tool: str
    devops_cli_status: CapabilityStatus
    tool_status: CapabilityStatus
    citation: str
    is_gap: bool = False
    description: str = ""


class CapabilityGap(BaseModel):
    """Identified capability gap where comparable tool has feature absent in devops-cli."""

    model_config = ConfigDict(frozen=True)

    capability: str
    tool: str
    citation: str
    description: str = ""


class SurveyReport(BaseModel):
    """Complete survey report holding dependency maturity signals and capability comparisons."""

    model_config = ConfigDict(frozen=True)

    dependencies: list[DependencyMaturity] = Field(default_factory=list)
    capabilities: list[CapabilityComparison] = Field(default_factory=list)
    gaps: list[CapabilityGap] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
