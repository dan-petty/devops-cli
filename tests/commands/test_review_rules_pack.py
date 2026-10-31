"""Tests for the review Semgrep rule pack, `rules.lock` manifest, and CI workflow contract (#1145)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.commands.ci import get_check_specs
from devops_cli.commands.review import app as review_app
from devops_cli.config.defaults import DEFAULT_SEMGREP_CONFIG
from devops_cli.core.command_resolver import resolve_devops_argv
from devops_cli.dry_run.state import set_dry_run
from devops_cli.exceptions.validation import ValidationError
from devops_cli.main import app as root_app
from devops_cli.review.rules_pack import (
    RULE_PACK_DIR,
    RULES_LOCK_FILENAME,
    discover_pack_rules,
    normalize_pack_check_id,
    pinned_semgrep_version,
    read_rules_lock,
    run_rule_pack_tests,
    validate_rule_pair,
    verify_rules_lock,
)
from devops_cli.security.semgrep import _files_command, parse_semgrep_json
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.paths import FIXTURES, REPO_ROOT

RECALL_SET_PATH = FIXTURES / "review_recall" / "recall_set.json"
RULE_ID = "k8s-networkpolicy-ingress-any"
runner = CliRunner()


def test_networkpolicy_ingress_any_rule_and_test_cases() -> None:
    """`k8s-networkpolicy-ingress-any.yaml` is MIT-licensed with CWE metadata and tests both recall shapes."""
    rules = discover_pack_rules()
    assert RULE_ID in rules
    rule_path, test_path = rules[RULE_ID]
    raw_rule = rule_path.read_text(encoding="utf-8")
    rule_doc = yaml.safe_load(raw_rule)["rules"][0]
    meta = rule_doc["metadata"]
    docs = list(yaml.safe_load_all(test_path.read_text(encoding="utf-8")))
    test_lines = test_path.read_text(encoding="utf-8").splitlines()
    ruleid_count = sum(1 for line in test_lines if f"# ruleid: {RULE_ID}" in line)
    ok_count = sum(1 for line in test_lines if f"# ok: {RULE_ID}" in line)
    doc_names = [doc["metadata"]["name"] for doc in docs if isinstance(doc, dict)]
    assert (
        raw_rule.startswith("# SPDX-License-Identifier: MIT"),
        rule_doc["id"],
        meta["license"],
        bool(meta.get("cwe")),
        validate_rule_pair(RULE_ID, rule_path, test_path),
        ruleid_count,
        ok_count >= 2,
        doc_names,
    ) == (
        True,
        RULE_ID,
        "MIT",
        True,
        [],
        2,
        True,
        [
            "monitoring-default-perimeter",
            "otel-default-perimeter",
            "restricted-cidr-ingress",
            "egress-only-policy",
        ],
    )


def test_recall_set_entries_name_expected_tool_and_rule() -> None:
    """Every recall entry names the tool and rule expected to catch it, or `none` for VISION.md."""
    findings = json.loads(RECALL_SET_PATH.read_text(encoding="utf-8"))["findings"]
    pack_ids = set(discover_pack_rules())
    mapping = [
        (item["path"], item["class"], item.get("tool"), item.get("rule")) for item in findings
    ]
    semgrep_rules = {item["rule"] for item in findings if item.get("tool") == "semgrep"}
    assert (
        mapping,
        semgrep_rules <= pack_ids,
    ) == (
        [
            ("k8s/monitoring/networkpolicy.yaml", "Network Exposure", "semgrep", RULE_ID),
            ("k8s/otel/networkpolicy.yaml", "Network Exposure", "semgrep", RULE_ID),
            ("src/devops_cli/ai/rag/investigator.py", "Error Handling", "ruff", "BLE001"),
            ("docs/VISION.md", "Security Claims", "none", "none"),
            ("src/devops_cli/ai/spend/pricing.py", "Error Handling", "ruff", "BLE001"),
            ("src/devops_cli/ai/spend/pricing.py", "Error Handling", "ruff", "BLE001"),
        ],
        True,
    )


def test_offline_gate_every_pack_rule_matches_rules_lock() -> None:
    """Offline gate: every rule in `src/devops_cli/review/rules` has an up-to-date `rules.lock` entry."""
    lock = read_rules_lock()
    entry = lock.rules[RULE_ID]
    assert (
        verify_rules_lock(),
        set(lock.rules),
        entry.semgrep_version,
        len(entry.rule_sha256),
        len(entry.test_sha256),
    ) == (
        [],
        set(discover_pack_rules()),
        pinned_semgrep_version(),
        64,
        64,
    )


def test_rules_test_writes_and_checks_manifest_with_fake_semgrep(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`devops review rules test` runs `semgrep --test`, writes `rules.lock`, and `--check` catches drift."""
    pack_copy = tmp_path / "rules"
    shutil.copytree(RULE_PACK_DIR, pack_copy)
    (pack_copy / RULES_LOCK_FILENAME).unlink()
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        if "--version" in cmd:
            return subprocess.CompletedProcess(cmd, 0, f"{pinned_semgrep_version()}\n", "")
        return subprocess.CompletedProcess(cmd, 0, "1/1: ✓ All tests passed\n", "")

    monkeypatch.setattr("devops_cli.review.rules_pack.run_subprocess", fake_run)
    res_write = runner.invoke(
        review_app, ["rules", "test", "--rules-dir", str(pack_copy), "--format", "json"]
    )
    payload = json.loads(res_write.stdout)
    res_check = runner.invoke(
        review_app, ["rules", "test", "--rules-dir", str(pack_copy), "--check"]
    )
    # Tamper with the test file to trigger manifest drift on `--check`.
    test_file = pack_copy / f"{RULE_ID}.test.yaml"
    test_file.write_text(test_file.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
    res_drift = runner.invoke(
        review_app, ["rules", "test", "--rules-dir", str(pack_copy), "--check"]
    )
    assert (
        res_write.exit_code,
        RULE_ID in payload["rules"],
        any("--test" in c and "--metrics" in c for c in calls),
        res_check.exit_code,
        res_drift.exit_code,
        "test_sha256 drift" in (res_drift.stdout + res_drift.stderr),
    ) == (0, True, True, 0, 1, True)


def test_rules_test_fails_when_semgrep_test_fails_and_dry_run_is_pure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing `semgrep --test` raises `ValidationError`, and `--dry-run` starts no process."""
    pack_copy = tmp_path / "rules"
    shutil.copytree(RULE_PACK_DIR, pack_copy)
    started: list[list[str]] = []

    def fake_fail(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        started.append(list(cmd))
        if "--version" in cmd:
            return subprocess.CompletedProcess(cmd, 0, f"{pinned_semgrep_version()}\n", "")
        return subprocess.CompletedProcess(cmd, 1, "0/1: 1 test did not pass\n", "")

    monkeypatch.setattr("devops_cli.review.rules_pack.run_subprocess", fake_fail)
    res_dry = runner.invoke(
        root_app, ["--dry-run", "review", "rules", "test", "--rules-dir", str(pack_copy)]
    )
    dry_started = list(started)
    set_dry_run(False)
    with pytest.raises(ValidationError, match="semgrep --test failed"):
        run_rule_pack_tests(pack_copy)
    cmd = _files_command(["a.yaml"], DEFAULT_SEMGREP_CONFIG) or []
    parsed = parse_semgrep_json(
        {
            "results": [
                {
                    "check_id": f"src.devops_cli.review.rules.{RULE_ID}",
                    "path": "k8s/otel/networkpolicy.yaml",
                    "start": {"line": 32},
                    "end": {"line": 32},
                    "extra": {"message": "Ingress 0.0.0.0/0", "severity": "ERROR"},
                }
            ]
        }
    )
    assert (
        res_dry.exit_code,
        dry_started,
        len(started),
        normalize_pack_check_id(f"tmp.dir.{RULE_ID}"),
        str(RULE_PACK_DIR) in cmd,
        parsed[0].title.startswith(f"[{RULE_ID}]"),
    ) == (0, [], 2, RULE_ID, True, True)


def test_semgrep_gets_only_its_own_setting_and_not_the_environment_of_the_person(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> None:
    """`semgrep --version` and `semgrep --test` get only `SEMGREP_ENABLE_VERSION_CHECK=0` as the
    caller override, so an exported bash function or a token of the person neither reaches
    Semgrep nor trips the guard on loader and shell keys (#2205)."""
    pack_copy = tmp_path / "rules"
    shutil.copytree(RULE_PACK_DIR, pack_copy)
    monkeypatch.setenv("BASH_FUNC_which%%", '() {  /usr/bin/which "$@"\n}')
    monkeypatch.setenv("GITHUB_TOKEN", "example-token")
    process_fake.answer(
        lambda call: "--version" in call.argv,
        ProcessAnswer(stdout=f"{pinned_semgrep_version()}\n"),
    )

    run_rule_pack_tests(pack_copy)

    assert [(call.argv[1], call.env) for call in process_fake.calls] == [
        ("--version", {"SEMGREP_ENABLE_VERSION_CHECK": "0"}),
        ("--test", {"SEMGREP_ENABLE_VERSION_CHECK": "0"}),
    ]


def test_ci_workflow_runs_rule_pack_tests_when_rules_change() -> None:
    """`.github/workflows/ci.yml` defines a path-filtered `rule-pack` job outside `devops ci`."""
    workflow = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8"))
    job = workflow["jobs"]["rule-pack"]
    steps = {step["name"]: step for step in job["steps"]}
    detect = steps["Detect Changed Rule Pack Files"]
    run_step = steps["Run Semgrep Rule Pack Tests"]
    changed_cond = "steps.changed_rules.outputs.changed == 'true'"
    assert (
        (job["name"], job["if"], job["permissions"]),
        (":(glob)src/devops_cli/review/rules/**" in detect["run"], detect["env"]["BASE_REF"]),
        (steps["Set up uv toolchain"].get("if"), run_step.get("if")),
        (
            "devops install-tools --tool semgrep" in run_step["run"],
            "semgrep --test --metrics off src/devops_cli/review/rules" in run_step["run"],
            "devops review rules test --check" in run_step["run"],
        ),
        [step["name"] for step in job["steps"] if "${{" in step.get("run", "")],
        "rule-pack" in {spec.name for spec in get_check_specs()},
        resolve_devops_argv(["review", "rules", "test", "--check"]),
    ) == (
        ("Rule Pack Tests", "github.event_name == 'pull_request'", {"contents": "read"}),
        (True, "${{ github.base_ref }}"),
        (changed_cond, changed_cond),
        (True, True, True),
        [],
        False,
        None,
    )
