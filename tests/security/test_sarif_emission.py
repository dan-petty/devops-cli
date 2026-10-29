"""The SARIF 2.1.0 document that devops-cli writes: runs, rules, results, scanner outcomes and
tool run records."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import jsonschema
import pytest
from syrupy.assertion import SnapshotAssertion

from devops_cli.config.constants import (
    CONST_SARIF_FINGERPRINT_KEY,
    CONST_SARIF_LEVELS,
    CONST_SARIF_SCHEMA_URI,
    CONST_SARIF_SECURITY_SEVERITY_PROPERTY,
    CONST_SARIF_VERSION,
    CONST_SEVERITY_ORDER,
)
from devops_cli.security.base import ScanOutcome
from devops_cli.security.sarif import (
    to_sarif,
    write_sarif,
)
from devops_cli.security.tool_executor import ToolRun
from tests.support.builders import make_normalized_finding
from tests.support.paths import FIXTURES


def test_an_emitted_document_declares_the_supported_schema_and_version() -> None:
    """Consumers dispatch on these two fields before reading anything else."""
    document = to_sarif([make_normalized_finding()])
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
    document = to_sarif(
        [
            make_normalized_finding(tool="bandit"),
            make_normalized_finding(tool="semgrep", rule_id="S1"),
        ]
    )
    drivers = [run["tool"]["driver"]["name"] for run in document["runs"]]
    assert drivers == ["bandit", "semgrep"]


def test_every_emitted_level_is_one_sarif_defines() -> None:
    """A level outside the enumeration is rejected by SARIF consumers outright."""
    findings = [
        make_normalized_finding(severity=name, rule_id=f"R{name}") for name in CONST_SEVERITY_ORDER
    ]
    levels = {result["level"] for run in to_sarif(findings)["runs"] for result in run["results"]}
    assert levels <= CONST_SARIF_LEVELS


def test_results_reference_their_rule_by_index_and_id() -> None:
    """Both are required for a consumer to resolve the rule metadata."""
    document = to_sarif(
        [
            make_normalized_finding(rule_id="B602"),
            make_normalized_finding(rule_id="B307", line=6, message="eval"),
        ]
    )
    run = document["runs"][0]
    results = run["results"]
    assert [(result["ruleId"], result["ruleIndex"]) for result in results] == [
        ("B602", 0),
        ("B307", 1),
    ]


def test_a_repeated_rule_is_declared_once_and_referenced_twice() -> None:
    """Re-declaring a rule per result bloats the document and breaks rule-level config."""
    document = to_sarif(
        [make_normalized_finding(path="a.py"), make_normalized_finding(path="b.py")]
    )
    run = document["runs"][0]
    assert (len(run["tool"]["driver"]["rules"]), len(run["results"])) == (1, 2)


def test_a_result_carries_a_versioned_fingerprint() -> None:
    """An unversioned key would silently re-open suppressions if the scheme changed."""
    result = to_sarif([make_normalized_finding()])["runs"][0]["results"][0]
    assert (
        result["partialFingerprints"][CONST_SARIF_FINGERPRINT_KEY]
        == make_normalized_finding().fingerprint
    )


def test_a_rule_carries_the_security_severity_github_ranks_by() -> None:
    """GitHub code scanning orders by this property, not by the SARIF level."""
    rule = to_sarif([make_normalized_finding(severity="CRITICAL")])["runs"][0]["tool"]["driver"][
        "rules"
    ][0]
    assert rule["properties"]["security-severity"] == "9.5"


def test_a_finding_with_no_path_emits_no_location() -> None:
    """An empty artifact uri is invalid; omitting the location is not."""
    result = to_sarif([make_normalized_finding(path="", line=None)])["runs"][0]["results"][0]
    assert "locations" not in result


def test_a_non_positive_line_emits_no_region() -> None:
    """SARIF regions are one-based, so line 0 is not expressible."""
    result = to_sarif([make_normalized_finding(line=0)])["runs"][0]["results"][0]
    physical = result["locations"][0]["physicalLocation"]
    assert (physical["artifactLocation"]["uri"], "region" in physical) == (
        "src/app.py",
        False,
    )


def test_a_symbolic_locator_is_emitted_as_a_logical_location() -> None:
    """A Kubernetes resource has no line, but it does have a name."""
    finding = make_normalized_finding(line=None, symbol="Deployment/api", path="deploy.yml")
    location = to_sarif([finding])["runs"][0]["results"][0]["locations"][0]
    assert location["logicalLocations"] == [{"name": "Deployment/api"}]


def test_a_document_is_written_to_disk_as_json(tmp_path: Path) -> None:
    """The file has to be parseable by anything that reads SARIF."""
    destination = write_sarif([make_normalized_finding()], tmp_path / "nested" / "out.sarif")
    document = json.loads(destination.read_text())
    assert document["runs"][0]["results"][0]["ruleId"] == "B602"


_SARIF_SCHEMA = json.loads((FIXTURES / "sarif-schema-2.1.0.json").read_text(encoding="utf-8"))


def _assert_valid_sarif(document: dict[str, Any]) -> None:
    """Validate a document against the vendored OASIS SARIF 2.1.0 schema."""
    validator = jsonschema.validators.validator_for(_SARIF_SCHEMA)
    validator(_SARIF_SCHEMA).validate(document)


def _timed(status: str, reason: str = "") -> ScanOutcome:
    """Build an outcome carrying the execution window a real scanner records."""
    outcome = ScanOutcome(status, [], reason)
    outcome.started_utc = "2026-10-01T12:00:00.000Z"
    outcome.ended_utc = "2026-10-01T12:00:01.500Z"
    return outcome


def _drivers(document: dict[str, Any]) -> list[str]:
    return [run["tool"]["driver"]["name"] for run in document["runs"]]


def _notifications(document: dict[str, Any]) -> list[tuple[str, str, str]]:
    run = next(r for r in document["runs"] if r["tool"]["driver"]["name"] == "devops-cli")
    return [
        (n["properties"]["tool"], n["properties"]["status"], n["level"])
        for n in run["invocations"][0]["toolExecutionNotifications"]
    ]


def test_a_scanner_that_ran_gets_a_run_even_with_no_results() -> None:
    """A run with zero results is how a consumer learns the tool looked and found nothing."""
    document = to_sarif([], {"bandit": _timed("ran")})
    run = document["runs"][0]
    assert (_drivers(document), run["results"], run["invocations"]) == (
        ["bandit"],
        [],
        [
            {
                "executionSuccessful": True,
                "startTimeUtc": "2026-10-01T12:00:00.000Z",
                "endTimeUtc": "2026-10-01T12:00:01.500Z",
            }
        ],
    )
    _assert_valid_sarif(document)


def test_a_scanner_that_did_not_run_gets_no_run_only_a_notification(
    cli: Callable[..., Any],
) -> None:
    """An empty run for a tool that never ran would close that tool's open alerts."""
    outcomes = {
        "bandit": ScanOutcome("unavailable", [], "Binary 'bandit' not found on PATH"),
        "popeye": ScanOutcome("not_applicable", [], "No Kubernetes context"),
        "semgrep": ScanOutcome("failed", [], "Scanner exited with code 2: boom"),
    }
    document = to_sarif([], outcomes)
    invocation = document["runs"][0]["invocations"][0]
    assert (
        _drivers(document),
        _notifications(document),
        invocation["executionSuccessful"],
    ) == (
        ["devops-cli"],
        [
            ("bandit", "unavailable", "warning"),
            ("popeye", "not_applicable", "note"),
            ("semgrep", "failed", "error"),
        ],
        False,
    )
    _assert_valid_sarif(document)


