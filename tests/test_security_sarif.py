"""Test suite for the unified SARIF engine, finding taxonomy, correlation, and suppression."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.review_schema import Finding
from devops_cli.commands.scan import app as scan_app
from devops_cli.config.constants import (
    CONST_SARIF_FINGERPRINT_KEY,
    CONST_SARIF_LEVELS,
    CONST_SARIF_SCHEMA_URI,
    CONST_SARIF_VERSION,
    CONST_SEVERITY_ORDER,
)
from devops_cli.security.normalization import (
    NormalizedFinding,
    as_dict,
    correlate,
    deduplicate,
    extract_rule_id,
    filter_by_severity,
    normalize_finding,
    normalize_path,
    normalize_results,
    normalize_severity,
    rank,
    severity_rank,
    split_location,
    strip_rule_prefix,
    summarize,
    to_finding,
)
from devops_cli.security.pipeline import build_report, report_from_findings
from devops_cli.security.sarif import (
    SarifError,
    from_sarif,
    read_sarif,
    to_sarif,
    write_sarif,
)
from devops_cli.security.suppression import (
    SuppressionPolicyError,
    SuppressionRule,
    empty_policy,
    load_policy,
)

runner = CliRunner()


def make(
    tool: str = "bandit",
    rule_id: str = "B602",
    severity: str = "HIGH",
    message: str = "subprocess call with shell=True",
    path: str = "src/app.py",
    line: int | None = 4,
    **kwargs: Any,
) -> NormalizedFinding:
    """Build a normalized finding with sensible defaults."""
    return NormalizedFinding(
        tool=tool,
        rule_id=rule_id,
        severity=severity,
        message=message,
        path=path,
        line=line,
        **kwargs,
    )


# =============================================================================
# Location Parsing
# =============================================================================


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("src/app.py:42", ("src/app.py", 42, None)),
        ("src/app.py", ("src/app.py", None, None)),
        ("", ("", None, None)),
        ("manifests/deploy.yml:Deployment/api", ("manifests/deploy.yml", None, "Deployment/api")),
        ("registry.example.com/img:efficiency", ("registry.example.com/img", None, "efficiency")),
        ("/abs/path/file.py:7", ("/abs/path/file.py", 7, None)),
        (":1", ("", None, "1")),
        ("src/app.py:0", ("src/app.py", 0, None)),
    ],
)
def test_scanner_location_strings_are_split_into_structure(
    location: str, expected: tuple[str, int | None, str | None]
) -> None:
    """Scanners write several location shapes, and none may raise or lose information.

    Assuming an integer suffix would either crash on 'Deployment/api' or silently discard
    it, and SARIF needs the parts separated to build a physical location at all.
    """
    assert split_location(location) == expected


def test_a_windows_style_drive_letter_does_not_become_a_line_number() -> None:
    """Splitting on the last colon keeps a drive-qualified path intact."""
    assert split_location("C:/repo/app.py:12") == ("C:/repo/app.py", 12, None)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (".github/workflows/ci.yml", ".github/workflows/ci.yml"),
        ("./src/app.py", "src/app.py"),
        ("src/app.py", "src/app.py"),
        ("", ""),
    ],
)
def test_paths_are_normalized_without_mangling_leading_dots(raw: str, expected: str) -> None:
    """A dotfile directory must survive normalization.

    Stripping a character set rather than a prefix turns '.github/ci.yml' into
    'github/ci.yml', naming a directory that does not exist.
    """
    assert normalize_path(raw) == expected


def test_an_absolute_path_is_made_relative_to_the_scan_root() -> None:
    """Fingerprints must not change because a scan ran from a different directory."""
    assert normalize_path("/repo/src/app.py", base=Path("/repo")) == "src/app.py"


def test_an_absolute_path_outside_the_scan_root_is_left_alone() -> None:
    """A path that is not under the root cannot be made relative to it."""
    assert normalize_path("/elsewhere/app.py", base=Path("/repo")) == "/elsewhere/app.py"


# =============================================================================
# Severity Taxonomy
# =============================================================================


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("CRITICAL", "CRITICAL"),
        ("critical", "CRITICAL"),
        ("BLOCKER", "CRITICAL"),
        ("error", "HIGH"),
        ("HIGH", "HIGH"),
        ("moderate", "MEDIUM"),
        ("warning", "MEDIUM"),
        ("minor", "LOW"),
        ("note", "LOW"),
        ("informational", "INFO"),
        ("unknown", "INFO"),
        ("  high  ", "HIGH"),
    ],
)
def test_scanner_severity_vocabularies_map_onto_one_scale(raw: str, expected: str) -> None:
    """Each scanner spells severity differently; ranking requires one vocabulary."""
    assert normalize_severity(raw) == expected


def test_an_unrecognised_severity_is_not_silently_demoted() -> None:
    """Demoting an unknown severity to INFO is how a real issue drops out of a report."""
    assert (normalize_severity("catastrophic"), normalize_severity(None)) == ("MEDIUM", "MEDIUM")


def test_severity_ranking_orders_most_severe_first() -> None:
    """The rank is the sort key used by every report."""
    ranks = [severity_rank(name) for name in CONST_SEVERITY_ORDER]
    assert ranks == sorted(ranks)


# =============================================================================
# Rule Identity
# =============================================================================


def test_a_bracketed_rule_prefix_is_recovered_from_the_title() -> None:
    """Scanners smuggle the rule id into the title; SARIF needs it as a field."""
    assert extract_rule_id("[B105] Possible hardcoded password", "bandit") == "B105"


def test_a_title_without_a_rule_prefix_gets_a_derived_identifier() -> None:
    """SARIF requires a ruleId, so one is derived rather than left empty."""
    rule_id = extract_rule_id("Something went wrong", "semgrep")
    assert rule_id.startswith("semgrep.")


def test_a_derived_identifier_is_stable_across_cosmetic_differences() -> None:
    """The same defect worded with different spacing or case must share an id."""
    first = extract_rule_id("Insecure  Deserialization", "semgrep")
    second = extract_rule_id("insecure deserialization", "semgrep")
    assert first == second


def test_different_messages_get_different_derived_identifiers() -> None:
    """Distinct defects must not collapse onto one rule."""
    assert extract_rule_id("Issue A", "semgrep") != extract_rule_id("Issue B", "semgrep")


def test_a_rule_prefix_is_stripped_from_the_displayed_message() -> None:
    """The id is a field now, so repeating it in the message is noise."""
    assert strip_rule_prefix("[B602] shell=True identified") == "shell=True identified"


def test_a_non_identifier_bracketed_prefix_is_not_taken_as_a_rule() -> None:
    """A message that merely begins with a bracketed word has no rule id to recover."""
    assert extract_rule_id("[see docs for details] something", "trivy").startswith("trivy.")


# =============================================================================
# Fingerprints
# =============================================================================


def test_a_fingerprint_survives_the_finding_moving_to_a_new_line() -> None:
    """A finding pushed down by an unrelated edit is the same finding.

    Including the line would re-open every suppression the next time anything above it
    changed, which makes fingerprint-based suppression useless in practice.
    """
    assert make(line=4).fingerprint == make(line=91).fingerprint


def test_a_fingerprint_distinguishes_the_same_rule_in_different_files() -> None:
    """Accepting a finding in one file must not accept it everywhere."""
    assert make(path="src/a.py").fingerprint != make(path="src/b.py").fingerprint


def test_a_fingerprint_distinguishes_different_rules_in_one_file() -> None:
    """Two defects on the same line are two findings."""
    assert make(rule_id="B602").fingerprint != make(rule_id="B307").fingerprint


def test_a_fingerprint_distinguishes_the_same_rule_reported_by_two_tools() -> None:
    """Tools disagree about what a rule means, so their results are not interchangeable."""
    assert make(tool="bandit").fingerprint != make(tool="semgrep").fingerprint


def test_a_fingerprint_ignores_whitespace_differences_in_the_message() -> None:
    """A scanner reflowing its own message must not invalidate a suppression."""
    assert (
        make(message="shell=True  identified").fingerprint
        == make(message="shell=True identified").fingerprint
    )


# =============================================================================
# Deduplication and Correlation
# =============================================================================


def test_the_same_finding_reported_twice_is_collapsed() -> None:
    """Overlapping file subsets make a scanner report the same result more than once."""
    assert len(deduplicate([make(), make(line=90), make()])) == 1


def test_deduplication_keeps_genuinely_distinct_findings() -> None:
    """Collapsing too eagerly hides real results."""
    findings = [make(rule_id="B602"), make(rule_id="B307"), make(path="src/other.py")]
    assert len(deduplicate(findings)) == 3


def test_deduplication_preserves_the_first_occurrence() -> None:
    """The retained result should be the one the earliest scanner produced."""
    first = make(tool="bandit")
    assert deduplicate([first, make(tool="bandit", line=99)])[0] is first


def test_findings_from_different_tools_at_one_location_form_a_cluster() -> None:
    """A line several tools flagged is the observable fact worth surfacing."""
    clusters = correlate([make(tool="bandit"), make(tool="semgrep", rule_id="py.shell")])
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
    clusters = correlate([make(tool="bandit"), make(tool="semgrep", rule_id="py.shell")])
    assert len(clusters[0].findings) == 2


def test_findings_at_different_lines_do_not_cluster() -> None:
    """Location is part of the correlation identity."""
    assert len(correlate([make(line=4), make(line=40)])) == 2


def test_a_cluster_reports_the_most_severe_assessment_any_tool_made() -> None:
    """If one scanner calls it critical, reporting it as medium is the dangerous error."""
    cluster = correlate([make(tool="a", severity="LOW"), make(tool="b", severity="CRITICAL")])[0]
    assert cluster.severity == "CRITICAL"


def test_a_clusters_representative_is_its_most_severe_finding() -> None:
    """The row shown for a cluster should be its worst result."""
    cluster = correlate([make(tool="a", severity="LOW"), make(tool="b", severity="CRITICAL")])[0]
    assert cluster.representative.severity == "CRITICAL"


def test_clusters_are_ranked_by_severity_then_corroboration() -> None:
    """At equal severity, a line several tools flagged ranks above one only a single tool did."""
    findings = [
        make(path="solo.py", severity="HIGH", tool="bandit", message="solo issue"),
        make(path="both.py", severity="HIGH", tool="bandit", message="shared issue"),
        make(path="both.py", severity="HIGH", tool="semgrep", message="shared issue"),
        make(path="low.py", severity="LOW", tool="bandit", message="minor issue"),
    ]
    clusters = correlate(findings)
    assert [(cluster.representative.path, cluster.confirmations) for cluster in clusters] == [
        ("both.py", 2),
        ("solo.py", 1),
        ("low.py", 1),
    ]


def test_findings_are_ranked_most_severe_first() -> None:
    """The report is ordered by what matters most."""
    ordered = rank([make(severity="LOW"), make(severity="CRITICAL"), make(severity="MEDIUM")])
    assert [finding.severity for finding in ordered] == ["CRITICAL", "MEDIUM", "LOW"]


def test_filtering_by_severity_keeps_the_threshold_itself() -> None:
    """A minimum severity is inclusive of that severity."""
    findings = [make(severity=name) for name in CONST_SEVERITY_ORDER]
    kept = filter_by_severity(findings, "MEDIUM")
    assert [finding.severity for finding in kept] == ["CRITICAL", "HIGH", "MEDIUM"]


def test_the_summary_reports_severities_with_no_findings() -> None:
    """An absent CRITICAL count is indistinguishable from a scan that never looked."""
    assert summarize([make(severity="HIGH")]) == {
        "CRITICAL": 0,
        "HIGH": 1,
        "MEDIUM": 0,
        "LOW": 0,
        "INFO": 0,
    }


# =============================================================================
# Conversion To and From Scanner Findings
# =============================================================================


def test_a_scanner_finding_is_normalized_into_structure() -> None:
    """The whole pipeline depends on recovering structure from the display strings."""
    normalized = normalize_finding(
        Finding(
            severity="high",
            location="src/app.py:42",
            title="[B602] shell=True identified",
            description="Detail",
            fix="Use shell=False",
        ),
        tool="bandit",
    )
    assert (
        normalized.tool,
        normalized.rule_id,
        normalized.severity,
        normalized.path,
        normalized.line,
        normalized.message,
    ) == ("bandit", "B602", "HIGH", "src/app.py", 42, "shell=True identified")


def test_a_finding_with_no_title_falls_back_to_its_description() -> None:
    """An empty message would render an unreadable row and an empty SARIF result."""
    normalized = normalize_finding(
        Finding(severity="LOW", location="a.py:1", title="", description="Fallback text"),
        tool="trivy",
    )
    assert normalized.message == "Fallback text"


def test_registry_results_are_flattened_with_their_tool_names() -> None:
    """The tool is the key of the results mapping and must survive normalization."""
    results = {
        "bandit": [Finding(severity="HIGH", location="a.py:1", title="[B1] x")],
        "semgrep": [Finding(severity="LOW", location="b.py:2", title="[S1] y")],
    }
    normalized = normalize_results(results)
    assert sorted((finding.tool, finding.rule_id) for finding in normalized) == [
        ("bandit", "B1"),
        ("semgrep", "S1"),
    ]


def test_a_normalized_finding_converts_back_for_the_existing_renderers() -> None:
    """Existing tables consume Finding, so the conversion must round-trip."""
    restored = to_finding(make())
    assert (restored.severity, restored.location, restored.title) == (
        "HIGH",
        "src/app.py:4",
        "[B602] subprocess call with shell=True",
    )


def test_a_symbolic_locator_survives_the_round_trip() -> None:
    """A Kubernetes resource locator is not a line number and must not become one."""
    normalized = normalize_finding(
        Finding(severity="HIGH", location="deploy.yml:Deployment/api", title="[KL1] issue"),
        tool="kubelinter",
    )
    assert (normalized.symbol, to_finding(normalized).location) == (
        "Deployment/api",
        "deploy.yml:Deployment/api",
    )


def test_a_normalized_finding_serializes_with_its_fingerprint() -> None:
    """JSON consumers need the identity to suppress by."""
    payload = as_dict(make())
    assert (payload["tool"], payload["rule_id"], len(payload["fingerprint"])) == (
        "bandit",
        "B602",
        32,
    )


# =============================================================================
# SARIF Emission
# =============================================================================


def test_an_emitted_document_declares_the_supported_schema_and_version() -> None:
    """Consumers dispatch on these two fields before reading anything else."""
    document = to_sarif([make()])
    assert (document["$schema"], document["version"]) == (
        CONST_SARIF_SCHEMA_URI,
        CONST_SARIF_VERSION,
    )


def test_an_empty_scan_still_produces_a_valid_document() -> None:
    """Emitting nothing reads as 'the scan did not run', which is a different claim."""
    document = to_sarif([])
    assert (len(document["runs"]), document["runs"][0]["results"]) == (1, [])


def test_each_tool_gets_its_own_run() -> None:
    """A run carries exactly one tool driver, so merging misattributes findings."""
    document = to_sarif([make(tool="bandit"), make(tool="semgrep", rule_id="S1")])
    drivers = [run["tool"]["driver"]["name"] for run in document["runs"]]
    assert drivers == ["bandit", "semgrep"]


def test_every_emitted_level_is_one_sarif_defines() -> None:
    """A level outside the enumeration is rejected by SARIF consumers outright."""
    findings = [make(severity=name, rule_id=f"R{name}") for name in CONST_SEVERITY_ORDER]
    levels = {result["level"] for run in to_sarif(findings)["runs"] for result in run["results"]}
    assert levels <= CONST_SARIF_LEVELS


def test_results_reference_their_rule_by_index_and_id() -> None:
    """Both are required for a consumer to resolve the rule metadata."""
    document = to_sarif([make(rule_id="B602"), make(rule_id="B307", line=6, message="eval")])
    run = document["runs"][0]
    results = run["results"]
    assert [(result["ruleId"], result["ruleIndex"]) for result in results] == [
        ("B602", 0),
        ("B307", 1),
    ]


def test_a_repeated_rule_is_declared_once_and_referenced_twice() -> None:
    """Re-declaring a rule per result bloats the document and breaks rule-level config."""
    document = to_sarif([make(path="a.py"), make(path="b.py")])
    run = document["runs"][0]
    assert (len(run["tool"]["driver"]["rules"]), len(run["results"])) == (1, 2)


def test_a_result_carries_a_versioned_fingerprint() -> None:
    """An unversioned key would silently re-open suppressions if the scheme changed."""
    result = to_sarif([make()])["runs"][0]["results"][0]
    assert result["partialFingerprints"][CONST_SARIF_FINGERPRINT_KEY] == make().fingerprint


def test_a_rule_carries_the_security_severity_github_ranks_by() -> None:
    """GitHub code scanning orders by this property, not by the SARIF level."""
    rule = to_sarif([make(severity="CRITICAL")])["runs"][0]["tool"]["driver"]["rules"][0]
    assert rule["properties"]["security-severity"] == "9.5"


def test_a_finding_with_no_path_emits_no_location() -> None:
    """An empty artifact uri is invalid; omitting the location is not."""
    result = to_sarif([make(path="", line=None)])["runs"][0]["results"][0]
    assert "locations" not in result


def test_a_non_positive_line_emits_no_region() -> None:
    """SARIF regions are one-based, so line 0 is not expressible."""
    result = to_sarif([make(line=0)])["runs"][0]["results"][0]
    physical = result["locations"][0]["physicalLocation"]
    assert (physical["artifactLocation"]["uri"], "region" in physical) == ("src/app.py", False)


def test_a_symbolic_locator_is_emitted_as_a_logical_location() -> None:
    """A Kubernetes resource has no line, but it does have a name."""
    finding = make(line=None, symbol="Deployment/api", path="deploy.yml")
    location = to_sarif([finding])["runs"][0]["results"][0]["locations"][0]
    assert location["logicalLocations"] == [{"name": "Deployment/api"}]


def test_a_document_is_written_to_disk_as_json(tmp_path: Path) -> None:
    """The file has to be parseable by anything that reads SARIF."""
    destination = write_sarif([make()], tmp_path / "nested" / "out.sarif")
    document = json.loads(destination.read_text())
    assert document["runs"][0]["results"][0]["ruleId"] == "B602"


# =============================================================================
# SARIF Ingestion
# =============================================================================


def test_a_document_round_trips_through_emission_and_ingestion() -> None:
    """Emission and ingestion are inverses over the normalized taxonomy."""
    original = [
        make(tool="bandit", rule_id="B602", severity="HIGH"),
        make(tool="semgrep", rule_id="S1", severity="LOW", path="b.py", line=9, message="m"),
    ]
    restored = from_sarif(to_sarif(original))
    assert [(f.tool, f.rule_id, f.severity, f.path, f.line, f.message) for f in restored] == [
        (f.tool, f.rule_id, f.severity, f.path, f.line, f.message) for f in original
    ]


def test_fingerprints_survive_a_round_trip() -> None:
    """A suppression keyed on a fingerprint must still apply after a SARIF round trip."""
    original = make()
    assert from_sarif(to_sarif([original]))[0].fingerprint == original.fingerprint


def test_a_third_party_document_is_ingested_without_a_bespoke_parser() -> None:
    """Any SARIF-emitting tool joins the pipeline with no new parsing code.

    This is the shape CodeQL emits: severity carried as a numeric rule property rather than
    only as a level.
    """
    document = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "CodeQL",
                        "rules": [
                            {
                                "id": "py/clear-text-logging",
                                "shortDescription": {"text": "Clear-text logging"},
                                "fullDescription": {"text": "Sensitive data logged."},
                                "help": {"text": "Redact before logging."},
                                "properties": {"security-severity": "7.5"},
                            }
                        ],
                    }
                },
                "results": [
                    {
                        "ruleId": "py/clear-text-logging",
                        "ruleIndex": 0,
                        "level": "warning",
                        "message": {"text": "Sensitive value logged here."},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "src/auth.py"},
                                    "region": {"startLine": 88},
                                }
                            }
                        ],
                    }
                ],
            }
        ],
    }
    findings = from_sarif(document)
    assert (
        findings[0].tool,
        findings[0].rule_id,
        findings[0].severity,
        findings[0].path,
        findings[0].line,
        findings[0].fix,
    ) == ("CodeQL", "py/clear-text-logging", "HIGH", "src/auth.py", 88, "Redact before logging.")


def test_a_numeric_security_severity_outranks_the_coarser_level() -> None:
    """`level` collapses critical and high into `error`, losing the triage ordering."""
    document = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "CodeQL",
                        "rules": [{"id": "r", "properties": {"security-severity": "9.8"}}],
                    }
                },
                "results": [{"ruleId": "r", "level": "error", "message": {"text": "m"}}],
            }
        ],
    }
    assert from_sarif(document)[0].severity == "CRITICAL"


@pytest.mark.parametrize(
    ("score", "expected"),
    [("9.0", "CRITICAL"), ("7.0", "HIGH"), ("4.0", "MEDIUM"), ("0.5", "LOW"), ("0.0", "INFO")],
)
def test_security_severity_scores_band_as_github_documents(score: str, expected: str) -> None:
    """Banding differently from GitHub would rank the same document two ways."""
    document = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "t",
                        "rules": [{"id": "r", "properties": {"security-severity": score}}],
                    }
                },
                "results": [{"ruleId": "r", "message": {"text": "m"}}],
            }
        ],
    }
    assert from_sarif(document)[0].severity == expected


def test_a_result_with_no_level_defaults_as_the_specification_says() -> None:
    """SARIF's default level when unspecified is 'warning'."""
    document = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "t"}},
                "results": [{"ruleId": "r", "message": {"text": "m"}}],
            }
        ],
    }
    assert from_sarif(document)[0].severity == "MEDIUM"


