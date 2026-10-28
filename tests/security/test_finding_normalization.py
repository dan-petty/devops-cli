"""How a scanner finding is normalized: its location, severity, rule identity, and the
conversion to and from the review's findings."""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.ai.review_schema import Finding
from devops_cli.config.constants import (
    CONST_SEVERITY_ORDER,
)
from devops_cli.security.normalization import (
    as_dict,
    extract_rule_id,
    normalize_finding,
    normalize_path,
    normalize_results,
    normalize_severity,
    severity_rank,
    split_location,
    strip_rule_prefix,
    to_finding,
)
from tests.support.builders import make_normalized_finding


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("src/app.py:42", ("src/app.py", 42, None)),
        ("src/app.py", ("src/app.py", None, None)),
        ("", ("", None, None)),
        (
            "manifests/deploy.yml:Deployment/api",
            ("manifests/deploy.yml", None, "Deployment/api"),
        ),
        (
            "registry.example.com/img:efficiency",
            ("registry.example.com/img", None, "efficiency"),
        ),
        ("/abs/path/file.py:7", ("/abs/path/file.py", 7, None)),
        (":1", ("", 1, None)),
        ("src/views.py:40-45", ("src/views.py", 40, None)),
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
    assert (normalize_severity("catastrophic"), normalize_severity(None)) == (
        "MEDIUM",
        "MEDIUM",
    )


def test_severity_ranking_orders_most_severe_first() -> None:
    """The rank is the sort key used by every report."""
    ranks = [severity_rank(name) for name in CONST_SEVERITY_ORDER]
    assert ranks == sorted(ranks)


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
    restored = to_finding(make_normalized_finding())
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
    payload = as_dict(make_normalized_finding())
    assert (payload["tool"], payload["rule_id"], len(payload["fingerprint"])) == (
        "bandit",
        "B602",
        64,
    )
