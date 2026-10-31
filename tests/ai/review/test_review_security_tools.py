"""Unit tests for security tools integration in AI review pipeline and native agent tools."""

from __future__ import annotations

import json
from pathlib import Path

from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.tools.registry import get_default_tools
from tests.support.fakes.git import GitFake
from tests.support.fakes.process import ProcessAnswer
from tests.support.fakes.scanners import ScannerFake
from tests.support.fakes.tool_executor import ToolAnswer


def test_native_security_tools_in_registry() -> None:
    """get_default_tools must register all discrete security scanner tools."""
    tools = get_default_tools()
    tool_names = [t.__name__ for t in tools if hasattr(t, "__name__")]
    assert "scan_trivy" in tool_names
    assert "scan_kubelinter" in tool_names
    assert "scan_pluto" in tool_names
    assert "scan_bandit" in tool_names
    assert "scan_popeye" in tool_names


_MANIFEST = """\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
spec:
  template:
    spec:
      containers:
        - name: app
          image: example.com/app:1.0
---
apiVersion: extensions/v1beta1
kind: Ingress
metadata:
  name: app
"""


def _scanned_workspace(root: Path) -> Path:
    """A checkout with a Dockerfile, a Python module and a Kubernetes manifest, whose review.toml
    names the Kubernetes version that Pluto checks against."""
    root.mkdir()
    (root / ".git").mkdir()
    files = {
        "Dockerfile": "FROM alpine\n",
        "src/main.py": "import subprocess\n" * 15,
        "k8s/app.yaml": _MANIFEST,
        ".devops/review.toml": 'kubernetes_version = "v1.31.0"\n',
    }
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    return root


def _script_scanner_reports(scanner_fake: ScannerFake, workspace: Path) -> None:
    """Script one finding for Trivy, Bandit, kube-linter and Pluto, in the report that each tool
    prints."""
    trivy = {
        "Results": [
            {
                "Target": "Dockerfile",
                "Misconfigurations": [
                    {
                        "ID": "DS002",
                        "Title": "Image user should not be 'root'",
                        "Severity": "HIGH",
                        "Resolution": "Add 'USER <non root user name>' line to the Dockerfile",
                    }
                ],
            }
        ]
    }
    bandit = {
        "errors": [],
        "results": [
            {
                "filename": str(workspace / "src" / "main.py"),
                "issue_severity": "HIGH",
                "issue_text": "subprocess call with shell=True identified, security issue.",
                "line_number": 10,
                "test_id": "B602",
                "test_name": "subprocess_popen_with_shell_equals_true",
            }
        ],
    }
    kube_linter = {
        "Reports": [
            {
                "Check": "no-read-only-root-fs",
                "Diagnostic": {
                    "Message": 'container "app" does not have a read-only root file system'
                },
                "Remediation": "Set readOnlyRootFilesystem to true in the container securityContext.",
                "Object": {
                    "K8sObject": {"GroupVersionKind": {"Kind": "Deployment"}, "Name": "app"},
                    "Metadata": {"FilePath": str(workspace / "k8s" / "app.yaml")},
                },
            }
        ]
    }
    pluto = {
        "items": [
            {
                "name": "app",
                "filePath": "k8s/app.yaml",
                "api": {
                    "version": "extensions/v1beta1",
                    "kind": "Ingress",
                    "deprecated-in": "v1.14.0",
                    "removed-in": "v1.22.0",
                    "replacement-api": "networking.k8s.io/v1",
                },
                "deprecated": True,
                "removed": True,
            }
        ]
    }
    # Each tool's exit code for a report with a finding: Pluto's 3 says that an API is removed.
    for tool, exit_code, report in (
        ("trivy", 0, trivy),
        ("bandit", 1, bandit),
        ("kube-linter", 1, kube_linter),
        ("pluto", 3, pluto),
    ):
        scanner_fake.script(tool, ToolAnswer(exit_code=exit_code, stdout=json.dumps(report)))


