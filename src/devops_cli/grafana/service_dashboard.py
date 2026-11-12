"""The SRE template of the service dashboards (#5184, docs/DESIGN.md "Grafana layout", C12, C14).

`service_dashboard` builds the classic dashboard JSON of one Kubernetes service from a
`ServiceSpec` with the Grafana Foundation SDK: the row of the four SLO tiles, the burn rate and
the error budget, the golden signals in the order of the SRE book (latency, traffic, errors,
saturation), then the collapsed rows of capacity, logs and profiles. `make dashboards` runs this
module on `k8s/monitoring/dashboards/services.toml`, which writes `<uid>.json` for each spec next
to that file, and the dashboard sidecar provisions the files.

The SDK is in the dependency group `dashboards`, not in the runtime dependencies. Its release
0.0.22 writes the schema version 42 of the classic dashboard, which Grafana 13.3.1 reads and the
dashboard sidecar provisions. The SDK marks its classic builder deprecated in favor of its v2
builder, which the sidecar does not provision, so the import keeps that one warning out.

Each query uses the Grafana variables `$namespace` and `$workload`. A spec with `variables` keeps
them as dashboard variables; another spec puts its namespace and workload in their place.

The colors come from the token build (`devops_cli.design`): series 1 and 2 take the hex values of
`color.data.cat.1` and `color.data.cat.2`, which pass 3:1 on the four Grafana backgrounds. Each
other color is a Grafana color name that changes with the theme. This module holds no color
literal.
"""

from __future__ import annotations

import argparse
import json
import tomllib
import warnings
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from string import Template
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.design import tokens

with warnings.catch_warnings():
    # The classic builder is the one whose JSON the dashboard sidecar provisions.
    warnings.filterwarnings(
        "ignore", message="Prefer using dashboardv2", category=DeprecationWarning
    )
    from grafana_foundation_sdk.builders import common as common_builders
    from grafana_foundation_sdk.builders import dashboard as dashboard_builders
    from grafana_foundation_sdk.builders import grafanapyroscope, logs, loki, prometheus, stat
    from grafana_foundation_sdk.builders import timeseries as timeseries_builders
    from grafana_foundation_sdk.cog.builder import Builder
    from grafana_foundation_sdk.cog.encoder import JSONEncoder
    from grafana_foundation_sdk.models import common
    from grafana_foundation_sdk.models import dashboard as dashboard_models

type Resource = Literal["memory", "cpu"]
type ProfileType = Literal[
    "process_cpu:cpu:nanoseconds:cpu:nanoseconds", "memory:inuse_space:bytes:space:bytes"
]

# The file of the specs, and the file that `make dashboards` writes for each spec next to it.
SPEC_FILE_NAME: Final = "services.toml"
DASHBOARD_SUFFIX: Final = ".json"

# The Grafana color names that change with the theme (docs/DESIGN.md, "Grafana"): `text` for a
# single series, a third entity and the 1x pace; `semi-dark-orange` for warn; `red` for fail.
GRAFANA_TEXT: Final = "text"
GRAFANA_WARN: Final = "semi-dark-orange"
GRAFANA_FAIL: Final = "red"
GRAFANA_COLOR_NAMES: Final = frozenset({GRAFANA_TEXT, GRAFANA_WARN, GRAFANA_FAIL})

# The data sources that k8s/monitoring/grafana-values.yaml provisions, by their fixed uid.
_PROMETHEUS: Final = common.DataSourceRef(type_val="prometheus", uid="prometheus")
_LOKI: Final = common.DataSourceRef(type_val="loki", uid="loki")
_PYROSCOPE: Final = common.DataSourceRef(type_val="grafana-pyroscope-datasource", uid="pyroscope")

# The Grafana dash arrays of series 2 and 3 (the presets `[10, 10]` and `[30, 3, 3]`), and the
# style `dots` of a reference line (C14).
_SERIES_DASHES: Final[tuple[tuple[int, ...], ...]] = ((), (10, 10), (30, 3, 3))
_REFERENCE_DASH: Final[tuple[int, ...]] = (0, 10)

# The grid of the layout (docs/DESIGN.md, "Grafana layout"): 24 columns, the SLO tiles `w6 h4`,
# the charts `w12 h8`, a full-width row and the log and profile panels.
_GRID_WIDTH: Final = 24
_TILE: Final = (6, 4)
_CHART: Final = (12, 8)
_HALF_TILE: Final = (12, 4)
_WARN_LOGS: Final = (24, 8)
_ALL_LOGS: Final = (24, 12)
_PROFILE: Final = (24, 12)