def test_built_in_pattern_findings_never_carry_the_real_tools_driver_name(
    cli: Callable[..., Any],
) -> None:
    """Findings from devops-cli's own patterns are attributed to devops-cli, not to gitleaks."""
    finding = make_normalized_finding(
        tool="gitleaks", rule_id="aws-access-key-id", path="app.env", line=1
    )
    outcomes = {"gitleaks": ScanOutcome("built-in patterns", [finding], "Binary not found")}
    document = to_sarif([finding], outcomes)
    results = document["runs"][0]["results"]
    assert (
        _drivers(document),
        [r["ruleId"] for r in results],
        _notifications(document),
        document["runs"][0]["invocations"][0]["executionSuccessful"],
    ) == (
        ["devops-cli"],
        ["aws-access-key-id"],
        [("gitleaks", "built-in patterns", "note")],
        True,
    )
    _assert_valid_sarif(document)


def test_a_non_gating_finding_is_a_recommendation_without_a_security_severity() -> None:
    """A workflow audit finding is advice, so it must not rank as a security alert."""
    finding = make_normalized_finding(
        tool="zizmor", rule_id="template-injection", severity="MEDIUM", gating=False
    )
    document = to_sarif([finding], {"zizmor": _timed("ran")})
    rule = document["runs"][0]["tool"]["driver"]["rules"][0]
    result = document["runs"][0]["results"][0]
    assert (
        result["level"],
        rule["properties"].get("problem.severity"),
        CONST_SARIF_SECURITY_SEVERITY_PROPERTY in rule["properties"],
    ) == ("note", "recommendation", False)
    _assert_valid_sarif(document)


