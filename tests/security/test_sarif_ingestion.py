"""Reading a SARIF document from any tool, including the malformed structures a reader meets."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from devops_cli.security.sarif import (
    SarifError,
    from_sarif,
    read_sarif,
    to_sarif,
    write_sarif,
)
from tests.support.builders import make_normalized_finding


def test_a_document_round_trips_through_emission_and_ingestion() -> None:
    """Emission and ingestion are inverses over the normalized taxonomy."""
    original = [
        make_normalized_finding(tool="bandit", rule_id="B602", severity="HIGH"),
        make_normalized_finding(
            tool="semgrep",
            rule_id="S1",
            severity="LOW",
            path="b.py",
            line=9,
            message="m",
        ),
    ]
    restored = from_sarif(to_sarif(original))
    assert [(f.tool, f.rule_id, f.severity, f.path, f.line, f.message) for f in restored] == [
        (f.tool, f.rule_id, f.severity, f.path, f.line, f.message) for f in original
    ]


def test_fingerprints_survive_a_round_trip() -> None:
    """A suppression keyed on a fingerprint must still apply after a SARIF round trip."""
    original = make_normalized_finding()
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
    ) == (
        "CodeQL",
        "py/clear-text-logging",
        "HIGH",
        "src/auth.py",
        88,
        "Redact before logging.",
    )


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
    [
        ("9.0", "CRITICAL"),
        ("7.0", "HIGH"),
        ("4.0", "MEDIUM"),
        ("0.5", "LOW"),
        ("0.0", "INFO"),
    ],
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
    document = {
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "t"}}, "results": []}],
    }
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
    with pytest.raises(SarifError) as raised:
        from_sarif(document)
    assert str(raised.value) != ""


def test_reading_a_file_that_is_not_json_reports_the_file(tmp_path: Path) -> None:
    """The error has to name what could not be read."""
    path = tmp_path / "broken.sarif"
    path.write_text("{not json")
    with pytest.raises(SarifError, match=re.escape("broken.sarif")):
        read_sarif(path)


def test_reading_a_written_document_recovers_its_findings(tmp_path: Path) -> None:
    """The file written and the file read are the same document."""
    destination = write_sarif([make_normalized_finding()], tmp_path / "out.sarif")
    assert read_sarif(destination)[0].rule_id == "B602"


def _document(results: list[Any], rules: list[Any] | None = None, tool: Any = None) -> Any:
    """Build a minimal SARIF document around the given results."""
    driver: dict[str, Any] = {"name": "t"}
    if rules is not None:
        driver["rules"] = rules
    return {
        "version": "2.1.0",
        "runs": [
            {
                "tool": tool if tool is not None else {"driver": driver},
                "results": results,
            }
        ],
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
        [
            {
                "ruleId": "r",
                "message": {"text": "m"},
                "properties": {"severity": "CRITICAL"},
            }
        ]
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
        (
            "artifact location not an object",
            [{"physicalLocation": {"artifactLocation": 1}}],
        ),
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
        "runs": [
            "nonsense",
            {"tool": {"driver": {"name": "t"}}, "results": [{"ruleId": "kept"}]},
        ],
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
