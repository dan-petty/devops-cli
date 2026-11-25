"""The SLO rule groups of the product, and the Sloth specs that they come from (#4709).

`k8s/devops/monitoring/slos/` holds one Sloth `prometheus/v1` spec for each SLO of the product, and
`src/devops_cli/prometheus/slo_rules.py` renders the rule groups of
`k8s/devops/monitoring/prometheus-rules-values.yaml` from them. A spec names its service by the
`name` of an entry of `k8s/catalog.toml`, so the catalog data is the one list of the services, and
a spec that names another id belongs to no service of the environment. The render replaces the text
between the two marker comments of the values file, so the check renders the groups into a copy of
the file and refuses a copy that differs from the committed file: a spec that nobody rendered
fails here, and an edit outside the markers passes. This module reads files and starts no
`kubectl`, as `environment_freeze` does.

The spec is the one place of an objective, and the row of `k8s/README.md` that it replaces names it
instead of holding a second copy: the row of SLO 5 keeps its objective until its own spec, so the
check reads the rows of the four SLOs of this change only. Rule SRE3 of `docs/guidelines/sre.md`
gives each new alert a runbook row in the alert table of the document that owns its rule group, so
the check refuses an alert of the four groups with no row of the Alerting table.
"""

from __future__ import annotations

import difflib
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from devops_cli.prometheus.slo_rules import (
    SloSpec,
    load_slo_specs,
    render_slo_groups,
    write_slo_groups,
)
from tests.support.paths import REPO_ROOT

_NAME: Final[str] = "slo-rules"
SPEC_FOLDER: Final[Path] = REPO_ROOT / "k8s" / "devops" / "monitoring" / "slos"
RULE_FILE: Final[Path] = (
    REPO_ROOT / "k8s" / "devops" / "monitoring" / "prometheus-rules-values.yaml"
)
CATALOG_PATH: Final[Path] = REPO_ROOT / "k8s" / "catalog.toml"
README_PATH: Final[Path] = REPO_ROOT / "k8s" / "README.md"
# The SLO rows of the Service levels table of `k8s/README.md` that this change moves into a spec:
# the number of the row, and the spec file that holds its objective, its error budget and its
# window. SLO 5 has no spec yet, so no entry names it and the check reads none of its row.
SLO_SPEC_ROWS: Final[tuple[tuple[int, str], ...]] = (
    (1, "roadmap-service-rounds.yaml"),
    (2, "runner-jobs-duration.yaml"),
    (3, "llm-gateway-requests.yaml"),
    (4, "llm-gateway-latency.yaml"),
)
# The two headings of `k8s/README.md` that hold the tables of the SLOs and of the alerts.
_SLO_TABLE_HEADING: Final[str] = "Service levels"
_ALERT_TABLE_HEADING: Final[str] = "Alerting"
# The lines of context of each hunk of the difference that a stale render prints.
_DIFF_CONTEXT: Final[int] = 3
# The command that renders the groups again, for the reader of a failed check.
_REGENERATE: Final[str] = (
    "uv run python src/devops_cli/prometheus/slo_rules.py"
    " k8s/devops/monitoring/slos k8s/devops/monitoring/prometheus-rules-values.yaml --write"
)


def catalog_services(path: Path) -> frozenset[str]:
    """The `name` of each service of the catalog data of `path`."""
    document = tomllib.loads(path.read_text(encoding="utf-8"))
    return frozenset(str(entry["name"]) for entry in document["service"])


def _relative(path: Path) -> str:
    """The path from the root of the repository, or the path itself when it sits elsewhere."""
    return str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)


def unknown_services(specs: Sequence[SloSpec], services: frozenset[str]) -> list[str]:
    """One line for each spec whose `service` is no name of `services`."""
    catalog = _relative(CATALOG_PATH)
    return [
        f"{_NAME}: {_relative(spec.path)}: the service `{spec.service}` is no `name` of {catalog}"
        for spec in specs
        if spec.service not in services
    ]


def check_each_spec_names_a_catalog_service() -> None:
    """Each Sloth spec of the product names a service of the catalog data."""
    findings = unknown_services(load_slo_specs(SPEC_FOLDER), catalog_services(CATALOG_PATH))
    assert not findings, "\n".join(findings)


def render_differences(committed: str, rendered: str) -> list[str]:
    """One line for each line of the difference between `committed` and its `rendered` text."""
    return [
        f"{_NAME}: {line}"
        for line in difflib.unified_diff(
            committed.splitlines(),
            rendered.splitlines(),
            fromfile=_relative(RULE_FILE),
            tofile=f"the render of {_relative(SPEC_FOLDER)}",
            lineterm="",
            n=_DIFF_CONTEXT,
        )
    ]


