"""SARIF 2.1.0 ingestion and emission for the unified scanner pipeline.

Every scanner in this codebase has its own output shape and its own parser. SARIF is the
interchange format those tools already speak, and it is what GitHub code scanning, IDEs and
policy engines consume, so producing it turns findings from something only this CLI can
read into something the rest of the toolchain can. Reading it means a scanner that emits
SARIF needs no bespoke parser at all.

Emission and ingestion are inverses over the normalized taxonomy, which is what the
round-trip tests assert.

Reference: https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from devops_cli.config.constants import (
    CONST_SARIF_FINGERPRINT_KEY,
    CONST_SARIF_LEVEL_TO_SEVERITY,
    CONST_SARIF_LEVEL_WARNING,
    CONST_SARIF_LEVELS,
    CONST_SARIF_SCHEMA_URI,
    CONST_SARIF_SECURITY_SEVERITY_PROPERTY,
    CONST_SARIF_VERSION,
    CONST_SEVERITY_TO_SARIF_LEVEL,
    CONST_SEVERITY_TO_SECURITY_SCORE,
)
from devops_cli.security.normalization import (
    NormalizedFinding,
    normalize_severity,
)

CONST_SARIF_TOOL_NAME = "devops-cli"
CONST_SARIF_TOOL_URI = "https://github.com/dan-petty/devops-cli"


class SarifError(ValueError):
    """Raised when a document does not conform to SARIF 2.1.0."""


# =============================================================================
# Emission
# =============================================================================


def _rule_for(finding: NormalizedFinding) -> dict[str, Any]:
    """Build the rule descriptor a result refers to by id."""
    return {
        "id": finding.rule_id,
        "name": finding.rule_id,
        "shortDescription": {"text": finding.message or finding.rule_id},
        "fullDescription": {"text": finding.description or finding.message},
        "help": {"text": finding.fix or finding.description or finding.message},
        "properties": {
            # GitHub code scanning orders by this rather than by `level`, so both are
            # emitted: the level for generic consumers, the score for GitHub.
            CONST_SARIF_SECURITY_SEVERITY_PROPERTY: CONST_SEVERITY_TO_SECURITY_SCORE.get(
                finding.severity, "5.0"
            ),
            "tags": ["security", finding.tool],
        },
    }


def _location_for(finding: NormalizedFinding) -> list[dict[str, Any]]:
    """Build the physical location for a result, omitting it when there is no path."""
    if not finding.path:
        return []
    physical: dict[str, Any] = {"artifactLocation": {"uri": finding.path}}
    if finding.line is not None:
        # SARIF regions are one-based; a zero or negative line is not expressible, so it is
        # dropped rather than written as an invalid region a consumer would reject.
        if finding.line > 0:
            physical["region"] = {"startLine": finding.line}
    location: dict[str, Any] = {"physicalLocation": physical}
    if finding.symbol:
        location["logicalLocations"] = [{"name": finding.symbol}]
    return [location]


def _result_for(finding: NormalizedFinding, rule_index: int) -> dict[str, Any]:
    """Build a single SARIF result."""
    result: dict[str, Any] = {
        "ruleId": finding.rule_id,
        "ruleIndex": rule_index,
        "level": CONST_SEVERITY_TO_SARIF_LEVEL.get(finding.severity, CONST_SARIF_LEVEL_WARNING),
        "message": {"text": finding.message or finding.description or finding.rule_id},
        "partialFingerprints": {CONST_SARIF_FINGERPRINT_KEY: finding.fingerprint},
        "properties": {"tool": finding.tool, "severity": finding.severity},
    }
    locations = _location_for(finding)
    if locations:
        result["locations"] = locations
    return result


def _run_for(tool: str, findings: list[NormalizedFinding]) -> dict[str, Any]:
    """Build one SARIF run for a single tool.

    Each tool gets its own run because a run carries exactly one tool driver; merging them
    would attribute every finding to whichever driver was written first.
    """
    rule_indices: dict[str, int] = {}
    rules: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []

    for finding in findings:
        index = rule_indices.get(finding.rule_id)
        if index is None:
            index = len(rules)
            rule_indices[finding.rule_id] = index
            rules.append(_rule_for(finding))
        results.append(_result_for(finding, index))

    return {
        "tool": {
            "driver": {
                "name": tool,
                "informationUri": CONST_SARIF_TOOL_URI,
                "rules": rules,
            }
        },
        "results": results,
    }


def to_sarif(findings: list[NormalizedFinding]) -> dict[str, Any]:
    """Render normalized findings as a SARIF 2.1.0 document.

    An empty list still produces a valid document with a single empty run. Emitting nothing
    would be read by a consumer as "the scan did not happen" rather than "the scan found
    nothing", which are very different claims to make about a security scan.
    """
    by_tool: dict[str, list[NormalizedFinding]] = {}
    for finding in findings:
        by_tool.setdefault(finding.tool or CONST_SARIF_TOOL_NAME, []).append(finding)

    runs = [_run_for(tool, tool_findings) for tool, tool_findings in sorted(by_tool.items())]
    if not runs:
        runs = [_run_for(CONST_SARIF_TOOL_NAME, [])]

    return {
        "$schema": CONST_SARIF_SCHEMA_URI,
        "version": CONST_SARIF_VERSION,
        "runs": runs,
    }


def write_sarif(findings: list[NormalizedFinding], destination: Path) -> Path:
    """Write a SARIF document to disk, returning the path written."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(to_sarif(findings), indent=2) + "\n", encoding="utf-8")
    return destination


