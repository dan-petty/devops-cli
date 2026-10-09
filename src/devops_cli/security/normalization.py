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
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from devops_cli.ai.review_schema import Finding, _cwe_number, _parse_location
from devops_cli.config.constants import (
    CONST_SARIF_FINGERPRINT_KEY,
    CONST_SEVERITY_ALIASES,
    CONST_SEVERITY_MEDIUM,
    CONST_SEVERITY_ORDER,
)
from devops_cli.review.fingerprint import compute_fingerprint_v2

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

    Scanners write `path:line`, but also `path:Deployment/ns/name`, `image:efficiency` and
    `path:simulation`. Assuming an integer would either raise or silently drop the locator,
    so a non-numeric suffix is preserved as a symbol instead. A line range, `path:start-end`
    as Semgrep writes a multi-line result, reads as its start line: it is a line, not a name.
    """
    line_path, start, _ = _parse_location(location)
    if start is not None:
        return line_path, start, None
    head, separator, tail = location.rpartition(":")
    if not separator:
        return location.strip(), None, None
    path = head.strip()
    suffix = tail.strip()
    if not path:
        # A leading colon means there was no path, only a locator.
        return "", None, suffix or None
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
    gating: bool = True
    tool_version: str | None = None
    partial_fingerprints: Mapping[str, str] = field(default_factory=dict)
    rule_properties: Mapping[str, Any] = field(default_factory=dict)
    baseline_state: str | None = None
    logical_locations: tuple[dict[str, Any], ...] = ()
    file_content: str | None = None
    occurrence_index: int = 0
    end_line: int | None = None
    cwe: str | None = None

    @property
    def rank(self) -> int:
        """Sort key, most severe first."""
        return severity_rank(self.severity)

    @property
    def location(self) -> str:
        """Render the location back into the scanner display form."""
        if self.symbol:
            return f"{self.path}:{self.symbol}" if self.path else self.symbol
        if self.line is not None:
            if self.end_line is not None and self.end_line != self.line:
                loc_range = f"{self.line}-{self.end_line}"
                return f"{self.path}:{loc_range}" if self.path else loc_range
            return f"{self.path}:{self.line}" if self.path else str(self.line)
        return self.path

    @property
    def fingerprint(self) -> str:
        """A stable identity for this finding using fingerprint v2."""
        if CONST_SARIF_FINGERPRINT_KEY in self.partial_fingerprints:
            return self.partial_fingerprints[CONST_SARIF_FINGERPRINT_KEY]

        logical_loc: str | None = None
        if self.symbol:
            logical_loc = self.symbol
        elif self.logical_locations:
            first = self.logical_locations[0]
            if isinstance(first, dict) and first.get("name"):
                logical_loc = str(first["name"])

        content = self.file_content
        if content is None and self.path:
            try:
                p = Path(self.path)
                if p.is_file():
                    content = p.read_text(encoding="utf-8", errors="replace")
            except OSError, RuntimeError:
                pass

        return compute_fingerprint_v2(
            tool=self.tool,
            rule_id=self.rule_id,
            path=self.path,
            start_line=self.line,
            file_content=content,
            enclosing_symbol=self.symbol,
            logical_location=logical_loc,
            occurrence_index=self.occurrence_index,
        )

    @property
    def correlation_key(self) -> tuple[str, tuple[int | None, int | None] | None, str | None]:
        """The identity used to relate findings across tools.

        Path or logical location, region (start, end), and CWE.
        """
        return (_finding_locator(self), _finding_region(self), _extract_cwe(self))


def _finding_locator(finding: NormalizedFinding) -> str:
    """Return the path or logical location identifying where the finding sits."""
    if finding.symbol:
        return finding.symbol
    if finding.logical_locations:
        first = finding.logical_locations[0]
        if isinstance(first, dict) and first.get("name"):
            return str(first["name"])
    return finding.path


def _finding_region(finding: NormalizedFinding) -> tuple[int | None, int | None] | None:
    """Return (start_line, end_line) or None if finding has no line."""
    if finding.line is None:
        return None
    start = finding.line
    end = finding.end_line if finding.end_line is not None else start
    return (start, end)


def _iter_strings(value: Any) -> Iterator[str]:
    """Yield strings from either a scalar string or a list of elements."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        yield from (item for item in value if isinstance(item, str))


def _extract_cwe_candidates(finding: NormalizedFinding) -> Iterator[str]:
    """Yield all candidate strings from finding metadata that might contain a CWE."""
    if finding.rule_properties:
        yield from _iter_strings(finding.rule_properties.get("cwe"))
        yield from _iter_strings(finding.rule_properties.get("tags"))
    yield from finding.references
    yield finding.rule_id
    yield finding.message


