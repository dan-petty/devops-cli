"""The SLO rule groups of the product: the render of a Sloth spec (#4709).

`docs/guidelines/sre.md` says that Sloth generates the recording rules and the burn-rate alerts of
each SLO from one spec, and that no person writes an SLO rule by hand. The runner image holds no
`sloth` program, so this module renders the `prometheus/v1` format of a spec itself: the seven
error ratios, the objective, its error budget and the 28-day window, then the four alerts of
Table 2 of the guideline, each guarded by the events that the low-sample rule needs.

`k8s/devops/monitoring/slos/` holds one spec for each SLO of the product, and the render of the
folder is the text between the two marker comments of
`k8s/devops/monitoring/prometheus-rules-values.yaml`, which the Prometheus chart loads. Run this
module with the folder, that file and `--write` to render it again; without `--write` it prints the
groups. The `k8s` row of `devops ci` fails when the file and a fresh render differ, so a spec that
nobody rendered fails the pull request.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

import yaml

from devops_cli.exceptions import ConfigurationError
from devops_cli.output import write_stdout
from devops_cli.prometheus.promql import grouping_labels

# The window of each SLO: 28 days, the built-in `google-28d` window of Sloth
# (docs/guidelines/sre.md, "SLOs and error budgets").
SLO_WINDOW_DAYS: Final = 28
# The events that the long window of an alert needs before it may fire. An SLO with fewer gives
# "low sample" and no alert (docs/guidelines/sre.md, "SLOs and error budgets").
SLO_MIN_EVENTS: Final = 20
# The two comments of the values file that hold the render: `write_slo_groups` replaces the text
# between them, and leaves the rest of the file as it is.
SLO_GROUPS_START_MARKER: Final = "# BEGIN slo-rules"
SLO_GROUPS_END_MARKER: Final = "# END slo-rules"
# The `severity` label of each kind of row of Table 2 (docs/guidelines/sre.md, rule SRE4): a page
# needs a person within the hour, and each other alert is a warning.
_SLO_SEVERITY: Final[dict[str, str]] = {"Page": "critical", "Ticket": "warning"}
# The percent that a spec writes its objective in, against the ratio that it records.
_PERCENT: Final = Decimal(100)
# The width of the YAML of the groups: the comment lines of the values file wrap at 100 also.
_YAML_WIDTH: Final = 100


class _ValuesDumper(yaml.SafeDumper):
    """The dumper of the values file: a query that holds line breaks keeps its lines."""


def _represent_text(dumper: yaml.SafeDumper, text: str) -> yaml.ScalarNode:
    """Represent a string, in the literal style when it holds the lines of an alert query."""
    style = "|" if "\n" in text else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", text, style=style)


_ValuesDumper.add_representer(str, _represent_text)


@dataclass(frozen=True)
class SloBurnRateRow:
    """One row of Table 2 of `docs/guidelines/sre.md`: the two windows of one burn-rate alert."""

    kind: str
    long_window: str
    short_window: str
    burn_rate: Decimal

    @property
    def alert_suffix(self) -> str:
        """The end of the alert name of the row: its kind and its long window, as `Page1h`."""
        return f"{self.kind}{self.long_window}"

    @property
    def severity(self) -> str:
        """The `severity` label of the row."""
        return _SLO_SEVERITY[self.kind]


# The four rows of Table 2 of `docs/guidelines/sre.md`, in the order of the table.
SLO_BURN_RATE_ROWS: Final[tuple[SloBurnRateRow, ...]] = (
    SloBurnRateRow("Page", "1h", "5m", Decimal("13.44")),
    SloBurnRateRow("Page", "6h", "30m", Decimal("5.6")),
    SloBurnRateRow("Ticket", "1d", "2h", Decimal("2.8")),
    SloBurnRateRow("Ticket", "3d", "6h", Decimal("0.93")),
)
# The seven error-ratio windows of a spec, from the shortest to the longest: the name that the
# group records the ratio under, and the window that the ratio covers.
SLO_RATIO_WINDOWS: Final[tuple[tuple[str, str], ...]] = (
    ("slo:sli_error:ratio_rate5m", "5m"),
    ("slo:sli_error:ratio_rate30m", "30m"),
    ("slo:sli_error:ratio_rate1h", "1h"),
    ("slo:sli_error:ratio_rate2h", "2h"),
    ("slo:sli_error:ratio_rate6h", "6h"),
    ("slo:sli_error:ratio_rate1d", "1d"),
    ("slo:sli_error:ratio_rate3d", "3d"),
)
# The name of each series that a group records: the seven error ratios, the objective, its error
# budget and the window, as Sloth records them.
SLO_RECORD_NAMES: Final[tuple[str, ...]] = (
    *(record for record, _ in SLO_RATIO_WINDOWS),
    "slo:objective:ratio",
    "slo:error_budget:ratio",
    "slo:time_period:days",
)
# The record name of each error ratio, by the window that it covers.
_RATIO_RECORDS: Final[dict[str, str]] = {window: record for record, window in SLO_RATIO_WINDOWS}
# The placeholder of the window in the two event queries of a spec.
_WINDOW_PLACEHOLDER: Final = "{{.window}}"


@dataclass(frozen=True)
class SloSpec:
    """One Sloth `prometheus/v1` spec: the service of the catalog and its one SLO.

    The spec holds the two event queries of its SLI over the `{{.window}}` placeholder, and the
    name of its alerts.
    """

    path: Path
    service: str
    name: str
    objective: Decimal
    description: str
    error_query: str
    total_query: str
    alerting_name: str

    @property
    def grouping(self) -> frozenset[str]:
        """The labels that the total query groups by: the labels that the event guard matches."""
        return grouping_labels(self.total_query)

    @property
    def group_name(self) -> str:
        """The name of the rule group: `slo-` and the stem of the spec file."""
        return f"slo-{self.path.stem}"

    @property
    def error_budget(self) -> Decimal:
        """The budget ratio of the objective: `1 - objective / 100`."""
        return 1 - self.objective / _PERCENT


def _decimal_text(value: Decimal) -> str:
    """A decimal as a PromQL number: no exponent, and no trailing zero of the spec file."""
    return format(value.normalize(), "f")


def _field(document: Any, path: Path, *keys: str) -> Any:
    """The value under `keys` of a spec document, or a refusal that names the file and the key."""
    value = document
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            raise ConfigurationError(f"{path}: the Sloth spec holds no `{'.'.join(keys)}`")
        value = value[key]
    return value


def _alerting_name(slo: Any, path: Path) -> str:
    """The prefix of the alert names: the `alerting.name` of the spec, else its file stem."""
    alerting = slo.get("alerting") if isinstance(slo, dict) else None
    name = alerting.get("name") if isinstance(alerting, dict) else None
    if name:
        return str(name)
    return "".join(part.capitalize() for part in path.stem.split("-"))


def _load_slo_spec(path: Path) -> SloSpec:
    """The one spec of one file of the folder."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    slos = _field(document, path, "slos")
    if not isinstance(slos, list) or len(slos) != 1:
        raise ConfigurationError(f"{path}: the Sloth spec holds one SLO")
    (slo,) = slos
    return SloSpec(
        path=path,
        service=str(_field(document, path, "service")),
        name=str(_field(slo, path, "name")),
        objective=Decimal(str(_field(slo, path, "objective"))),
        description=str(_field(slo, path, "description")),
        error_query=str(_field(slo, path, "sli", "events", "error_query")),
        total_query=str(_field(slo, path, "sli", "events", "total_query")),
        alerting_name=_alerting_name(slo, path),
    )


