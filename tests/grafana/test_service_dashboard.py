"""The SRE template of the service dashboards (#5184).

`devops_cli.grafana.service_dashboard` builds the dashboard of a Kubernetes service from a spec
with the Grafana Foundation SDK, in the layout of docs/DESIGN.md ("Grafana layout", C12 and C14),
and `make dashboards` writes each spec of `k8s/monitoring/dashboards/services.toml` as
`<uid>.json`. tests/fixtures/dashboard_queries/ holds the cases that evaluate the SLO queries with
promtool.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from coloraide import Color
from pydantic import ValidationError

from devops_cli.design import THEME_MODES, tokens
from devops_cli.grafana.service_dashboard import (
    GRAFANA_COLOR_NAMES,
    SPEC_FILE_NAME,
    ServiceSpec,
    dashboard_text,
    load_specs,
    main,
    service_dashboard,
)
from tests.support.design_tokens import DESIGN_SPEC, GRAFANA_BACKGROUNDS
from tests.support.paths import REPO_ROOT

DASHBOARDS = REPO_ROOT / "k8s" / "monitoring" / "dashboards"
TEMPLATE = REPO_ROOT / "src" / "devops_cli" / "grafana" / "service_dashboard.py"
CPU_PROFILE = "process_cpu:cpu:nanoseconds:cpu:nanoseconds"
MEMORY_PROFILE = "memory:inuse_space:bytes:space:bytes"
# A constant reference line, such as `vector(14.4)` (C14).
REFERENCE = re.compile(r"vector\(\s*[0-9.]+\s*\)")
HEX = re.compile(r"#[0-9a-fA-F]{6}\b")
# The color modes of a field: one color, the thresholds, the shades of one color, and the ramp
# of a heatmap (docs/DESIGN.md, "Grafana").
COLOR_MODES = frozenset({"fixed", "thresholds", "shades", "continuous-cividis"})
UNIT_PANELS = frozenset({"timeseries", "stat"})
# The lowest contrast of a series color on each Grafana background (docs/DESIGN.md, C7).
SERIES_CONTRAST = 3.0


def _spec(**changes: Any) -> ServiceSpec:
    """The spec of the cart of a shop, with the CPU profiles, and `changes` put in."""
    fields: dict[str, Any] = {
        "uid": "shop-cart",
        "title": "Cart: SLO and golden signals",
        "description": "The SLO and the golden signals of the cart.",
        "namespace": "shop",
        "workload": "cart",
        "profiles": (CPU_PROFILE,),
    }
    return ServiceSpec.model_validate(fields | changes)


def _panels(panels: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    """Each panel that is not a row, the panels of a collapsed row included."""
    for panel in panels:
        if panel["type"] == "row":
            yield from _panels(panel.get("panels", []))
        else:
            yield panel


def _by_title(dashboard: dict[str, Any], title: str) -> dict[str, Any]:
    (found,) = [panel for panel in _panels(dashboard["panels"]) if panel["title"] == title]
    return found


def _sentence_case(title: str) -> bool:
    """A title in sentence case: a capital first letter, then capitals only in acronyms."""
    words = [word.strip(",:()") for word in title.split()]
    return title[:1].isupper() and all(
        word.isupper() or not word[:1].isupper() for word in words[1:] if word
    )


def _panel_problems(panel: dict[str, Any]) -> list[str]:
    """One line for each rule of the "Grafana" row of docs/DESIGN.md that a panel breaks: a
    title in sentence case that names the signal and the measure, a description, and one unit
    for a panel of numbers."""
    title = panel["title"]
    problems = []
    if ": " not in title or not _sentence_case(title):
        problems.append(f"{title}: not a sentence-case title 'Signal: measure'")
    if not panel.get("description"):
        problems.append(f"{title}: no description")
    if panel["type"] in UNIT_PANELS:
        field_config = panel["fieldConfig"]
        override_units = [
            prop["value"]
            for override in field_config["overrides"]
            for prop in override["properties"]
            if prop["id"] == "unit"
        ]
        if not field_config["defaults"].get("unit") or override_units:
            problems.append(f"{title}: not one unit")
    return problems


def _data_targets(panel: dict[str, Any]) -> list[dict[str, Any]]:
    return [target for target in panel["targets"] if not REFERENCE.fullmatch(target["expr"])]


def _series_problems(panel: dict[str, Any]) -> list[str]:
    """A time series draws at most 3 series and "Other" (C7): at most 3 data targets, and each
    has a fixed legend, so it names one series."""
    data = _data_targets(panel)
    problems = [f"{panel['title']}: {len(data)} series"] if len(data) > 3 else []
    problems.extend(
        f"{panel['title']}: the legend {target['legendFormat']!r} names each series"
        for target in data
        if "{{" in target.get("legendFormat", "{{")
    )
    return problems


def _overrides(panel: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The override properties of each series of a panel, by the series name."""
    return {
        override["matcher"]["options"]: {
            prop["id"]: prop["value"] for prop in override["properties"]
        }
        for override in panel["fieldConfig"]["overrides"]
    }


