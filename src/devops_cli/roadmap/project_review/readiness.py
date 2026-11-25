"""Production readiness row map and automated readiness readers (#5537)."""

from __future__ import annotations

import base64
import binascii
import json
import shlex
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Final
from urllib.parse import quote, urlencode

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.config.commands import BIN_DEVOPS, BIN_SCORECARD
from devops_cli.config.settings import Settings
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.git import GitHubNotFoundError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.project_review.catalog import ReaderKind
from devops_cli.roadmap.project_review.data import Fact, FactStatus, RepoReadiness
from devops_cli.roadmap.project_review.readers import PagedSession, Reads, read_github

_SCORECARD_TIMEOUT_SECONDS: Final = 120.0
_DEVOPS_CMD_TIMEOUT_SECONDS: Final = 120.0
_SECTION_READINESS: Final = "readiness"
_UNIT_READINESS: Final = "readiness"
_SCORECARD_MET_SCORE: Final = 10
_AGENTS_GUIDE_MARKERS: Final = ("Where to look", "guidelines/")
_FALLBACK_WORKFLOW_KEYWORDS: Final = ("codeql", "sast")
_FALLBACK_RENOVATE_PATHS: Final = (".github/renovate.json", "renovate.json")


class ReadinessState(StrEnum):
    """State reported for one row of the production readiness guideline."""

    MET = "met"
    PARTLY_MET = "partly met"
    NOT_MET = "not met"
    DOES_NOT_APPLY = "does not apply"
    NOT_READABLE = "not readable"


class ReadinessScope(StrEnum):
    """Target scope of a readiness guideline row."""

    REPO = "Repo"
    SERVICE = "Service"
    BOTH = "Both"


class CheckKind(StrEnum):
    """Mechanism that measures a production readiness row."""

    SCORECARD = "scorecard"
    FILE = "file"
    COMMAND = "command"
    PROMQL = "promql"
    CATALOG = "catalog"
    SETTINGS = "settings"
    MANUAL = "manual"


@dataclass(frozen=True)
class ReadinessRowSpec:
    """One row of `docs/guidelines/production-readiness.md` without state or issue IDs."""

    id: str
    scope: ReadinessScope
    level: str
    kind: CheckKind
    definition: str
    scorecard_checks: tuple[str, ...] = ()
    kube_linter_checks: tuple[str, ...] = ()
    commands: tuple[str, ...] = ()
    files: tuple[str, ...] = ()
    is_manual: bool = False
    runnable: bool = True


def _row(
    row_id: str,
    scope: ReadinessScope,
    level: str,
    kind: CheckKind,
    definition: str,
    *,
    scorecard: tuple[str, ...] = (),
    kube_linter: tuple[str, ...] = (),
    commands: tuple[str, ...] = (),
    files: tuple[str, ...] = (),
    manual: bool = False,
    runnable: bool = False,
) -> ReadinessRowSpec:
    """Compact constructor keeping the 91-row map concise and uniform."""
    return ReadinessRowSpec(
        id=row_id,
        scope=scope,
        level=level,
        kind=kind,
        definition=definition,
        scorecard_checks=scorecard,
        kube_linter_checks=kube_linter,
        commands=commands,
        files=files,
        is_manual=manual,
        runnable=runnable,
    )


_R = ReadinessScope.REPO
_S = ReadinessScope.SERVICE
_B = ReadinessScope.BOTH
_REQ = "Required"
_REC = "Recommended"
_LAT = "Later"