# The size of a stat number (C12 a: a 36 px number).
_TILE_VALUE_SIZE: Final = 36
# The burn rates of the page lines of the multiwindow alerts (SRE workbook, Table 5-8): the
# window, its hours, and the share of the budget that it spends at the line.
_PAGE_WINDOWS: Final[tuple[tuple[str, int, Decimal], ...]] = (
    ("1h", 1, Decimal("0.02")),
    ("6h", 6, Decimal("0.05")),
)
# The share of the budget left under which a tile shows warn (C12 a).
_BUDGET_WARN: Final = Decimal("0.25")
# The pace of an even burn: the budget is spent at the end of the window.
_EVEN_BURN: Final = Decimal(1)
# The latency quantiles of the golden signals (C12 d).
_QUANTILES: Final[tuple[tuple[str, str], ...]] = (("0.5", "p50"), ("0.95", "p95"), ("0.99", "p99"))
# The Loki levels of the warnings panel: `detected_level` of `discover_log_levels`.
_WARN_LEVELS: Final = "(?i)(warn|warning|error|err|critical|fatal|panic)"
_PODS: Final = "$workload-[a-z0-9]+-[a-z0-9]+"
_STEP: Final = "$__rate_interval"
# The Min step of the budget chart: each point reads the whole window.
_BUDGET_STEP: Final = "15m"
_HOURS_PER_DAY: Final = 24
_PERCENT: Final = Decimal(100)
_NBSP: Final = "\u00a0"
_TIMES: Final = "\u00d7"
_TAGS: Final[tuple[str, ...]] = ("sre", "service", "generated")
_PROFILE_TITLES: Final[dict[str, str]] = {
    "process_cpu:cpu:nanoseconds:cpu:nanoseconds": "Profiles: CPU time",
    "memory:inuse_space:bytes:space:bytes": "Profiles: memory in use",
}


