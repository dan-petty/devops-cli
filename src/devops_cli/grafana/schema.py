"""Typed Grafana dashboard schema models.

Dashboards were maintained as large static JSON files in which every panel repeated its
datasource binding, colour mode, legend options, and grid position. That boilerplate is
tedious to diff, impossible to parameterise across clusters, and offers no way to catch a
malformed query or an overlapping layout before Grafana renders it.

These models describe the Grafana 10+ dashboard JSON shape, so a dashboard can be built
in Python, type-checked, linted, and serialised to exactly the JSON Grafana expects.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.config.constants import (
    CONST_GRAFANA_DASHBOARD_GRID_WIDTH,
    CONST_GRAFANA_DEFAULT_DATASOURCE_TYPE,
    CONST_GRAFANA_SCHEMA_VERSION,
)


class Datasource(BaseModel):
    """A datasource reference attached to a dashboard, panel, or target."""

    type: str = Field(default=CONST_GRAFANA_DEFAULT_DATASOURCE_TYPE)
    uid: str = Field(default=CONST_GRAFANA_DEFAULT_DATASOURCE_TYPE)


class GridPos(BaseModel):
    """A panel's position and size on the 24-column dashboard grid."""

    h: int = Field(default=8, description="Height in grid rows")
    w: int = Field(default=12, description="Width in grid columns")
    x: int = Field(default=0, description="Left offset in grid columns")
    y: int = Field(default=0, description="Top offset in grid rows")

    @property
    def right(self) -> int:
        """Column immediately past the panel's right edge."""
        return self.x + self.w

    @property
    def bottom(self) -> int:
        """Row immediately past the panel's bottom edge."""
        return self.y + self.h

    def overlaps(self, other: GridPos) -> bool:
        """Report whether two panels occupy any of the same grid cells."""
        return (
            self.x < other.right
            and other.x < self.right
            and self.y < other.bottom
            and other.y < self.bottom
        )


class Target(BaseModel):
    """A single query backing a panel."""

    model_config = ConfigDict(populate_by_name=True)

    expr: str = Field(default="", description="PromQL expression")
    legend_format: str = Field(default="", alias="legendFormat")
    ref_id: str = Field(default="A", alias="refId")
    datasource: Datasource = Field(default_factory=Datasource)


class Legend(BaseModel):
    """Panel legend rendering options."""

    model_config = ConfigDict(populate_by_name=True)

    display_mode: str = Field(default="list", alias="displayMode")
    placement: str = Field(default="bottom")


class FieldDefaults(BaseModel):
    """Default field configuration shared by a panel's series."""

    color: dict[str, Any] = Field(default_factory=lambda: {"mode": "palette-classic"})
    custom: dict[str, Any] = Field(default_factory=dict)
    unit: str = Field(default="short")


class FieldConfig(BaseModel):
    """Field configuration block, mirroring the Grafana panel schema."""

    defaults: FieldDefaults = Field(default_factory=FieldDefaults)
    overrides: list[dict[str, Any]] = Field(default_factory=list)


class Panel(BaseModel):
    """A dashboard panel."""

    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(default=0)
    title: str = Field(default="")
    type: str = Field(default="timeseries")
    grid_pos: GridPos = Field(default_factory=GridPos, alias="gridPos")
    targets: list[Target] = Field(default_factory=list)
    datasource: Datasource | None = Field(default=None)
    field_config: FieldConfig | None = Field(default=None, alias="fieldConfig")
    options: dict[str, Any] = Field(default_factory=dict)
    collapsed: bool | None = Field(default=None)

    @property
    def is_row(self) -> bool:
        """Report whether the panel is a layout row rather than a visualisation."""
        return self.type == "row"


class Dashboard(BaseModel):
    """A complete Grafana dashboard."""

    model_config = ConfigDict(populate_by_name=True)

    uid: str = Field(default="")
    title: str = Field(default="")
    tags: list[str] = Field(default_factory=list)
    timezone: str = Field(default="browser")
    editable: bool = Field(default=True)
    refresh: str = Field(default="30s")
    schema_version: int = Field(default=CONST_GRAFANA_SCHEMA_VERSION, alias="schemaVersion")
    version: int = Field(default=1)
    panels: list[Panel] = Field(default_factory=list)
    time: dict[str, str] = Field(default_factory=lambda: {"from": "now-6h", "to": "now"})
    annotations: dict[str, Any] = Field(default_factory=dict)
    links: list[dict[str, Any]] = Field(default_factory=list)

    def to_grafana_json(self) -> dict[str, Any]:
        """Serialise to the exact JSON shape Grafana accepts.

        Aliases are emitted (``gridPos``, ``schemaVersion``) and unset optional fields are
        omitted, so a generated dashboard is byte-comparable with a hand-authored one.
        """
        return self.model_dump(by_alias=True, exclude_none=True)

    @property
    def grid_width(self) -> int:
        """The dashboard grid width panels must fit within."""
        return CONST_GRAFANA_DASHBOARD_GRID_WIDTH


__all__ = [
    "Dashboard",
    "Datasource",
    "FieldConfig",
    "FieldDefaults",
    "GridPos",
    "Legend",
    "Panel",
    "Target",
]
