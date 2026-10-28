"""Deduplication, correlation and ranking of normalized findings."""

from __future__ import annotations

from devops_cli.config.constants import (
    CONST_SEVERITY_ORDER,
)
from devops_cli.security.normalization import (
    correlate,
    deduplicate,
    filter_by_severity,
    rank,
    summarize,
)
from tests.support.builders import make_normalized_finding


def test_the_same_finding_reported_twice_is_collapsed() -> None:
    """Overlapping file subsets make a scanner report the same result more than once."""
    assert (
        len(
            deduplicate(
                [
                    make_normalized_finding(),
                    make_normalized_finding(line=90),
                    make_normalized_finding(),
                ]
            )
        )
        == 1
    )


def test_deduplication_keeps_genuinely_distinct_findings() -> None:
    """Collapsing too eagerly hides real results."""
    findings = [
        make_normalized_finding(rule_id="B602"),
        make_normalized_finding(rule_id="B307"),
        make_normalized_finding(path="src/other.py"),
    ]
    assert len(deduplicate(findings)) == 3


def test_deduplication_preserves_the_first_occurrence() -> None:
    """The retained result should be the one the earliest scanner produced."""
    first = make_normalized_finding(tool="bandit")
    assert deduplicate([first, make_normalized_finding(tool="bandit", line=99)])[0] is first


def test_findings_from_different_tools_at_one_location_form_a_cluster() -> None:
    """A line several tools flagged is the observable fact worth surfacing."""
    clusters = correlate(
        [
            make_normalized_finding(tool="bandit"),
            make_normalized_finding(tool="semgrep", rule_id="py.shell"),
        ]
    )
    assert (len(clusters), clusters[0].confirmations, clusters[0].tools) == (
        1,
        2,
        ("bandit", "semgrep"),
    )


def test_clustering_does_not_merge_findings_into_one() -> None:
    """Two tools reporting one line may describe different problems.

    Collapsing them into a single result would hide one of them, so the cluster groups and
    keeps both.
    """
    clusters = correlate(
        [
            make_normalized_finding(tool="bandit"),
            make_normalized_finding(tool="semgrep", rule_id="py.shell"),
        ]
    )
    assert len(clusters[0].findings) == 2


def test_findings_at_different_lines_do_not_cluster() -> None:
    """Location is part of the correlation identity."""
    assert len(correlate([make_normalized_finding(line=4), make_normalized_finding(line=40)])) == 2


def test_findings_on_different_objects_do_not_cluster() -> None:
    """A report renders clusters, so two objects sharing a message would share one row."""
    clusters = correlate(
        [
            make_normalized_finding(line=None, symbol="Service/monitoring/a"),
            make_normalized_finding(line=None, symbol="Service/b"),
        ]
    )
    assert len(clusters) == 2


def test_a_cluster_reports_the_most_severe_assessment_any_tool_made() -> None:
    """If one scanner calls it critical, reporting it as medium is the dangerous error."""
    cluster = correlate(
        [
            make_normalized_finding(tool="a", severity="LOW"),
            make_normalized_finding(tool="b", severity="CRITICAL"),
        ]
    )[0]
    assert cluster.severity == "CRITICAL"


def test_a_clusters_representative_is_its_most_severe_finding() -> None:
    """The row shown for a cluster should be its worst result."""
    cluster = correlate(
        [
            make_normalized_finding(tool="a", severity="LOW"),
            make_normalized_finding(tool="b", severity="CRITICAL"),
        ]
    )[0]
    assert cluster.representative.severity == "CRITICAL"


def test_clusters_are_ranked_by_severity_then_corroboration() -> None:
    """At equal severity, a line several tools flagged ranks above one only a single tool did."""
    findings = [
        make_normalized_finding(
            path="solo.py", severity="HIGH", tool="bandit", message="solo issue"
        ),
        make_normalized_finding(
            path="both.py", severity="HIGH", tool="bandit", message="shared issue"
        ),
        make_normalized_finding(
            path="both.py", severity="HIGH", tool="semgrep", message="shared issue"
        ),
        make_normalized_finding(
            path="low.py", severity="LOW", tool="bandit", message="minor issue"
        ),
    ]
    clusters = correlate(findings)
    assert [(cluster.representative.path, cluster.confirmations) for cluster in clusters] == [
        ("both.py", 2),
        ("solo.py", 1),
        ("low.py", 1),
    ]


def test_findings_are_ranked_most_severe_first() -> None:
    """The report is ordered by what matters most."""
    ordered = rank(
        [
            make_normalized_finding(severity="LOW"),
            make_normalized_finding(severity="CRITICAL"),
            make_normalized_finding(severity="MEDIUM"),
        ]
    )
    assert [finding.severity for finding in ordered] == ["CRITICAL", "MEDIUM", "LOW"]


def test_filtering_by_severity_keeps_the_threshold_itself() -> None:
    """A minimum severity is inclusive of that severity."""
    findings = [make_normalized_finding(severity=name) for name in CONST_SEVERITY_ORDER]
    kept = filter_by_severity(findings, "MEDIUM")
    assert [finding.severity for finding in kept] == ["CRITICAL", "HIGH", "MEDIUM"]


def test_the_summary_reports_severities_with_no_findings() -> None:
    """An absent CRITICAL count is indistinguishable from a scan that never looked."""
    assert summarize([make_normalized_finding(severity="HIGH")]) == {
        "CRITICAL": 0,
        "HIGH": 1,
        "MEDIUM": 0,
        "LOW": 0,
        "INFO": 0,
    }
