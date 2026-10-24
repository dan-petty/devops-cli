"""Property-based fuzzing tests for SARIF 2.1.0 parser and emitter.

Grounds all property assertions in the OASIS SARIF 2.1.0 specification:
- §3.2.7: version property requirement
- §3.13: sarifLog runs property requirement
- §3.14: run object and tool component definition
- §3.27: result object properties and severity level mappings
- §3.28: location and physicalLocation objects
"""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import Phase, example, given, settings
from hypothesis import strategies as st

from devops_cli.config.constants import CONST_SARIF_LEVEL_TO_SEVERITY, CONST_SARIF_VERSION
from devops_cli.security.normalization import NormalizedFinding
from devops_cli.security.sarif import SarifError, from_sarif, to_sarif

_FUZZ_SETTINGS = settings(
    phases=[Phase.explicit, Phase.generate],
    derandomize=True,
    max_examples=35,
    deadline=None,
)


# =============================================================================
# 1. Version Requirement & Top-Level Schema (§3.2.7, §3.13)
# =============================================================================


@_FUZZ_SETTINGS
@given(
    version=st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=20).filter(
        lambda v: v != CONST_SARIF_VERSION
    )
)
@example(version="2.0.0")
@example(version="1.0.0")
@example(version="")
@example(version="2.1.1")
def test_sarif_version_clause_3_2_7(version: str) -> None:
    """SARIF 2.1.0 §3.2.7: A SARIF log file SHALL declare version == '2.1.0'.

    Any other version string must cause from_sarif to raise SarifError.
    """
    doc = {"version": version, "runs": []}
    with pytest.raises(SarifError, match="Unsupported SARIF version"):
        from_sarif(doc)


@_FUZZ_SETTINGS
@given(
    non_obj=st.one_of(
        st.integers(),
        st.floats(),
        st.booleans(),
        st.text(max_size=20),
        st.lists(st.integers(), max_size=3),
    )
)
@example(non_obj=[])
@example(non_obj="sarif")
@example(non_obj=42)
def test_sarif_non_object_rejected_clause_3_13(non_obj: Any) -> None:
    """SARIF 2.1.0 §3.13: The root value of a SARIF log SHALL be a JSON object."""
    with pytest.raises(SarifError, match="SARIF document must be a JSON object"):
        from_sarif(non_obj)


@_FUZZ_SETTINGS
@given(
    invalid_runs=st.one_of(
        st.none(),
        st.integers(),
        st.text(max_size=20),
        st.dictionaries(st.text(max_size=5), st.text(max_size=5), max_size=2),
    )
)
@example(invalid_runs=None)
@example(invalid_runs="not-a-list")
@example(invalid_runs=123)
def test_sarif_missing_runs_array_clause_3_13_1(invalid_runs: Any) -> None:
    """SARIF 2.1.0 §3.13.1: A SARIF document is missing a 'runs' array."""
    doc = {"version": CONST_SARIF_VERSION, "runs": invalid_runs}
    with pytest.raises(SarifError, match="SARIF document is missing a 'runs' array"):
        from_sarif(doc)


# =============================================================================
# 2. Results Extraction and Invariants (§3.14, §3.27, §3.28)
# =============================================================================


@_FUZZ_SETTINGS
@given(
    tool_name=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=20),
    rule_id=st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-", min_size=1, max_size=20),
    level=st.sampled_from(["error", "warning", "note", "none"]),
    file_path=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_./", min_size=1, max_size=30),
    line_num=st.integers(min_value=1, max_value=10000),
    message_text=st.text(
        alphabet=st.characters(blacklist_categories=("Cs",)), min_size=1, max_size=50
    ),
)
@example(
    tool_name="semgrep",
    rule_id="SEC-001",
    level="error",
    file_path="src/main.py",
    line_num=42,
    message_text="Hardcoded token",
)
@example(
    tool_name="bandit",
    rule_id="B101",
    level="warning",
    file_path="test.py",
    line_num=1,
    message_text="assert used",
)
@example(
    tool_name="scanner",
    rule_id="INFO-1",
    level="none",
    file_path="doc.md",
    line_num=10,
    message_text="Informational notice",
)
def test_sarif_results_extraction_clause_3_27(
    tool_name: str,
    rule_id: str,
    level: str,
    file_path: str,
    line_num: int,
    message_text: str,
) -> None:
    """SARIF 2.1.0 §3.14 (run), §3.27 (result), §3.28 (location): from_sarif extracts normalized findings."""
    doc = {
        "version": CONST_SARIF_VERSION,
        "runs": [
            {
                "tool": {"driver": {"name": tool_name, "version": "1.0.0"}},
                "results": [
                    {
                        "ruleId": rule_id,
                        "level": level,
                        "message": {"text": message_text},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": file_path},
                                    "region": {"startLine": line_num},
                                }
                            }
                        ],
                    }
                ],
            }
        ],
    }

    findings = from_sarif(doc)
    assert len(findings) == 1
    f = findings[0]
    expected_severity = CONST_SARIF_LEVEL_TO_SEVERITY[level]

    assert (f.tool, f.rule_id, f.severity, f.path, f.line) == (
        tool_name,
        rule_id,
        expected_severity,
        file_path,
        line_num,
    )


# =============================================================================
# 3. Round-Trip Invariants (§3.13, §3.27)
# =============================================================================


@_FUZZ_SETTINGS
@given(
    rule_ids=st.lists(
        st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-", min_size=1, max_size=15),
        min_size=0,
        max_size=5,
    )
)
@example(rule_ids=[])
@example(rule_ids=["CWE-89"])
@example(rule_ids=["RULE-A", "RULE-B", "RULE-C"])
def test_sarif_roundtrip_invariants_clause_3_13(rule_ids: list[str]) -> None:
    """SARIF 2.1.0 §3.13, §3.27: to_sarif produces valid SARIF that round-trips via from_sarif."""
    original_findings = [
        NormalizedFinding(
            tool="devops-cli",
            rule_id=rid,
            severity="MEDIUM",
            message=f"Issue {rid}",
            path="src/file.py",
            line=10,
        )
        for rid in rule_ids
    ]

    doc = to_sarif(original_findings)
    assert doc.get("version") == CONST_SARIF_VERSION
    assert isinstance(doc.get("runs"), list)

    ingested = from_sarif(doc)
    assert len(ingested) == len(original_findings)
    assert [f.rule_id for f in ingested] == [f.rule_id for f in original_findings]
