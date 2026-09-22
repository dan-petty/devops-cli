"""Shared domain models for Grafana API responses."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GrafanaDashboard(BaseModel):
    """A Grafana dashboard entry from /api/search."""

    uid: str = ""
    title: str = ""
    folder_title: str = Field("General", alias="folderTitle")

    model_config = ConfigDict(populate_by_name=True)


class GrafanaDatasource(BaseModel):
    """A Grafana datasource from /api/datasources."""

    name: str = ""
    type: str = ""
    url: str = ""
    is_default: bool = Field(False, alias="isDefault")

    model_config = ConfigDict(populate_by_name=True)


class GrafanaAlertRule(BaseModel):
    """A Grafana unified alerting rule from /api/v1/provisioning/alert-rules."""

    uid: str = ""
    title: str = ""
    folder_uid: str = Field("", alias="folderUID")
    condition: str = ""

    model_config = ConfigDict(populate_by_name=True)


class DashboardLintIssue(BaseModel):
    """A single problem detected in a dashboard definition."""

    severity: str = Field(default="error", description="Issue severity: error or warning")
    message: str = Field(..., description="Human-readable description of the problem")
    panel: str = Field(default="", description="Title of the offending panel, when applicable")


class DashboardLintReport(BaseModel):
    """Aggregated lint results for one dashboard."""

    dashboard_uid: str = Field(default="", description="Dashboard uid")
    dashboard_title: str = Field(default="", description="Dashboard title")
    source_file: str = Field(default="", description="File the dashboard was loaded from")
    panel_count: int = Field(default=0, description="Number of panels inspected")
    issues: list[DashboardLintIssue] = Field(default_factory=list, description="Detected problems")

    @property
    def errors(self) -> list[DashboardLintIssue]:
        """Issues that would render the dashboard incorrectly."""
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[DashboardLintIssue]:
        """Issues worth attention that still render."""
        return [issue for issue in self.issues if issue.severity != "error"]

    @property
    def passed(self) -> bool:
        """Report whether the dashboard is free of errors."""
        return not self.errors