def test_a_gating_finding_keeps_its_security_severity_beside_outcomes() -> None:
    """Outcome handling must not strip the score GitHub ranks security alerts by."""
    document = to_sarif([make_normalized_finding(severity="HIGH")], {"bandit": _timed("ran")})
    rule = document["runs"][0]["tool"]["driver"]["rules"][0]
    assert CONST_SARIF_SECURITY_SEVERITY_PROPERTY in rule["properties"]
    _assert_valid_sarif(document)


@pytest.mark.parametrize(
    "document",
    [
        to_sarif([]),
        to_sarif(
            [
                make_normalized_finding(),
                make_normalized_finding(tool="semgrep", rule_id="S1", line=None),
            ]
        ),
        to_sarif([make_normalized_finding(path="", line=None)]),
    ],
)
def test_every_emitted_document_conforms_to_the_sarif_schema(
    document: dict[str, Any],
) -> None:
    """Code scanning rejects an upload that fails the OASIS schema."""
    _assert_valid_sarif(document)


def test_the_report_command_records_why_scanners_did_not_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Any]
) -> None:
    """Scanners missing from the workstation become notifications, never empty runs."""
    destination = tmp_path / "out.sarif"
    monkeypatch.setenv("PATH", str(tmp_path / "no-programs"))
    with patch(
        "devops_cli.security.registry.ScannerRegistry.list_scanners",
        return_value=["bandit", "gitleaks"],
    ):
        result = cli(["scan", "report", str(tmp_path), "--sarif", str(destination)])
    document = json.loads(destination.read_text(encoding="utf-8"))
    tools = [tool for tool, _, _ in _notifications(document)]
    assert (result.exit_code, _drivers(document), tools) == (
        0,
        ["devops-cli"],
        ["bandit", "gitleaks"],
    )
    _assert_valid_sarif(document)