def load_slo_specs(directory: Path) -> list[SloSpec]:
    """Each Sloth spec of `directory`, in the order of its file names.

    Two specs with one service and one SLO name record one series name twice, so the load refuses
    the pair.
    """
    specs = [_load_slo_spec(path) for path in sorted(directory.glob("*.yaml"))]
    seen: dict[tuple[str, str], Path] = {}
    for spec in specs:
        holder = seen.setdefault((spec.service, spec.name), spec.path)
        if holder != spec.path:
            raise ConfigurationError(
                f"{spec.path}: the service `{spec.service}` already holds the SLO "
                f"`{spec.name}` in {holder}"
            )
    return specs


def _window_query(query: str, window: str) -> str:
    """One event query of a spec, over `window`."""
    return query.replace(_WINDOW_PLACEHOLDER, window)


def _labels(spec: SloSpec) -> dict[str, str]:
    """The labels of each series that the group records: its service and its SLO."""
    return {"service": spec.service, "slo": spec.name}


def _ratio_rule(spec: SloSpec, record: str, window: str) -> dict[str, Any]:
    """The recording rule of one error ratio: the error events over the valid events."""
    error = _window_query(spec.error_query, window)
    total = _window_query(spec.total_query, window)
    return {"record": record, "expr": f"({error}) / ({total})", "labels": _labels(spec)}


def _constant_rule(spec: SloSpec, record: str, value: str) -> dict[str, Any]:
    """The recording rule of a constant of the spec, as `vector(0.99)`."""
    return {"record": record, "expr": f"vector({value})", "labels": _labels(spec)}


def _ratio_selector(spec: SloSpec, window: str) -> str:
    """The recorded error ratio of one window, with the labels that keep the groups apart."""
    return f'{_RATIO_RECORDS[window]}{{service="{spec.service}", slo="{spec.name}"}}'