def _reference_lines(panel: dict[str, Any]) -> list[tuple[str, str, str]]:
    """The constant of each reference line of a panel, with its color and its line fill."""
    styles = _overrides(panel)
    return [
        (
            target["expr"],
            styles[target["legendFormat"]]["color"]["fixedColor"],
            styles[target["legendFormat"]]["custom.lineStyle"]["fill"],
        )
        for target in panel["targets"]
        if REFERENCE.fullmatch(target["expr"])
    ]


def _passing_hex() -> frozenset[str]:
    """The token colors of both themes that pass 3:1 on the four Grafana backgrounds."""
    colors = {
        str(value).lower()
        for theme in THEME_MODES
        for name, value in tokens(theme).items()
        if name.startswith("color-") and HEX.fullmatch(str(value))
    }
    return frozenset(
        color
        for color in colors
        if all(
            Color(color).contrast(background, method="wcag21") >= SERIES_CONTRAST
            for background in GRAFANA_BACKGROUNDS.values()
        )
    )


def _colors(node: Any) -> Iterator[tuple[str, str]]:
    """Each color setting of a dashboard as (key, value): the mode and the fixed color of each
    field color, and the color of each threshold step."""
    if isinstance(node, list):
        for item in node:
            yield from _colors(item)
    if not isinstance(node, dict):
        return
    for key, value in node.items():
        if key == "color" and isinstance(value, str):
            yield key, value
        elif key == "color" and isinstance(value, dict):
            yield "mode", value["mode"]
            if "fixedColor" in value:
                yield "fixedColor", value["fixedColor"]
        else:
            yield from _colors(value)


def color_problems(dashboard: dict[str, Any]) -> list[str]:
    """One line for each color of a dashboard that is not a token hex that passes 3:1 on the
    four Grafana backgrounds, or a Grafana color name of docs/DESIGN.md, and for each hex text
    that is not such a token."""
    passing = _passing_hex()
    problems = [
        f"{key} {value}"
        for key, value in _colors(dashboard)
        if (key == "mode" and value not in COLOR_MODES)
        or (key != "mode" and value.lower() not in passing | GRAFANA_COLOR_NAMES)
    ]
    problems.extend(
        f"hex {value}"
        for value in HEX.findall(json.dumps(dashboard))
        if value.lower() not in passing
    )
    return problems


def _committed() -> list[dict[str, Any]]:
    return [
        json.loads((DASHBOARDS / f"{spec.uid}.json").read_text(encoding="utf-8"))
        for spec in load_specs(DASHBOARDS / SPEC_FILE_NAME)
    ]


def test_the_layout_puts_the_slo_row_the_golden_signals_and_the_collapsed_rows_in_order() -> None:
    """Row 1 holds the 4 SLO tiles (`w6 h4`), row 2 the burn rate and the budget (`w12 h8`),
    then the golden signals in the order latency, traffic, errors and saturation (`w12 h8`, two
    to a line), then the collapsed rows of capacity, logs and profiles (docs/DESIGN.md, "Grafana
    layout")."""
    dashboard = service_dashboard(_spec())

    assert [
        (
            panel["type"],
            panel["title"].partition(":")[0],
            tuple(panel["gridPos"][key] for key in ("x", "y", "w", "h")),
            panel.get("collapsed"),
        )
        for panel in dashboard["panels"]
    ] == [
        ("row", "Service level objective", (0, 0, 24, 1), False),
        ("stat", "SLO", (0, 1, 6, 4), None),
        ("stat", "SLI", (6, 1, 6, 4), None),
        ("stat", "Error budget", (12, 1, 6, 4), None),
        ("stat", "Burn rate", (18, 1, 6, 4), None),
        ("timeseries", "Burn rate", (0, 5, 12, 8), None),
        ("timeseries", "Error budget", (12, 5, 12, 8), None),
        ("row", "Golden signals", (0, 13, 24, 1), False),
        ("timeseries", "Latency", (0, 14, 12, 8), None),
        ("timeseries", "Traffic", (12, 14, 12, 8), None),
        ("timeseries", "Errors", (0, 22, 12, 8), None),
        ("timeseries", "Saturation", (12, 22, 12, 8), None),
        ("row", "Capacity", (0, 30, 24, 1), True),
        ("row", "Logs", (0, 31, 24, 1), True),
        ("row", "Profiles", (0, 32, 24, 1), True),
    ]


