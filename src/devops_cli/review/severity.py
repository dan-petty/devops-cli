"""Pure function severity calculation and derivation tracking (#871).

Severity is a pure function of SARIF level, rule severity, security-severity / CVSS,
and path-class severity caps from `.devops/review.toml`.
"""

from __future__ import annotations

from collections.abc import Mapping

from devops_cli.config.constants import (
    CONST_SEVERITY_ALIASES,
    CONST_SEVERITY_CRITICAL,
    CONST_SEVERITY_HIGH,
    CONST_SEVERITY_INFO,
    CONST_SEVERITY_LOW,
    CONST_SEVERITY_MEDIUM,
    CONST_SEVERITY_ORDER,
)

_SARIF_LEVEL_TO_SEVERITY: dict[str, str] = {
    "error": CONST_SEVERITY_HIGH,
    "warning": CONST_SEVERITY_MEDIUM,
    "note": CONST_SEVERITY_LOW,
    "none": CONST_SEVERITY_INFO,
}


def _severity_from_cvss(score: float | int | str) -> tuple[str, str] | None:
    """Map numeric security-severity or CVSS score (0.0 - 10.0) to severity."""
    try:
        val = float(score)
    except TypeError, ValueError:
        return None

    if val >= 9.0:
        return CONST_SEVERITY_CRITICAL, f"cvss={val:.1f} >= 9.0"
    if val >= 7.0:
        return CONST_SEVERITY_HIGH, f"cvss={val:.1f} >= 7.0"
    if val >= 4.0:
        return CONST_SEVERITY_MEDIUM, f"cvss={val:.1f} >= 4.0"
    if val > 0.0:
        return CONST_SEVERITY_LOW, f"cvss={val:.1f} > 0.0"
    return CONST_SEVERITY_INFO, f"cvss={val:.1f} == 0.0"


def _min_severity(s1: str, s2: str) -> str:
    """Return the less severe of two severity levels."""
    rank1 = CONST_SEVERITY_ORDER.index(s1)
    rank2 = CONST_SEVERITY_ORDER.index(s2)
    return CONST_SEVERITY_ORDER[max(rank1, rank2)]


def _determine_base_severity(
    security_severity: float | int | str | None,
    rule_severity: str | None,
    sarif_level: str | None,
) -> tuple[str, str]:
    """Resolve base severity from CVSS, rule severity, SARIF level or default."""
    if security_severity is not None:
        cvss_res = _severity_from_cvss(security_severity)
        if cvss_res is not None:
            return cvss_res

    if rule_severity and rule_severity.strip():
        norm = CONST_SEVERITY_ALIASES.get(rule_severity.strip().upper())
        if norm:
            return norm, f"rule_severity={rule_severity.strip()}"

    if sarif_level and sarif_level.strip():
        norm_level = sarif_level.strip().lower()
        if norm_level in _SARIF_LEVEL_TO_SEVERITY:
            return _SARIF_LEVEL_TO_SEVERITY[norm_level], f"sarif_level={norm_level}"

    return CONST_SEVERITY_MEDIUM, "default=MEDIUM"


def _apply_severity_cap(
    base_sev: str,
    source_desc: str,
    path_class: str | None,
    severity_caps: Mapping[str, str] | None,
) -> tuple[str, str]:
    """Cap effective severity if path class cap applies."""
    if not (path_class and severity_caps and path_class in severity_caps):
        return base_sev, f"{source_desc} -> {base_sev}"

    raw_cap = severity_caps[path_class]
    cap = CONST_SEVERITY_ALIASES.get(raw_cap.strip().upper(), raw_cap.strip().upper())
    if cap not in CONST_SEVERITY_ORDER:
        return base_sev, f"{source_desc} -> {base_sev}"

    capped = _min_severity(base_sev, cap)
    if capped != base_sev:
        return capped, f"{source_desc} -> {base_sev}, capped by {path_class}={cap} -> {capped}"
    return base_sev, f"{source_desc} -> {base_sev} (within {path_class} cap {cap})"


def derive_severity(
    *,
    security_severity: float | int | str | None = None,
    rule_severity: str | None = None,
    sarif_level: str | None = None,
    path_class: str | None = None,
    severity_caps: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    """Calculate effective severity and record the precise derivation.

    Returns:
        (effective_severity, derivation_string)
    """
    base_sev, source_desc = _determine_base_severity(security_severity, rule_severity, sarif_level)
    return _apply_severity_cap(base_sev, source_desc, path_class, severity_caps)