def test_a_run_with_no_results_contributes_nothing() -> None:
    """A clean tool is not an error."""
    document = {"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "t"}}, "results": []}]}
    assert from_sarif(document) == []


def test_an_unnamed_driver_does_not_lose_the_run() -> None:
    """A malformed driver must not discard the findings beneath it."""
    document = {
        "version": "2.1.0",
        "runs": [{"tool": {}, "results": [{"ruleId": "r", "message": {"text": "m"}}]}],
    }
    assert from_sarif(document)[0].tool == "unknown"


def test_a_malformed_result_is_skipped_rather_than_failing_the_document() -> None:
    """Discarding a whole scan over one bad entry loses every real finding with it."""
    document = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "t"}},
                "results": [
                    "not-an-object",
                    {"ruleId": "good", "message": {"text": "kept"}},
                ],
            }
        ],
    }
    findings = from_sarif(document)
    assert (len(findings), findings[0].rule_id) == (1, "good")


@pytest.mark.parametrize(
    ("description", "document"),
    [
        ("not an object", ["runs"]),
        ("missing version", {"runs": []}),
        ("unsupported version", {"version": "1.0.0", "runs": []}),
        ("missing runs", {"version": "2.1.0"}),
        ("runs not a list", {"version": "2.1.0", "runs": {}}),
    ],
)
def test_a_document_that_is_not_sarif_is_rejected(description: str, document: Any) -> None:
    """Silently returning no findings would read as a clean scan."""
    with pytest.raises(SarifError):
        from_sarif(document)


