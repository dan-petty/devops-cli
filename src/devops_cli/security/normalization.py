"""Normalized security finding taxonomy shared across every scanner.

Each scanner produces a :class:`Finding` whose `location` is a free-form string and whose
rule identifier, where it survives at all, is embedded in the title as a bracketed prefix.
That is enough to print a table and nothing more: two scanners reporting the same line
cannot be recognised as related, a result cannot be addressed by rule, and SARIF cannot be
emitted at all because it requires a `ruleId` and a structured location.

This module recovers that structure. It is deliberately separate from `Finding` itself,
which is also the schema an LLM populates during review, so tightening the security
taxonomy does not constrain what a model is allowed to return.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from devops_cli.ai.review_schema import Finding
from devops_cli.config.constants import (
    CONST_SEVERITY_ALIASES,
    CONST_SEVERITY_MEDIUM,
    CONST_SEVERITY_ORDER,
)

# A bracketed prefix is how every scanner in this codebase smuggles its rule id into the
# title, e.g. "[B105] Possible hardcoded password". Recovering it is what allows a result
# to be suppressed or grouped by rule rather than by the wording of its message.
_RULE_PREFIX_RE = re.compile(r"^\s*\[([A-Za-z0-9][A-Za-z0-9._\-]{1,63})\]\s*")
_DRY_RUN_PREFIX_RE = re.compile(r"^\s*\[DRY-RUN\]\s*", re.IGNORECASE)
# Collapse whitespace and volatile numbers so the same defect worded slightly differently
# by one scanner across two runs still fingerprints identically.
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_severity(value: str | None) -> str:
    """Map a scanner's severity spelling onto the shared vocabulary.

    An unrecognised severity becomes MEDIUM rather than INFO: silently demoting a finding
    this code does not understand is how a real issue gets filtered out of a report.
    """
    if not value:
        return CONST_SEVERITY_MEDIUM
    return CONST_SEVERITY_ALIASES.get(value.strip().upper(), CONST_SEVERITY_MEDIUM)


def severity_rank(severity: str) -> int:
    """Return the sort key for a severity, most severe first."""
    normalized = normalize_severity(severity)
    return CONST_SEVERITY_ORDER.index(normalized)


def split_location(location: str) -> tuple[str, int | None, str | None]:
    """Split a scanner location string into path, line number, and symbolic locator.

    Scanners write `path:line`, but also `path:Deployment/name`, `image:efficiency` and
    `path:simulation`. Assuming an integer would either raise or silently drop the locator,
    so a non-numeric suffix is preserved as a symbol instead.
    """
    if not location:
        return "", None, None
    head, separator, tail = location.rpartition(":")
    if not separator:
        return location.strip(), None, None
    path = head.strip()
    suffix = tail.strip()
    if not path:
        # A leading colon means there was no path, only a locator.
        return "", None, suffix or None
    if suffix.isdigit():
        return path, int(suffix), None
    return path, None, suffix or None


def normalize_path(path: str, base: Path | None = None) -> str:
    """Render a path relative to the scan root with forward slashes.

    Fingerprints must not change because a scan ran from a different working directory, and
    SARIF artifact URIs are required to be relative.
    """
    if not path:
        return ""
    candidate = Path(path)
    if base is not None and candidate.is_absolute():
        try:
            candidate = candidate.relative_to(base)
        except ValueError:
            pass
    # removeprefix, not lstrip: lstrip strips a character set, so ".github/ci.yml" would
    # lose its leading dot and name a directory that does not exist.
    return candidate.as_posix().removeprefix("./")


def _canonical_message(text: str) -> str:
    """Reduce a message to a form stable across cosmetic differences."""
    stripped = _DRY_RUN_PREFIX_RE.sub("", _RULE_PREFIX_RE.sub("", text or ""))
    return _WHITESPACE_RE.sub(" ", stripped).strip().lower()


def extract_rule_id(title: str, tool: str) -> str:
    """Recover the rule identifier from a title, falling back to a derived one.

    SARIF requires a `ruleId`, and suppression by rule is only meaningful if the identifier
    is stable. When a scanner supplies none, one is derived from the tool and the canonical
    message so that repeated occurrences of the same defect share an id.
    """
    match = _RULE_PREFIX_RE.match(title or "")
    if match:
        return match.group(1)
    digest = hashlib.sha256(_canonical_message(title).encode()).hexdigest()[:12]
    return f"{tool}.{digest}" if tool else digest


def strip_rule_prefix(title: str) -> str:
    """Return a title with its bracketed rule prefix removed."""
    return _RULE_PREFIX_RE.sub("", title or "").strip()


@dataclass(frozen=True)
class NormalizedFinding:
    """A scanner finding with the structure SARIF and deduplication require."""

    tool: str
    rule_id: str
    severity: str
    message: str
    path: str = ""
    line: int | None = None
    symbol: str | None = None
    description: str = ""
    fix: str = ""
    references: tuple[str, ...] = ()

    @property
    def rank(self) -> int:
        """Sort key, most severe first."""
        return severity_rank(self.severity)

    @property
    def location(self) -> str:
        """Render the location back into the scanner display form."""
        locator = self.symbol if self.symbol else self.line
        return f"{self.path}:{locator}" if locator is not None else self.path

    @property
    def fingerprint(self) -> str:
        """A stable identity for this finding.

        The line number is deliberately excluded. A finding that moves because unrelated
        code was inserted above it is the same finding, and including the line would
        re-open every suppression on the next edit. Path, tool, rule and canonical message
        are what actually identify it.
        """
        parts = (self.tool, self.rule_id, self.path, _canonical_message(self.message))
        return hashlib.sha256("␟".join(parts).encode()).hexdigest()[:32]

    @property
    def correlation_key(self) -> tuple[str, int | None, str]:
        """The identity used to relate findings *across* tools.

        Tool and rule id are excluded on purpose: different scanners name the same defect
        differently, and the observable thing they agree on is the location and what they
        say about it.
        """
        return (self.path, self.line, _canonical_message(self.message))


def normalize_finding(finding: Finding, tool: str, base: Path | None = None) -> NormalizedFinding:
    """Convert a scanner `Finding` into the normalized taxonomy."""
    raw_path, line, symbol = split_location(finding.location)
    return NormalizedFinding(
        tool=tool,
        rule_id=extract_rule_id(finding.title, tool),
        severity=normalize_severity(finding.severity),
        message=strip_rule_prefix(finding.title) or finding.description,
        path=normalize_path(raw_path, base),
        line=line,
        symbol=symbol,
        description=finding.description,
        fix=finding.fix,
        references=tuple(finding.references),
    )


def normalize_results(
    results: dict[str, list[Finding]], base: Path | None = None
) -> list[NormalizedFinding]:
    """Normalize a registry scan result mapping into a flat list."""
    return [
        normalize_finding(finding, tool, base)
        for tool, findings in results.items()
        for finding in findings
    ]


def deduplicate(findings: list[NormalizedFinding]) -> list[NormalizedFinding]:
    """Drop findings that are byte-for-byte the same defect, keeping the first seen.

    A scanner invoked over overlapping file subsets reports the same result more than once;
    so does a registry that runs two scanners sharing an underlying engine.
    """
    seen: set[str] = set()
    unique: list[NormalizedFinding] = []
    for finding in findings:
        if finding.fingerprint in seen:
            continue
        seen.add(finding.fingerprint)
        unique.append(finding)
    return unique


@dataclass
class FindingCluster:
    """A group of findings that different tools reported about the same thing."""

    key: tuple[str, int | None, str]
    findings: list[NormalizedFinding] = field(default_factory=list)

    @property
    def tools(self) -> tuple[str, ...]:
        """Tools that reported this cluster, in a stable order."""
        return tuple(sorted({finding.tool for finding in self.findings}))

    @property
    def severity(self) -> str:
        """The most severe assessment any tool made.

        Taking the maximum rather than an average or the first: if any scanner considers it
        critical, reporting it as medium is the failure mode that matters.
        """
        return min(self.findings, key=lambda finding: finding.rank).severity

    @property
    def representative(self) -> NormalizedFinding:
        """The finding shown when the cluster is rendered as a single row."""
        return min(self.findings, key=lambda finding: (finding.rank, finding.tool))

    @property
    def confirmations(self) -> int:
        """How many distinct tools reported this."""
        return len(self.tools)


def correlate(findings: list[NormalizedFinding]) -> list[FindingCluster]:
    """Group findings that refer to the same defect at the same place.

    Clusters are *not* merged into one finding. Two tools reporting the same line may be
    describing genuinely different problems, and collapsing them would hide one. Grouping
    states what is observable — that several tools flagged the same place — and leaves the
    individual results intact.
    """
    clusters: dict[tuple[str, int | None, str], FindingCluster] = {}
    for finding in findings:
        cluster = clusters.get(finding.correlation_key)
        if cluster is None:
            cluster = FindingCluster(key=finding.correlation_key)
            clusters[finding.correlation_key] = cluster
        cluster.findings.append(finding)
    return rank_clusters(list(clusters.values()))


def rank(findings: list[NormalizedFinding]) -> list[NormalizedFinding]:
    """Order findings by severity, then by location, for a stable report."""
    return sorted(
        findings,
        key=lambda finding: (finding.rank, finding.path, finding.line or 0, finding.rule_id),
    )


def rank_clusters(clusters: list[FindingCluster]) -> list[FindingCluster]:
    """Order clusters by severity, then by how many tools agreed, then by location.

    Corroboration is a ranking signal: a line three scanners flagged is likelier to deserve
    attention than one only a single scanner did, at the same severity.
    """
    return sorted(
        clusters,
        key=lambda cluster: (
            severity_rank(cluster.severity),
            -cluster.confirmations,
            cluster.representative.path,
            cluster.representative.line or 0,
        ),
    )


def filter_by_severity(findings: list[NormalizedFinding], minimum: str) -> list[NormalizedFinding]:
    """Keep findings at or above a minimum severity."""
    threshold = severity_rank(minimum)
    return [finding for finding in findings if finding.rank <= threshold]


def summarize(findings: list[NormalizedFinding]) -> dict[str, int]:
    """Count findings by severity, including severities with no findings.

    Reporting only the severities present makes an empty CRITICAL indistinguishable from a
    report that never looked for one.
    """
    counts = dict.fromkeys(CONST_SEVERITY_ORDER, 0)
    for finding in findings:
        counts[normalize_severity(finding.severity)] += 1
    return counts


def to_finding(normalized: NormalizedFinding) -> Finding:
    """Convert back to the display `Finding` used by the existing renderers."""
    title = (
        f"[{normalized.rule_id}] {normalized.message}" if normalized.rule_id else normalized.message
    )
    return Finding(
        severity=normalized.severity,
        location=normalized.location,
        title=title,
        description=normalized.description,
        fix=normalized.fix,
        references=list(normalized.references),
    )


def as_dict(normalized: NormalizedFinding) -> dict[str, Any]:
    """Render a normalized finding as a JSON-serializable mapping."""
    return {
        "tool": normalized.tool,
        "rule_id": normalized.rule_id,
        "severity": normalized.severity,
        "message": normalized.message,
        "path": normalized.path,
        "line": normalized.line,
        "symbol": normalized.symbol,
        "fingerprint": normalized.fingerprint,
        "fix": normalized.fix,
        "references": list(normalized.references),
    }


__all__ = [
    "FindingCluster",
    "NormalizedFinding",
    "as_dict",
    "correlate",
    "deduplicate",
    "extract_rule_id",
    "filter_by_severity",
    "normalize_finding",
    "normalize_path",
    "normalize_results",
    "normalize_severity",
    "rank",
    "rank_clusters",
    "severity_rank",
    "split_location",
    "strip_rule_prefix",
    "summarize",
    "to_finding",
]
