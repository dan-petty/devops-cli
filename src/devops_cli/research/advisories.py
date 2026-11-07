"""The advisories that affect the pins of a repository, from OSV, GitHub and CISA KEV (#3898, #3987).

The inventory lists the pins. The Python and Node packages go to OSV in batches
(`POST /v1/querybatch`), each with its exact version, so OSV matches the version to the affected
ranges. Each advisory id that a batch names is read once for each package (`GET /v1/vulns/{id}`)
for its severity, ranges and fixed versions.

OSV does not match versions of GitHub Actions, and has no ecosystem for images, charts and release
binaries. GitHub gives their advisories: the reviewed advisories that name an Action
(`GET /advisories`), and the advisories that a repository published, for a component that the
watch list maps to that repository (`GET /repos/{owner}/{repo}/security-advisories`). GitHub does
not match versions, so `version_match` does, from the ranges of the advisory. A pin that names no
one release (`v7`, a commit, a range) is counted in `unpinned`.

A CVE of a finding that the CISA KEV list names sets `exploited`. No model reads any of it.

A component of another kind is counted as not covered, with its ecosystem.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Final

from packaging.version import InvalidVersion, Version

from devops_cli.config.constants import CONST_SEVERITY_ALIASES, CONST_SEVERITY_ORDER
from devops_cli.config.defaults import (
    DEFAULT_GITHUB_ADVISORIES_AFFECTS_MAX,
    DEFAULT_OSV_BATCH_MAX_QUERIES,
)
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.models.vulnerability import PackageLookupResult, VulnerabilityRecord
from devops_cli.research.github_advisories import (
    GhsaAdvisory,
    GhsaLookup,
    GhsaVulnerability,
    GitHubAdvisoryClient,
)
from devops_cli.research.kev import KevClient
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
from devops_cli.research.version_match import in_range, pinned_version
from devops_cli.research.watch import WatchList
from devops_cli.security.vulnerability_lookup import OSVClient

# The OSV ecosystem of each kind of component that is a package of a registry.
_OSV_ECOSYSTEMS: Final[dict[ComponentKind, tuple[Ecosystem, str]]] = {
    ComponentKind.PYTHON_PACKAGE: (Ecosystem.PYPI, "PyPI"),
    ComponentKind.NODE_PACKAGE: (Ecosystem.NPM, "npm"),
}
# A tool of the tools lock is named by its key, which is not always the name of its package: the
# key `openspec` is the package `@fission-ai/openspec`. The Python and Node lists hold the package.
_TOOL_LOCK_ENTRY: Final[str] = "tool-lock-entry"
# The ecosystem of the GitHub Actions in the GitHub Advisory Database.
_GITHUB_ACTIONS: Final[str] = "actions"
_SOURCE_OSV: Final[str] = "OSV"
_SOURCE_GITHUB: Final[str] = "GitHub"
_CVE_PREFIX: Final[str] = "CVE-"

PackageKey = tuple[str, str, str]
# The name and the version of a component that GitHub is asked about.
PinKey = tuple[str, str]
# A repository whose advisories are read, and the package that the pins match (None: any).
WatchKey = tuple[str, str | None]


@dataclass
class _Pin:
    """The components that pin one release, and that release."""

    version: Version
    components: list[Component] = field(default_factory=list)


@dataclass
class _Plan:
    """What a run asks, and what it leaves out."""

    osv: dict[PackageKey, list[Component]] = field(default_factory=dict)
    actions: dict[PinKey, _Pin] = field(default_factory=dict)
    repositories: dict[WatchKey, dict[PinKey, _Pin]] = field(default_factory=dict)
    not_covered: Counter[str] = field(default_factory=Counter)
    unpinned: int = 0

    @property
    def queried(self) -> int:
        return (
            len(self.osv)
            + len(self.actions)
            + sum(len(pins) for pins in self.repositories.values())
        )


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


def _plan(inventory: Inventory, watch: WatchList) -> _Plan:
    """The packages to ask about, with the components that pin each; the components left out,
    counted by reason; and the number of pins that are no exact version."""
    plan = _Plan()
    for component in inventory.components:
        osv = _OSV_ECOSYSTEMS.get(component.kind)
        if osv is not None:
            if _is_exact(component):
                key = (component.name, component.version, osv[1])
                plan.osv.setdefault(key, []).append(component)
            else:
                plan.unpinned += 1
            continue
        if component.kind is ComponentKind.TOOL and any(
            component.ecosystem is known for known, _ in _OSV_ECOSYSTEMS.values()
        ):
            plan.not_covered[_TOOL_LOCK_ENTRY] += 1
            continue
        entry = (
            None
            if component.ecosystem is Ecosystem.GITHUB_ACTIONS
            else watch.entry_of(component.ecosystem, component.name)
        )
        if component.ecosystem is not Ecosystem.GITHUB_ACTIONS and entry is None:
            plan.not_covered[component.ecosystem.value] += 1
        elif (release := pinned_version(component.version)) is None:
            plan.unpinned += 1
        else:
            pin = (component.name, component.version)
            group = (
                plan.actions
                if entry is None
                else plan.repositories.setdefault((entry.repo, entry.package), {})
            )
            group.setdefault(pin, _Pin(release)).components.append(component)
    return plan


def advisory_requests(inventory: Inventory, watch: WatchList | None = None) -> list[PlannedRequest]:
    """The requests of a run, as a dry run lists them. It makes none.

    The advisory ids come from the answer of the batch, so the second request names a placeholder.
    The KEV list is read only when a finding names a CVE.
    """
    plan = _plan(inventory, watch or WatchList())
    requests: list[PlannedRequest] = []
    if plan.osv:
        requests += [
            PlannedRequest(
                "POST",
                OSVClient.BATCH_URL,
                repeat=f"for each {DEFAULT_OSV_BATCH_MAX_QUERIES} packages",
            ),
            PlannedRequest(
                "GET",
                f"{OSVClient.RECORD_URL}/<advisory id>",
                repeat="for each advisory id that the batch names",
            ),
        ]
    if plan.actions:
        requests.append(
            PlannedRequest(
                "GET",
                f"{GitHubAdvisoryClient.ADVISORIES_URL}?ecosystem={_GITHUB_ACTIONS}&affects=<names>",
                repeat=f"for each {DEFAULT_GITHUB_ADVISORIES_AFFECTS_MAX} action names",
            )
        )
    requests += [
        PlannedRequest("GET", f"{GitHubAdvisoryClient.REPOSITORY_URL}/{repo}/security-advisories")
        for repo in sorted({repo for repo, _ in plan.repositories})
    ]
    if plan.osv or plan.actions or plan.repositories:
        requests.append(
            PlannedRequest("GET", KevClient.URL, condition="when a finding names a CVE")
        )
    return requests


def _severity_rank(severity: str) -> int:
    return (
        CONST_SEVERITY_ORDER.index(severity)
        if severity in CONST_SEVERITY_ORDER
        else len(CONST_SEVERITY_ORDER)
    )


def _osv_finding(components: list[Component], record: VulnerabilityRecord) -> AdvisoryFinding:
    return AdvisoryFinding(
        component=components[0],
        locations=[f"{c.file}:{c.line}" for c in components],
        advisory_id=record.id,
        aliases=record.aliases,
        severity=record.severity,
        summary=record.summary,
        affected_range=record.affected_version_range,
        fixed_version=record.fixed_version,
        source=_SOURCE_OSV,
    )


def _failure(components: list[Component], advisory_id: str, reason: str) -> LookupFailure:
    first = components[0]
    return LookupFailure(
        ecosystem=first.ecosystem,
        name=first.name,
        version=first.version,
        advisory_id=advisory_id,
        reason=reason,
    )


def _osv_findings(plan: _Plan, osv: OSVClient) -> tuple[list[AdvisoryFinding], list[LookupFailure]]:
    """The findings of the packages that OSV matches, and the lookups that failed."""
    answers = osv.query_batch(list(plan.osv))
    records: dict[tuple[str, str, str], PackageLookupResult] = {}
    findings: list[AdvisoryFinding] = []
    failures: list[LookupFailure] = []
    for key, components in plan.osv.items():
        answer = answers[key]
        if answer.status != "ok":
            failures.append(_failure(components, "", answer.reason))
            continue
        for named in answer.vulnerabilities:
            record_key = (named.id, components[0].name, key[2])
            if record_key not in records:
                records[record_key] = osv.get_vulnerability(*record_key)
            record = records[record_key]
            if record.status != "ok":
                failures.append(_failure(components, named.id, record.reason))
                continue
            findings.append(_osv_finding(components, record.vulnerabilities[0]))
    return findings, failures


def _github_finding(
    components: list[Component], advisory: GhsaAdvisory, vulnerability: GhsaVulnerability
) -> AdvisoryFinding:
    severity = (advisory.severity or "").upper()
    return AdvisoryFinding(
        component=components[0],
        locations=[f"{c.file}:{c.line}" for c in components],
        advisory_id=advisory.ghsa_id,
        aliases=[advisory.cve_id] if advisory.cve_id else [],
        severity=CONST_SEVERITY_ALIASES.get(severity, "UNKNOWN"),
        summary=advisory.summary or "",
        affected_range=vulnerability.vulnerable_version_range or "",
        fixed_version=vulnerability.fixed_version,
        source=_SOURCE_GITHUB,
    )


def _github_matches(
    pin: _Pin,
    lookup: GhsaLookup,
    package: str | None,
    ecosystem: str | None,
) -> tuple[list[AdvisoryFinding], list[LookupFailure]]:
    """The advisories of `lookup` that affect the pinned version of `components`.

    `package` (and `ecosystem`, when set) selects the vulnerabilities that name the component; with
    no `package` every vulnerability of an advisory counts. An advisory with a range that cannot be
    read is a failure.
    """
    components, version = pin.components, pin.version
    if lookup.status != "ok":
        return [], [_failure(components, "", lookup.reason)]
    findings: list[AdvisoryFinding] = []
    failures: list[LookupFailure] = []
    for advisory in lookup.advisories:
        for vulnerability in advisory.vulnerabilities:
            named = vulnerability.package
            if package is not None and (
                named is None
                or (ecosystem is not None and named.ecosystem != ecosystem)
                or named.name.casefold() != package.casefold()
            ):
                continue
            try:
                affected = in_range(version, vulnerability.vulnerable_version_range or "")
            except ValueError as exc:
                failures.append(_failure(components, advisory.ghsa_id, str(exc)))
                break
            if affected:
                findings.append(_github_finding(components, advisory, vulnerability))
                break
    return findings, failures


def _github_findings(
    plan: _Plan, github: GitHubAdvisoryClient
) -> tuple[list[AdvisoryFinding], list[LookupFailure]]:
    """The findings of the Actions and of the mapped components, and the lookups that failed."""
    findings: list[AdvisoryFinding] = []
    failures: list[LookupFailure] = []
    if plan.actions:
        names = sorted({name for name, _ in plan.actions})
        lookups = github.for_packages(_GITHUB_ACTIONS, names)
        for (name, _), pin in plan.actions.items():
            found, failed = _github_matches(pin, lookups[name], name, _GITHUB_ACTIONS)
            findings += found
            failures += failed
    lookups_by_repository: dict[str, GhsaLookup] = {}
    for (repository, package), pins in sorted(
        plan.repositories.items(), key=lambda item: (item[0][0], item[0][1] or "")
    ):
        if repository not in lookups_by_repository:
            lookups_by_repository[repository] = github.for_repository(repository)
        for pin in pins.values():
            found, failed = _github_matches(pin, lookups_by_repository[repository], package, None)
            findings += found
            failures += failed
    return findings, failures


def _flag_exploited(
    findings: list[AdvisoryFinding], kev: KevClient
) -> tuple[list[AdvisoryFinding], str]:
    """The findings with `exploited` set from the KEV list, and the reason that the list could not
    be read (empty when it was). The list is read only when a finding names a CVE."""

    def cves(finding: AdvisoryFinding) -> set[str]:
        return {i for i in (finding.advisory_id, *finding.aliases) if i.startswith(_CVE_PREFIX)}

    if not any(cves(f) for f in findings):
        return findings, ""
    listed = kev.load()
    if listed.status != "ok":
        return findings, listed.reason
    return [f.model_copy(update={"exploited": bool(cves(f) & listed.cves)}) for f in findings], ""


def find_advisories(
    inventory: Inventory,
    client: OSVClient | None = None,
    *,
    watch: WatchList | None = None,
    github: GitHubAdvisoryClient | None = None,
    kev: KevClient | None = None,
) -> AdvisoryReport:
    """The advisories that affect the pins of `inventory`, most severe first.

    A lookup that fails is in `failures`, and a KEV list that cannot be read is `kev_failure`: the
    component and the flag have no verdict, and are not clean.
    """
    plan = _plan(inventory, watch or WatchList())
    findings, failures = _osv_findings(plan, client or OSVClient()) if plan.osv else ([], [])
    if plan.actions or plan.repositories:
        github_found, github_failed = _github_findings(plan, github or GitHubAdvisoryClient())
        findings += github_found
        failures += github_failed
    findings, kev_failure = _flag_exploited(findings, kev or KevClient())
    findings.sort(key=lambda f: (_severity_rank(f.severity), f.component.name, f.advisory_id))
    return AdvisoryReport(
        findings=findings,
        failures=failures,
        kev_failure=kev_failure,
        summary=AdvisorySummary(
            components=inventory.summary.total,
            queried=plan.queried,
            with_findings=len({(f.component.name, f.component.version) for f in findings}),
            findings=len(findings),
            unpinned=plan.unpinned,
            failed=len(failures),
            exploited=sum(f.exploited for f in findings),
            not_covered=dict(sorted(plan.not_covered.items())),
        ),
    )