def test_reading_a_file_that_is_not_json_reports_the_file(tmp_path: Path) -> None:
    """The error has to name what could not be read."""
    path = tmp_path / "broken.sarif"
    path.write_text("{not json")
    with pytest.raises(SarifError, match=re.escape("broken.sarif")):
        read_sarif(path)


def test_reading_a_written_document_recovers_its_findings(tmp_path: Path) -> None:
    """The file written and the file read are the same document."""
    destination = write_sarif([make()], tmp_path / "out.sarif")
    assert read_sarif(destination)[0].rule_id == "B602"


# =============================================================================
# Suppression Policy
# =============================================================================


def write_policy(path: Path, body: str) -> Path:
    """Write a suppression policy file."""
    path.write_text(body)
    return path


def test_a_rule_glob_suppresses_matching_findings(tmp_path: Path) -> None:
    """Suppressing by rule is the common case."""
    policy = load_policy(
        write_policy(
            tmp_path / "p.yml",
            "suppressions:\n  - rule: B6*\n    reason: accepted\n",
        )
    )
    kept, suppressed = policy.apply([make(rule_id="B602"), make(rule_id="B307")])
    assert ([f.rule_id for f in kept], len(suppressed)) == (["B307"], 1)


def test_a_path_glob_scopes_a_suppression(tmp_path: Path) -> None:
    """A suppression accepted for test fixtures must not apply to production code."""
    policy = load_policy(
        write_policy(
            tmp_path / "p.yml",
            'suppressions:\n  - rule: "*"\n    paths: ["tests/**"]\n',
        )
    )
    kept, _ = policy.apply([make(path="tests/fixtures/a.py"), make(path="src/app.py")])
    assert [finding.path for finding in kept] == ["src/app.py"]


