"""A review's scanners leave out, by rule id, the rules that never gave a valid finding on this
repository (#1024): kube-linter's `dangling-service`, and Semgrep's `non-literal-import` and
`exec-detected`. Semgrep's `logger-credential-disclosure` stays, because one of its findings was
valid. The exclusions are read here from what the scanner fake saw a review's scans handed."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

from devops_cli.security.kubelinter import run_kubelinter_scan
from devops_cli.security.semgrep import run_semgrep_scan
from tests.support.fakes.scanners import ScannerFake
from tests.support.fakes.tool_executor import ToolAnswer
from tests.support.paths import FIXTURES

NON_LITERAL_IMPORT = "python.lang.security.audit.non-literal-import.non-literal-import"
EXEC_DETECTED = "python.lang.security.audit.exec-detected.exec-detected"
LOGGER_CREDENTIAL_DISCLOSURE = (
    "python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure"
)

_SERVICE = (
    "apiVersion: v1\nkind: Service\nmetadata:\n  name: web\nspec:\n"
    "  selector:\n    app: web\n  ports:\n    - port: 80\n"
)
_SEMGREP_RULES = (
    "rules:\n  - id: eval-of-input\n    languages: [python]\n    severity: ERROR\n"
    "    message: eval of input\n    pattern: eval(input())\n"
)

# (producer, rule, label, where) of one labelled finding.
LabelledFinding = tuple[str, str | None, str, str]


def _review_exclusions(scanner_fake: ScannerFake, tmp_path: Path) -> tuple[Any, list[str]]:
    """The kube-linter config that a review's scan of a manifest is handed, and the Semgrep
    command of a review's scan of a Python file."""
    tree = (tmp_path / "tree").resolve()
    tree.mkdir()
    manifest = tree / "service.yaml"
    manifest.write_text(_SERVICE, encoding="utf-8")
    app = tree / "app.py"
    app.write_text('print("hello")\n', encoding="utf-8")
    rules = tree / "rules.yaml"
    rules.write_text(_SEMGREP_RULES, encoding="utf-8")
    scanner_fake.snapshot_workdirs = True
    scanner_fake.script("kube-linter", ToolAnswer(stdout='{"Checks": [], "Reports": []}'))

    run_kubelinter_scan(manifest, isolated=True)
    run_semgrep_scan([app], config=str(rules), reviewed_tree=tree)

    kube_linter, semgrep = scanner_fake.runs
    config = yaml.safe_load(kube_linter.workdir_files["kube-linter.yaml"])
    return config, semgrep.argv


def _excluded_rules(argv: list[str]) -> set[str]:
    """The rule ids that a Semgrep command names with `--exclude-rule`."""
    return {argv[i + 1] for i, word in enumerate(argv[:-1]) if word == "--exclude-rule"}


def _replay(
    findings: Iterable[LabelledFinding], checks: set[str], rules: set[str]
) -> tuple[dict[str | None, int], list[str], int]:
    """How many findings of each rule the exclusions drop, where each dropped valid finding is,
    and how many valid findings stay."""
    dropped: Counter[str | None] = Counter()
    valid_dropped: list[str] = []
    valid_kept = 0
    for producer, rule, label, where in findings:
        excluded = (producer == "kube-linter" and rule in checks) or (
            producer == "semgrep" and rule in rules
        )
        valid = label.startswith("valid")
        if excluded:
            dropped[rule] += 1
            if valid:
                valid_dropped.append(where)
        elif valid:
            valid_kept += 1
    return dict(dropped), valid_dropped, valid_kept


def _s3_to_s5_candidates() -> list[LabelledFinding]:
    """The scanner candidates of the review sessions S3 to S5, labelled by their evaluation."""
    path = FIXTURES / "review_replay" / "s3_s5_scanner_candidates.json"
    rows = json.loads(path.read_text(encoding="utf-8"))["candidates"]
    return [
        (row["producer"], row["rule"], row["label"], f"{row['session']}[{row['candidate']}]")
        for row in rows
    ]


def _loop_study_labels() -> list[LabelledFinding]:
    """The labelled findings of the review redesign's S11 and S12-S21 runs (#1138)."""
    path = FIXTURES / "review_labels" / "labels.json"
    rows = json.loads(path.read_text(encoding="utf-8"))["labels"]
    return [
        (row["identity"]["producer"], row["identity"]["rule"], row["label"], row["defect_id"])
        for row in rows
    ]


def test_a_review_kube_linter_scan_leaves_out_dangling_service_and_keeps_the_default_checks(
    scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    """kube-linter runs one manifest at a time in a review, so it never sees the pods of a
    Service's sibling file or of a Helm release: `dangling-service` is left out, and every other
    default check stays."""
    config, _ = _review_exclusions(scanner_fake, tmp_path)

    assert config == {"checks": {"exclude": ["dangling-service"]}}


def test_a_review_semgrep_scan_leaves_out_non_literal_import_and_exec_detected(
    scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    """The review's Semgrep scan leaves out the two rules by id and keeps the logger rule."""
    _, argv = _review_exclusions(scanner_fake, tmp_path)

    assert (_excluded_rules(argv), LOGGER_CREDENTIAL_DISCLOSURE in argv) == (
        {NON_LITERAL_IMPORT, EXEC_DETECTED},
        False,
    )


def test_a_semgrep_scan_outside_a_review_leaves_out_no_rule(
    scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    """Only a review's scan leaves the rules out: `devops scan` runs every rule of its config."""
    app = tmp_path / "app.py"
    app.write_text('print("hello")\n', encoding="utf-8")
    rules = tmp_path / "rules.yaml"
    rules.write_text(_SEMGREP_RULES, encoding="utf-8")

    run_semgrep_scan(app, config=str(rules))

    [run] = scanner_fake.runs
    assert _excluded_rules(run.argv) == set()


def test_the_review_exclusions_drop_no_finding_that_was_labelled_valid(
    scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    """Replayed over the labelled S3-S5 candidates and the labelled S11-S21 findings, the
    exclusions drop only false findings, and every valid finding, the logger rule's too, stays."""
    config, argv = _review_exclusions(scanner_fake, tmp_path)
    checks = set(config["checks"]["exclude"])
    rules = _excluded_rules(argv)

    replays = (
        _replay(_s3_to_s5_candidates(), checks, rules),
        _replay(_loop_study_labels(), checks, rules),
    )

    assert replays == (
        ({"dangling-service": 12, NON_LITERAL_IMPORT: 21, EXEC_DETECTED: 1}, [], 8),
        ({"dangling-service": 17, NON_LITERAL_IMPORT: 4}, [], 20),
    )
