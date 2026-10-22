"""Unit tests for review tool version resolution and expected-output canary gates (#1143)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review_schema import Finding
from devops_cli.config.constants import (
    CONST_CANARY_EXPECTED_RESULTS,
    CONST_CANARY_TOOLS,
)
from devops_cli.review.canary import (
    CanaryCacheKey,
    build_canary_command,
    evaluate_canary_gate,
    get_canary_cache,
    materialize_canary_fixtures,
    resolve_mypy_python_version,
    resolve_review_kubernetes_version,
    resolve_ruff_target_version,
    run_tool_canary,
)
from devops_cli.security.base import ScanOutcome
from devops_cli.security.mypy import MypyScanner, run_mypy_scan
from devops_cli.security.pluto import PlutoScanner, run_pluto_scan
from devops_cli.security.ruff import RuffScanner, run_ruff_scan
from tests.support.paths import FIXTURES

_RECORDED_FIXTURE_PATH = FIXTURES / "review_canary" / "recorded_outputs.json"


@pytest.fixture
def recorded_outputs() -> dict[str, Any]:
    """Load recorded canary outputs captured from the pinned binaries."""
    payload = json.loads(_RECORDED_FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


# ── Criterion 1: Version flags come from the project; missing is a coverage gap ──


def test_project_version_flags_for_ruff_mypy_and_pluto(tmp_path: Path) -> None:
    """Verify ruff, mypy, and Pluto take their version flags from project config."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nrequires-python = ">=3.14"\n\n'
        '[tool.mypy]\npython_version = "3.14"\n',
        encoding="utf-8",
    )
    (tmp_path / ".devops").mkdir()
    (tmp_path / ".devops" / "review.toml").write_text(
        'kubernetes_version = "v1.31.0"\n',
        encoding="utf-8",
    )
    py_file = tmp_path / "app.py"
    py_file.write_text("x: int = 1\n", encoding="utf-8")
    manifest = tmp_path / "deploy.yaml"
    manifest.write_text("apiVersion: apps/v1\nkind: Deployment\n", encoding="utf-8")

    ruff_cmd = RuffScanner().build_command(py_file, tree=tmp_path)
    mypy_cmd = MypyScanner().build_command(py_file, tree=tmp_path)
    pluto_cmd = PlutoScanner().build_command(manifest, tree=tmp_path)

    assert (
        resolve_ruff_target_version(tmp_path),
        resolve_mypy_python_version(tmp_path),
        resolve_review_kubernetes_version(tree=tmp_path),
        "--target-version=py314" in ruff_cmd,
        "--python-version=3.14" in mypy_cmd,
        pluto_cmd[-2:],
    ) == (
        "py314",
        "3.14",
        "v1.31.0",
        True,
        True,
        ["--target-versions", "k8s=v1.31.0"],
    )