class ServiceSpec(BaseModel):
    """The spec of the dashboard of one Kubernetes service: its identity, its request metrics
    and its SLO. Each selector can name the Grafana variables `$namespace` and `$workload`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    uid: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,39}$")
    title: str
    description: str
    namespace: str
    workload: str
    variables: bool = False
    # The counter of the requests of the service, with the matchers that select the service. It
    # ends with its matchers in braces, because `errors` goes into them.
    requests: str = Field(
        default='traefik_service_requests_total{service=~"$namespace-$workload-[0-9]+@kubernetes"}',
        pattern=r"\}$",
    )
    # The matcher, added to `requests`, that selects the failed requests.
    errors: str = 'code=~"5.."'
    # The histogram buckets of the latency of the successful requests.
    latency: str = (
        "traefik_service_request_duration_seconds_bucket"
        '{service=~"$namespace-$workload-[0-9]+@kubernetes", code!~"5.."}'
    )
    slo_target: Decimal = Field(default=Decimal("0.999"), gt=0, lt=1)
    slo_window_days: int = Field(default=30, gt=0)
    saturation: tuple[Resource, ...] = Field(default=("memory", "cpu"), min_length=1, max_length=2)
    logs: bool = True
    profiles: tuple[ProfileType, ...] = ()

    @property
    def budget(self) -> Decimal:
        """The error budget: the share of the requests that can fail."""
        return 1 - self.slo_target

    @property
    def window(self) -> str:
        """The SLO window as a PromQL duration."""
        return f"{self.slo_window_days}d"


@dataclass(frozen=True)
class _Line:
    """One line of a time series: its legend name, its query, its color and its dash. A
    reference line is a constant or a limit, drawn 1 px in the style `dots`."""

    name: str
    expr: str
    color: str
    dash: tuple[int, ...] = ()
    reference: bool = False


@dataclass(frozen=True)
class _Resource:
    """The names, the query of the use and the axis of one resource of the containers of the
    workload: `title` starts a title, and `name` goes in a sentence."""

    title: str
    name: str
    use: str
    unit: str
    axis: str


_RESOURCES: Final[dict[str, _Resource]] = {
    "memory": _Resource(
        title="Memory",
        name="memory",
        use="container_memory_working_set_bytes{$containers}",
        unit="bytes",
        axis="Memory (bytes)",
    ),
    "cpu": _Resource(
        title="CPU",
        name="CPU",
        use=f"rate(container_cpu_usage_seconds_total{{$containers}}[{_STEP}])",
        unit="short",
        axis="CPU (cores)",
    ),
}
_CONTAINERS: Final = f'namespace="$namespace", pod=~"{_PODS}", container!=""'
_RESOURCE_SERIES: Final = (
    'kube_pod_container_resource_{kind}{{namespace="$namespace", pod=~"{pods}", '
    'resource="{resource}"}}'
)


def _number(value: Decimal) -> str:
    """A number as PromQL and a legend write it: no exponent and no trailing zero."""
    return format(value.normalize(), "f")


def _px(token: str) -> float:
    """The width in px of a chart stroke token, such as `1.5px`."""
    return float(str(tokens("light")[token]).removesuffix("px"))


def _series_colors() -> tuple[str, str, str]:
    """The colors of series 1, 2 and 3: the token hex of `color.data.cat.1` and `cat.2`, which
    are the same in both themes, and the Grafana color `text`."""
    values = tokens("light")
    return str(values["color-data-cat-1"]), str(values["color-data-cat-2"]), GRAFANA_TEXT


def _series(index: int, name: str, expr: str) -> _Line:
    """Series `index` (0, 1 or 2) of a chart with its color and its dash."""
    return _Line(name, expr, _series_colors()[index], _SERIES_DASHES[index])


def _single(name: str, expr: str) -> _Line:
    """The one series of a chart, in `text` (a single series uses `color.fg`)."""
    return _Line(name, expr, GRAFANA_TEXT)


def _reference(name: str, value: Decimal, color: str) -> _Line:
    """A constant reference line, such as a page line or a limit (C14)."""
    return _Line(name, f"vector({_number(value)})", color, _REFERENCE_DASH, reference=True)


def _limit(name: str, expr: str) -> _Line:
    """A reference line that a query gives, such as a resource limit."""
    return _Line(name, expr, GRAFANA_FAIL, _REFERENCE_DASH, reference=True)


class _Queries:
    """The PromQL of the SLO and the golden signals of one spec."""

    def __init__(self, spec: ServiceSpec) -> None:
        self._spec = spec
        self._failed = f"{spec.requests[:-1]}, {spec.errors}}}"

    def _sum(self, function: str, selector: str, window: str) -> str:
        return f"sum({function}({selector}[{window}]))"

    def error_ratio(self, window: str, function: str = "increase") -> str:
        """The share of the requests that failed in `window`. With requests and no failed
        request, the failed count is the zero of the requests, not a constant."""
        total = self._sum(function, self._spec.requests, window)
        failed = self._sum(function, self._failed, window)
        return f"({failed} or {total} * 0) / {total}"

    def sli(self) -> str:
        """The share of the requests that succeeded over the SLO window."""
        return f"1 - {self.error_ratio(self._spec.window)}"

    def budget_left(self) -> str:
        """The share of the error budget that is left over the SLO window."""
        return f"1 - {self.error_ratio(self._spec.window)} / {_number(self._spec.budget)}"

    def burn_rate(self, window: str) -> str:
        """How fast the requests of `window` spend the budget: 1 spends it in the SLO window."""
        return f"{self.error_ratio(window)} / {_number(self._spec.budget)}"

    def latency(self, quantile: str) -> str:
        return f"histogram_quantile({quantile}, sum by (le) (rate({self._spec.latency}[{_STEP}])))"

    def traffic(self) -> str:
        return self._sum("rate", self._spec.requests, _STEP)

    def resource_series(self, kind: str, resource: str) -> str:
        """The sum of the requests or the limits of `resource` of the workload's containers."""
        selector = _RESOURCE_SERIES.format(kind=kind, pods=_PODS, resource=resource)
        return f"sum({selector})"

    def use(self, resource: str) -> str:
        """The use of `resource` by the workload's containers."""
        use = Template(_RESOURCES[resource].use).safe_substitute(containers=_CONTAINERS)
        return f"sum({use})"

    def saturation(self, resource: str) -> str:
        """The highest share of its limit of `resource` that a container of the workload uses."""
        use = Template(_RESOURCES[resource].use).safe_substitute(containers=_CONTAINERS)
        limits = _RESOURCE_SERIES.format(kind="limits", pods=_PODS, resource=resource)
        return f"max(sum by (pod, container) ({use}) / sum by (pod, container) ({limits}))"