def test_pipeline_multi_scanner_aggregation(
    tmp_path: Path, git_fake: GitFake, scanner_fake: ScannerFake
) -> None:
    """Each payload holds the findings of the scanners of its file: Trivy for the Dockerfile,
    Bandit for the Python module, kube-linter and Pluto for the manifest. The orchestrator takes
    a temporary workspace and the scanner fake through its constructor (#2098)."""
    git_fake.answer(
        lambda call: bool(call.argv and "rev-parse" in call.argv),
        ProcessAnswer(returncode=0, stdout="1111111111111111111111111111111111111111\n"),
    )
    git_fake.answer(
        lambda call: bool(call.argv and "status" in call.argv),
        ProcessAnswer(returncode=0, stdout=""),
    )
    git_fake.answer(
        lambda call: bool(call.argv and "diff" in call.argv),
        ProcessAnswer(returncode=0, stdout=""),
    )
    git_fake.answer(
        lambda call: bool(call.argv and "ls-files" in call.argv),
        ProcessAnswer(
            returncode=0,
            stdout="Dockerfile\0src/main.py\0k8s/app.yaml\0.devops/review.toml\0",
        ),
    )
    workspace = _scanned_workspace(tmp_path / "workspace")
    _script_scanner_reports(scanner_fake, workspace)
    orchestrator = ReviewPipelineOrchestrator(
        session_id="test-sec-tools",
        session_dir=tmp_path / "test-sec-tools",
        target_dir=workspace,
        tool_executor=scanner_fake,
    )

    payloads = orchestrator.init_per_file_payloads(
        file_paths=["Dockerfile", "src/main.py", "k8s/app.yaml"],
        metadata_by_path={},
    )

    assert {p.file_path: sorted(f.title for f in p.findings) for p in payloads} == {
        "Dockerfile": ["[DS002] Image user should not be 'root'"],
        "src/main.py": ["[B602] subprocess call with shell=True identified, security issue."],
        "k8s/app.yaml": [
            "[Removed API] Ingress 'app' uses extensions/v1beta1",
            '[no-read-only-root-fs] container "app" does not have a read-only root file system',
        ],
    }


def test_review_pipeline_admit_inline_suppression_added_by_change(
    scanner_fake: ScannerFake,
    tmp_path: Path,
    git_fake: GitFake,
) -> None:
    """Inline suppressions added by the change stay OPEN with suppressed_by_change=True."""
    from devops_cli.review.state import FindingState

    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    # Bandit's own marker: Bandit ignores noqa comments, and so does admission (#1341)
    (src_dir / "main.py").write_text("import os  # nosec B602\n", encoding="utf-8")

    bandit = {
        "errors": [],
        "results": [
            {
                "filename": str(tmp_path / "src" / "main.py"),
                "issue_severity": "HIGH",
                "issue_text": "Shell injection",
                "line_number": 1,
                "test_id": "B602",
                "test_name": "subprocess_popen_with_shell_equals_true",
            }
        ],
    }
    scanner_fake.script("bandit", ToolAnswer(exit_code=1, stdout=json.dumps(bandit)))

    orch_added = ReviewPipelineOrchestrator(
        session_id="test-added-supp",
        session_dir=tmp_path / "test-added-supp",
        target_dir=tmp_path,
        tool_executor=scanner_fake,
    )
    orch_added.init_per_file_payloads(
        file_paths=["src/main.py"],
        metadata_by_path={},
        added_diff_lines={("src/main.py", 1)},
    )
    f_added = orch_added.admitted_scanner_findings[0]

    orch_base = ReviewPipelineOrchestrator(
        session_id="test-base-supp",
        session_dir=tmp_path / "test-base-supp",
        target_dir=tmp_path,
        tool_executor=scanner_fake,
    )
    orch_base.init_per_file_payloads(
        file_paths=["src/main.py"],
        metadata_by_path={},
        added_diff_lines=set(),
    )
    f_base = orch_base.admitted_scanner_findings[0]

    assert (
        f_added.state,
        f_added.suppressed_by_change,
        f_base.state,
        f_base.suppressed_by_change,
    ) == (FindingState.OPEN, True, FindingState.SUPPRESSED, False)