def test_a_tool_glob_scopes_a_suppression(tmp_path: Path) -> None:
    """Accepting one tool's opinion must not silence another's."""
    policy = load_policy(write_policy(tmp_path / "p.yml", 'suppressions:\n  - tools: ["bandit"]\n'))
    kept, _ = policy.apply([make(tool="bandit"), make(tool="semgrep")])
    assert [finding.tool for finding in kept] == ["semgrep"]


def test_a_fingerprint_suppression_matches_exactly_one_finding(tmp_path: Path) -> None:
    """A fingerprint accepts one specific result, not a class of them."""
    target = make()
    policy = load_policy(
        write_policy(tmp_path / "p.yml", f"suppressions:\n  - fingerprint: {target.fingerprint}\n")
    )
    kept, suppressed = policy.apply([target, make(path="other.py")])
    assert ([f.path for f in kept], len(suppressed)) == (["other.py"], 1)


def test_an_expired_suppression_stops_suppressing(tmp_path: Path) -> None:
    """A suppression that never lapses is indistinguishable from a blind spot."""
    policy = load_policy(
        write_policy(
            tmp_path / "p.yml",
            "suppressions:\n  - rule: B602\n    expires: 2020-01-01\n",
        )
    )
    kept, suppressed = policy.apply([make()], today=date(2026, 9, 21))
    assert (len(kept), len(suppressed)) == (1, 0)