def test_the_sarif_document_of_findings_from_three_tools(snapshot: SnapshotAssertion) -> None:
    """The document of a located, a symbolic, a second-tool and a file-only finding conforms to
    the OASIS SARIF 2.1.0 schema; the snapshot is the whole document."""
    document = to_sarif(
        [
            make_normalized_finding(),
            make_normalized_finding(
                path="manifests/prometheus.yaml",
                line=None,
                symbol="Service/monitoring/prometheus",
            ),
            make_normalized_finding(
                tool="semgrep",
                rule_id="python.lang.security.deserialization",
                message="Avoid using pickle",
                path="src/loader.py",
                line=12,
            ),
            make_normalized_finding(
                tool="trivy",
                rule_id="CVE-2023-1234",
                severity="CRITICAL",
                message="vulnerable package dependency",
                path="package-lock.json",
                line=None,
            ),
        ]
    )

    _assert_valid_sarif(document)
    assert document == snapshot


def _record(tool: str = "gitleaks", version: str = "8.21.2", **changes: Any) -> ToolRun:
    """The record of one run of `tool`, as a review keeps it."""
    fields: dict[str, Any] = {
        "tool": tool,
        "version": version,
        "binary_sha256": hashlib.sha256(tool.encode()).hexdigest(),
        "executor": "direct",
        "network": "host",
        "config_digest": "0123456789abcdef",
        "ruleset_digest": "4f53cda18c2baa0c",
        "argv_template": (tool, "detect", "--config", "{config}", "{targets}"),
        "targets_digest": "fedcba9876543210",
        "commit": "0" * 40,
        **changes,
    }
    return ToolRun(**fields)


def _run_of(document: dict[str, Any], tool: str) -> dict[str, Any]:
    return next(run for run in document["runs"] if run["tool"]["driver"]["name"] == tool)


def test_the_run_of_a_tool_holds_each_record_of_that_tool_in_its_property_bag() -> None:
    """A consumer of the document reads which binary, config and ruleset gave a result. Each
    record goes in the run of its tool with the field names of `ToolRun`, in the order of the
    runs. A record that its caller did not settle holds nothing that an invocation requires, and
    no record holds what an artifact or `versionControlProvenance` requires."""
    first = _record(targets_digest="1111111111111111")
    second = _record(targets_digest="2222222222222222", commit=None)
    document = to_sarif(
        [make_normalized_finding(tool="gitleaks", rule_id="aws-access-key-id")],
        tool_runs=[first, _record(tool="bandit", version="1.8.6"), second],
    )
    run = _run_of(document, "gitleaks")
    assert (
        [ToolRun.model_validate(record) for record in run["properties"]["tool_runs"]],
        sorted(set(run) - {"tool", "results", "properties"}),
    ) == ([first, second], [])
    _assert_valid_sarif(document)


@pytest.mark.parametrize(
    ("result_version", "record_versions", "expected"),
    [
        (None, ["8.21.2", "8.21.2"], "8.21.2"),
        ("8.20.0", ["8.21.2"], "8.20.0"),
        (None, ["8.21.2", "8.22.0"], None),
    ],
)
def test_the_driver_names_the_version_of_its_records_when_no_result_names_one(
    result_version: str | None, record_versions: list[str], expected: str | None
) -> None:
    """The version that the tool gave with a result comes first. Records that name two versions
    do not say which one gave the results."""
    document = to_sarif(
        [make_normalized_finding(tool="gitleaks", tool_version=result_version)],
        tool_runs=[_record(version=version) for version in record_versions],
    )
    assert document["runs"][0]["tool"]["driver"].get("version") == expected
    _assert_valid_sarif(document)


@pytest.mark.parametrize(
    ("settled", "results"),
    [
        ([(0, True), (0, True)], []),
        ([(0, True), (2, False)], None),
        ([(0, True), (None, None)], None),
    ],
    ids=["every-run-succeeded", "a-run-failed", "a-run-not-settled"],
)
def test_a_tool_with_records_and_no_result_has_a_run_that_says_how_it_ended(
    settled: list[tuple[int | None, bool | None]], results: list[Any] | None
) -> None:
    """A run with an empty results array says that the tool looked and found nothing. It is true
    only when every run of the tool succeeded. Otherwise the run has no results, which SARIF reads
    as null: the tool did not finish its analysis (SARIF 2.1.0, 3.14.23)."""
    records = [
        _record(tool="bandit", exit_code=exit_code, success=success)
        for exit_code, success in settled
    ]

    document = to_sarif([make_normalized_finding(tool="gitleaks")], tool_runs=records)

    assert (_drivers(document), _run_of(document, "bandit").get("results")) == (
        ["bandit", "gitleaks"],
        results,
    )
    _assert_valid_sarif(document)


