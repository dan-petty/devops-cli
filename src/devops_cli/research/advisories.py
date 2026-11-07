"""The advisories that affect the pins of a repository, from OSV (#3898).

The inventory lists the pins. The Python and Node packages go to OSV in batches
(`POST /v1/querybatch`), each with its exact version, so OSV matches the version to the affected
ranges. Each advisory id that a batch names is read once for each package (`GET /v1/vulns/{id}`)
for its severity, ranges and fixed versions. No model reads any of it.

A component of another kind is counted as not covered, with its ecosystem: OSV has no ecosystem
for container images, Helm charts, Terraform providers and release binaries, and it does not match
versions of GitHub Actions (a query for a version of `tj-actions/changed-files` that its advisory
names gave no result on 2026-11-07).
"""

from __future__ import annotations

from collections import Counter
from typing import Final

from packaging.version import InvalidVersion, Version

from devops_cli.config.constants import CONST_SEVERITY_ORDER
from devops_cli.config.defaults import DEFAULT_OSV_BATCH_MAX_QUERIES
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.models.vulnerability import PackageLookupResult, VulnerabilityRecord
from devops_cli.research.models import (
    AdvisoryFinding,
    AdvisoryReport,
    AdvisorySummary,
    Component,
    ComponentKind,
    Ecosystem,
    Inventory,
    LookupFailure,
)
from devops_cli.security.vulnerability_lookup import OSVClient

# The OSV ecosystem of each kind of component that is a package of a registry.
_OSV_ECOSYSTEMS: Final[dict[ComponentKind, tuple[Ecosystem, str]]] = {
    ComponentKind.PYTHON_PACKAGE: (Ecosystem.PYPI, "PyPI"),
    ComponentKind.NODE_PACKAGE: (Ecosystem.NPM, "npm"),
}
# A tool of the tools lock is named by its key, which is not always the name of its package: the
# key `openspec` is the package `@fission-ai/openspec`. The Python and Node lists hold the package.
_TOOL_LOCK_ENTRY: Final[str] = "tool-lock-entry"

PackageKey = tuple[str, str, str]


def _is_exact(component: Component) -> bool:
    """Whether the component pins one version. OSV answers a query with no version with every
    advisory of the package, so a range or an empty version is never sent. The lock of a Node
    package always names one version."""
    if component.ecosystem is Ecosystem.PYPI:
        try:
            Version(component.version)
        except InvalidVersion:
            return False
    return bool(component.version)


def _plan(inventory: Inventory) -> tuple[dict[PackageKey, list[Component]], Counter[str], int]:
    """The packages to ask about, with the components that pin each; the components left out,
    counted by reason; and the number of pins that are no exact version."""
    packages: dict[PackageKey, list[Component]] = {}
    not_covered: Counter[str] = Counter()
    unpinned = 0
    for component in inventory.components:
        osv = _OSV_ECOSYSTEMS.get(component.kind)
        if osv is None:
            is_package_tool = component.kind is ComponentKind.TOOL and any(
                component.ecosystem is known for known, _ in _OSV_ECOSYSTEMS.values()
            )
            not_covered[_TOOL_LOCK_ENTRY if is_package_tool else component.ecosystem.value] += 1
        elif not _is_exact(component):
            unpinned += 1
        else:
            key = (component.name, component.version, osv[1])
            packages.setdefault(key, []).append(component)
    return packages, not_covered, unpinned


def advisory_requests(inventory: Inventory) -> list[PlannedRequest]:
    """The requests of a run, as a dry run lists them. It makes none.

    The advisory ids come from the answer of the batch, so the second request names a placeholder.
    """
    packages, _, _ = _plan(inventory)
    if not packages:
        return []
    return [
        PlannedRequest(
            "POST", OSVClient.BATCH_URL, repeat=f"for each {DEFAULT_OSV_BATCH_MAX_QUERIES} packages"
        ),
        PlannedRequest(
            "GET",
            f"{OSVClient.RECORD_URL}/<advisory id>",
            repeat="for each advisory id that the batch names",
        ),
    ]


def _severity_rank(severity: str) -> int:
    return (
        CONST_SEVERITY_ORDER.index(severity)
        if severity in CONST_SEVERITY_ORDER
        else len(CONST_SEVERITY_ORDER)
    )


def _finding(components: list[Component], record: VulnerabilityRecord) -> AdvisoryFinding:
    return AdvisoryFinding(
        component=components[0],
        locations=[f"{c.file}:{c.line}" for c in components],
        advisory_id=record.id,
        aliases=record.aliases,
        severity=record.severity,
        summary=record.summary,
        affected_range=record.affected_version_range,
        fixed_version=record.fixed_version,
    )


def find_advisories(inventory: Inventory, client: OSVClient | None = None) -> AdvisoryReport:
    """The advisories that affect the pins of `inventory`, most severe first.

    A lookup that fails is in `failures`: its component is no clean one.
    """
    osv = client or OSVClient()
    packages, not_covered, unpinned = _plan(inventory)
    answers = osv.query_batch(list(packages))
    records: dict[tuple[str, str, str], PackageLookupResult] = {}
    findings: list[AdvisoryFinding] = []
    failures: list[LookupFailure] = []
    for key, components in packages.items():
        answer = answers[key]
        first = components[0]
        if answer.status != "ok":
            failures.append(
                LookupFailure(
                    ecosystem=first.ecosystem,
                    name=first.name,
                    version=first.version,
                    advisory_id="",
                    reason=answer.reason,
                )
            )
            continue
        for named in answer.vulnerabilities:
            record_key = (named.id, first.name, key[2])
            if record_key not in records:
                records[record_key] = osv.get_vulnerability(*record_key)
            record = records[record_key]
            if record.status != "ok":
                failures.append(
                    LookupFailure(
                        ecosystem=first.ecosystem,
                        name=first.name,
                        version=first.version,
                        advisory_id=named.id,
                        reason=record.reason,
                    )
                )
                continue
            findings.append(_finding(components, record.vulnerabilities[0]))
    findings.sort(key=lambda f: (_severity_rank(f.severity), f.component.name, f.advisory_id))
    return AdvisoryReport(
        findings=findings,
        failures=failures,
        summary=AdvisorySummary(
            components=inventory.summary.total,
            queried=len(packages),
            with_findings=len({(f.component.name, f.component.version) for f in findings}),
            findings=len(findings),
            unpinned=unpinned,
            failed=len(failures),
            not_covered=dict(sorted(not_covered.items())),
        ),
    )