class _Ids:
    """The panel ids of one dashboard, in the order of the panels."""

    def __init__(self) -> None:
        self._last = 0

    def next(self) -> int:
        self._last += 1
        return self._last


def _grid(size: tuple[int, int]) -> dashboard_models.GridPos:
    """A grid size; the dashboard builder puts the panel in the next free place."""
    width, height = size
    return dashboard_models.GridPos(w=width, h=height)


def _override(line: _Line, stroke: float) -> list[dashboard_models.DynamicConfigValue]:
    """The color, dash and width of one line (C14)."""
    style: dict[str, Any] = {"fill": "solid"}
    if line.dash:
        style = {"fill": "dot" if line.reference else "dash", "dash": list(line.dash)}
    return [
        dashboard_models.DynamicConfigValue(
            id_val="color", value={"mode": "fixed", "fixedColor": line.color}
        ),
        dashboard_models.DynamicConfigValue(id_val="custom.lineStyle", value=style),
        dashboard_models.DynamicConfigValue(id_val="custom.lineWidth", value=stroke),
    ]


def _fixed(color: str) -> dashboard_builders.FieldColor:
    return (
        dashboard_builders.FieldColor()
        .mode(dashboard_models.FieldColorModeId.FIXED)
        .fixed_color(color)
    )


def _thresholds(steps: Sequence[tuple[Decimal | None, str]]) -> dashboard_builders.ThresholdsConfig:
    """Absolute thresholds: the color of the lowest step, then each value and its color."""
    return (
        dashboard_builders.ThresholdsConfig()
        .mode(dashboard_models.ThresholdsMode.ABSOLUTE)
        .steps(
            [
                dashboard_models.Threshold(
                    value=None if value is None else float(value), color=color
                )
                for value, color in steps
            ]
        )
    )


@dataclass(frozen=True)
class _Chart:
    """A time series: its title, description, unit, axis title and lines."""

    title: str
    description: str
    unit: str
    axis: str
    lines: tuple[_Line, ...]
    soft_min: bool = False
    maximum: Decimal | None = None
    interval: str | None = None


def _query(line: _Line, ref_id: str) -> prometheus.Dataquery:
    return prometheus.Dataquery().expr(line.expr).legend_format(line.name).ref_id(ref_id)


def _chart(chart: _Chart, ids: _Ids, size: tuple[int, int] = _CHART) -> Builder[Any]:
    """A time series in the form of the chart rules: lines of 1.5 px with no fill, y from 0
    (or a soft 0 for a level that can fall under it), a list legend and one unit (C4 to C8)."""
    data_stroke = _px("chart-stroke-data")
    reference_stroke = _px("chart-stroke-reference")
    panel = (
        timeseries_builders.Panel()
        .id(ids.next())
        .title(chart.title)
        .description(chart.description)
        .datasource(_PROMETHEUS)
        .grid_pos(_grid(size))
        .unit(chart.unit)
        .axis_label(chart.axis)
        .color_scheme(_fixed(GRAFANA_TEXT))
        .draw_style(common.GraphDrawStyle.LINE)
        .line_width(data_stroke)
        .fill_opacity(0)
        .show_points(common.VisibilityMode.NEVER)
        .legend(
            common_builders.VizLegendOptions()
            .display_mode(common.LegendDisplayMode.LIST)
            .placement(common.LegendPlacement.BOTTOM)
            .show_legend(True)
        )
        .tooltip(
            common_builders.VizTooltipOptions()
            .mode(common.TooltipDisplayMode.MULTI)
            .sort(common.SortOrder.NONE)
        )
    )
    panel = panel.axis_soft_min(0) if chart.soft_min else panel.min(0)
    if chart.maximum is not None:
        panel = panel.max(float(chart.maximum))
    if chart.interval is not None:
        panel = panel.interval(chart.interval)
    for index, line in enumerate(chart.lines):
        stroke = reference_stroke if line.reference else data_stroke
        panel = panel.with_target(_query(line, chr(ord("A") + index)))
        panel = panel.override_by_name(line.name, _override(line, stroke))
    return panel


