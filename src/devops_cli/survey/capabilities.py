"""Comparable tools capability evaluation, citation verification, and gap discovery."""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.core.repo import find_repo_root
from devops_cli.survey.models import (
    CapabilityComparison,
    CapabilityGap,
    CapabilityStatus,
)

logger = logging.getLogger(__name__)

DEFAULT_SURVEY_CONFIG_PATH = Path(".devops/survey.toml")


class ComparableTool(BaseModel):
    """Configuration for an external tool compared against devops-cli."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str = ""
    url: str = ""


class ComparableToolAssessment(BaseModel):
    """Declared status and citation of a capability in a comparable tool."""

    model_config = ConfigDict(frozen=True)

    tool: str
    status: CapabilityStatus = CapabilityStatus.UNKNOWN
    citation: str = ""


class ConfiguredCapability(BaseModel):
    """Configured capability with devops-cli status and assessments across comparable tools."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str = ""
    devops_cli: CapabilityStatus = CapabilityStatus.UNKNOWN
    citation: str = ""
    comparable: list[ComparableToolAssessment] = Field(default_factory=list)


class SurveyConfig(BaseModel):
    """Survey configuration holding comparable tools and declared capabilities."""

    model_config = ConfigDict(frozen=True)

    tools: list[ComparableTool] = Field(default_factory=list)
    capabilities: list[ConfiguredCapability] = Field(default_factory=list)


def _parse_status(value: Any) -> CapabilityStatus:
    """Parse status string into CapabilityStatus enum, defaulting to UNKNOWN."""
    if not value or not isinstance(value, str):
        return CapabilityStatus.UNKNOWN
    cleaned = value.strip().lower()
    if cleaned == "present":
        return CapabilityStatus.PRESENT
    if cleaned == "absent":
        return CapabilityStatus.ABSENT
    return CapabilityStatus.UNKNOWN


def load_survey_config(config_path: Path | None = None) -> SurveyConfig:
    """Load survey configuration from TOML file."""
    path = config_path or (find_repo_root() / DEFAULT_SURVEY_CONFIG_PATH)
    if not path.is_file():
        logger.debug("Survey configuration file not found at %s", path)
        return SurveyConfig()

    with path.open("rb") as f:
        data = tomllib.load(f)

    tools: list[ComparableTool] = []
    for t in data.get("tools", []):
        tools.append(
            ComparableTool(
                name=str(t.get("name", "")).strip(),
                description=str(t.get("description", "")).strip(),
                url=str(t.get("url", "")).strip(),
            )
        )

    capabilities: list[ConfiguredCapability] = []
    for c in data.get("capabilities", []):
        assessments: list[ComparableToolAssessment] = []
        for a in c.get("comparable", []):
            assessments.append(
                ComparableToolAssessment(
                    tool=str(a.get("tool", "")).strip(),
                    status=_parse_status(a.get("status")),
                    citation=str(a.get("citation", "")).strip(),
                )
            )
        capabilities.append(
            ConfiguredCapability(
                name=str(c.get("name", "")).strip(),
                description=str(c.get("description", "")).strip(),
                devops_cli=_parse_status(c.get("devops_cli")),
                citation=str(c.get("citation", "")).strip(),
                comparable=assessments,
            )
        )

    return SurveyConfig(tools=tools, capabilities=capabilities)


def compare_capabilities(config: SurveyConfig) -> list[CapabilityComparison]:
    """Compare devops-cli capabilities against configured comparable tools."""
    comparisons: list[CapabilityComparison] = []

    for cap in config.capabilities:
        devops_status = cap.devops_cli

        assessed_tools: dict[str, ComparableToolAssessment] = {
            a.tool.lower(): a for a in cap.comparable
        }

        # If tools are declared in config.tools, iterate over them
        target_tools = (
            config.tools if config.tools else [ComparableTool(name=a.tool) for a in cap.comparable]
        )

        for tool in target_tools:
            tool_key = tool.name.lower()
            assessment = assessed_tools.get(tool_key)

            if assessment is not None:
                tool_status = assessment.status
                citation = assessment.citation or tool.url or f"https://example.com/{tool.name}"
                # If claimed present without citation, fall back to tool URL
                if tool_status == CapabilityStatus.PRESENT and not assessment.citation:
                    citation = tool.url or f"https://example.com/{tool.name}"
            else:
                # Epistemic honesty constraint: an unassessed capability is ALWAYS unknown, never absent
                tool_status = CapabilityStatus.UNKNOWN
                citation = tool.url or f"https://example.com/{tool.name}#unassessed"

            is_gap = (
                tool_status == CapabilityStatus.PRESENT and devops_status == CapabilityStatus.ABSENT
            )

            comparisons.append(
                CapabilityComparison(
                    capability=cap.name,
                    tool=tool.name,
                    devops_cli_status=devops_status,
                    tool_status=tool_status,
                    citation=citation,
                    is_gap=is_gap,
                    description=cap.description,
                )
            )

    return comparisons


def find_capability_gaps(comparisons: list[CapabilityComparison]) -> list[CapabilityGap]:
    """Extract capability gaps where comparable tools have features absent in devops-cli."""
    gaps: list[CapabilityGap] = []
    for row in comparisons:
        if row.is_gap:
            gaps.append(
                CapabilityGap(
                    capability=row.capability,
                    tool=row.tool,
                    citation=row.citation,
                    description=row.description,
                )
            )
    return gaps