def test_each_settled_record_is_one_invocation_of_the_run_of_its_tool() -> None:
    """An invocation says if the tool succeeded, and the exit code alone does not say it: Gitleaks
    exits with 1 when it finds a secret (SARIF 2.1.0, 3.20.14). The command line is the template
    of the record, in the order of the runs. A record that its caller did not settle has no
    invocation, and a run that timed out has no exit code of its own (3.20.9)."""
    document = to_sarif(
        [make_normalized_finding(tool="gitleaks")],
        tool_runs=[
            _record(exit_code=1, success=True),
            _record(),
            _record(exit_code=2, success=False),
            _record(exit_code=None, success=False),
        ],
    )

    command = "gitleaks detect --config {config} {targets}"
    assert _run_of(document, "gitleaks")["invocations"] == [
        {"commandLine": command, "executionSuccessful": True, "exitCode": 1},
        {"commandLine": command, "executionSuccessful": False, "exitCode": 2},
        {"commandLine": command, "executionSuccessful": False},
    ]
    _assert_valid_sarif(document)


def test_the_command_line_quotes_each_argument_for_a_shell_but_a_placeholder() -> None:
    """A consumer can split the command line as a POSIX shell does. A placeholder stands as it
    is, so that it is the same string as its redaction token (SARIF 2.1.0, 3.5.2)."""
    record = _record(
        tool="semgrep",
        argv_template=("semgrep", "--exclude", "a b", "--json", "{ruleset}", "{targets}"),
        exit_code=0,
        success=True,
    )

    document = to_sarif([], tool_runs=[record])

    [invocation] = _run_of(document, "semgrep")["invocations"]
    assert invocation["commandLine"] == "semgrep --exclude 'a b' --json {ruleset} {targets}"


@pytest.mark.parametrize(
    ("templates", "tokens"),
    [
        (
            [("gitleaks", "--config", "{config}", "{targets}"), ("gitleaks", "{ruleset}")],
            ["{targets}", "{config}", "{ruleset}"],
        ),
        ([("gitleaks", "detect", "{targets}")], ["{targets}"]),
        ([("gitleaks", "version")], None),
    ],
    ids=["three-placeholders", "targets-only", "no-placeholder"],
)
def test_the_placeholders_of_the_command_lines_are_the_redaction_tokens_of_the_run(
    templates: list[tuple[str, ...]], tokens: list[str] | None
) -> None:
    """A placeholder stands for a path of the host, so a command line from the template is a
    redacted string, and its run names each token (SARIF 2.1.0, 3.14.28)."""
    records = [_record(argv_template=template, exit_code=0, success=True) for template in templates]

    document = to_sarif([make_normalized_finding(tool="gitleaks")], tool_runs=records)

    assert _run_of(document, "gitleaks").get("redactionTokens") == tokens
    _assert_valid_sarif(document)


def test_the_run_of_a_scanner_that_ran_holds_its_records_beside_its_invocation() -> None:
    """With the outcomes of the scanners, the outcome says that the scanner succeeded, and the
    records of the scanner go in its run."""
    record = _record(tool="bandit", version="1.8.6")
    document = to_sarif([], {"bandit": _timed("ran")}, tool_runs=[record])
    [run] = document["runs"]
    assert (
        run["tool"]["driver"]["version"],
        run["properties"]["tool_runs"],
        run["invocations"][0]["executionSuccessful"],
    ) == ("1.8.6", [record.model_dump(mode="json")], True)
    _assert_valid_sarif(document)