def test_missing_project_versions_report_coverage_gap(tmp_path: Path) -> None:
    """Verify missing requires-python, mypy python_version, or kubernetes_version is a coverage gap."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "no-versions"\n', encoding="utf-8")
    (tmp_path / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    py_file = tmp_path / "app.py"
    py_file.write_text("x = 1\n", encoding="utf-8")
    manifest = tmp_path / "deploy.yaml"
    manifest.write_text(
        "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: demo\n",
        encoding="utf-8",
    )

    ruff_outcome = run_ruff_scan([py_file], tree=tmp_path, require_version=True)
    mypy_outcome = run_mypy_scan([py_file], tree=tmp_path, checkout_root=tmp_path)
    pluto_outcome = run_pluto_scan(manifest, tree=tmp_path, require_version=True)

    assert (
        (ruff_outcome.status, ruff_outcome.reason),
        (mypy_outcome.status, mypy_outcome.reason),
        (pluto_outcome.status, pluto_outcome.reason),
    ) == (
        ("coverage_gap", "missing requires-python in pyproject.toml"),
        ("coverage_gap", "missing mypy python_version in pyproject.toml"),
        ("coverage_gap", "missing review.kubernetes_version in .devops/review.toml"),
    )


# ── Criterion 2: Canary fixtures and expected (rule, line) gate ──────────────


def test_canary_fixtures_contain_pep758_pep695_pep649_manifest_and_dockerfile(
    tmp_path: Path,
) -> None:
    """Verify materialized canary fixtures include PEP 758, 695, and 649 constructs, manifest, and Dockerfile."""
    files = materialize_canary_fixtures(tmp_path)
    py_text = files["python"].read_text(encoding="utf-8")
    probes_text = files["semgrep_probes"].read_text(encoding="utf-8")
    manifest_text = files["manifest"].read_text(encoding="utf-8")
    dockerfile_text = files["dockerfile"].read_text(encoding="utf-8")

    assert (
        "type Items[T] = list[T]" in py_text,
        "def make_forward(value: ForwardTarget) -> ForwardTarget:" in py_text,
        "except ValueError, TypeError:" in py_text,
        "canary-pep758-tuple" in probes_text and "canary-pep758-as-binding" in probes_text,
        "kind: Ingress" in manifest_text and "privileged: true" in manifest_text,
        dockerfile_text.startswith("FROM "),
    ) == (True, True, True, True, True, True)


def test_canary_gate_requires_exact_match_on_expected_rule_and_line_set(
    recorded_outputs: dict[str, Any],
    tmp_path: Path,
) -> None:
    """Verify every pinned tool's recorded output matches its exact (rule, line) set and drift fails."""
    results = {
        tool: evaluate_canary_gate(tool, recorded_outputs[tool]["output"])
        for tool in CONST_CANARY_TOOLS
    }
    wrong_line_ruff = {
        "runs": [
            {
                "results": [
                    {
                        "ruleId": "B006",
                        "locations": [{"physicalLocation": {"region": {"startLine": 99}}}],
                    }
                ]
            }
        ]
    }
    extra_finding_bandit = {
        "results": [
            {"test_id": "B307", "line_number": 26},
            {"test_id": "B101", "line_number": 10},
        ]
    }
    cmds = {tool: build_canary_command(tool, tmp_path) for tool in CONST_CANARY_TOOLS}

    assert (
        all(res.passed and res.status == "passed" for res in results.values()),
        {tool: res.actual for tool, res in results.items()},
        evaluate_canary_gate("ruff", wrong_line_ruff).passed,
        evaluate_canary_gate("bandit", extra_finding_bandit).passed,
        set(cmds),
    ) == (
        True,
        CONST_CANARY_EXPECTED_RESULTS,
        False,
        False,
        set(CONST_CANARY_TOOLS),
    )


# ── Criterion 3: Semgrep 1.178.0 fails and 1.179.0 passes offline ────────────


def test_semgrep_1_178_0_recorded_output_fails_and_1_179_0_passes(
    recorded_outputs: dict[str, Any],
) -> None:
    """Verify Semgrep 1.178.0's PEP 758 misparse fails the canary gate while 1.179.0 passes."""
    res_1178 = evaluate_canary_gate("semgrep", recorded_outputs["semgrep_1_178_0"]["output"])
    res_1179 = evaluate_canary_gate("semgrep", recorded_outputs["semgrep"]["output"])

    assert (
        res_1178.passed,
        res_1178.status,
        res_1178.actual,
        res_1179.passed,
        res_1179.status,
        res_1179.actual,
    ) == (
        False,
        "canary-failed",
        frozenset({("canary-pep758-as-binding", 17)}),
        True,
        "passed",
        frozenset({("canary-pep758-tuple", 17)}),
    )


# ── Criterion 4: Caching per (tool, version, binary_sha, language_version, ruleset_digest) ──


def test_canary_caches_once_per_five_tuple_key(recorded_outputs: dict[str, Any]) -> None:
    """Verify run_tool_canary executes once per (tool, version, binary_sha, language_version, ruleset_digest)."""
    invocations: list[str] = []

    def fake_runner(tool: str, _cmd: list[str], _workdir: Path) -> dict[str, Any]:
        invocations.append(tool)
        return dict(recorded_outputs[tool]["output"])

    first = run_tool_canary(
        "ruff",
        version="0.16.8",
        binary_sha="sha-a",
        language_version="py314",
        ruleset_digest="digest-1",
        runner=fake_runner,
    )
    second = run_tool_canary(
        "ruff",
        version="0.16.8",
        binary_sha="sha-a",
        language_version="py314",
        ruleset_digest="digest-1",
        runner=fake_runner,
    )
    third = run_tool_canary(
        "ruff",
        version="0.16.8",
        binary_sha="sha-a",
        language_version="py313",
        ruleset_digest="digest-1",
        runner=fake_runner,
    )

    expected_key = CanaryCacheKey("ruff", "0.16.8", "sha-a", "py314", "digest-1")
    assert (
        len(invocations),
        first == second,
        first.cache_key,
        third.cache_key.language_version,
        len(get_canary_cache()),
    ) == (2, True, expected_key, "py313", 2)