@dataclass(frozen=True)
class _Tile:
    """A stat: its title, description, query, unit, decimals and threshold steps."""

    title: str
    description: str
    expr: str
    unit: str
    decimals: int
    steps: tuple[tuple[Decimal | None, str], ...] = ((None, GRAFANA_TEXT),)


def _tile(tile: _Tile, ids: _Ids, size: tuple[int, int] = _TILE) -> Builder[Any]:
    """A stat with a 36 px number in the color of its state (C12 a)."""
    return (
        stat.Panel()
        .id(ids.next())
        .title(tile.title)
        .description(tile.description)
        .datasource(_PROMETHEUS)
        .grid_pos(_grid(size))
        .unit(tile.unit)
        .decimals(tile.decimals)
        .color_scheme(
            dashboard_builders.FieldColor().mode(dashboard_models.FieldColorModeId.THRESHOLDS)
        )
        .thresholds(_thresholds(tile.steps))
        .color_mode(common.BigValueColorMode.VALUE)
        .graph_mode(common.BigValueGraphMode.NONE)
        .text_mode(common.BigValueTextMode.VALUE)
        .justify_mode(common.BigValueJustifyMode.CENTER)
        .text(common_builders.VizTextDisplayOptions().value_size(_TILE_VALUE_SIZE))
        .reduce_options(common_builders.ReduceDataOptions().calcs(["lastNotNull"]))
        .with_target(prometheus.Dataquery().expr(tile.expr).instant().ref_id("A"))
    )


def _percent(value: Decimal) -> str:
    """A share as text: `99.9 %`, with a no-break space before the sign."""
    return f"{_number(value * _PERCENT)}{_NBSP}%"


def _times(value: Decimal) -> str:
    """A multiplier as text: `14.4×`."""
    return f"{_number(value)}{_TIMES}"


def _page_rate(spec: ServiceSpec, hours: int, share: Decimal) -> Decimal:
    """The burn rate at which a window of `hours` spends `share` of the budget."""
    return share * spec.slo_window_days * _HOURS_PER_DAY / hours


def _slo_tiles(spec: ServiceSpec, queries: _Queries, ids: _Ids) -> Iterator[Builder[Any]]:
    """The four SLO tiles: the target, the SLI, the budget left and the burn rate now."""
    days = spec.slo_window_days
    budget_warn_sli = 1 - (1 - _BUDGET_WARN) * spec.budget
    page = _page_rate(spec, *_PAGE_WINDOWS[0][1:])
    yield _tile(
        _Tile(
            title=f"SLO: target over {days} days",
            description=(
                f"The share of the requests that must succeed over the last {days} days. "
                "The owner of the service sets it in k8s/monitoring/dashboards/services.toml."
            ),
            expr=f"vector({_number(spec.slo_target)})",
            unit="percentunit",
            decimals=1,
        ),
        ids,
    )
    yield _tile(
        _Tile(
            title="SLI: successful requests",
            description=(
                f"The share of the requests of the last {days} days that did not fail. "
                f"A failed request has a code that matches {spec.errors}. Red: under the SLO. "
                f"Orange: less than {_percent(_BUDGET_WARN)} of the error budget is left."
            ),
            expr=queries.sli(),
            unit="percentunit",
            decimals=3,
            steps=(
                (None, GRAFANA_FAIL),
                (spec.slo_target, GRAFANA_WARN),
                (budget_warn_sli, GRAFANA_TEXT),
            ),
        ),
        ids,
    )
    yield _tile(
        _Tile(
            title=f"Error budget: left over {days} days",
            description=(
                f"The share of the error budget of the last {days} days that the failed "
                f"requests did not spend. The budget is {_percent(spec.budget)} of the requests. "
                f"Orange: less than {_percent(_BUDGET_WARN)} is left. Red: the budget is spent."
            ),
            expr=queries.budget_left(),
            unit="percentunit",
            decimals=1,
            steps=((None, GRAFANA_FAIL), (Decimal(0), GRAFANA_WARN), (_BUDGET_WARN, GRAFANA_TEXT)),
        ),
        ids,
    )
    yield _tile(
        _Tile(
            title="Burn rate: last hour",
            description=(
                "How fast the requests of the last hour spend the error budget. At 1x the "
                f"budget lasts {days} days. Orange: faster than 1x. Red: at the page line "
                f"{_times(page)}, which spends 2 % of the budget in one hour."
            ),
            expr=queries.burn_rate(_PAGE_WINDOWS[0][0]),
            unit="x",
            decimals=1,
            steps=((None, GRAFANA_TEXT), (_EVEN_BURN, GRAFANA_WARN), (page, GRAFANA_FAIL)),
        ),
        ids,
    )