READINESS_ROWS: Final[tuple[ReadinessRowSpec, ...]] = (
    # Ownership and documents
    _row(
        "OWN-1",
        _S,
        _REQ,
        CheckKind.CATALOG,
        "Service catalog entry, tier, data class, dependencies.",
    ),
    _row(
        "OWN-2",
        _R,
        _REQ,
        CheckKind.SCORECARD,
        "License, security policy, and baseline repository files.",
        scorecard=("License", "Security-Policy"),
        files=("README.md", "CONTRIBUTING.md", "AGENTS.md", "CODEOWNERS"),
    ),
    _row(
        "OWN-3",
        _R,
        _REQ,
        CheckKind.FILE,
        "OpenSpec configuration on branch.",
        files=("openspec/config.yaml",),
    ),
    _row("OWN-4", _B, _REC, CheckKind.MANUAL, "Architecture Decision Records.", manual=True),
    _row("OWN-5", _B, _REQ, CheckKind.COMMAND, "Docs validation.", commands=("devops docs check",)),
    _row(
        "OWN-6",
        _R,
        "Required for a repository in `service.repos`",
        CheckKind.COMMAND,
        "Repository onboarding plan prerequisites.",
        commands=("devops repos onboard <owner>/<name> --plan",),
        runnable=True,
    ),
    _row(
        "OWN-7",
        _R,
        _REC,
        CheckKind.FILE,
        "AGENTS Where to look table routes to guidelines.",
        files=("AGENTS.md",),
    ),
    # SLOs, monitoring and alerting
    _row("SLO-1", _S, _REQ, CheckKind.CATALOG, "Sloth spec per user journey."),
    _row(
        "SLO-2",
        _S,
        _REQ,
        CheckKind.CATALOG,
        "Generated SLO rules and promtool tests.",
        commands=("promtool test rules",),
    ),
    _row("SLO-3", _S, _REQ, CheckKind.MANUAL, "Error budget policy applied by jobs.", manual=True),
    _row("SLO-4", _S, _REQ, CheckKind.CATALOG, "SRE dashboard table entry."),
    _row("SLO-5", _S, _REQ, CheckKind.PROMQL, "Metrics, logs, and W3C trace collection."),
    _row("SLO-6", _S, _REQ, CheckKind.PROMQL, "Cause alerts and promtool test files."),
    _row(
        "SLO-7",
        _S,
        _REQ,
        CheckKind.COMMAND,
        "Alert runbook rows.",
        commands=("devops prometheus rules",),
    ),
    _row(
        "SLO-8",
        _S,
        _REQ,
        CheckKind.PROMQL,
        "Alert routing and delivery.",
        commands=("amtool config routes test",),
    ),
    _row("SLO-9", _B, _REC, CheckKind.PROMQL, "External heartbeat monitor."),
    _row("SLO-10", _S, _REC, CheckKind.PROMQL, "Deploy and alert dashboard annotations."),
    _row("SLO-11", _S, _LAT, CheckKind.PROMQL, "Black-box probe and alert."),
    # Incidents and on-call
    _row(
        "INC-1", _S, _REQ, CheckKind.MANUAL, "Severity response targets and triggers.", manual=True
    ),
    _row("INC-2", _S, _REQ, CheckKind.MANUAL, "Incident issues with UTC timeline."),
    _row("INC-3", _S, _REQ, CheckKind.MANUAL, "Blameless postmortem records."),
    _row("INC-4", _S, _REQ, CheckKind.MANUAL, "Service stop steps.", manual=True),
    _row("INC-5", _S, _LAT, CheckKind.MANUAL, "Incident drill record."),
    # Release and change management
    _row(
        "REL-1",
        _R,
        _REQ,
        CheckKind.SCORECARD,
        "Default branch ruleset and protection.",
        scorecard=("Branch-Protection",),
        commands=("devops gh api repos/<owner>/<repo>/rules/branches/main",),
    ),
    _row("REL-2", _R, _REQ, CheckKind.MANUAL, "Person merge attribution."),
    _row(
        "REL-3",
        _R,
        "Later, when a second maintainer joins",
        CheckKind.SCORECARD,
        "Independent pull request code review.",
        scorecard=("Code-Review",),
    ),
    _row(
        "REL-4",
        _R,
        _REQ,
        CheckKind.SCORECARD,
        "CI tests, SAST, and fail-to-pass gate.",
        scorecard=("CI-Tests", "SAST"),
        commands=("devops ci fail-to-pass --base <ref>",),
    ),
    _row(
        "REL-5",
        _R,
        _REQ,
        CheckKind.FILE,
        "Release-please changelog on branch.",
        files=("CHANGELOG.md",),
    ),
    _row(
        "REL-6",
        _S,
        _REQ,
        CheckKind.COMMAND,
        "Argo CD sync and self-heal.",
        commands=("devops argo cd apps status <app>",),
    ),
    _row(
        "REL-7",
        _S,
        _REQ,
        CheckKind.CATALOG,
        "Rollout strategy, readiness probe, drain limit.",
        kube_linter=("no-rolling-update-strategy", "no-readiness-probe"),
    ),
    _row(
        "REL-8", _S, _REQ, CheckKind.MANUAL, "Setting changes live before tightening.", manual=True
    ),
    _row(
        "REL-9",
        _S,
        _REQ,
        CheckKind.COMMAND,
        "Secrets synced before rollout.",
        commands=(
            "devops k8s push-secrets --only <namespace>/<name> --plan",
            "kubectl get externalsecret -A",
        ),
    ),
    _row(
        "REL-10",
        _S,
        "Required for a new service or a new rollout path",
        CheckKind.MANUAL,
        "Post-rollout go-live check.",
    ),
    _row("REL-11", _S, _REQ, CheckKind.MANUAL, "Tested rollback steps.", manual=True),
    _row("REL-12", _B, _REC, CheckKind.MANUAL, "Out-of-git change issue record."),
    _row(
        "REL-13",
        _R,
        _REC,
        CheckKind.COMMAND,
        "DORA metrics in project review.",
        commands=("devops roadmap review run",),
    ),
    _row(
        "REL-14",
        _S,
        "Later, when the service runs 2 replicas",
        CheckKind.CATALOG,
        "Progressive rollout analysis.",
    ),
    # Security and supply chain
    _row(
        "SEC-1",
        _R,
        _REQ,
        CheckKind.SCORECARD,
        "Security policy and private vulnerability reporting.",
        scorecard=("Security-Policy",),
        commands=("devops gh api repos/<owner>/<repo>/private-vulnerability-reporting",),
    ),
    _row(
        "SEC-2",
        _R,
        _REQ,
        CheckKind.COMMAND,
        "Secret scanning and push protection.",
        commands=("devops gh api repos/<owner>/<repo>",),
    ),
    _row(
        "SEC-3",
        _R,
        _REQ,
        CheckKind.SCORECARD,
        "SAST and CodeQL code scanning.",
        scorecard=("SAST",),
    ),
    _row(
        "SEC-4",
        _R,
        _REQ,
        CheckKind.SCORECARD,
        "Pinned dependencies and vulnerability audit.",
        scorecard=("Pinned-Dependencies", "Vulnerabilities"),
        commands=("devops ci audit", "devops k8s image-pins"),
    ),
    _row(
        "SEC-5",
        _R,
        _REQ,
        CheckKind.SCORECARD,
        "Minimal workflow permissions and static checks.",
        scorecard=("Token-Permissions", "Dangerous-Workflow"),
        commands=("devops scan workflows",),
    ),
    _row(
        "SEC-6",
        _R,
        _REQ,
        CheckKind.SCORECARD,
        "Automated dependency updates via Renovate.",
        scorecard=("Dependency-Update-Tool",),
    ),
    _row(
        "SEC-7",
        _R,
        _REQ,
        CheckKind.COMMAND,
        "Scanner findings resolved or expiring ignore.",
        commands=("devops gh api repos/<owner>/<repo>/code-scanning/alerts",),
    ),
    _row("SEC-8", _R, _REQ, CheckKind.MANUAL, "Trivy image build gate."),
    _row("SEC-9", _S, _REC, CheckKind.MANUAL, "Third-party image Trivy reports."),
    _row(
        "SEC-10",
        _R,
        _REQ,
        CheckKind.SCORECARD,
        "Signed image provenance and SBOM.",
        scorecard=("Signed-Releases", "SBOM"),
        commands=("devops gh api repos/<owner>/<repo>/attestations/sha256:<digest>",),
    ),
    _row("SEC-11", _S, _REC, CheckKind.CATALOG, "Sandbox execution runtimeClassName."),
    _row("SEC-12", _R, _REQ, CheckKind.MANUAL, "HTTP egress gate and zero telemetry."),
    _row(
        "SEC-13",
        _S,
        "Required for a new service",
        CheckKind.COMMAND,
        "Threat model and security review.",
        commands=("devops review",),
    ),
    _row(
        "SEC-14",
        _R,
        "Later, before a move into an organization",
        CheckKind.MANUAL,
        "Signed wheel and sdist provenance.",
    ),
    _row(
        "SEC-15",
        _R,
        "Later, before a move into an organization",
        CheckKind.MANUAL,
        "Permissive license scan.",
    ),
    _row(
        "SEC-16",
        _R,
        "Later, before a move into an organization",
        CheckKind.SCORECARD,
        "Scheduled Scorecard and Best Practices badge.",
        scorecard=("Token-Permissions", "CII-Best-Practices"),
    ),
    _row("SEC-17", _S, _LAT, CheckKind.CATALOG, "Cluster image provenance admission policy."),
    _row("SEC-18", _S, _LAT, CheckKind.MANUAL, "CIS Kubernetes benchmark."),
    # Access and secrets
    _row(
        "ACC-1",
        _S,
        _REQ,
        CheckKind.COMMAND,
        "Platform secrets and ExternalSecrets.",
        commands=("devops k8s push-secrets --plan", "kubectl get externalsecret -A"),
    ),
    _row(
        "ACC-2",
        _B,
        _REQ,
        CheckKind.MANUAL,
        "Owner-only secret, settings, ruleset, and App gates.",
        manual=True,
    ),
    _row(
        "ACC-3",
        _R,
        "Later, when the onboard command ships, and before a move into an organization",
        CheckKind.SETTINGS,
        "Baseline settings via onboard and OpenTofu.",
        commands=("devops tf plan",),
    ),
    _row(
        "ACC-4",
        _S,
        _REQ,
        CheckKind.MANUAL,
        "Credential rotation and leak runbook.",
        commands=("devops k8s push-secrets --rotate",),
        manual=True,
    ),
    _row(
        "ACC-5",
        _S,
        _REQ,
        CheckKind.COMMAND,
        "Dedicated ServiceAccount and minimal RBAC.",
        kube_linter=("default-service-account",),
        commands=("devops k8s rbac-audit",),
    ),
    _row(
        "ACC-6",
        _S,
        "Required for a service that makes pods",
        CheckKind.CATALOG,
        "ValidatingAdmissionPolicy for spawned pods.",
    ),
    _row(
        "ACC-7",
        _S,
        _REQ,
        CheckKind.COMMAND,
        "Pod Security restricted enforcement.",
        kube_linter=("run-as-non-root", "privilege-escalation-container"),
        commands=("devops k8s lint",),
    ),
    _row(
        "ACC-8",
        _S,
        _REQ,
        CheckKind.CATALOG,
        "Minimal namespace NetworkPolicies.",
        kube_linter=("non-isolated-pod",),
        commands=("kubectl -n <namespace> get networkpolicy",),
    ),
    _row(
        "ACC-9",
        _S,
        "Required for a service with an endpoint",
        CheckKind.CATALOG,
        "Tunnel, Cloudflare Access, and token refusal test.",
    ),
    _row(
        "ACC-10",
        _S,
        "Required for a new datasource",
        CheckKind.MANUAL,
        "Read-only anonymous Grafana datasource token.",
        manual=True,
    ),
    _row("ACC-11", _S, _REQ, CheckKind.SETTINGS, "Scoped GitHub App permissions."),
    _row(
        "ACC-12",
        _S,
        _LAT,
        CheckKind.CATALOG,
        "File-mounted secrets when supported.",
        kube_linter=("read-secret-from-env-var",),
    ),
    _row("ACC-13", _S, _LAT, CheckKind.PROMQL, "Long-lived credential age metric."),
    _row(
        "ACC-14",
        _S,
        _LAT,
        CheckKind.SETTINGS,
        "Kubernetes API audit policy.",
        commands=("devops infra",),
    ),
    # Data, backups and recovery
    _row("DATA-1", _S, _REQ, CheckKind.CATALOG, "Catalog data class and personal data stores."),
    _row(
        "DATA-2", _S, _REQ, CheckKind.CATALOG, "Off-node and off-cluster backups for owned state."
    ),
    _row("DATA-3", _S, _REQ, CheckKind.PROMQL, "Monthly restore test metric."),
    _row(
        "DATA-4",
        _S,
        _REQ,
        CheckKind.CATALOG,
        "Stale backup and restore alerts.",
        commands=("promtool test rules",),
    ),
    _row("DATA-5", _S, _REQ, CheckKind.CATALOG, "Documented store RTO."),
    _row("DATA-6", _S, _REQ, CheckKind.CATALOG, "GitOps prune and delete protection on stores."),
    _row(
        "DATA-7", _B, _REQ, CheckKind.MANUAL, "Log, span, error masking and committed address gate."
    ),
    _row(
        "DATA-8",
        _B,
        "Later, when the backups of DATA-2 exist",
        CheckKind.MANUAL,
        "Full cluster rebuild drill record.",
    ),
    # Capacity, performance and cost
    _row(
        "CAP-1",
        _S,
        _REQ,
        CheckKind.CATALOG,
        "CPU/memory requests, memory limit, and limit alert.",
        kube_linter=("unset-cpu-requirements", "unset-memory-requirements"),
    ),
    _row(
        "CAP-2",
        _S,
        _REQ,
        CheckKind.CATALOG,
        "Readiness and liveness probes.",
        kube_linter=("no-readiness-probe", "no-liveness-probe"),
    ),
    _row("CAP-3", _S, _REQ, CheckKind.CATALOG, "Single worker node loss capacity."),
    _row(
        "CAP-4",
        _S,
        _REC,
        CheckKind.COMMAND,
        "Load test or peak SLI check.",
        commands=("devops test load",),
    ),
    _row(
        "CAP-5",
        _S,
        "Later, when the service runs 2 replicas",
        CheckKind.CATALOG,
        "Replicas and PodDisruptionBudget.",
    ),
    _row("CAP-6", _S, _REQ, CheckKind.PROMQL, "Paid API budget, alert, and spend dashboard."),
    # Dependencies and failure modes
    _row("DEP-1", _S, _REQ, CheckKind.CATALOG, "Catalog dependency list and fault tests."),
    _row(
        "DEP-2",
        _B,
        _REQ,
        CheckKind.MANUAL,
        "Nested call time limits and bounded retries.",
        manual=True,
    ),
    _row("DEP-3", _B, _REQ, CheckKind.MANUAL, "Explicit backing service URL settings."),
    _row(
        "DEP-4",
        _R,
        _REQ,
        CheckKind.SCORECARD,
        "Dependency reputation, maintenance, and permissive license.",
        scorecard=("Maintained",),
    ),
    _row(
        "DEP-5", _S, _LAT, CheckKind.COMMAND, "Chaos test results.", commands=("devops k8s chaos",)
    ),
    # Readiness record
    _row(
        "EVD-1",
        _B,
        "Required for a launch",
        CheckKind.MANUAL,
        "Launch pull request readiness report record.",
    ),
    _row("EVD-2", _B, _REQ, CheckKind.MANUAL, "Owner launch approval and exception comments."),
    _row(
        "EVD-3",
        _S,
        _REC,
        CheckKind.COMMAND,
        "Periodic project review readiness run.",
        commands=("devops roadmap review run",),
    ),
)