# ── Criterion 5 & Refinement: Failed canary withholds findings and marks coverage ──


def test_failed_canary_withholds_findings_and_records_rejection_and_coverage_state(
    recorded_outputs: dict[str, Any],
    tmp_path: Path,
) -> None:
    """Admit a finding from a failed-canary tool and assert rejection count and coverage state."""
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    target_py = src_dir / "main.py"
    target_py.write_text("import subprocess\n", encoding="utf-8")

    # Seed the canary cache with a failing result for Semgrep (1.178.0 output) and passing Bandit.
    run_tool_canary(
        "semgrep",
        runner=lambda *_: recorded_outputs["semgrep_1_178_0"]["output"],
    )
    run_tool_canary(
        "bandit",
        runner=lambda *_: recorded_outputs["bandit"]["output"],
    )

    semgrep_finding = ScanOutcome(
        "ran",
        [
            Finding(
                severity="HIGH",
                location="src/main.py:1",
                title="[python.lang.security.audit.exec] Dangerous exec",
                description="Found dangerous call",
                fix="Avoid exec",
            )
        ],
    )
    bandit_finding = ScanOutcome("ran", [])

    orchestrator = ReviewPipelineOrchestrator(
        session_id="test-canary-fail",
        session_dir=tmp_path / "session",
        target_dir=tmp_path,
        llm_client=MagicMock(),
    )
    with (
        patch("devops_cli.security.semgrep.run_semgrep_scan", return_value=semgrep_finding),
        patch("devops_cli.security.bandit.run_bandit_scan", return_value=bandit_finding),
        patch("devops_cli.ai.review.pipeline._scan_secrets", return_value=[]),
    ):
        by_file = orchestrator._run_static_scanners(["src/main.py"])

    assert (
        by_file,
        orchestrator.admitted_scanner_findings,
        orchestrator.rejection_counts.get("canary-failed"),
        orchestrator.static_analyzers.get("Semgrep"),
        orchestrator.static_analyzer_reasons.get("Semgrep"),
        orchestrator.coverage["Semgrep"]["src/main.py"],
        orchestrator.coverage["Bandit"]["src/main.py"],
    ) == (
        {},
        [],
        1,
        "failed",
        "canary failed",
        "canary failed",
        "scanned",
    )


def test_review_start_runs_canaries_automatically_via_subprocess_when_unmocked(
    recorded_outputs: dict[str, Any],
    tmp_path: Path,
) -> None:
    """Verify ReviewPipelineOrchestrator automatically runs and caches tool canaries at review start."""
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "main.py").write_text("x = 1\n", encoding="utf-8")

    def fake_canary_subprocess(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        bin_name = Path(cmd[0]).name
        tool_key = "mypy" if "-m" in cmd and "mypy" in cmd else bin_name
        out = recorded_outputs[tool_key]["output"]
        stdout_str = out if isinstance(out, str) else json.dumps(out)
        return subprocess.CompletedProcess(cmd, 0, stdout_str, "")

    orchestrator = ReviewPipelineOrchestrator(
        session_id="test-auto-canary",
        session_dir=tmp_path / "session",
        target_dir=tmp_path,
        llm_client=MagicMock(),
    )
    with (
        patch(
            "devops_cli.review.canary.run_subprocess",
            MagicMock(side_effect=fake_canary_subprocess),
        ) as mock_canary_proc,
        patch("devops_cli.security.bandit.run_bandit_scan", return_value=ScanOutcome("ran", [])),
        patch("devops_cli.security.semgrep.run_semgrep_scan", return_value=ScanOutcome("ran", [])),
        patch("devops_cli.ai.review.pipeline._scan_secrets", return_value=[]),
    ):
        orchestrator._run_static_scanners(["src/main.py"])
        orchestrator._run_static_scanners(["src/main.py"])

    assert (
        mock_canary_proc.call_count,
        orchestrator.canary_results["bandit"],
        orchestrator.canary_results["semgrep"],
    ) == (2, True, True)


def test_the_semgrep_canary_sends_no_metrics_and_checks_no_version(tmp_path: Path) -> None:
    """The canary runs Semgrep as every other scan does, on its probe rules alone (#1144)."""
    assert build_canary_command("semgrep", tmp_path) == [
        "semgrep",
        "scan",
        "--json",
        "--metrics",
        "off",
        "--disable-version-check",
        "--config",
        "semgrep_probes.yaml",
        "--disable-nosem",
        "--quiet",
        "canary.py",
    ]