def _burn_chart(spec: ServiceSpec, queries: _Queries) -> _Chart:
    """The 1 h and 6 h burn rates against their page lines, and the 1x pace (C12 c)."""
    lines: list[_Line] = []
    pages: list[_Line] = []
    for index, (window, hours, share) in enumerate(_PAGE_WINDOWS):
        rate = _page_rate(spec, hours, share)
        lines.append(_series(index, f"{hours} h burn rate", queries.burn_rate(window)))
        pages.append(
            _reference(f"Page line of the {hours} h burn: {_times(rate)}", rate, GRAFANA_FAIL)
        )
    pace = _reference(f"Budget pace: {_times(_EVEN_BURN)}", _EVEN_BURN, GRAFANA_TEXT)
    return _Chart(
        title="Burn rate: 1 h and 6 h windows",
        description=(
            "How fast the failed requests spend the error budget. Compare the 1 h line only with "
            "its page line, and the 6 h line only with its page line. At the 1x pace the budget "
            f"lasts {spec.slo_window_days} days."
        ),
        unit="x",
        axis=f"Burn rate ({_TIMES})",
        lines=(*lines, *pages, pace),
    )


def _budget_chart(spec: ServiceSpec, queries: _Queries) -> _Chart:
    """The budget left of the rolling window, with its warn line and its end (C12 b)."""
    days = spec.slo_window_days
    return _Chart(
        title=f"Error budget: left over the rolling {days} days",
        description=(
            f"Each point is the share of the error budget left of the {days} days before it. A "
            "steady burn at 1x keeps the line at 0 %. Under 0 % the failed requests spent more "
            "than the budget."
        ),
        unit="percentunit",
        axis="Budget left (%)",
        lines=(
            _single("Budget left", queries.budget_left()),
            _reference(f"Warn: {_percent(_BUDGET_WARN)} left", _BUDGET_WARN, GRAFANA_WARN),
            _reference("Budget spent", Decimal(0), GRAFANA_FAIL),
        ),
        soft_min=True,
        maximum=Decimal(1),
        interval=_BUDGET_STEP,
    )


def _golden_signals(spec: ServiceSpec, queries: _Queries) -> tuple[_Chart, ...]:
    """Latency, traffic, errors and saturation, in the order of the SRE book (C12 d)."""
    latency = tuple(
        _series(index, name, queries.latency(quantile))
        for index, (quantile, name) in enumerate(_QUANTILES)
    )
    saturation = tuple(
        _series(index, _RESOURCES[resource].title, queries.saturation(resource))
        for index, resource in enumerate(spec.saturation)
    )
    return (
        _Chart(
            title="Latency: p50, p95 and p99 of successful requests",
            description=(
                "The quantiles of the time to answer a request that did not fail, from the "
                "buckets of the latency histogram. A quantile is in its bucket, so it is "
                "only as exact as the bucket bounds."
            ),
            unit="s",
            axis="Latency (s)",
            lines=latency,
        ),
        _Chart(
            title="Traffic: requests per second",
            description="The requests to the service each second, from the request counter.",
            unit="reqps",
            axis="Traffic (requests/s)",
            lines=(_single("Requests", queries.traffic()),),
        ),
        _Chart(
            title="Errors: share of failed requests",
            description=(
                f"The share of the requests that failed: a code that matches {spec.errors}. "
                f"Over the SLO line the service spends its budget faster than 1x."
            ),
            unit="percentunit",
            axis="Errors (% of requests)",
            lines=(
                _single("Failed requests", queries.error_ratio(_STEP, "rate")),
                _reference(f"SLO: {_percent(spec.budget)} can fail", spec.budget, GRAFANA_TEXT),
            ),
        ),
        _Chart(
            title="Saturation: highest share of a container limit",
            description=(
                "For each resource, the highest share of its limit that one container of the "
                "workload uses. At the limit, the kernel kills the container for memory and "
                "throttles it for CPU."
            ),
            unit="percentunit",
            axis="Saturation (% of the limit)",
            lines=(*saturation, _reference("Limit", Decimal(1), GRAFANA_FAIL)),
        ),
    )