def test_a_suppression_expiring_today_is_still_in_force(tmp_path: Path) -> None:
    """Expiry is end-of-day, so a policy does not lapse a day early."""
    policy = load_policy(
        write_policy(
            tmp_path / "p.yml",
            "suppressions:\n  - rule: B602\n    expires: 2026-09-21\n",
        )
    )
    kept, _ = policy.apply([make()], today=date(2026, 9, 21))
    assert kept == []


def test_an_unparseable_expiry_is_treated_as_expired(tmp_path: Path) -> None:
    """Defaulting a typo to 'never' turns a mistake into a permanent suppression."""
    policy = load_policy(
        write_policy(
            tmp_path / "p.yml",
            "suppressions:\n  - rule: B602\n    expires: not-a-date\n",
        )
    )
    kept, _ = policy.apply([make()])
    assert len(kept) == 1


def test_expired_rules_are_reported_for_review(tmp_path: Path) -> None:
    """A lapsed suppression should prompt a decision, not vanish silently."""
    policy = load_policy(
        write_policy(
            tmp_path / "p.yml",
            "suppressions:\n  - rule: B602\n    expires: 2020-01-01\n",
        )
    )
    assert [rule.rule for rule in policy.expired_rules(date(2026, 9, 21))] == ["B602"]


def test_a_policy_inherits_rules_from_the_baseline_it_extends(tmp_path: Path) -> None:
    """A shared baseline must not be copied into every repository that needs it."""
    write_policy(tmp_path / "base.yml", "suppressions:\n  - rule: SHARED\n")
    policy = load_policy(
        write_policy(
            tmp_path / "child.yml",
            "extends: base.yml\nsuppressions:\n  - rule: LOCAL\n",
        )
    )
    assert [rule.rule for rule in policy.rules] == ["LOCAL", "SHARED"]


def test_local_rules_are_matched_before_inherited_ones(tmp_path: Path) -> None:
    """A repository must be able to override a baseline, not only add to it."""
    write_policy(tmp_path / "base.yml", 'suppressions:\n  - rule: "*"\n    reason: baseline\n')
    policy = load_policy(
        write_policy(
            tmp_path / "child.yml",
            'extends: base.yml\nsuppressions:\n  - rule: "B602"\n    reason: local\n',
        )
    )
    rule = policy.suppresses(make())
    assert rule is not None
    assert rule.reason == "local"


def test_a_policy_extending_several_baselines_collects_all_of_them(tmp_path: Path) -> None:
    """Composition is the point of inheritance."""
    write_policy(tmp_path / "a.yml", "suppressions:\n  - rule: A\n")
    write_policy(tmp_path / "b.yml", "suppressions:\n  - rule: B\n")
    policy = load_policy(write_policy(tmp_path / "child.yml", "extends: [a.yml, b.yml]\n"))
    assert sorted(rule.rule for rule in policy.rules) == ["A", "B"]


def test_a_baseline_reached_twice_is_loaded_once(tmp_path: Path) -> None:
    """Two policies extending a common baseline is ordinary, not a cycle."""
    write_policy(tmp_path / "base.yml", "suppressions:\n  - rule: SHARED\n")
    write_policy(tmp_path / "left.yml", "extends: base.yml\n")
    write_policy(tmp_path / "right.yml", "extends: base.yml\n")
    policy = load_policy(write_policy(tmp_path / "child.yml", "extends: [left.yml, right.yml]\n"))
    assert [rule.rule for rule in policy.rules] == ["SHARED"]


def test_a_cyclic_inheritance_chain_terminates(tmp_path: Path) -> None:
    """A policy that extends itself must not recurse until the interpreter stops it."""
    write_policy(tmp_path / "a.yml", "extends: b.yml\nsuppressions:\n  - rule: A\n")
    write_policy(tmp_path / "b.yml", "extends: a.yml\nsuppressions:\n  - rule: B\n")
    policy = load_policy(tmp_path / "a.yml")
    assert sorted(rule.rule for rule in policy.rules) == ["A", "B"]