def _extract_cwe(finding: NormalizedFinding) -> str | None:
    """Extract canonical CWE identifier (e.g. 'CWE-89') from finding metadata."""
    if finding.cwe:
        num = _cwe_number(finding.cwe)
        return f"CWE-{num}" if num is not None else finding.cwe.upper()

    for candidate in _extract_cwe_candidates(finding):
        if (num := _cwe_number(candidate)) is not None:
            return f"CWE-{num}"

    return None


def _regions_overlap(
    r1: tuple[int | None, int | None] | None,
    r2: tuple[int | None, int | None] | None,
    tolerance: int = 2,
) -> bool:
    """Check if two regions overlap within tolerance."""
    if r1 is None and r2 is None:
        return True
    if r1 is None or r2 is None:
        return False
    s1, e1 = r1
    s2, e2 = r2
    if s1 is None or s2 is None:
        return True
    act_e1 = e1 if e1 is not None else s1
    act_e2 = e2 if e2 is not None else s2
    return max(s1, s2) <= min(act_e1, act_e2) + tolerance


def _findings_correlate(a: NormalizedFinding, b: NormalizedFinding) -> bool:
    """Report whether two findings correlate (different tools, same locator, overlapping region, compatible CWE)."""
    if a.tool == b.tool:
        return False

    loc_a = _finding_locator(a).strip().lower()
    loc_b = _finding_locator(b).strip().lower()
    if loc_a != loc_b:
        return False

    if not _regions_overlap(_finding_region(a), _finding_region(b)):
        return False

    cwe_a = _extract_cwe(a)
    cwe_b = _extract_cwe(b)
    if cwe_a is not None and cwe_b is not None and cwe_a != cwe_b:
        return False

    return True


def _total_finding_key(finding: NormalizedFinding) -> tuple[Any, ...]:
    """Total sort key: parsed path, start line, end line, rule id, tool, fingerprint."""
    file_part, start_line, end_line = _parse_location(finding.location)
    path_key = (file_part or finding.path).lower()
    start_key = (
        start_line if start_line is not None else (finding.line if finding.line is not None else -1)
    )
    end_key = (
        end_line
        if end_line is not None
        else (finding.end_line if finding.end_line is not None else start_key)
    )
    return (
        path_key,
        start_key,
        end_key,
        finding.rule_id,
        finding.tool,
        finding.fingerprint,
    )


def _region_span(finding: NormalizedFinding) -> int:
    """Return the line span of a finding's region, smaller is narrower."""
    _file_part, start_line, end_line = _parse_location(finding.location)
    s = start_line if start_line is not None else finding.line
    e = (
        end_line
        if end_line is not None
        else (finding.end_line if finding.end_line is not None else s)
    )
    if s is not None and e is not None:
        return abs(e - s)
    if s is not None:
        return 0
    return 999999


def _pick_representative(members: list[NormalizedFinding]) -> NormalizedFinding:
    """Choose cluster representative: highest severity, narrowest parsed region, total key."""
    best = min(
        members,
        key=lambda m: (
            m.rank,
            _region_span(m),
            _total_finding_key(m),
        ),
    )
    all_refs = tuple(sorted(dict.fromkeys(r for m in members for r in m.references)))
    if best.references != all_refs:
        from dataclasses import replace

        return replace(best, references=all_refs)
    return best


def assign_occurrence_indices(findings: list[NormalizedFinding]) -> list[NormalizedFinding]:
    """Assign deterministic occurrence indices among findings with colliding base identities."""
    from dataclasses import replace

    seen_locs: dict[str, dict[tuple[int | None, str | None], int]] = {}
    updated: list[NormalizedFinding] = []

    for f in findings:
        content = f.file_content
        if content is None and f.path:
            try:
                p = Path(f.path)
                if p.is_file():
                    content = p.read_text(encoding="utf-8", errors="replace")
            except OSError, RuntimeError:
                pass

        if not content or f.line is None:
            updated.append(f)
            continue

        target_f = f if f.file_content is not None else replace(f, file_content=content)
        base_fp = (
            target_f.fingerprint
            if target_f.occurrence_index == 0
            else replace(target_f, occurrence_index=0).fingerprint
        )
        loc_key = (target_f.line, target_f.symbol)

        if base_fp not in seen_locs:
            seen_locs[base_fp] = {loc_key: 0}
            idx = 0
        else:
            loc_dict = seen_locs[base_fp]
            if loc_key in loc_dict:
                idx = loc_dict[loc_key]
            else:
                idx = len(loc_dict)
                loc_dict[loc_key] = idx

        if idx != target_f.occurrence_index or target_f.file_content != f.file_content:
            updated.append(replace(target_f, occurrence_index=idx))
        else:
            updated.append(target_f)

    return updated