def _capacity(spec: ServiceSpec, queries: _Queries, ids: _Ids) -> Iterator[Builder[Any]]:
    """The use, request and limit of each resource, and its headroom as a number (C12 f)."""
    for resource in spec.saturation:
        found = _RESOURCES[resource]
        use = queries.use(resource)
        limit = queries.resource_series("limits", resource)
        yield _chart(
            _Chart(
                title=f"{found.title}: use, request and limit",
                description=(
                    f"The {found.name} that the containers of the workload use and request, "
                    "and their limit, summed over the pods."
                ),
                unit=found.unit,
                axis=found.axis,
                lines=(
                    _series(0, "Use", use),
                    _series(1, "Request", queries.resource_series("requests", resource)),
                    _limit("Limit", limit),
                ),
            ),
            ids,
        )
    for resource in spec.saturation:
        found = _RESOURCES[resource]
        yield _tile(
            _Tile(
                title=f"Headroom: {found.name} under the limit",
                description=(
                    f"The {found.name} that the containers of the workload can use before they reach "
                    "their limits, summed over the pods."
                ),
                expr=f"{queries.resource_series('limits', resource)} - {queries.use(resource)}",
                unit=found.unit,
                decimals=1,
            ),
            ids,
            _HALF_TILE,
        )


def _logs(ids: _Ids) -> Iterator[Builder[Any]]:
    """The warnings and errors above all lines of the workload's pods (Loki)."""
    stream = f'{{namespace="$namespace"}} | pod=~"{_PODS}"'
    panels = (
        (
            "Logs: warnings and errors",
            "The lines of the pods of the workload that Loki gives the level warn, error, "
            "critical, fatal or panic.",
            f'{stream} | detected_level=~"{_WARN_LEVELS}"',
            _WARN_LOGS,
        ),
        ("Logs: all lines", "All lines of the pods of the workload.", stream, _ALL_LOGS),
    )
    for title, description, expr, size in panels:
        yield (
            logs.Panel()
            .id(ids.next())
            .title(title)
            .description(description)
            .datasource(_LOKI)
            .grid_pos(_grid(size))
            .show_time(True)
            .wrap_log_message(True)
            .enable_log_details(True)
            .sort_order(common.LogsSortOrder.DESCENDING)
            .dedup_strategy(common.LogsDedupStrategy.NONE)
            .with_target(loki.Dataquery().expr(expr).ref_id("A"))
        )


def _profiles(spec: ServiceSpec, ids: _Ids) -> Iterator[Builder[Any]]:
    """One flame graph for each profile type of the spec (Pyroscope)."""
    selector = '{service_namespace="$namespace", service_name="$workload"}'
    for profile in spec.profiles:
        yield (
            dashboard_builders.Panel()
            .type("flamegraph")
            .id(ids.next())
            .title(_PROFILE_TITLES[profile])
            .description(
                "Where the processes of the workload spend this resource over the time range, "
                "from the continuous profiles that Alloy sends to Pyroscope."
            )
            .datasource(_PYROSCOPE)
            .grid_pos(_grid(_PROFILE))
            .with_target(
                grafanapyroscope.Dataquery()
                .label_selector(selector)
                .profile_type_id(profile)
                .query_type("profile")
                .group_by([])
                .ref_id("A")
            )
        )


def _collapsed(
    title: str, ids: _Ids, panels: Iterator[Builder[Any]], y: int | None
) -> dashboard_builders.Row:
    """A collapsed row with its panels. A row with no `y` goes under the panels above it; a
    collapsed row takes one grid line, so the next row has the `y` after it."""
    row = dashboard_builders.Row(title).id(ids.next())
    if y is not None:
        row = row.grid_pos(dashboard_models.GridPos(h=1, w=_GRID_WIDTH, x=0, y=y))
    for panel in panels:
        row = row.with_panel(panel)
    return row


def _variables(spec: ServiceSpec) -> list[Builder[Any]]:
    """The single-value variables of the namespace and the workload, on their spec values."""
    found: list[Builder[Any]] = []
    for name, label, query, value in (
        (
            "namespace",
            "Namespace",
            "label_values(kube_deployment_spec_replicas, namespace)",
            spec.namespace,
        ),
        (
            "workload",
            "Workload",
            'label_values(kube_deployment_spec_replicas{namespace="$namespace"}, deployment)',
            spec.workload,
        ),
    ):
        found.append(
            dashboard_builders.QueryVariable(name)
            .label(label)
            .datasource(_PROMETHEUS)
            .query(query)
            .current(dashboard_models.VariableOption(selected=True, text=value, value=value))
            .refresh(dashboard_models.VariableRefresh.ON_DASHBOARD_LOAD)
            .sort(dashboard_models.VariableSort.ALPHABETICAL_ASC)
        )
    return found