READINESS_BY_ID: Final[dict[str, ReadinessRowSpec]] = {row.id: row for row in READINESS_ROWS}


@dataclass(frozen=True)
class ScorecardCheckResult:
    """One check outcome parsed from OpenSSF Scorecard JSON."""

    name: str
    score: int
    state: ReadinessState
    reason: str = ""


class RepoVisibility(BaseModel):
    """Subset of GitHub `/repos/<owner>/<name>` fields used for privacy and fallback."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    private: bool = False
    default_branch: str = "main"
    license_spdx: str | None = None


def score_to_state(score: int) -> ReadinessState:
    """Map an OpenSSF Scorecard numeric score (`-1..10`) to a readiness state."""
    if score < 0:
        return ReadinessState.NOT_READABLE
    if score >= _SCORECARD_MET_SCORE:
        return ReadinessState.MET
    if score > 0:
        return ReadinessState.PARTLY_MET
    return ReadinessState.NOT_MET


def parse_scorecard_json(raw: str | Mapping[str, Any]) -> dict[str, ScorecardCheckResult]:
    """Parse Scorecard JSON output (string or decoded mapping) by check name."""
    payload = json.loads(raw) if isinstance(raw, str) else dict(raw)
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return {}
    results: dict[str, ScorecardCheckResult] = {}
    for item in checks:
        if not isinstance(item, Mapping):
            continue
        name = item.get("name")
        score = item.get("score")
        if not isinstance(name, str) or isinstance(score, bool) or not isinstance(score, int):
            continue
        results[name] = ScorecardCheckResult(
            name=name,
            score=score,
            state=score_to_state(score),
            reason=str(item.get("reason") or ""),
        )
    return results


def build_scorecard_cmd(repo: str) -> list[str]:
    """Command arguments to run OpenSSF Scorecard with JSON output on `repo`."""
    return [BIN_SCORECARD, f"--repo=github.com/{repo}", "--format", "json"]


def read_scorecard(repo: str, *, cwd: Path | None = None) -> dict[str, ScorecardCheckResult] | None:
    """Run the pinned Scorecard binary on `repo`; return `None` when it cannot read it."""
    cmd = build_scorecard_cmd(repo)
    try:
        proc = run_subprocess(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            quiet=True,
            timeout=_SCORECARD_TIMEOUT_SECONDS,
        )
    except OSError, DevOpsCLIError:
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        parsed = parse_scorecard_json(proc.stdout)
    except json.JSONDecodeError, ValueError:
        return None
    return parsed or None


def readiness_targets(settings: Settings) -> list[str]:
    """Ordered unique repository names from `service.repos` and `infra.repos`."""
    seen: list[str] = []
    for repo in [*settings.service.repos, *(entry.repo for entry in settings.infra.repos)]:
        if repo not in seen:
            seen.append(repo)
    return seen


def _contents_path(repo: str, file_path: str, ref: str | None) -> str:
    quoted = quote(file_path, safe="/")
    suffix = f"?{urlencode({'ref': ref})}" if ref else ""
    return f"repos/{repo}/contents/{quoted}{suffix}"


def _read_single(
    session: PagedSession,
    path: str,
    now: datetime,
    reads: Reads,
) -> Any | None:
    """Read one GitHub REST object endpoint via `read_github`, returning `None` on 404."""
    try:
        pages = read_github(session, path, now, reads, paginate=False)
    except GitHubNotFoundError:
        return None
    return pages[0] if pages else None


def _read_collection(
    session: PagedSession,
    path: str,
    now: datetime,
    reads: Reads,
) -> list[Any]:
    """Read a GitHub REST array endpoint via `read_github`, returning `[]` on 404."""
    try:
        return read_github(session, path, now, reads, paginate=False)
    except GitHubNotFoundError:
        return []


def _decode_content(payload: Any) -> str | None:
    """Decode base64 file content returned by the GitHub contents endpoint."""
    if not isinstance(payload, Mapping) or payload.get("type") != "file":
        return None
    if payload.get("encoding") != "base64":
        return None
    raw = payload.get("content")
    if not isinstance(raw, str):
        return None
    try:
        return base64.b64decode(raw).decode("utf-8")
    except binascii.Error, UnicodeDecodeError:
        return None


def _read_repo_visibility(
    session: PagedSession,
    repo: str,
    now: datetime,
    reads: Reads,
) -> RepoVisibility:
    """Read visibility and license metadata for `repo` via `read_github`."""
    try:
        payload = _read_single(session, f"repos/{repo}", now, reads)
    except DevOpsCLIError:
        return RepoVisibility()
    if not isinstance(payload, Mapping):
        return RepoVisibility()
    license_obj = payload.get("license")
    spdx = (
        str(license_obj.get("spdx_id"))
        if isinstance(license_obj, Mapping) and license_obj.get("spdx_id")
        else None
    )
    return RepoVisibility(
        private=bool(payload.get("private", False)),
        default_branch=str(payload.get("default_branch") or "main"),
        license_spdx=spdx,
    )


def _fetch_file(
    session: PagedSession,
    repo: str,
    path: str,
    ref: str | None,
    now: datetime,
    reads: Reads,
    cache: dict[str, str | None],
) -> str | None:
    """Fetch and cache text content for `path` at `ref` via `read_github`."""
    if path not in cache:
        try:
            payload = _read_single(session, _contents_path(repo, path, ref), now, reads)
        except DevOpsCLIError:
            cache[path] = None
            return None
        cache[path] = _decode_content(payload)
    return cache[path]


def _combine_states(states: Sequence[ReadinessState]) -> ReadinessState:
    """Fold multiple check outcomes into one row state."""
    if not states or all(state is ReadinessState.NOT_READABLE for state in states):
        return ReadinessState.NOT_READABLE
    readable = [state for state in states if state is not ReadinessState.NOT_READABLE]
    if all(state is ReadinessState.MET for state in readable) and len(readable) == len(states):
        return ReadinessState.MET
    if all(state is ReadinessState.NOT_MET for state in readable) and len(readable) == len(states):
        return ReadinessState.NOT_MET
    return ReadinessState.PARTLY_MET


def _fallback_scorecard_from_github(
    session: PagedSession,
    repo: str,
    visibility: RepoVisibility,
    ref: str | None,
    now: datetime,
    reads: Reads,
    file_cache: dict[str, str | None],
) -> dict[str, ScorecardCheckResult]:
    """Read private-repository practice equivalents through the GitHub API (#5537)."""
    results: dict[str, ScorecardCheckResult] = {}
    has_license = bool(visibility.license_spdx and visibility.license_spdx != "NOASSERTION")
    results["License"] = ScorecardCheckResult(
        "License",
        _SCORECARD_MET_SCORE if has_license else 0,
        ReadinessState.MET if has_license else ReadinessState.NOT_MET,
    )
    sec_text = _fetch_file(session, repo, "SECURITY.md", ref, now, reads, file_cache)
    results["Security-Policy"] = ScorecardCheckResult(
        "Security-Policy",
        _SCORECARD_MET_SCORE if sec_text is not None else 0,
        ReadinessState.MET if sec_text is not None else ReadinessState.NOT_MET,
    )
    has_renovate = any(
        _fetch_file(session, repo, candidate, ref, now, reads, file_cache) is not None
        for candidate in _FALLBACK_RENOVATE_PATHS
    )
    results["Dependency-Update-Tool"] = ScorecardCheckResult(
        "Dependency-Update-Tool",
        _SCORECARD_MET_SCORE if has_renovate else 0,
        ReadinessState.MET if has_renovate else ReadinessState.NOT_MET,
    )
    workflows = _read_collection(
        session, _contents_path(repo, ".github/workflows", ref), now, reads
    )
    wf_names = [
        str(entry.get("name", "")).lower() for entry in workflows if isinstance(entry, Mapping)
    ]
    has_sast = any(any(kw in name for kw in _FALLBACK_WORKFLOW_KEYWORDS) for name in wf_names)
    results["SAST"] = ScorecardCheckResult(
        "SAST",
        _SCORECARD_MET_SCORE if has_sast else 0,
        ReadinessState.MET if has_sast else ReadinessState.NOT_MET,
    )
    results["CI-Tests"] = ScorecardCheckResult(
        "CI-Tests",
        _SCORECARD_MET_SCORE if wf_names else 0,
        ReadinessState.MET if wf_names else ReadinessState.NOT_MET,
    )
    branch_rules = _read_collection(
        session,
        f"repos/{repo}/rules/branches/{quote(visibility.default_branch, safe='')}",
        now,
        reads,
    )
    has_rules = len(branch_rules) > 0
    results["Branch-Protection"] = ScorecardCheckResult(
        "Branch-Protection",
        _SCORECARD_MET_SCORE if has_rules else 0,
        ReadinessState.MET if has_rules else ReadinessState.NOT_MET,
    )
    requires_review = any(
        isinstance(rule, Mapping)
        and isinstance(rule.get("parameters"), Mapping)
        and int(rule["parameters"].get("required_approving_review_count", 0)) >= 1
        for rule in branch_rules
    )
    results["Code-Review"] = ScorecardCheckResult(
        "Code-Review",
        _SCORECARD_MET_SCORE if requires_review else 0,
        ReadinessState.MET if requires_review else ReadinessState.NOT_MET,
    )
    releases = _read_collection(session, f"repos/{repo}/releases", now, reads)
    has_releases = len(releases) > 0
    results["Signed-Releases"] = ScorecardCheckResult(
        "Signed-Releases",
        _SCORECARD_MET_SCORE if has_releases else 0,
        ReadinessState.MET if has_releases else ReadinessState.NOT_MET,
    )
    return results


def _evaluate_files(
    row: ReadinessRowSpec,
    session: PagedSession,
    repo: str,
    ref: str | None,
    now: datetime,
    reads: Reads,
    file_cache: dict[str, str | None],
) -> tuple[ReadinessState, str]:
    """Evaluate file checks for `row` using GitHub contents queries."""
    states: list[ReadinessState] = []
    for path in row.files:
        text = _fetch_file(session, repo, path, ref, now, reads, file_cache)
        if text is None:
            states.append(ReadinessState.NOT_MET)
        elif row.id == "OWN-7" and path == "AGENTS.md":
            has_route = all(marker in text for marker in _AGENTS_GUIDE_MARKERS)
            states.append(ReadinessState.MET if has_route else ReadinessState.NOT_MET)
        else:
            states.append(ReadinessState.MET)
    query = _contents_path(repo, row.files[0], ref) if row.files else ""
    return _combine_states(states), query


def _command_argv(template: str, repo: str, ref: str | None) -> list[str]:
    """Expand `<owner>/<name>` and optional `<ref>` in a devops command string."""
    parts = [
        repo if part == "<owner>/<name>" else (ref or "HEAD") if part == "<ref>" else part
        for part in shlex.split(template)
    ]
    if parts and parts[0] == "devops":
        parts[0] = BIN_DEVOPS
    return parts


def _state_from_json_payload(payload: Mapping[str, Any]) -> ReadinessState | None:
    """Resolve a `ReadinessState` from a parsed JSON mapping, or `None` when unrecognized."""
    raw_state = payload.get("state") or payload.get("status")
    if isinstance(raw_state, str):
        normalized = raw_state.replace("_", " ").lower()
        for member in ReadinessState:
            if normalized == member.value:
                return member
    if "failing" in payload:
        return ReadinessState.NOT_MET if payload["failing"] else ReadinessState.MET
    for key in ("ok", "passed"):
        if key in payload:
            return ReadinessState.MET if payload[key] else ReadinessState.NOT_MET
    return None


def _state_from_command_output(returncode: int, stdout: str) -> ReadinessState:
    """Interpret JSON stdout first and return code second for a devops CLI check."""
    text = stdout.strip()
    if text:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, Mapping):
            parsed = _state_from_json_payload(payload)
            if parsed is not None:
                return parsed
    return ReadinessState.MET if returncode == 0 else ReadinessState.NOT_MET