def test_each_panel_has_one_unit_a_sentence_case_title_and_a_description() -> None:
    """Each panel names its signal and its measure in sentence case and has a description; each
    panel of numbers has one unit, which no override changes (docs/DESIGN.md, C2 and C4)."""
    panels = list(_panels(service_dashboard(_spec(variables=True)).get("panels", [])))

    assert (len(panels), [line for panel in panels for line in _panel_problems(panel)]) == (17, [])


def test_the_panel_rules_report_a_title_case_title_a_missing_description_and_two_units() -> None:
    """The rules report a title that is not in sentence case, a panel with no description, and
    a panel whose override sets a second unit."""
    panel = _by_title(service_dashboard(_spec()), "Traffic: requests per second")
    broken = panel | {"title": "Traffic: Requests Per Second", "description": ""}
    broken["fieldConfig"] = {
        "defaults": {"unit": "reqps"},
        "overrides": [{"matcher": {}, "properties": [{"id": "unit", "value": "s"}]}],
    }

    assert _panel_problems(broken) == [
        "Traffic: Requests Per Second: not a sentence-case title 'Signal: measure'",
        "Traffic: Requests Per Second: no description",
        "Traffic: Requests Per Second: not one unit",
    ]


def test_no_time_series_draws_more_than_three_series_and_other() -> None:
    """Each time series has at most 3 data series, each with a fixed name; a reference line is a
    constant and is not a series (C7)."""
    time_series = [
        panel
        for panel in _panels(service_dashboard(_spec()).get("panels", []))
        if panel["type"] == "timeseries"
    ]

    assert (
        len(time_series),
        [line for panel in time_series for line in _series_problems(panel)],
    ) == (
        8,
        [],
    )


def test_a_time_series_with_four_series_or_a_legend_of_each_series_is_reported() -> None:
    panel = {
        "title": "Latency: p95",
        "targets": [{"expr": "up", "legendFormat": "{{pod}}"}]
        + [{"expr": "up", "legendFormat": "One"}] * 3,
    }

    assert _series_problems(panel) == [
        "Latency: p95: 4 series",
        "Latency: p95: the legend '{{pod}}' names each series",
    ]


def test_the_burn_rate_chart_starts_at_zero_in_x_with_its_page_lines_and_the_pace() -> None:
    """The burn rate has y min 0 and the unit `x`; the 1 h line is drawn against its page line
    14.4, the 6 h line against 6, and the 1x pace is a line in `text` (C12 c, C14)."""
    panel = _by_title(service_dashboard(_spec()), "Burn rate: 1 h and 6 h windows")

    assert (
        panel["fieldConfig"]["defaults"]["min"],
        panel["fieldConfig"]["defaults"]["unit"],
        [target["legendFormat"] for target in _data_targets(panel)],
        _reference_lines(panel),
    ) == (
        0,
        "x",
        ["1 h burn rate", "6 h burn rate"],
        [("vector(14.4)", "red", "dot"), ("vector(6)", "red", "dot"), ("vector(1)", "text", "dot")],
    )


def test_each_line_has_no_fill_and_each_reference_line_is_a_dotted_named_color() -> None:
    """Each time series has the fill opacity 0, and each constant line has a Grafana color
    name and the line style `dots` (C14)."""
    time_series = [
        panel
        for panel in _panels(service_dashboard(_spec()).get("panels", []))
        if panel["type"] == "timeseries"
    ]

    assert (
        {panel["fieldConfig"]["defaults"]["custom"]["fillOpacity"] for panel in time_series},
        sorted(
            {
                (color, fill)
                for panel in time_series
                for _expr, color, fill in _reference_lines(panel)
            }
        ),
    ) == ({0}, [("red", "dot"), ("semi-dark-orange", "dot"), ("text", "dot")])


def test_the_tiles_show_the_state_of_the_budget_and_the_burn_rate() -> None:
    """The budget tile is red under 0 % and orange under 25 %; the burn tile is orange from 1x
    and red from the page line 14.4x (C12 a)."""
    dashboard = service_dashboard(_spec())

    assert [
        [
            (step["value"], step["color"])
            for step in _by_title(dashboard, title)["fieldConfig"]["defaults"]["thresholds"][
                "steps"
            ]
        ]
        for title in ("Error budget: left over 30 days", "Burn rate: last hour")
    ] == [
        [(None, "red"), (0.0, "semi-dark-orange"), (0.25, "text")],
        [(None, "text"), (1.0, "semi-dark-orange"), (14.4, "red")],
    ]