def _builder(spec: ServiceSpec) -> dashboard_builders.Dashboard:
    """The SDK builder of the dashboard of `spec`, in the order of the layout."""
    queries = _Queries(spec)
    ids = _Ids()
    board = (
        dashboard_builders.Dashboard(spec.title)
        .uid(spec.uid)
        .description(spec.description)
        .tags(list(_TAGS))
        .time("now-24h", "now")
        .refresh("1m")
        .timezone("utc")
        .tooltip(dashboard_models.DashboardCursorSync.CROSSHAIR)
        .readonly()
    )
    if spec.variables:
        board = board.variables(_variables(spec))
    slo = f"Service level objective: {_percent(spec.slo_target)} over {spec.slo_window_days} days"
    board = board.with_row(dashboard_builders.Row(slo).id(ids.next()))
    for tile in _slo_tiles(spec, queries, ids):
        board = board.with_panel(tile)
    board = board.with_panel(_chart(_burn_chart(spec, queries), ids))
    board = board.with_panel(_chart(_budget_chart(spec, queries), ids))
    board = board.with_row(dashboard_builders.Row("Golden signals").id(ids.next()))
    for chart in _golden_signals(spec, queries):
        board = board.with_panel(_chart(chart, ids))
    collapsed: list[tuple[str, Iterator[Builder[Any]]]] = [
        ("Capacity", _capacity(spec, queries, ids))
    ]
    if spec.logs:
        collapsed.append(("Logs", _logs(ids)))
    if spec.profiles:
        collapsed.append(("Profiles", _profiles(spec, ids)))
    row_y: int | None = None
    for title, panels in collapsed:
        row = _collapsed(title, ids, panels, None if row_y is None else row_y + 1)
        board = board.with_row(row)
        # The dashboard builder gives each row a grid position.
        position = row.build().grid_pos
        row_y = position.y if position is not None else row_y
    return board


def _fill_in(node: Any, spec: ServiceSpec) -> Any:
    """`node` with the namespace and the workload of `spec` in place of their variables."""
    if isinstance(node, str):
        return Template(node).safe_substitute(namespace=spec.namespace, workload=spec.workload)
    if isinstance(node, list):
        return [_fill_in(item, spec) for item in node]
    if isinstance(node, dict):
        return {key: _fill_in(value, spec) for key, value in node.items()}
    return node


def service_dashboard(spec: ServiceSpec) -> dict[str, Any]:
    """The classic dashboard JSON of `spec`, as the dashboard sidecar provisions it."""
    built: dict[str, Any] = json.loads(JSONEncoder().encode(_builder(spec).build()))
    built["annotations"] = {"list": []}
    built["templating"] = {"list": built.get("templating", {}).get("list", [])}
    if spec.variables:
        return built
    filled: dict[str, Any] = _fill_in(built, spec)
    return filled


def dashboard_text(spec: ServiceSpec) -> str:
    """The text of the dashboard file of `spec`: sorted keys, two-space indent, a final newline."""
    return json.dumps(service_dashboard(spec), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def load_specs(spec_file: Path) -> list[ServiceSpec]:
    """The specs of the `[[service]]` tables of `spec_file`."""
    document = tomllib.loads(spec_file.read_text(encoding="utf-8"))
    return [ServiceSpec.model_validate(entry) for entry in document["service"]]


def write_dashboards(spec_file: Path) -> list[Path]:
    """Write `<uid>.json` next to `spec_file` for each of its specs, and return the paths."""
    written = []
    for spec in load_specs(spec_file):
        path = spec_file.with_name(f"{spec.uid}{DASHBOARD_SUFFIX}")
        path.write_text(dashboard_text(spec), encoding="utf-8")
        written.append(path)
    return written


def main(argv: Sequence[str] | None = None) -> None:
    """`make dashboards`: write the dashboard of each spec of the spec file."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spec_file", type=Path)
    write_dashboards(parser.parse_args(argv).spec_file)


if __name__ == "__main__":
    main()