def _evaluate_command_row(
    row: ReadinessRowSpec,
    repo: str,
    ref: str | None,
) -> tuple[ReadinessState, str, str, str]:
    """Run a configured devops command and return `(state, source, query, reason)`."""
    template = row.commands[0]
    argv = _command_argv(template, repo, ref)
    shown = " ".join(argv)
    try:
        proc = run_subprocess(
            argv,
            capture_output=True,
            text=True,
            check=False,
            quiet=True,
            timeout=_DEVOPS_CMD_TIMEOUT_SECONDS,
        )
    except (OSError, DevOpsCLIError) as exc:
        return ReadinessState.NOT_READABLE, template, shown, str(exc)
    state = _state_from_command_output(proc.returncode, proc.stdout)
    reason = "" if state is not ReadinessState.NOT_READABLE else "command did not yield readiness"
    return state, shown, shown, reason


def _evaluate_row(
    row: ReadinessRowSpec,
    *,
    repo: str,
    ref: str | None,
    session: PagedSession,
    now: datetime,
    reads: Reads,
    scorecard: dict[str, ScorecardCheckResult] | None,
    scorecard_source_is_github: bool,
    check_scorecard_files: bool,
    file_cache: dict[str, str | None],
) -> Fact:
    """Evaluate a single readiness row into a `Fact`."""
    if row.is_manual:
        return Fact(
            id=row.id,
            section=_SECTION_READINESS,
            value={
                "state": ReadinessState.NOT_READABLE.value,
                "scope": row.scope.value,
                "level": row.level,
            },
            unit=_UNIT_READINESS,
            n=None,
            source="manual",
            query="manual",
            definition=row.definition,
            read_at=now,
            status=FactStatus.SKIPPED,
            reason=MESSAGES.roadmap.review_readiness_manual,
        )

    if row.kind is CheckKind.SCORECARD:
        checks = scorecard or {}
        states = [
            checks[name].state if name in checks else ReadinessState.NOT_READABLE
            for name in row.scorecard_checks
        ]
        if (
            row.files
            and check_scorecard_files
            and scorecard is not None
            and not scorecard_source_is_github
        ):
            # OWN-2 checks files on default branch/ref in addition to Scorecard checks when reachable.
            file_state, _ = _evaluate_files(row, session, repo, ref, now, reads, file_cache)
            if file_state is not ReadinessState.NOT_READABLE:
                states.append(file_state)
        state = _combine_states(states)
        source = (
            ReaderKind.GITHUB.value
            if scorecard_source_is_github
            else (", ".join(row.scorecard_checks) or BIN_SCORECARD)
        )
        query = (
            f"repos/{repo}" if scorecard_source_is_github else " ".join(build_scorecard_cmd(repo))
        )
        return _row_fact(row, state=state, n=len(states), source=source, query=query, now=now)

    if row.kind is CheckKind.FILE:
        state, query = _evaluate_files(row, session, repo, ref, now, reads, file_cache)
        return _row_fact(
            row,
            state=state,
            n=len(row.files),
            source=ReaderKind.GITHUB.value,
            query=query,
            now=now,
        )

    if row.kind is CheckKind.COMMAND and row.runnable and row.commands:
        state, source, query, reason = _evaluate_command_row(row, repo, ref)
        return _row_fact(
            row,
            state=state,
            n=1 if state is not ReadinessState.NOT_READABLE else None,
            source=source,
            query=query,
            now=now,
            reason=reason,
        )

    return _row_fact(
        row,
        state=ReadinessState.NOT_READABLE,
        n=None,
        source=row.commands[0] if row.commands else row.kind.value,
        query=row.commands[0] if row.commands else row.kind.value,
        now=now,
        reason=MESSAGES.roadmap.review_readiness_unread.format(kind=row.kind.value),
    )