def test_a_parent_is_resolved_relative_to_the_file_that_names_it(tmp_path: Path) -> None:
    """A shared baseline can sit outside the repository being scanned."""
    (tmp_path / "shared").mkdir()
    (tmp_path / "repo").mkdir()
    write_policy(tmp_path / "shared" / "base.yml", "suppressions:\n  - rule: SHARED\n")
    policy = load_policy(write_policy(tmp_path / "repo" / "p.yml", "extends: ../shared/base.yml\n"))
    assert [rule.rule for rule in policy.rules] == ["SHARED"]


def test_a_missing_policy_file_is_an_error(tmp_path: Path) -> None:
    """Scanning without a policy the operator asked for reports accepted findings."""
    with pytest.raises(SuppressionPolicyError):
        load_policy(tmp_path / "absent.yml")


def test_a_policy_that_is_not_a_mapping_is_rejected(tmp_path: Path) -> None:
    """A list at the top level is a common mistake and must not be read as empty."""
    with pytest.raises(SuppressionPolicyError):
        load_policy(write_policy(tmp_path / "p.yml", "- rule: B602\n"))


def test_a_suppressions_key_that_is_not_a_list_is_rejected(tmp_path: Path) -> None:
    """Silently ignoring it would suppress nothing while appearing configured."""
    with pytest.raises(SuppressionPolicyError):
        load_policy(write_policy(tmp_path / "p.yml", "suppressions: B602\n"))


def test_invalid_yaml_reports_the_file(tmp_path: Path) -> None:
    """The error names the file so it can be fixed."""
    with pytest.raises(SuppressionPolicyError, match=re.escape("p.yml")):
        load_policy(write_policy(tmp_path / "p.yml", "suppressions: [unclosed\n"))


def test_an_empty_policy_file_suppresses_nothing(tmp_path: Path) -> None:
    """A placeholder file is valid and inert."""
    policy = load_policy(write_policy(tmp_path / "p.yml", "\n"))
    kept, suppressed = policy.apply([make()])
    assert (len(kept), len(suppressed)) == (1, 0)


def test_an_empty_policy_object_suppresses_nothing() -> None:
    """The default when no policy is configured."""
    kept, suppressed = empty_policy().apply([make()])
    assert (len(kept), len(suppressed)) == (1, 0)


def test_a_rule_without_a_fingerprint_matches_by_pattern() -> None:
    """The two matching modes are exclusive; a fingerprint overrides the patterns."""
    rule = SuppressionRule(rule="B602", fingerprint="deadbeef")
    assert rule.matches(make()) is False


# =============================================================================
# Report Pipeline
# =============================================================================


def test_a_report_deduplicates_and_correlates_scanner_output(tmp_path: Path) -> None:
    """The whole point of the pipeline is one coherent result rather than N tables."""
    results = {
        "bandit": [
            Finding(severity="HIGH", location="src/app.py:4", title="[B602] shell true"),
            Finding(severity="HIGH", location="src/app.py:4", title="[B602] shell true"),
        ],
        "semgrep": [
            Finding(severity="HIGH", location="src/app.py:4", title="[S1] shell true"),
        ],
    }
    report = build_report(results, tmp_path)
    assert (report.total, report.duplicates_removed, len(report.clusters)) == (2, 1, 1)


def test_a_report_counts_every_severity(tmp_path: Path) -> None:
    """A missing key would be read as a severity that was never checked."""
    report = build_report({"bandit": []}, tmp_path)
    assert report.counts == dict.fromkeys(CONST_SEVERITY_ORDER, 0)


def test_suppression_is_applied_before_deduplication(tmp_path: Path) -> None:
    """The suppressed list must name every occurrence hidden, not just the first.

    Reporting one suppression where a rule silenced four understates what the policy does.
    """
    policy = load_policy(write_policy(tmp_path / "p.yml", "suppressions:\n  - rule: B602\n"))
    results = {
        "bandit": [
            Finding(severity="HIGH", location="src/app.py:4", title="[B602] shell true"),
            Finding(severity="HIGH", location="src/app.py:4", title="[B602] shell true"),
        ]
    }
    report = build_report(results, tmp_path, policy=policy)
    assert (report.total, len(report.suppressed)) == (0, 2)


def test_a_minimum_severity_filters_the_report(tmp_path: Path) -> None:
    """A noisy INFO stream drowns the findings that matter."""
    results = {
        "bandit": [
            Finding(severity="INFO", location="a.py:1", title="[I1] minor"),
            Finding(severity="CRITICAL", location="b.py:2", title="[C1] severe"),
        ]
    }
    report = build_report(results, tmp_path, min_severity="HIGH")
    assert [finding.rule_id for finding in report.findings] == ["C1"]


def test_a_report_identifies_its_most_severe_finding(tmp_path: Path) -> None:
    """The gate threshold is evaluated against this."""
    results = {
        "bandit": [
            Finding(severity="LOW", location="a.py:1", title="[L] minor"),
            Finding(severity="CRITICAL", location="b.py:2", title="[C] severe"),
        ]
    }
    assert build_report(results, tmp_path).highest_severity() == "CRITICAL"


def test_an_empty_report_has_no_highest_severity(tmp_path: Path) -> None:
    """A clean scan must not be reported as having a severity."""
    assert build_report({"bandit": []}, tmp_path).highest_severity() is None


@pytest.mark.parametrize(
    ("severity", "threshold", "expected"),
    [
        ("CRITICAL", "HIGH", True),
        ("HIGH", "HIGH", True),
        ("MEDIUM", "HIGH", False),
        ("INFO", "INFO", True),
    ],
)
def test_the_gate_threshold_is_inclusive(
    severity: str, threshold: str, expected: bool, tmp_path: Path
) -> None:
    """A gate set at HIGH must fail on a HIGH finding, not only above it."""
    results = {"bandit": [Finding(severity=severity, location="a.py:1", title="[R] issue")]}
    assert build_report(results, tmp_path).exceeds(threshold) is expected