def _event_guard(spec: SloSpec, window: str) -> str:
    """The guard of the low-sample rule: the long window holds at least `SLO_MIN_EVENTS`.

    The `and` matches on the labels that the total query groups by, so the guard counts the events
    of the same series as the ratios. A spec that groups by no label matches on no label: a plain
    `and` would compare two label sets that differ, and no alert would fire.
    """
    total = _window_query(spec.total_query, window)
    matching = f"on ({', '.join(sorted(spec.grouping))})" if spec.grouping else "on ()"
    return f"and {matching} ({total} >= {SLO_MIN_EVENTS})"


def _alert_rule(spec: SloSpec, row: SloBurnRateRow) -> dict[str, Any]:
    """The alert of one row of Table 2: both of its ratios above the burn rate, and the guard."""
    threshold = f" > ({_decimal_text(row.burn_rate)} * {_decimal_text(spec.error_budget)})"
    ratios = (
        "(\n"
        f"  {_ratio_selector(spec, row.long_window)}{threshold}\n"
        "  and\n"
        f"  {_ratio_selector(spec, row.short_window)}{threshold}\n"
        ")"
    )
    return {
        "alert": f"{spec.alerting_name}{row.alert_suffix}",
        "expr": f"{ratios}\n{_event_guard(spec, row.long_window)}",
        "labels": {"severity": row.severity},
    }


def render_slo_groups(specs: Sequence[SloSpec]) -> list[dict[str, Any]]:
    """One rule group for each spec: its recorded series, then the four alerts of Table 2."""
    return [
        {
            "name": spec.group_name,
            "rules": [
                *(_ratio_rule(spec, record, window) for record, window in SLO_RATIO_WINDOWS),
                _constant_rule(
                    spec, "slo:objective:ratio", _decimal_text(spec.objective / _PERCENT)
                ),
                _constant_rule(spec, "slo:error_budget:ratio", _decimal_text(spec.error_budget)),
                _constant_rule(spec, "slo:time_period:days", str(SLO_WINDOW_DAYS)),
                *(_alert_rule(spec, row) for row in SLO_BURN_RATE_ROWS),
            ],
        }
        for spec in specs
    ]


def _marker_index(lines: Sequence[str], marker: str, path: Path, after: int = -1) -> int:
    """The index of the line of `marker` in `lines`, or a refusal that names the file."""
    for index, line in enumerate(lines):
        if index > after and line.strip() == marker:
            return index
    raise ConfigurationError(f"{path}: the file holds no `{marker}` line")


def _groups_text(groups: Sequence[dict[str, Any]], indent: str) -> list[str]:
    """The lines of the YAML of `groups`, indented by `indent`."""
    dumped = yaml.dump(list(groups), Dumper=_ValuesDumper, sort_keys=False, width=_YAML_WIDTH)
    return [f"{indent}{line}" if line else line for line in dumped.splitlines()]


def write_slo_groups(path: Path, groups: Sequence[dict[str, Any]]) -> None:
    """Replace the text between the two marker comments of `path` with `groups`, and nothing else.

    The markers sit at the indentation of the `groups` list of the values file, so the render keeps
    the file's layout: the groups above the start marker and the keys below the end marker stay as
    they are.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    start = _marker_index(lines, SLO_GROUPS_START_MARKER, path)
    end = _marker_index(lines, SLO_GROUPS_END_MARKER, path, after=start)
    indent = lines[start][: len(lines[start]) - len(lines[start].lstrip())]
    body = _groups_text(groups, indent)
    path.write_text("\n".join([*lines[: start + 1], *body, *lines[end:]]) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> None:
    """Render the specs of a folder: print the groups, or write them into the values file."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("specs", type=Path, help="the folder of the Sloth specs")
    parser.add_argument("rule_file", type=Path, help="the values file that holds the two markers")
    parser.add_argument(
        "--write", action="store_true", help="write the groups into the values file"
    )
    arguments = parser.parse_args(argv)
    groups = render_slo_groups(load_slo_specs(arguments.specs))
    if arguments.write:
        write_slo_groups(arguments.rule_file, groups)
    else:
        write_stdout(yaml.dump(groups, Dumper=_ValuesDumper, sort_keys=False, width=_YAML_WIDTH))


if __name__ == "__main__":
    main()


__all__ = [
    "SLO_BURN_RATE_ROWS",
    "SLO_GROUPS_END_MARKER",
    "SLO_GROUPS_START_MARKER",
    "SLO_MIN_EVENTS",
    "SLO_RATIO_WINDOWS",
    "SLO_RECORD_NAMES",
    "SLO_WINDOW_DAYS",
    "SloBurnRateRow",
    "SloSpec",
    "load_slo_specs",
    "main",
    "render_slo_groups",
    "write_slo_groups",
]