def _row_fact(
    row: ReadinessRowSpec,
    *,
    state: ReadinessState,
    n: int | None,
    source: str,
    query: str,
    now: datetime,
    reason: str = "",
) -> Fact:
    is_readable = state is not ReadinessState.NOT_READABLE
    return Fact(
        id=row.id,
        section=_SECTION_READINESS,
        value={"state": state.value, "scope": row.scope.value, "level": row.level},
        unit=_UNIT_READINESS,
        n=n,
        source=source,
        query=query,
        definition=row.definition,
        read_at=now,
        status=FactStatus.OK if is_readable else FactStatus.SKIPPED,
        reason=""
        if is_readable
        else (reason or MESSAGES.roadmap.review_readiness_unread.format(kind=row.kind.value)),
    )


def evaluate_repository_readiness(
    repo: str,
    *,
    session: PagedSession,
    now: datetime,
    ref: str | None = None,
    rows: Sequence[ReadinessRowSpec] = READINESS_ROWS,
    scorecard_data: Mapping[str, Any] | None = None,
    reads: Reads | None = None,
    force_visibility_check: bool = False,
) -> tuple[RepoReadiness, bool]:
    """Evaluate all readiness rows of `repo` at `ref`, returning `(report, is_private)`."""
    counter = reads or Reads()
    need_scorecard = any(row.kind is CheckKind.SCORECARD and not row.is_manual for row in rows)
    need_files = any(row.kind is CheckKind.FILE and not row.is_manual for row in rows)
    check_visibility = force_visibility_check or (
        scorecard_data is None and (need_scorecard or need_files)
    )
    visibility = (
        _read_repo_visibility(session, repo, now, counter) if check_visibility else RepoVisibility()
    )
    file_cache: dict[str, str | None] = {}
    scorecard: dict[str, ScorecardCheckResult] | None = None
    fallback_github = False

    if need_scorecard:
        if scorecard_data is not None:
            scorecard = parse_scorecard_json(scorecard_data)
        else:
            scorecard = read_scorecard(repo)
            if scorecard is None and visibility.private:
                scorecard = _fallback_scorecard_from_github(
                    session, repo, visibility, ref, now, counter, file_cache
                )
                fallback_github = True

    facts = [
        _evaluate_row(
            row,
            repo=repo,
            ref=ref,
            session=session,
            now=now,
            reads=counter,
            scorecard=scorecard,
            scorecard_source_is_github=fallback_github,
            check_scorecard_files=scorecard_data is None,
            file_cache=file_cache,
        )
        for row in rows
    ]
    return RepoReadiness(repo=repo, ref=ref, facts=facts), visibility.private