# =============================================================================
# Ingestion
# =============================================================================


def _driver_name(run: dict[str, Any]) -> str:
    """Resolve the tool name for a run, falling back when the driver is absent."""
    tool = run.get("tool")
    if isinstance(tool, dict):
        driver = tool.get("driver")
        if isinstance(driver, dict):
            name = driver.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
    return "unknown"


def _driver_rules(run: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the rule descriptors declared by a run's driver."""
    tool = run.get("tool")
    driver = tool.get("driver") if isinstance(tool, dict) else None
    rules = driver.get("rules") if isinstance(driver, dict) else None
    return [rule for rule in rules if isinstance(rule, dict)] if isinstance(rules, list) else []


def _resolve_rule(result: dict[str, Any], rules: list[dict[str, Any]]) -> dict[str, Any]:
    """Resolve the rule a result refers to, by id or by index."""
    rule_id = result.get("ruleId")
    if isinstance(rule_id, str):
        for rule in rules:
            if rule.get("id") == rule_id:
                return rule
    index = result.get("ruleIndex")
    if isinstance(index, int) and 0 <= index < len(rules):
        return rules[index]
    return {}


def _severity_from(result: dict[str, Any], rule: dict[str, Any]) -> str:
    """Derive a severity from a result's level or its rule's security-severity score.

    The numeric score is preferred where present, because `level` collapses critical and
    high into `error` and that distinction is the one a triage queue is ordered by.
    """
    properties = rule.get("properties")
    if isinstance(properties, dict):
        score = properties.get(CONST_SARIF_SECURITY_SEVERITY_PROPERTY)
        severity = _severity_from_score(score)
        if severity:
            return severity

    result_properties = result.get("properties")
    if isinstance(result_properties, dict):
        declared = result_properties.get("severity")
        if isinstance(declared, str) and declared.strip():
            return normalize_severity(declared)

    level = result.get("level")
    if isinstance(level, str) and level in CONST_SARIF_LEVELS:
        return CONST_SARIF_LEVEL_TO_SEVERITY[level]
    # SARIF's default level when unspecified is "warning".
    return CONST_SARIF_LEVEL_TO_SEVERITY[CONST_SARIF_LEVEL_WARNING]


def _severity_from_score(score: Any) -> str | None:
    """Map GitHub's numeric security-severity onto the shared vocabulary."""
    if score is None:
        return None
    try:
        value = float(score)
    except TypeError, ValueError:
        return None
    if value >= 9.0:
        return "CRITICAL"
    if value >= 7.0:
        return "HIGH"
    if value >= 4.0:
        return "MEDIUM"
    if value > 0.0:
        return "LOW"
    return "INFO"


def _text_of(container: Any, key: str) -> str:
    """Read a SARIF multiformat message string."""
    if isinstance(container, dict):
        nested = container.get(key)
        if isinstance(nested, dict):
            text = nested.get("text")
            if isinstance(text, str):
                return text
        if isinstance(nested, str):
            return nested
    return ""


def _location_of(result: dict[str, Any]) -> tuple[str, int | None, str | None]:
    """Extract path, line and logical name from a result's first location."""
    locations = result.get("locations")
    if not isinstance(locations, list) or not locations:
        return "", None, None
    first = locations[0]
    if not isinstance(first, dict):
        return "", None, None

    physical = first.get("physicalLocation")
    path, line = "", None
    if isinstance(physical, dict):
        artifact = physical.get("artifactLocation")
        if isinstance(artifact, dict):
            uri = artifact.get("uri")
            if isinstance(uri, str):
                path = uri
        region = physical.get("region")
        if isinstance(region, dict):
            start = region.get("startLine")
            if isinstance(start, int) and start > 0:
                line = start

    symbol = None
    logical = first.get("logicalLocations")
    if isinstance(logical, list) and logical and isinstance(logical[0], dict):
        name = logical[0].get("name")
        if isinstance(name, str) and name.strip():
            symbol = name.strip()

    return path, line, symbol


def _finding_from_result(
    result: dict[str, Any], rules: list[dict[str, Any]], tool: str
) -> NormalizedFinding:
    """Convert one SARIF result into a normalized finding."""
    rule = _resolve_rule(result, rules)
    rule_id = result.get("ruleId") or rule.get("id") or f"{tool}.unknown"
    path, line, symbol = _location_of(result)
    message = _text_of(result, "message") or _text_of(rule, "shortDescription")

    return NormalizedFinding(
        tool=tool,
        rule_id=str(rule_id),
        severity=_severity_from(result, rule),
        message=message or str(rule_id),
        path=path,
        line=line,
        symbol=symbol,
        description=_text_of(rule, "fullDescription") or message,
        fix=_text_of(rule, "help"),
    )


def from_sarif(document: Any) -> list[NormalizedFinding]:
    """Parse a SARIF document into normalized findings.

    Raises :class:`SarifError` when the document is not SARIF at all. A malformed *result*
    inside an otherwise valid document is skipped rather than fatal: discarding an entire
    scan because one tool emitted one bad entry loses every real finding alongside it.
    """
    if not isinstance(document, dict):
        raise SarifError("SARIF document must be a JSON object")
    version = document.get("version")
    if version != CONST_SARIF_VERSION:
        raise SarifError(f"Unsupported SARIF version '{version}'; expected {CONST_SARIF_VERSION}")
    runs = document.get("runs")
    if not isinstance(runs, list):
        raise SarifError("SARIF document is missing a 'runs' array")

    findings: list[NormalizedFinding] = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        tool = _driver_name(run)
        rules = _driver_rules(run)
        results = run.get("results")
        if not isinstance(results, list):
            continue
        for result in results:
            if isinstance(result, dict):
                findings.append(_finding_from_result(result, rules, tool))
    return findings


def read_sarif(source: Path) -> list[NormalizedFinding]:
    """Read and parse a SARIF document from disk."""
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SarifError(f"'{source}' is not valid JSON: {exc}") from exc
    return from_sarif(document)


__all__ = [
    "SarifError",
    "from_sarif",
    "read_sarif",
    "to_sarif",
    "write_sarif",
]