def test_an_empty_report_never_trips_the_gate(tmp_path: Path) -> None:
    """A clean scan must not fail the build."""
    assert build_report({"bandit": []}, tmp_path).exceeds("INFO") is False


def test_a_report_serializes_for_json_consumers(tmp_path: Path) -> None:
    """Machine consumers need the counts, the clusters and the fingerprints."""
    results = {"bandit": [Finding(severity="HIGH", location="a.py:1", title="[B1] issue")]}
    payload = build_report(results, tmp_path).as_dict()
    assert (payload["total"], payload["tools"], payload["counts"]["HIGH"]) == (1, ["bandit"], 1)


def test_a_report_can_be_built_from_ingested_sarif() -> None:
    """An imported document flows through the same suppression and ranking."""
    report = report_from_findings([make(), make(line=90)], "imported.sarif")
    assert (report.total, report.duplicates_removed) == (1, 1)


# =============================================================================
# CLI
# =============================================================================


def test_the_report_command_renders_correlated_findings(tmp_path: Path) -> None:
    """The command is the pipeline's only user-facing surface."""
    results = {"bandit": [Finding(severity="HIGH", location="a.py:4", title="[B602] shell true")]}
    with (
        patch(
            "devops_cli.security.registry.ScannerRegistry.list_scanners", return_value=["bandit"]
        ),
        patch("devops_cli.security.registry.ScannerRegistry.get") as mock_get,
    ):
        mock_get.return_value.scan.return_value = results["bandit"]
        result = runner.invoke(scan_app, ["report", str(tmp_path)])
    assert (result.exit_code, "B602" in result.stdout) == (0, True)


def test_the_report_command_rejects_an_unknown_scanner(tmp_path: Path) -> None:
    """A typo must not silently scan with nothing and report success."""
    result = runner.invoke(scan_app, ["report", str(tmp_path), "--scanner", "nosuchtool"])
    assert result.exit_code == 2


def test_the_report_command_fails_the_build_on_a_severe_finding(tmp_path: Path) -> None:
    """The gate is what makes the command usable in CI."""
    findings = [Finding(severity="CRITICAL", location="a.py:4", title="[C1] severe")]
    with (
        patch(
            "devops_cli.security.registry.ScannerRegistry.list_scanners", return_value=["bandit"]
        ),
        patch("devops_cli.security.registry.ScannerRegistry.get") as mock_get,
    ):
        mock_get.return_value.scan.return_value = findings
        result = runner.invoke(scan_app, ["report", str(tmp_path), "--fail-on", "HIGH"])
    assert result.exit_code == 1


def test_the_report_command_passes_when_nothing_meets_the_gate(tmp_path: Path) -> None:
    """A gate that always fails is a gate nobody keeps."""
    findings = [Finding(severity="LOW", location="a.py:4", title="[L1] minor")]
    with (
        patch(
            "devops_cli.security.registry.ScannerRegistry.list_scanners", return_value=["bandit"]
        ),
        patch("devops_cli.security.registry.ScannerRegistry.get") as mock_get,
    ):
        mock_get.return_value.scan.return_value = findings
        result = runner.invoke(scan_app, ["report", str(tmp_path), "--fail-on", "HIGH"])
    assert result.exit_code == 0


def test_the_report_command_writes_sarif(tmp_path: Path) -> None:
    """Exporting is how findings reach GitHub code scanning."""
    findings = [Finding(severity="HIGH", location="a.py:4", title="[B602] shell true")]
    destination = tmp_path / "out.sarif"
    with (
        patch(
            "devops_cli.security.registry.ScannerRegistry.list_scanners", return_value=["bandit"]
        ),
        patch("devops_cli.security.registry.ScannerRegistry.get") as mock_get,
    ):
        mock_get.return_value.scan.return_value = findings
        result = runner.invoke(scan_app, ["report", str(tmp_path), "--sarif", str(destination)])
    document = json.loads(destination.read_text())
    assert (result.exit_code, document["version"]) == (0, CONST_SARIF_VERSION)


def test_a_failing_scanner_does_not_discard_the_others(tmp_path: Path) -> None:
    """One broken tool must not lose every other tool's findings."""
    good = [Finding(severity="HIGH", location="a.py:4", title="[B602] shell true")]

    def scanner_for(name: str) -> Any:
        from unittest.mock import MagicMock

        scanner = MagicMock()
        if name == "broken":
            scanner.scan.side_effect = RuntimeError("scanner crashed")
        else:
            scanner.scan.return_value = good
        return scanner

    with (
        patch(
            "devops_cli.security.registry.ScannerRegistry.list_scanners",
            return_value=["broken", "bandit"],
        ),
        patch("devops_cli.security.registry.ScannerRegistry.get", side_effect=scanner_for),
    ):
        result = runner.invoke(scan_app, ["report", str(tmp_path), "--json"])
    assert (result.exit_code, "B602" in result.stdout) == (0, True)


def test_the_sarif_command_ingests_a_document(tmp_path: Path) -> None:
    """Third-party SARIF joins the same report."""
    destination = write_sarif([make()], tmp_path / "in.sarif")
    result = runner.invoke(scan_app, ["sarif", str(destination)])
    assert (result.exit_code, "B602" in result.stdout) == (0, True)


def test_the_sarif_command_rejects_a_document_that_is_not_sarif(tmp_path: Path) -> None:
    """Reporting a clean scan for an unreadable document is the dangerous outcome."""
    path = tmp_path / "bad.sarif"
    path.write_text('{"version": "1.0.0"}')
    result = runner.invoke(scan_app, ["sarif", str(path)])
    assert result.exit_code == 2


def test_the_sarif_command_applies_a_suppression_policy(tmp_path: Path) -> None:
    """Suppression applies equally to ingested findings."""
    destination = write_sarif([make()], tmp_path / "in.sarif")
    policy = write_policy(tmp_path / "p.yml", "suppressions:\n  - rule: B602\n")
    result = runner.invoke(
        scan_app, ["sarif", str(destination), "--suppress", str(policy), "--json"]
    )
    payload = json.loads(result.stdout)
    assert (result.exit_code, payload["total"], payload["suppressed"]) == (0, 0, 1)


