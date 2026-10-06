"""Domain models for Atlassian Statuspage v2 operational status feeds."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.config.constants import (
    CONST_STATUSPAGE_COMPONENT_STATUS_VALUES,
    CONST_STATUSPAGE_INDICATOR_VALUES,
)


class StatuspagePage(BaseModel):
    """Statuspage tenant and metadata description."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str
    name: str
    url: str
    time_zone: str | None = None
    updated_at: str | None = None


class StatuspageStatus(BaseModel):
    """Aggregate operational status indicator and description."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    indicator: str
    description: str

    @property
    def severity_code(self) -> int:
        """Numeric severity level: 0=none/operational, 1=minor, 2=major, 3=critical."""
        return CONST_STATUSPAGE_INDICATOR_VALUES.get(self.indicator.lower(), 0)


class StatuspageComponent(BaseModel):
    """Individual service component operational status."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str
    name: str
    status: str
    description: str | None = None
    group: bool = False
    group_id: str | None = None
    position: int | None = None

    @property
    def status_code(self) -> int:
        """Numeric status code: 0=operational, 1=degraded, 2=partial_outage, 3=major_outage."""
        return CONST_STATUSPAGE_COMPONENT_STATUS_VALUES.get(self.status.lower(), 0)


class StatuspageIncident(BaseModel):
    """Active or recently updated service incident."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str
    name: str
    status: str
    impact: str
    created_at: str | None = None
    updated_at: str | None = None
    shortlink: str | None = None


class StatuspageSummary(BaseModel):
    """Complete Statuspage v2 summary response payload."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    page: StatuspagePage
    status: StatuspageStatus
    components: list[StatuspageComponent] = Field(default_factory=list)
    incidents: list[StatuspageIncident] = Field(default_factory=list)

    @property
    def is_operational(self) -> bool:
        """Whether all systems are reported fully operational."""
        return self.status.indicator.lower() == "none"

    @property
    def active_incidents(self) -> list[StatuspageIncident]:
        """Incidents that are not yet marked resolved."""
        return [inc for inc in self.incidents if inc.status.lower() != "resolved"]