def check_the_slo_groups_are_the_render_of_the_specs(tmp_path: Path) -> None:
    """The `slo-` groups of the product rule file are the render of the Sloth specs.

    `write_slo_groups` replaces the text between the two marker comments of the file, so the check
    renders the four groups into a copy of the committed file: the copy differs from the file only
    when a spec changed and nobody rendered it again, and a failure prints that difference.
    """
    rendered = tmp_path / RULE_FILE.name
    rendered.write_text(RULE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    write_slo_groups(rendered, render_slo_groups(load_slo_specs(SPEC_FOLDER)))
    findings = render_differences(
        RULE_FILE.read_text(encoding="utf-8"), rendered.read_text(encoding="utf-8")
    )
    assert not findings, "\n".join([*findings, f"{_NAME}: render the groups again: {_REGENERATE}"])


def section_lines(text: str, heading: str) -> list[str]:
    """The lines of the `## <heading>` section of `text`, up to the next `## ` heading."""
    lines = text.splitlines()
    title = f"## {heading}"
    if title not in lines:
        return []
    rest = lines[lines.index(title) + 1 :]
    end = next((index for index, line in enumerate(rest) if line.startswith("## ")), len(rest))
    return rest[:end]


def table_rows(lines: Sequence[str]) -> list[tuple[str, ...]]:
    """The cells of each body row of the first GFM table of `lines`, without its header row and
    its delimiter row."""
    rows = [line for line in lines if line.startswith("|")]
    return [tuple(cell.strip() for cell in row.strip().strip("|").split("|")) for row in rows[2:]]


def slo_row_findings(text: str, rows: Sequence[tuple[int, str]]) -> list[str]:
    """One line for each row of `rows` whose spec is no file of the folder, that names no spec of
    the folder, or that still holds a percentage."""
    table = table_rows(section_lines(text, _SLO_TABLE_HEADING))
    findings: list[str] = []
    for number, spec in rows:
        path = SPEC_FOLDER / spec
        if not path.is_file():
            findings.append(f"{_NAME}: {_relative(path)} is no spec file of the folder")
        row = next((cells for cells in table if cells and cells[0] == str(number)), None)
        if row is None:
            findings.append(f"{_NAME}: the Service levels table holds no row of SLO {number}")
            continue
        text_of_row = " | ".join(row)
        if spec not in text_of_row:
            findings.append(
                f"{_NAME}: the row of SLO {number} names no spec; name `slos/{spec}`, which holds "
                "its objective, its error budget and its window"
            )
        if "%" in text_of_row:
            findings.append(
                f"{_NAME}: the row of SLO {number} still holds a percentage; `slos/{spec}` holds "
                "its objective and its error budget"
            )
    return findings


def check_each_slo_row_names_its_spec() -> None:
    """Each SLO row of the Service levels table names the spec that holds its objective."""
    findings = slo_row_findings(README_PATH.read_text(encoding="utf-8"), SLO_SPEC_ROWS)
    assert not findings, "\n".join(findings)


def alert_names(specs: Sequence[SloSpec]) -> list[str]:
    """The name of each alert of the rule groups that `specs` render, in the order of the groups."""
    return [
        str(rule["alert"])
        for group in render_slo_groups(specs)
        for rule in group["rules"]
        if "alert" in rule
    ]


def alert_row_findings(text: str, alerts: Sequence[str]) -> list[str]:
    """One line for each alert of `alerts` that holds no row of the Alerting table.

    The first cell of a row names its alert, or its alerts, in backticks, so a row that names
    another alert in its "Fires when" cell holds no row of its own.
    """
    names = [cells[0] for cells in table_rows(section_lines(text, _ALERT_TABLE_HEADING)) if cells]
    return [
        f"{_NAME}: the Alerting table holds no row of the alert `{alert}`; add its row with the "
        "step to do (docs/guidelines/sre.md, rule SRE3)"
        for alert in alerts
        if not any(f"`{alert}`" in name for name in names)
    ]


def check_each_slo_alert_has_a_runbook_row() -> None:
    """Each alert of the four SLO groups holds a runbook row of the Alerting table."""
    findings = alert_row_findings(
        README_PATH.read_text(encoding="utf-8"),
        alert_names(load_slo_specs(SPEC_FOLDER)),
    )
    assert not findings, "\n".join(findings)
