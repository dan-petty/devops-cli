"""The fingerprint of a normalized finding: what it keeps across edits, and what tells two
findings apart."""

from __future__ import annotations

import hashlib
from pathlib import Path

from devops_cli.ai.review_schema import Finding
from devops_cli.config.constants import (
    CONST_SARIF_FINGERPRINT_KEY,
)
from devops_cli.security.normalization import (
    NormalizedFinding,
    normalize_finding,
)
from devops_cli.security.pipeline import build_report
from tests.support.builders import make_normalized_finding


def test_a_fingerprint_survives_the_finding_moving_to_a_new_line() -> None:
    """A finding pushed down by an unrelated edit is the same finding.

    Including the line would re-open every suppression the next time anything above it
    changed, which makes fingerprint-based suppression useless in practice.
    """
    assert (
        make_normalized_finding(line=4).fingerprint == make_normalized_finding(line=91).fingerprint
    )


def test_a_fingerprint_distinguishes_the_same_rule_in_different_files() -> None:
    """Accepting a finding in one file must not accept it everywhere."""
    assert (
        make_normalized_finding(path="src/a.py").fingerprint
        != make_normalized_finding(path="src/b.py").fingerprint
    )


def test_a_fingerprint_distinguishes_different_rules_in_one_file() -> None:
    """Two defects on the same line are two findings."""
    assert (
        make_normalized_finding(rule_id="B602").fingerprint
        != make_normalized_finding(rule_id="B307").fingerprint
    )


def test_a_fingerprint_distinguishes_the_same_rule_reported_by_two_tools() -> None:
    """Tools disagree about what a rule means, so their results are not interchangeable."""
    assert (
        make_normalized_finding(tool="bandit").fingerprint
        != make_normalized_finding(tool="semgrep").fingerprint
    )


def test_a_fingerprint_ignores_whitespace_differences_in_the_message() -> None:
    """A scanner reflowing its own message must not invalidate a suppression."""
    assert (
        make_normalized_finding(message="shell=True  identified").fingerprint
        == make_normalized_finding(message="shell=True identified").fingerprint
    )


_PINNED_FINDINGS: tuple[NormalizedFinding, ...] = (
    NormalizedFinding(
        tool="bandit",
        rule_id="B602",
        severity="HIGH",
        message="subprocess call with shell=True",
        path="src/app.py",
        line=4,
    ),
    NormalizedFinding(
        tool="bandit",
        rule_id="B602",
        severity="HIGH",
        message="subprocess call with shell=True",
        path="manifests/prometheus.yaml",
        symbol="Service/monitoring/prometheus",
    ),
    NormalizedFinding(
        tool="semgrep",
        rule_id="python.lang.security.deserialization",
        severity="HIGH",
        message="Avoid using pickle",
        path="src/loader.py",
        line=12,
    ),
    NormalizedFinding(
        tool="trivy",
        rule_id="CVE-2023-1234",
        severity="CRITICAL",
        message="vulnerable package dependency",
        path="package-lock.json",
    ),
)


def test_finding_fingerprints_are_pinned_to_literal_values() -> None:
    """Fixed findings have fixed 32-hex sha256 fingerprints."""
    f_canonical = NormalizedFinding(
        tool="bandit",
        rule_id="B602",
        severity="HIGH",
        message="  [B602]  subprocess   call\nwith shell=True  ",
        path="src/app.py",
        line=4,
    )
    assert (
        _PINNED_FINDINGS[0].fingerprint,
        _PINNED_FINDINGS[1].fingerprint,
        _PINNED_FINDINGS[2].fingerprint,
        _PINNED_FINDINGS[3].fingerprint,
        f_canonical.fingerprint,
    ) == (
        "19227d34cc30f79e188a26626d20c75af663231c02d2a0e6a79476f3abb760d2",
        "22d8c3aa39d17d2f705b923594dff772493bfe6a04c4fbdca5fcf3f10a5455e2",
        "9a6565333c71882f8e028ee3fd8241570e070c48671b49bce17c7b9de6ce90c9",
        "7b2e0b7673b70b6c45c65db5e5acc709930bb6243003372ed59757ba32e426ab",
        "19227d34cc30f79e188a26626d20c75af663231c02d2a0e6a79476f3abb760d2",
    )


def test_sarif_fingerprint_key_pinned() -> None:
    """Rule: an algorithm change bumps the key and updates the pins in the same commit, and its
    pull request title names the change, so release-please writes it as a changelog line."""
    assert CONST_SARIF_FINGERPRINT_KEY == "devopsCli/v2"


def test_swapping_parts_or_changing_separator_or_canonicalisation_alters_fingerprint() -> None:
    """Verify that swapping parts, altering separator, or changing canonicalisation breaks literal pin."""
    swapped = hashlib.sha256(
        "B602␟bandit␟src/app.py␟subprocess call with shell=true".encode()
    ).hexdigest()[:32]
    colon_sep = hashlib.sha256(
        b"bandit:B602:src/app.py:subprocess call with shell=true"
    ).hexdigest()[:32]
    uncanonical = hashlib.sha256(
        "bandit␟B602␟src/app.py␟subprocess call with shell=True".encode()
    ).hexdigest()[:32]

    assert (
        swapped != _PINNED_FINDINGS[0].fingerprint,
        colon_sep != _PINNED_FINDINGS[0].fingerprint,
        uncanonical != _PINNED_FINDINGS[0].fingerprint,
    ) == (True, True, True)


def test_a_finding_without_a_symbol_keeps_its_fingerprint() -> None:
    """Adding the symbol to the identity leaves every line-located fingerprint, and every
    suppression recorded against one, as it was."""
    assert (
        make_normalized_finding().fingerprint
        == "19227d34cc30f79e188a26626d20c75af663231c02d2a0e6a79476f3abb760d2"
    )


def test_a_fingerprint_distinguishes_two_objects_with_one_message() -> None:
    """Two Services in one manifest failing one check are two findings: an object's name,
    unlike a line, does not move when lines are added above it."""
    assert (
        make_normalized_finding(line=None, symbol="Service/monitoring/a").fingerprint
        != make_normalized_finding(line=None, symbol="Service/monitoring/b").fingerprint
    )


def test_a_multi_line_result_keeps_its_fingerprint_when_it_moves() -> None:
    """Semgrep writes `path:start-end`; the range is a line, not an object's name."""
    moved = [
        normalize_finding(
            Finding(severity="HIGH", location=location, title="[py.exec] dynamic exec"),
            tool="semgrep",
        )
        for location in ("src/views.py:40-45", "src/views.py:41-46")
    ]
    assert (moved[0].line, moved[0].symbol, moved[0].fingerprint) == (
        40,
        None,
        moved[1].fingerprint,
    )


def test_two_popeye_issues_on_two_resources_of_one_sanitizer_are_kept() -> None:
    """Popeye titles every issue of a sanitizer alike, so only the resource tells them apart."""
    issues = [
        Finding(
            severity="MEDIUM",
            location=f"k8s:pods/default/{name}",
            title="[PODS] Cluster Sanitizer Finding",
            description="No resources requests/limits defined",
        )
        for name in ("web-a", "web-b")
    ]
    assert len(build_report({"popeye": issues}, Path("k8s")).findings) == 2