def test_an_unreadable_suppression_policy_stops_the_scan(tmp_path: Path) -> None:
    """Continuing without the policy reports findings the operator believes are accepted."""
    destination = write_sarif([make()], tmp_path / "in.sarif")
    result = runner.invoke(
        scan_app, ["sarif", str(destination), "--suppress", str(tmp_path / "absent.yml")]
    )
    assert result.exit_code == 2


# =============================================================================
# Malformed SARIF Structures
# =============================================================================


def _document(results: list[Any], rules: list[Any] | None = None, tool: Any = None) -> Any:
    """Build a minimal SARIF document around the given results."""
    driver: dict[str, Any] = {"name": "t"}
    if rules is not None:
        driver["rules"] = rules
    return {
        "version": "2.1.0",
        "runs": [{"tool": tool if tool is not None else {"driver": driver}, "results": results}],
    }


def test_a_rule_resolved_only_by_index_is_still_found() -> None:
    """Some emitters omit ruleId on the result and reference the rule positionally."""
    document = _document(
        [{"ruleIndex": 1, "message": {"text": "m"}}],
        rules=[{"id": "first"}, {"id": "second", "help": {"text": "guidance"}}],
    )
    assert from_sarif(document)[0].fix == "guidance"


def test_an_out_of_range_rule_index_does_not_raise() -> None:
    """A malformed index must not take down the ingest."""
    document = _document([{"ruleIndex": 99, "message": {"text": "m"}}], rules=[{"id": "only"}])
    assert from_sarif(document)[0].message == "m"


def test_a_severity_declared_on_the_result_is_honoured() -> None:
    """Documents this tool emitted carry the original severity as a result property."""
    document = _document(
        [{"ruleId": "r", "message": {"text": "m"}, "properties": {"severity": "CRITICAL"}}]
    )
    assert from_sarif(document)[0].severity == "CRITICAL"


def test_a_non_numeric_security_severity_falls_back_to_the_level() -> None:
    """A malformed score must not be read as zero and demote the finding to INFO."""
    document = _document(
        [{"ruleId": "r", "level": "error", "message": {"text": "m"}}],
        rules=[{"id": "r", "properties": {"security-severity": "not-a-number"}}],
    )
    assert from_sarif(document)[0].severity == "HIGH"


def test_an_unrecognised_level_falls_back_to_the_specified_default() -> None:
    """A level outside the enumeration is not a reason to drop the result."""
    document = _document([{"ruleId": "r", "level": "catastrophic", "message": {"text": "m"}}])
    assert from_sarif(document)[0].severity == "MEDIUM"


def test_a_plain_string_message_is_read() -> None:
    """Not every emitter wraps its message in the multiformat object."""
    document = _document([{"ruleId": "r", "message": "flat text"}])
    assert from_sarif(document)[0].message == "flat text"


def test_a_result_with_no_message_falls_back_to_its_rule_id() -> None:
    """An empty message renders an unreadable row."""
    document = _document([{"ruleId": "r"}])
    assert from_sarif(document)[0].message == "r"


def test_a_result_with_no_rule_id_at_all_still_gets_one() -> None:
    """SARIF requires a ruleId downstream even when the source omitted it."""
    document = _document([{"message": {"text": "m"}}])
    assert from_sarif(document)[0].rule_id == "t.unknown"


@pytest.mark.parametrize(
    ("description", "locations"),
    [
        ("not a list", {"physicalLocation": {}}),
        ("empty list", []),
        ("first entry not an object", ["nonsense"]),
        ("no physical location", [{}]),
        ("artifact location not an object", [{"physicalLocation": {"artifactLocation": 1}}]),
        (
            "region without a start line",
            [{"physicalLocation": {"artifactLocation": {"uri": "a.py"}, "region": {}}}],
        ),
        (
            "non-positive start line",
            [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": "a.py"},
                        "region": {"startLine": 0},
                    }
                }
            ],
        ),
    ],
)
def test_malformed_locations_never_raise(description: str, locations: Any) -> None:
    """A location this code cannot read costs the location, not the finding."""
    document = _document([{"ruleId": "r", "message": {"text": "m"}, "locations": locations}])
    findings = from_sarif(document)
    assert (len(findings), findings[0].line) == (1, None), description


def test_an_empty_logical_location_name_is_ignored() -> None:
    """A blank name is not a symbol."""
    document = _document(
        [
            {
                "ruleId": "r",
                "message": {"text": "m"},
                "locations": [{"logicalLocations": [{"name": "   "}]}],
            }
        ]
    )
    assert from_sarif(document)[0].symbol is None


def test_a_run_that_is_not_an_object_is_skipped() -> None:
    """One bad run must not discard the others."""
    document = {
        "version": "2.1.0",
        "runs": ["nonsense", {"tool": {"driver": {"name": "t"}}, "results": [{"ruleId": "kept"}]}],
    }
    assert from_sarif(document)[0].rule_id == "kept"


def test_a_run_whose_results_are_not_a_list_is_skipped() -> None:
    """A malformed results array yields nothing rather than raising."""
    document = {
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "t"}}, "results": "nonsense"}],
    }
    assert from_sarif(document) == []


def test_a_driver_with_a_blank_name_falls_back() -> None:
    """A whitespace name would render an unlabelled tool column."""
    document = _document([{"ruleId": "r"}], tool={"driver": {"name": "   "}})
    assert from_sarif(document)[0].tool == "unknown"


def test_rules_that_are_not_a_list_are_ignored() -> None:
    """A malformed rules array must not break rule resolution."""
    document = _document([{"ruleId": "r", "message": {"text": "m"}}], rules=None)
    document["runs"][0]["tool"]["driver"]["rules"] = "nonsense"
    assert from_sarif(document)[0].rule_id == "r"


def test_a_non_mapping_rule_entry_is_ignored() -> None:
    """One bad rule descriptor must not hide the good ones."""
    document = _document(
        [{"ruleId": "good", "message": {"text": "m"}}],
        rules=["nonsense", {"id": "good", "help": {"text": "guidance"}}],
    )
    assert from_sarif(document)[0].fix == "guidance"
