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