class ReadinessReport(BaseModel):
    """Shared readiness report containing only public repositories (#5537)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    repositories: list[RepoReadiness] = Field(default_factory=list)


def collect_readiness(
    settings: Settings,
    *,
    session: PagedSession,
    now: datetime,
    ref: str | None = None,
    reads: Reads | None = None,
    rows: Sequence[ReadinessRowSpec] = READINESS_ROWS,
) -> ReadinessReport:
    """Evaluate all repositories in `service.repos` and `infra.repos`, excluding private repos."""
    public_reports: list[RepoReadiness] = []
    for repo in readiness_targets(settings):
        repo_report, is_private = evaluate_repository_readiness(
            repo,
            session=session,
            now=now,
            ref=ref,
            rows=rows,
            reads=reads,
            force_visibility_check=True,
        )
        if not is_private:
            public_reports.append(repo_report)
    return ReadinessReport(repositories=public_reports)


def planned_readiness(
    settings: Settings,
    *,
    ref: str | None = None,
    repo: str | None = None,
) -> list[PlannedRequest]:
    """Dry-run plan of readiness reads for configured repositories (or `[repo]`)."""
    targets = [repo] if repo else readiness_targets(settings)
    planned: list[PlannedRequest] = []
    for target in targets:
        planned.append(
            PlannedRequest(
                method=BIN_SCORECARD,
                target=target,
                argv=tuple(build_scorecard_cmd(target)),
            )
        )
        planned.append(
            PlannedRequest(
                method=ReaderKind.GITHUB,
                target=f"GET /repos/{target}",
            )
        )
        for row in READINESS_ROWS:
            if row.kind is CheckKind.FILE and row.files:
                for path in row.files:
                    planned.append(
                        PlannedRequest(
                            method=ReaderKind.GITHUB,
                            target=f"GET /{_contents_path(target, path, ref)}",
                        )
                    )
            elif row.kind is CheckKind.COMMAND and row.runnable and row.commands:
                argv = tuple(_command_argv(row.commands[0], target, ref))
                planned.append(
                    PlannedRequest(
                        method="devops",
                        target=" ".join(argv),
                        argv=argv,
                    )
                )
    return planned