def test_a_spec_with_variables_selects_the_namespace_and_the_workload() -> None:
    """A spec with variables gets single-value variables for the namespace and the workload, on
    the values of the spec, and its queries read them. A spec with none puts its values in
    place of the variables."""
    generic = service_dashboard(_spec(variables=True))
    fixed = service_dashboard(_spec())
    traffic = "Traffic: requests per second"

    assert (
        [
            (
                variable["name"],
                variable["multi"],
                variable["includeAll"],
                variable["current"]["value"],
            )
            for variable in generic["templating"]["list"]
        ],
        _by_title(generic, traffic)["targets"][0]["expr"],
        fixed["templating"]["list"],
        _by_title(fixed, traffic)["targets"][0]["expr"],
        "$namespace" in json.dumps(fixed) or "$workload" in json.dumps(fixed),
    ) == (
        [("namespace", False, False, "shop"), ("workload", False, False, "cart")],
        'sum(rate(traefik_service_requests_total{service=~"$namespace-$workload-[0-9]+@kubernetes"}'
        "[$__rate_interval]))",
        [],
        'sum(rate(traefik_service_requests_total{service=~"shop-cart-[0-9]+@kubernetes"}'
        "[$__rate_interval]))",
        False,
    )


def test_a_service_without_logs_or_profiles_has_no_such_row() -> None:
    rows = [
        panel["title"]
        for panel in service_dashboard(_spec(logs=False, profiles=())).get("panels", [])
        if panel["type"] == "row"
    ]

    assert rows == [
        "Service level objective: 99.9\u00a0% over 30 days",
        "Golden signals",
        "Capacity",
    ]


def test_the_log_row_shows_the_warnings_above_all_lines_of_the_workload_pods() -> None:
    """The warnings panel is the query of all lines with the case-insensitive filter of the
    levels that Loki detects. The pod is a filter after the stream selector, because a pod log
    carries `pod` as structured metadata (#1357)."""
    dashboard = service_dashboard(_spec())
    pods = 'pod=~"cart-[a-z0-9]+-[a-z0-9]+"'

    assert [
        (
            panel["title"],
            panel["datasource"]["uid"],
            panel["targets"][0]["expr"],
            panel["gridPos"]["h"],
        )
        for panel in dashboard["panels"][13]["panels"]
    ] == [
        (
            "Logs: warnings and errors",
            "loki",
            f'{{namespace="shop"}} | {pods} | detected_level=~"(?i)(warn|warning|error|err|critical|fatal|panic)"',
            8,
        ),
        ("Logs: all lines", "loki", f'{{namespace="shop"}} | {pods}', 12),
    ]


def test_the_profile_row_shows_a_flame_graph_of_each_profile_type_of_the_spec() -> None:
    """Each profile type of the spec gets a flame graph of the Pyroscope `service_name` of the
    workload in its namespace, with no `created_by_name` (#1134)."""
    dashboard = service_dashboard(_spec(profiles=(CPU_PROFILE, MEMORY_PROFILE)))

    assert [
        (
            panel["type"],
            panel["title"],
            panel["targets"][0]["profileTypeId"],
            panel["targets"][0]["labelSelector"],
        )
        for panel in dashboard["panels"][14]["panels"]
    ] == [
        (
            "flamegraph",
            "Profiles: CPU time",
            CPU_PROFILE,
            '{service_namespace="shop", service_name="cart"}',
        ),
        (
            "flamegraph",
            "Profiles: memory in use",
            MEMORY_PROFILE,
            '{service_namespace="shop", service_name="cart"}',
        ),
    ]


def test_the_slo_target_and_window_of_the_spec_set_the_budget_and_the_page_lines() -> None:
    """An SLO of 99 % over 28 days gives a budget of 0.01 and the page lines 13.44 and 5.6."""
    dashboard = service_dashboard(_spec(slo_target="0.99", slo_window_days=28))
    burn = _by_title(dashboard, "Burn rate: 1 h and 6 h windows")

    assert (
        dashboard["panels"][0]["title"],
        _by_title(dashboard, "SLO: target over 28 days")["targets"][0]["expr"],
        [expr for expr, _color, _fill in _reference_lines(burn)],
        burn["targets"][0]["expr"].endswith("[1h])) / 0.01"),
    ) == (
        "Service level objective: 99\u00a0% over 28 days",
        "vector(0.99)",
        ["vector(13.44)", "vector(5.6)", "vector(1)"],
        True,
    )


