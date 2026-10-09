"""`[severity_caps]` in `.devops/review.toml` caps a scanner finding at admission (#1301).

The caps are read from the review.toml the review reads its path classes and suppressions from,
and a secret scanner's finding keeps its severity wherever it is: a secret pasted into a document
is still a secret. Any other scanner's finding is capped, even one whose words name a password or
a credential.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.ai.review.pipeline import (
    ReviewPipelineOrchestrator,
    _admit_scanner_findings,
    _wrap_static_findings,
)
from devops_cli.ai.review_schema import Finding, SavedFinding
from devops_cli.security.gitleaks import parse_gitleaks_json
from devops_cli.security.trivy import parse_trivy_json

_REVIEW_TOML = """\
[paths]
test = ["tests/**"]
docs = ["docs/**"]

[severity_caps]
test = "LOW"
docs = "INFO"
"""

_FILES = {
    "tests/test_app.py": (
        "import subprocess\nsubprocess.call('ls', shell=True)\n"
        "password = 'hunter2'\nlogger.info('token %s', password)\n"
    ),
    "docs/notes.md": "token = 'not-a-real-token'\n",
    "docs/conf.py": "if x == x:\n    pass\n",
}


def _repository(root: Path) -> Path:
    """A project holding the review.toml above and the files the candidates cite; outside git,
    so the files are listed without running it."""
    (root / "pyproject.toml").write_text("[project]\nname = 'app'\n", encoding="utf-8")
    (root / ".devops").mkdir()
    (root / ".devops" / "review.toml").write_text(_REVIEW_TOML, encoding="utf-8")
    for name, text in _FILES.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    return root


def _candidates() -> list[SavedFinding]:
    """Bandit and Semgrep findings in a test, two of them about credentials, and Gitleaks and
    Trivy secrets and a Semgrep finding in documentation."""
    bandit = Finding(
        title="[B602] subprocess call with shell=True identified",
        location="tests/test_app.py:2",
        severity="HIGH",
    )
    hardcoded_password = Finding(
        title="[B105] Possible hardcoded password: 'hunter2'",
        location="tests/test_app.py:3",
        severity="MEDIUM",
    )
    credential_logged = Finding(
        title=(
            "[python.lang.security.audit.logging.logger-credential-leak."
            "python-logger-credential-disclosure] Detected a python logger call with a potential "
            "hardcoded secret being logged"
        ),
        location="tests/test_app.py:4",
        severity="HIGH",
    )
    gitleaks = parse_gitleaks_json(
        [
            {
                "RuleID": "slack-webhook-url",
                "Description": "Slack Webhook",
                "File": "docs/notes.md",
                "StartLine": 1,
            }
        ]
    )
    trivy = parse_trivy_json(
        {
            "Results": [
                {
                    "Target": "docs/notes.md",
                    "Secrets": [
                        {"RuleID": "github-pat", "Title": "GitHub PAT", "Severity": "CRITICAL"}
                    ],
                }
            ]
        }
    )
    semgrep = Finding(
        title="[python.lang.correctness.useless-eqeq.useless-eqeq] Useless comparison",
        location="docs/conf.py:1",
        severity="HIGH",
    )
    return [
        *_wrap_static_findings([bandit, hardcoded_password], tool="bandit"),
        *_wrap_static_findings([credential_logged], tool="semgrep"),
        *_wrap_static_findings(gitleaks, tool="gitleaks"),
        *_wrap_static_findings(trivy, tool="trivy"),
        *_wrap_static_findings([semgrep], tool="semgrep"),
    ]


def test_review_toml_severity_caps_apply_at_admission_and_spare_secret_findings(
    tmp_path: Path,
) -> None:
    """A Bandit HIGH in `tests/` is admitted LOW and a Semgrep HIGH in `docs/` INFO, while a
    Gitleaks and a Trivy secret in `docs/` keep the severity their scanner gave. Bandit's B105
    and Semgrep's credential-disclosure rule in `tests/` are capped: their words make them
    `secret_exposure` findings, but no secret scanner reported them."""
    root = _repository(tmp_path)
    orchestrator = ReviewPipelineOrchestrator(session_id="s1301-caps", target_dir=root)
    candidates = _candidates()

    admitted, reported = _admit_scanner_findings(
        candidates,
        session_id="s1301-caps",
        worktree_root=root,
        file_paths=sorted(_FILES),
        secret_scan_files=[],
        resolve_file_path=lambda p: root / p,
        path_classes=orchestrator.path_classes,
        severity_caps=orchestrator.severity_caps,
    )

    assert (
        orchestrator.severity_caps,
        [f.category for f in candidates[1:3]],
        [(f.tool, f.path, f.severity) for f in admitted],
        [f.severity for f in reported],
    ) == (
        {"test": "LOW", "docs": "INFO"},
        ["secret_exposure", "secret_exposure"],
        [
            ("bandit", "tests/test_app.py", "LOW"),
            ("bandit", "tests/test_app.py", "LOW"),
            ("semgrep", "tests/test_app.py", "LOW"),
            ("gitleaks", "docs/notes.md", "HIGH"),
            ("trivy", "docs/notes.md", "CRITICAL"),
            ("semgrep", "docs/conf.py", "INFO"),
        ],
        ["LOW", "LOW", "LOW", "HIGH", "CRITICAL", "INFO"],
    )


def test_a_review_caps_the_scanner_findings_it_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The orchestrator's scanner stage passes the caps it read to admission: Bandit's HIGH in a
    test is reported LOW."""
    from devops_cli.security.base import ScanOutcome

    root = _repository(tmp_path)
    bandit = Finding(
        title="[B602] subprocess call with shell=True identified",
        location="tests/test_app.py:2",
        severity="HIGH",
    )
    monkeypatch.setattr(
        "devops_cli.security.bandit.run_bandit_scan",
        lambda *_, **__: ScanOutcome("ran", [bandit]),
    )
    for scan in (
        "_scan_kubernetes_manifests",
        "_scan_container_and_lockfiles",
        "_scan_secrets",
        "_scan_semgrep",
    ):
        monkeypatch.setattr(f"devops_cli.ai.review.pipeline.{scan}", lambda *_, **__: [])
    orchestrator = ReviewPipelineOrchestrator(session_id="s1301-stage", target_dir=root)

    reported = orchestrator._run_static_scanners(["tests/test_app.py"])

    assert [f.severity for f in reported["tests/test_app.py"]] == ["LOW"]
