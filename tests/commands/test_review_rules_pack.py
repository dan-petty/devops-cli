"""Tests for the review Semgrep rule pack and its `rules.lock` manifest (#1145)."""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from shutil import which

import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.commands.review import app as review_app
from devops_cli.config.defaults import DEFAULT_LOCAL_BIN_DIR, DEFAULT_SEMGREP_CONFIG
from devops_cli.dry_run.state import set_dry_run
from devops_cli.exceptions.tools import DependencyError
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
from devops_cli.security.semgrep import files_command, parse_semgrep_json
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.paths import FIXTURES

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
    process_fake: ProcessFake,
) -> None:
    """`devops review rules test` runs `semgrep --test`, writes `rules.lock`, and `--check` catches drift."""
    pack_copy = tmp_path / "rules"
    shutil.copytree(RULE_PACK_DIR, pack_copy)
    (pack_copy / RULES_LOCK_FILENAME).unlink()
    process_fake.answer(
        lambda call: "--version" in call.argv,
        ProcessAnswer(stdout=f"{pinned_semgrep_version()}\n"),
    )
    process_fake.answer(
        lambda call: "--test" in call.argv, ProcessAnswer(stdout="1/1: ✓ All tests passed\n")
    )
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
        any("--test" in c.argv and "--metrics" in c.argv for c in process_fake.calls),
        res_check.exit_code,
        res_drift.exit_code,
        "test_sha256 drift" in (res_drift.stdout + res_drift.stderr),
    ) == (0, True, True, 0, 1, True)


def test_rules_test_fails_when_semgrep_test_fails_and_dry_run_is_pure(
    tmp_path: Path,
    process_fake: ProcessFake,
) -> None:
    """A failing `semgrep --test` raises `ValidationError`, and `--dry-run` starts no process."""
    pack_copy = tmp_path / "rules"
    shutil.copytree(RULE_PACK_DIR, pack_copy)
    process_fake.answer(
        lambda call: "--version" in call.argv,
        ProcessAnswer(stdout=f"{pinned_semgrep_version()}\n"),
    )
    process_fake.answer(
        lambda call: "--test" in call.argv,
        ProcessAnswer(returncode=1, stdout="0/1: 1 test did not pass\n"),
    )
    res_dry = runner.invoke(
        root_app, ["--dry-run", "review", "rules", "test", "--rules-dir", str(pack_copy)]
    )
    dry_started = list(process_fake.calls)
    set_dry_run(False)
    with pytest.raises(ValidationError, match="semgrep --test failed"):
        run_rule_pack_tests(pack_copy)
    cmd = files_command(["a.yaml"], DEFAULT_SEMGREP_CONFIG) or []
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
        len(process_fake.calls),
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


def _stand_in(folder: Path) -> Path:
    """An executable `semgrep` stand-in in `folder`."""
    folder.mkdir(parents=True, exist_ok=True)
    stand_in = folder / "semgrep"
    stand_in.write_text("#!/bin/sh\n", encoding="utf-8")
    stand_in.chmod(0o755)
    return stand_in


@pytest.fixture
def installer_semgrep() -> Iterator[Path]:
    """A `semgrep` stand-in in `~/.local/bin` of the isolated home, the folder of
    `devops install-tools`. The folders that the fixture makes go after the test."""
    folders = (DEFAULT_LOCAL_BIN_DIR, *DEFAULT_LOCAL_BIN_DIR.parents)
    made = [folder for folder in folders if not folder.exists()]
    stand_in = _stand_in(DEFAULT_LOCAL_BIN_DIR)
    try:
        yield stand_in
    finally:
        stand_in.unlink()
        if made:
            shutil.rmtree(made[-1])


def test_rules_test_runs_the_semgrep_on_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> None:
    """The rule pack test runs the `semgrep` that PATH names (#4362). The test gives back the
    PATH lookup that `process_fake` replaces."""
    pack_copy = tmp_path / "rules"
    shutil.copytree(RULE_PACK_DIR, pack_copy)
    stand_in = _stand_in(tmp_path / "bin")
    monkeypatch.setenv("PATH", str(stand_in.parent))
    monkeypatch.setattr(shutil, "which", which)
    process_fake.answer(lambda call: "--version" in call.argv, ProcessAnswer(stdout="1.99.0\n"))

    run_rule_pack_tests(pack_copy)

    assert [call.argv[0] for call in process_fake.calls] == [str(stand_in.resolve())] * 2


def test_rules_test_does_not_find_a_semgrep_only_in_the_installer_folder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    process_fake: ProcessFake,
    installer_semgrep: Path,
) -> None:
    """A `semgrep` only in `~/.local/bin` is not on PATH: the rule pack test raises
    `DependencyError` with an install hint and starts no process (#4362)."""
    pack_copy = tmp_path / "rules"
    shutil.copytree(RULE_PACK_DIR, pack_copy)
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    monkeypatch.setattr(shutil, "which", which)

    with pytest.raises(DependencyError) as caught:
        run_rule_pack_tests(pack_copy)

    assert (
        installer_semgrep.is_file(),
        caught.value.details["tool_name"],
        "semgrep.dev" in caught.value.details["install_hint"],
        process_fake.calls,
    ) == (True, "semgrep", True, [])