def test_a_spec_whose_requests_end_with_no_matchers_is_refused() -> None:
    """The failed requests add a matcher to the matchers of `requests`, so a selector with no
    matchers at its end is refused."""
    with pytest.raises(ValidationError, match="requests"):
        _spec(requests="traefik_service_requests_total")


def test_each_color_is_a_passing_token_hex_or_a_grafana_color_name() -> None:
    """The committed service dashboards and a fixture build hold only the token hex of series 1
    and 2, which pass 3:1 on the four Grafana backgrounds, and the Grafana names `text`,
    `semi-dark-orange` and `red` (docs/DESIGN.md, "Grafana")."""
    dashboards = [
        *_committed(),
        service_dashboard(_spec(variables=True, profiles=(CPU_PROFILE, MEMORY_PROFILE))),
    ]

    assert (len(dashboards), [line for board in dashboards for line in color_problems(board)]) == (
        3,
        [],
    )


def test_a_color_that_is_no_passing_token_or_grafana_name_is_reported() -> None:
    """A Grafana palette hex, the token hex of series 3 in the light theme (2.0:1 on the dark
    panel), a palette name and the classic palette mode each fail the color check."""
    broken = {
        "panels": [
            {"fieldConfig": {"defaults": {"color": {"mode": "palette-classic"}}}},
            {"fieldConfig": {"defaults": {"color": {"mode": "fixed", "fixedColor": "#73bf69"}}}},
            {"thresholds": {"steps": [{"color": "green", "value": None}]}},
            {"description": f"Drawn in {tokens('light')['color-data-cat-3']}."},
        ]
    }

    assert color_problems(broken) == [
        "mode palette-classic",
        "fixedColor #73bf69",
        "color green",
        "hex #73bf69",
        f"hex {tokens('light')['color-data-cat-3']}",
    ]


def test_the_template_holds_no_color_literal() -> None:
    """The template reads the series colors from the token build, so its source holds no hex."""
    assert HEX.findall(TEMPLATE.read_text(encoding="utf-8")) == []


def test_each_grafana_color_name_of_the_template_is_in_the_design_spec() -> None:
    """The Grafana color names of the template are those that the paragraph "Grafana" of
    docs/DESIGN.md names."""
    spec_text = DESIGN_SPEC.read_text(encoding="utf-8")
    paragraph = spec_text.split("### Grafana\n", 1)[1].split("\n## ", 1)[0]

    assert sorted(GRAFANA_COLOR_NAMES - set(re.findall(r"`([a-z-]+)`", paragraph))) == []


def test_each_committed_service_dashboard_is_the_build() -> None:
    """Each spec of services.toml has its dashboard file, and the file is the build of the spec
    (`make dashboards`), so no hand edit or old build stays in git."""
    specs = load_specs(DASHBOARDS / SPEC_FILE_NAME)

    assert (
        [spec.uid for spec in specs],
        [
            spec.uid
            for spec in specs
            if (DASHBOARDS / f"{spec.uid}.json").read_text(encoding="utf-8") != dashboard_text(spec)
        ],
    ) == (["devops-roadmap-service", "devops-sre-service"], [])


def test_the_build_writes_the_dashboard_of_each_spec_next_to_the_spec_file(tmp_path: Path) -> None:
    folder = tmp_path / "dashboards"
    folder.mkdir()
    spec_file = folder / SPEC_FILE_NAME
    spec_file.write_text(
        "[[service]]\n"
        'uid = "shop-cart"\n'
        'title = "Cart: SLO and golden signals"\n'
        'description = "The SLO and the golden signals of the cart."\n'
        'namespace = "shop"\n'
        'workload = "cart"\n'
        'slo_target = "0.995"\n',
        encoding="utf-8",
    )

    main([str(spec_file)])

    assert (
        sorted(path.name for path in folder.iterdir()),
        (folder / "shop-cart.json").read_text(encoding="utf-8"),
    ) == (
        ["services.toml", "shop-cart.json"],
        dashboard_text(_spec(slo_target="0.995", profiles=())),
    )


def test_the_readme_lists_the_service_dashboards_and_their_build() -> None:
    """k8s/README.md lists both service dashboards in their ConfigMap and names `make dashboards`."""
    readme = (REPO_ROOT / "k8s" / "README.md").read_text(encoding="utf-8")
    section = readme.split("## Grafana Dashboards\n", 1)[1].split("\n## ", 1)[0]
    (row,) = [
        line for line in section.splitlines() if line.startswith("| `grafana-service-dashboards`")
    ]

    assert (row, "`make dashboards`" in section) == (
        "| `grafana-service-dashboards` | `devops-roadmap-service.json`, `devops-sre-service.json` |",
        True,
    )
