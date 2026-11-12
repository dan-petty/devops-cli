"""The queries of the Grafana dashboard panels, evaluated on fixture series with promtool (#4680).

Each file `tests/fixtures/dashboard_queries/<dashboard>.yaml` holds the cases of the panels of
`k8s/monitoring/dashboards/<dashboard>.json`. A file is a promtool unit test file with no rule
file (`promtool test rules`), with these keys added:

- `shape` of a test group names the series shape that its input series model, one of `SHAPES`.
- `panel` and `ref_id` of each `promql_expr_test` case name the panel by its title and the target
  by its refId. `expr` is the query of that target as the dashboard holds it, with its Grafana
  variables.
- `variables` of a case gives the value of each variable of `expr`: `__range` and `__interval`
  as durations, and each dashboard variable as the text that Grafana puts in its place.
- `bars` of a case of a bar panel gives the range that the bars cover, such as `24h`, and
  `total` gives what the series of the case add in that range. The test adds up the bars of
  each `__interval` in the range, as Grafana draws them, and each expected sum is within 1 % of
  `total`.

The test replaces the variables as Grafana does, removes the added keys, writes one promtool
file for each dashboard and runs promtool once on it. docs/TESTING.md tells how to add a case.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.prometheus.client import parse_duration
from tests.support.paths import FIXTURES, REPO_ROOT
from tests.support.promtool import promtool

DASHBOARDS = REPO_ROOT / "k8s" / "monitoring" / "dashboards"
GRAFANA_VALUES = REPO_ROOT / "k8s" / "monitoring" / "grafana-values.yaml"
CASE_FILES = sorted((FIXTURES / "dashboard_queries").glob("*.yaml"))
CASE_IDS = [path.stem for path in CASE_FILES]

# The series shapes that the telemetry of devops-cli writes, as measured in #4675: a counter
# that the Service sends once each 15 min, a series that starts with a zero sample, a counter
# that drops to a low value when a pod starts, and a gauge that a snapshot writes each 15 min.
SHAPES = frozenset({"sparse_counter", "zero_start", "counter_reset", "snapshot_gauge"})

# The keys that the case files add to the promtool format. promtool refuses a key it does not
# know, so the test removes them.
GROUP_KEYS = frozenset({"shape"})
CASE_KEYS = frozenset({"panel", "ref_id", "variables", "bars", "total"})

# How far the sum of the bars of a case can be from the total of its series: `increase()`
# extrapolates each bar to the edges of its window (#4707).
BARS_TOLERANCE = 0.01

# The variable syntax of Grafana: `$name`, `[[name:format]]` and `${name.path:format}`
# (`variableRegex`, public/app/features/variables/utils.ts).
VARIABLE = re.compile(r"\$(\w+)|\[\[(\w+?)(?::(\w+))?\]\]|\$\{(\w+)(?:\.([^:^}]+))?(?::([^}]+))?\}")

# The variables that Grafana calculates from the range, the interval and the scrape interval.
# A case gives `__range` and `__interval`, and the test calculates the others.
DERIVED = frozenset({"__range_s", "__range_ms", "__interval_ms", "__rate_interval"})

# The scrape interval of a Prometheus data source that sets no `timeInterval` (Grafana default).
DEFAULT_SCRAPE_INTERVAL = "15s"


def _seconds(duration: object) -> int:
    """The whole seconds of a Prometheus duration such as `15m`, refusing a text that is none."""
    seconds = int(parse_duration(str(duration)))
    assert seconds > 0, f"{duration!r} is not a duration"
    return seconds


def rate_interval(interval_s: int, scrape_s: int) -> int:
    """The seconds of `$__rate_interval`: max($__interval + scrape interval, 4 x scrape interval)
    (Grafana, Prometheus template variables)."""
    return max(interval_s + scrape_s, 4 * scrape_s)


def grafana_values(given: Mapping[str, object], target: dict[str, Any]) -> dict[str, str]:
    """The text of each variable of a case of `target`: the dashboard variables as given, and the
    range and interval variables as Grafana writes them, in seconds."""
    assert not DERIVED & given.keys(), (
        f"give __range and __interval, not {sorted(DERIVED & given.keys())}"
    )
    values = {name: str(value) for name, value in given.items()}
    if "__range" in given:
        range_s = _seconds(given["__range"])
        values |= {
            "__range": f"{range_s}s",
            "__range_s": str(range_s),
            "__range_ms": str(range_s * 1000),
        }
    if "__interval" in given:
        interval_s = _seconds(given["__interval"])
        values |= {
            "__interval": f"{interval_s}s",
            "__interval_ms": str(interval_s * 1000),
            "__rate_interval": f"{rate_interval(interval_s, _scrape_s(target))}s",
        }
    return values


def summed_bars(query: str, bars: object, values: Mapping[str, str]) -> str:
    """`query` as the sum of its bars over the range `bars`: one bar each `$__interval`, at the
    multiples of the interval, as Grafana aligns the steps of a range query."""
    assert "__interval" in values, "a case with bars gives __interval"
    return f"sum_over_time(({query})[{_seconds(bars)}s:{values['__interval']}])"


def interpolate(expr: str, values: Mapping[str, str]) -> str:
    """`expr` with each variable that `values` names put in its place. A variable with no value,
    a field path or a format other than `raw` stays as it is."""

    def replace(match: re.Match[str]) -> str:
        name = match[1] or match[2] or match[4]
        style = match[3] or match[6]
        if name not in values or match[5] or style not in {None, "raw"}:
            return match[0]
        return values[name]

    return VARIABLE.sub(replace, expr)


def _panels(panels: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    """Each panel, the panels of a collapsed row included."""
    for panel in panels:
        yield panel
        yield from _panels(panel.get("panels", []))


def _targets(dashboard: dict[str, Any]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """The targets of a dashboard by the title of their panel and their refId. Each target holds
    the data source of its panel when it names none."""
    found: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for panel in _panels(dashboard["panels"]):
        for target in panel.get("targets", []):
            target.setdefault("datasource", panel.get("datasource"))
            found.setdefault((panel.get("title", ""), target.get("refId", "")), []).append(target)
    return found


def _dashboard(name: str) -> dict[str, Any]:
    dashboard: dict[str, Any] = json.loads(
        (DASHBOARDS / f"{name}.json").read_text(encoding="utf-8")
    )
    return dashboard


def _case_file(path: Path) -> dict[str, Any]:
    cases: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return cases


def _cases(case_file: dict[str, Any]) -> list[dict[str, Any]]:
    return [case for group in case_file["tests"] for case in group.get("promql_expr_test", [])]


def _where(name: str, case: Mapping[str, Any]) -> str:
    return f"{name}.json panel {case['panel']!r} refId {case['ref_id']}"


def query_mismatches(
    name: str, dashboard: dict[str, Any], cases: list[dict[str, Any]]
) -> list[str]:
    """One line for each case whose `expr` is not the query of its panel target, which names the
    dashboard, the panel title and the refId."""
    targets = _targets(dashboard)
    mismatches = []
    for case in cases:
        found = targets.get((case["panel"], case["ref_id"]), [])
        if len(found) != 1:
            mismatches.append(f"{_where(name, case)}: {len(found)} targets, not 1")
        elif found[0].get("expr") != case["expr"]:
            mismatches.append(f"{_where(name, case)}: the case query is not the panel query")
    return mismatches


@cache
def _scrape_intervals() -> dict[str, str]:
    """The scrape interval (`timeInterval`) of each Grafana data source, by uid."""
    sources = yaml.safe_load(GRAFANA_VALUES.read_text(encoding="utf-8"))["datasources"]
    return {
        source["uid"]: (source.get("jsonData") or {}).get("timeInterval", DEFAULT_SCRAPE_INTERVAL)
        for source in sources["datasources.yaml"]["datasources"]
    }


def _scrape_s(target: dict[str, Any]) -> int:
    """The scrape interval that Grafana uses for `$__rate_interval`: the Min step of the target,
    else the scrape interval of its data source."""
    return _seconds(target.get("interval") or _scrape_intervals()[target["datasource"]["uid"]])


def promtool_file(name: str, case_file: dict[str, Any]) -> dict[str, Any]:
    """The promtool unit test file of the cases of one dashboard: each `expr` with its variables
    in place, and the keys that promtool does not know removed."""
    targets = _targets(_dashboard(name))
    tests = []
    for group in case_file["tests"]:
        test = {key: value for key, value in group.items() if key not in GROUP_KEYS}
        test["promql_expr_test"] = []
        for case in group.get("promql_expr_test", []):
            (target,) = targets[(case["panel"], case["ref_id"])]
            values = grafana_values(case.get("variables", {}), target)
            query = interpolate(case["expr"], values)
            if "bars" in case:
                query = summed_bars(query, case["bars"], values)
            left = sorted({match[0] for match in VARIABLE.finditer(query)})
            assert not left, f"{_where(name, case)}: the case gives no value for {left}"
            test["promql_expr_test"].append(
                {key: value for key, value in case.items() if key not in CASE_KEYS}
                | {"expr": query}
            )
        tests.append(test)
    return {key: value for key, value in case_file.items() if key != "tests"} | {"tests": tests}


@pytest.mark.parametrize(
    ("interval", "scrape", "expected"),
    [("1m", "60s", 240), ("15m", "60s", 960), ("1h", "15m", 4500), ("30m", "15m", 3600)],
)
def test_rate_interval_is_the_larger_of_interval_plus_scrape_and_four_scrapes(
    interval: str, scrape: str, expected: int
) -> None:
    """`$__rate_interval` is max($__interval + scrape interval, 4 x scrape interval)."""
    assert rate_interval(_seconds(interval), _seconds(scrape)) == expected


def test_each_variable_syntax_takes_the_text_grafana_gives() -> None:
    """The range and interval variables are seconds, as Grafana writes them, and each syntax of a
    dashboard variable takes its value. A variable with no value or another format stays."""
    values = grafana_values(
        {"__range": "24h", "__interval": "1h", "job": "roadmap-service"}, {"interval": "60s"}
    )
    assert interpolate(
        'x{job=~"$job"}[$__range] $__range_s ${__range_ms} [[job]] ${job:raw} '
        "$__interval_ms [$__rate_interval] $repo ${job:regex}",
        values,
    ) == (
        'x{job=~"roadmap-service"}[86400s] 86400 86400000 roadmap-service roadmap-service '
        "3600000 [3660s] $repo ${job:regex}"
    )


def test_the_rate_interval_of_a_target_uses_its_min_step_over_the_data_source() -> None:
    """A target with a Min step uses it as the scrape interval; a target with none uses the
    `timeInterval` of its data source in `grafana-values.yaml`."""
    source = {"type": "prometheus", "uid": "prometheus"}
    assert (
        _scrape_s({"datasource": source, "interval": "15m"}),
        _scrape_s({"datasource": source}),
    ) == (900, _seconds(_scrape_intervals()["prometheus"]))


@pytest.mark.parametrize("cases", CASE_FILES, ids=CASE_IDS)
def test_each_case_holds_the_current_query_of_its_panel_target(cases: Path) -> None:
    """The `expr` of each case is the query that its panel target holds today, so a change of a
    covered query fails here until its cases change with it."""
    assert query_mismatches(cases.stem, _dashboard(cases.stem), _cases(_case_file(cases))) == []


def test_a_changed_query_names_the_dashboard_the_panel_and_the_ref_id() -> None:
    """A change of one character in a covered query fails with the dashboard, the panel title
    and the refId of the target."""
    dashboard = _dashboard("devops-cli")
    (target,) = _targets(dashboard)[("AI Spend in Range", "A")]
    target["expr"] = target["expr"].replace("$__range", "$__rang3")
    cases = _cases(_case_file(FIXTURES / "dashboard_queries" / "devops-cli.yaml"))
    changed = [case for case in cases if case["panel"] == "AI Spend in Range"]
    assert (changed != [], query_mismatches("devops-cli", dashboard, cases)) == (
        True,
        ["devops-cli.json panel 'AI Spend in Range' refId A: the case query is not the panel query"]
        * len(changed),
    )


def test_a_bars_case_adds_up_one_bar_each_interval_of_its_range() -> None:
    """A case with `bars` evaluates the sum of the bars of its panel: a subquery over the range
    of the bars, with one step each `$__interval`."""
    values = grafana_values({"__interval": "1h"}, {"interval": "60s"})
    assert summed_bars(interpolate("sum(increase(x[$__interval]))", values), "24h", values) == (
        "sum_over_time((sum(increase(x[3600s])))[86400s:3600s])"
    )


def _bars_off_their_total(case: Mapping[str, Any]) -> list[str]:
    """One line for each expected sample of a bars case that is not within `BARS_TOLERANCE` of
    the `total` of the case, or for a bars case with no total."""
    if "total" not in case:
        return [f"{case['panel']!r} refId {case['ref_id']}: a case with bars gives total"]
    total = float(case["total"])
    return [
        f"{case['panel']!r} refId {case['ref_id']}: {sample['value']} is not within 1 % of {total}"
        for sample in case["exp_samples"]
        if abs(float(sample["value"]) - total) > BARS_TOLERANCE * total
    ]


@pytest.mark.parametrize("cases", CASE_FILES, ids=CASE_IDS)
def test_the_bars_of_each_case_add_up_to_its_total_within_one_percent(cases: Path) -> None:
    """The hourly bars of a sparse counter add up to what the counter added in the range, within
    1 %: a bar panel does not count a sample in two bars or leave a gap between bars (#4707)."""
    bars = [case for case in _cases(_case_file(cases)) if "bars" in case]
    assert [line for case in bars for line in _bars_off_their_total(case)] == []


def test_the_cases_hold_each_series_shape() -> None:
    """The cases model each series shape of `SHAPES` at least once, and name no other shape."""
    shapes = {group.get("shape") for path in CASE_FILES for group in _case_file(path)["tests"]}
    assert (sorted(SHAPES - shapes), sorted(shapes - SHAPES - {None})) == ([], [])


@pytest.mark.live("promtool")
@pytest.mark.parametrize("cases", CASE_FILES, ids=CASE_IDS)
def test_promtool_gives_the_expected_samples_of_each_case(cases: Path, tmp_path: Path) -> None:
    """`promtool test rules` gives the `exp_samples` of each case of a dashboard, in one run."""
    unit_tests = tmp_path / cases.name
    unit_tests.write_text(
        yaml.safe_dump(promtool_file(cases.stem, _case_file(cases)), sort_keys=False),
        encoding="utf-8",
    )
    result = promtool("test", "rules", unit_tests)
    assert result.returncode == 0, result.stdout + result.stderr