def normalize_finding(
    finding: Finding,
    tool: str,
    base: Path | None = None,
    gating: bool = True,
) -> NormalizedFinding:
    """Convert a scanner `Finding` into the normalized taxonomy."""
    raw_path, line, symbol = split_location(finding.location)
    _, start_line, end_line = _parse_location(finding.location)
    norm_path = normalize_path(raw_path, base)

    file_content: str | None = None
    if norm_path:
        target_file = (base / norm_path) if base else Path(norm_path)
        if target_file.is_file():
            try:
                file_content = target_file.read_text(encoding="utf-8", errors="replace")
            except OSError, RuntimeError:
                pass

    return NormalizedFinding(
        tool=tool,
        rule_id=extract_rule_id(finding.title, tool),
        severity=normalize_severity(finding.severity),
        message=strip_rule_prefix(finding.title) or finding.description,
        path=norm_path,
        line=line if line is not None else start_line,
        end_line=end_line,
        symbol=symbol,
        description=finding.description,
        fix=finding.fix,
        references=tuple(finding.references),
        gating=gating,
        file_content=file_content,
    )


def normalize_results(
    results: dict[str, list[Finding]], base: Path | None = None
) -> list[NormalizedFinding]:
    """Normalize a registry scan result mapping into a flat list."""
    from devops_cli.security.registry import global_scanner_registry

    normalized: list[NormalizedFinding] = []
    for tool, findings in results.items():
        scanner = global_scanner_registry.get(tool)
        gating = getattr(scanner, "gating", True)
        for finding in findings:
            normalized.append(normalize_finding(finding, tool, base, gating=gating))
    return assign_occurrence_indices(normalized)


def deduplicate(findings: list[NormalizedFinding]) -> list[NormalizedFinding]:
    """Drop findings that are byte-for-byte the same defect, order-independently."""
    if not findings:
        return []

    indexed = assign_occurrence_indices(findings)
    sorted_findings = sorted(indexed, key=_total_finding_key)

    seen: set[str] = set()
    unique: list[NormalizedFinding] = []
    for finding in sorted_findings:
        if finding.fingerprint in seen:
            continue
        seen.add(finding.fingerprint)
        unique.append(finding)
    return unique


@dataclass
class FindingCluster:
    """A group of findings that different tools reported about the same thing."""

    key: tuple[str, tuple[int | None, int | None] | None, str | None]
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
        return _pick_representative(self.findings)

    @property
    def confirmations(self) -> int:
        """How many distinct tools reported this."""
        return len(self.tools)


def correlate(findings: list[NormalizedFinding]) -> list[FindingCluster]:
    """Group findings that refer to the same defect at the same place using complete linkage."""
    if not findings:
        return []

    sorted_findings = sorted(findings, key=_total_finding_key)

    clusters_members: list[list[NormalizedFinding]] = []
    for finding in sorted_findings:
        placed = False
        for cluster in clusters_members:
            if all(_findings_correlate(finding, member) for member in cluster):
                cluster.append(finding)
                placed = True
                break
        if not placed:
            clusters_members.append([finding])

    result_clusters: list[FindingCluster] = []
    for members in clusters_members:
        rep = _pick_representative(members)
        result_clusters.append(FindingCluster(key=rep.correlation_key, findings=members))

    return rank_clusters(result_clusters)


def rank(findings: list[NormalizedFinding]) -> list[NormalizedFinding]:
    """Order findings by severity, then by location, for a stable report."""
    return sorted(
        findings,
        key=lambda finding: (finding.rank, finding.path, finding.line or 0, finding.rule_id),
    )


def rank_clusters(clusters: list[FindingCluster]) -> list[FindingCluster]:
    """Order clusters by severity, then by how many tools agreed, then by location and rule."""

    def _cluster_sort_key(cluster: FindingCluster) -> tuple[Any, ...]:
        rep = cluster.representative
        file_part, start_line, end_line = _parse_location(rep.location)
        path_key = (file_part or rep.path).lower()
        start_key = (
            start_line if start_line is not None else (rep.line if rep.line is not None else -1)
        )
        end_key = (
            end_line
            if end_line is not None
            else (rep.end_line if rep.end_line is not None else start_key)
        )
        return (
            severity_rank(cluster.severity),
            -cluster.confirmations,
            path_key,
            start_key,
            end_key,
            rep.symbol or "",
            rep.rule_id,
            rep.tool,
            rep.fingerprint,
        )

    return sorted(clusters, key=_cluster_sort_key)


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
        "gating": normalized.gating,
    }


__all__ = [
    "FindingCluster",
    "NormalizedFinding",
    "as_dict",
    "assign_occurrence_indices",
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
