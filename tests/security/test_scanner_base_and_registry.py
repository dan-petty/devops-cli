"""The base security scanner: how a scan runs, falls back and reports a failure, and the registry of scanners."""

from __future__ import annotations

import errno
import json
import os
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.review_schema import Finding
from devops_cli.config.constants import (
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_SCANNER_STDOUT_EXCERPT_CHARS,
)
from devops_cli.dry_run.state import set_dry_run
from devops_cli.security.base import BaseSecurityScanner, ScanOutcome, materialize_targets
from devops_cli.security.registry import ScannerRegistry, global_scanner_registry
from tests.support.fakes.scanners import ScannerFake
from tests.support.fakes.tool_executor import ToolAnswer


class MockDummyScanner(BaseSecurityScanner):
    """Test scanner implementation."""

    name = "mock_tool"
    binary_name = "mock-tool-bin"

    def build_command(self, target_path: Path, **kwargs: Any) -> list[str]:
        return [self.binary_name, "--target", str(target_path)]

    def parse_output(self, data: Any, target_path: Path) -> list[Finding]:
        if not isinstance(data, list):
            return []
        findings: list[Finding] = []
        for item in data:
            findings.append(
                Finding(
                    severity=item.get("sev", "LOW"),
                    location=f"{target_path.name}:{item.get('line', 1)}",
                    title=item.get("title", "Issue"),
                    description=item.get("desc", "Description"),
                    fix="Fix it",
                )
            )
        return findings

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.call_count: int = 0

    def scan(self, target_path: Any, *args: Any, **kwargs: Any) -> ScanOutcome:
        self.call_count += 1
        return super().scan(target_path, *args, **kwargs)

    def fallback_scan(self, target_path: Path) -> list[Finding]:
        return [
            Finding(
                severity="INFO",
                location=f"{target_path.name}:1",
                title="Fallback finding",
                description="Triggered fallback",
                fix="Install mock tool",
            )
        ]


class FailingDummyScanner(MockDummyScanner):
    """Scanner that raises on scan execution."""

    def scan(self, target_path: Any, *args: Any, **kwargs: Any) -> ScanOutcome:
        self.call_count += 1
        raise RuntimeError("Scanner crashed")


def test_scanner_executes_successfully(tmp_path: Path, scanner_fake: ScannerFake) -> None:
    """When binary is available, scanner runs its tool and parses output."""
    fake_data = [{"sev": "HIGH", "line": 42, "title": "Critical flaw", "desc": "Buffer overflow"}]
    scanner_fake.script("mock-tool-bin", ToolAnswer(stdout=json.dumps(fake_data)))

    findings = MockDummyScanner().scan(tmp_path)

    assert [(f.severity, "42" in f.location, f.title) for f in findings] == [
        ("HIGH", True, "Critical flaw")
    ]


def test_scanner_falls_back_when_binary_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When binary is not on PATH, executes fallback scan."""
    monkeypatch.setenv("PATH", str(tmp_path / "no-programs"))

    findings = MockDummyScanner().scan(tmp_path)

    assert [f.title for f in findings] == ["Fallback finding"]


def test_scanner_falls_back_on_subprocess_error(tmp_path: Path, scanner_fake: ScannerFake) -> None:
    """When the tool cannot start, catches the exception and runs fallback."""
    scanner_fake.fail("mock-tool-bin", RuntimeError("Process execution failed"))

    findings = MockDummyScanner().scan(tmp_path)

    assert [f.title for f in findings] == ["Fallback finding"]


def test_scanner_falls_back_on_nonzero_exit_with_malformed_output(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """When the tool exits non-zero with malformed output, trigger fallback."""
    scanner_fake.script(
        "mock-tool-bin",
        ToolAnswer(exit_code=1, stdout="Fatal Error: corrupted config", stderr="fatal"),
    )

    findings = MockDummyScanner().scan(tmp_path)

    assert [f.title for f in findings] == ["Fallback finding"]


class _NoPatternsScanner(BaseSecurityScanner):
    """A scanner with no built-in patterns, so a failed run is reported as failed."""

    name = "no_patterns_tool"
    binary_name = "no-patterns-bin"

    def build_command(self, target_path: Path, **kwargs: Any) -> list[str]:
        return [self.binary_name, str(target_path)]

    def parse_output(self, data: Any, target_path: Path) -> list[Finding]:
        return []


def _failed_reason(
    tmp_path: Path, scanner_fake: ScannerFake, stdout: str, stderr: str
) -> tuple[str, str]:
    """Run _NoPatternsScanner on output exiting 1, returning the outcome's status and reason."""
    scanner_fake.script("no-patterns-bin", ToolAnswer(exit_code=1, stdout=stdout, stderr=stderr))
    outcome = _NoPatternsScanner().scan(tmp_path)
    return outcome.status, outcome.reason


def test_a_failed_scan_says_its_output_was_not_json_and_quotes_it(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """Verify the reason names non-JSON stdout and quotes its start on one line, then stderr."""
    reason = _failed_reason(
        tmp_path,
        scanner_fake,
        stdout='Working... ━━━━ 100% 0:00:20\n{\n  "errors": []\n}\n',
        stderr="[main]\tINFO\tprofile include tests: None\n",
    )

    assert reason == (
        "failed",
        "Scanner exited with code 1; output was not JSON, starting "
        '"Working... ━━━━ 100% 0:00:20 { "errors": [] }"; '
        "stderr: [main] INFO profile include tests: None",
    )


def test_a_failed_scan_quotes_a_bounded_start_of_its_output(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """Verify the quote and the whole reason are cut short, keeping as much stderr as fits."""
    status, reason = _failed_reason(tmp_path, scanner_fake, stdout="x" * 500, stderr="e" * 500)

    assert (status, len(reason), reason.partition('"')[2].partition('"')[0], reason[-12:]) == (
        "failed",
        CONST_MAX_ERROR_DETAIL_LENGTH,
        "x" * (CONST_SCANNER_STDOUT_EXCERPT_CHARS - 1) + "…",
        "e" * 11 + "…",
    )


def test_a_failed_scan_masks_its_output_before_cutting_the_quote(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """Verify a token the quote's cut would split is masked whole, so no part of it remains."""
    token = "ghp_" + "Q7rT2xW9yB4nM6kP1sD8fG3hJ5lZ0cV2aE7u"
    status, reason = _failed_reason(
        tmp_path, scanner_fake, stdout="x" * 87 + " " + token, stderr=""
    )

    assert (status, token[:11] in reason, reason.partition('"')[2].partition('"')[0]) == (
        "failed",
        False,
        "x" * 87 + " <masked-git…",
    )


def test_a_registered_scanner_is_found_by_name_and_listed() -> None:
    """The registry returns the scanner it registered, and lists its name."""
    registry = ScannerRegistry()
    scanner = MockDummyScanner()

    registry.register(scanner)

    assert (registry.get("mock_tool") is scanner, "mock_tool" in registry.list_scanners()) == (
        True,
        True,
    )


def test_a_batch_scan_gives_each_scanner_its_findings(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """A scanner whose tool reports nothing has an empty list in the batch results."""
    registry = ScannerRegistry()
    registry.register(MockDummyScanner())
    scanner_fake.script("mock-tool-bin", ToolAnswer(stdout="[]"))

    assert registry.scan_all(tmp_path) == {"mock_tool": []}


def test_a_scanner_that_raises_is_failed_and_only_named_registered_scanners_run(
    tmp_path: Path,
) -> None:
    """A scanner that raises is recorded as failed with its error, a name the registry does not
    hold is skipped, and a registered scanner that is not named does not run."""
    registry = ScannerRegistry()
    scanner = FailingDummyScanner()
    registry.register(scanner)
    other = MockDummyScanner()
    other.name = "other_tool"
    registry.register(other)

    results = registry.scan_all(tmp_path, names=["mock_tool", "unregistered"])

    assert (
        {name: (o.status, o.reason) for name, o in results.items()},
        other.call_count,
    ) == (
        {"mock_tool": ("failed", "Scanner crashed")},
        0,
    )


ALL_EXPECTED_SCANNER_NAMES = [
    "bandit",
    "gitleaks",
    "kubeconform",
    "kubelinter",
    "pluto",
    "popeye",
    "semgrep",
    "tflint",
    "trivy",
    "trivy-config",
]


def test_the_default_registry_holds_13_scanners_and_no_dive() -> None:
    """dive is gone (#2427): the default registry holds the 13 scanners that remain."""
    registry = ScannerRegistry(auto_load_defaults=True)

    assert (len(registry.list_scanners()), registry.get("dive")) == (13, None)


def test_all_11_scanners_registered_in_global_registry() -> None:
    """Verify 100% of all 11 security scanners are registered in global_scanner_registry."""
    registered = global_scanner_registry.list_scanners()
    for name in ALL_EXPECTED_SCANNER_NAMES:
        assert name in registered, f"Scanner '{name}' is not registered in global_scanner_registry"
        scanner = global_scanner_registry.get(name)
        assert scanner is not None
        assert isinstance(scanner, BaseSecurityScanner)
        assert scanner.name == name
        assert scanner.binary_name != ""


def test_all_11_scanner_classes_inherit_base_security_scanner() -> None:
    """Verify each of the 11 scanner classes subclasses BaseSecurityScanner."""
    from devops_cli.security import (
        BanditScanner,
        GitleaksScanner,
        KubeconformScanner,
        KubelinterScanner,
        PlutoScanner,
        PopeyeScanner,
        SemgrepScanner,
        TflintScanner,
        TrivyConfigScanner,
        TrivyScanner,
    )

    classes = [
        BanditScanner,
        GitleaksScanner,
        KubeconformScanner,
        KubelinterScanner,
        PlutoScanner,
        PopeyeScanner,
        SemgrepScanner,
        TflintScanner,
        TrivyConfigScanner,
        TrivyScanner,
    ]
    for cls in classes:
        assert issubclass(cls, BaseSecurityScanner)
        instance = cls()  # type: ignore[abstract]
        assert instance.name != ""
        assert instance.binary_name != ""


def _sample_target(scanner_name: str, tmp_path: Path) -> Path:
    """The file that a scanner scans in a contract test: a manifest for kubeconform, which starts
    only for a target that holds one (#2214), else a Python file."""
    name, text = (
        ("pod.yaml", "apiVersion: v1\nkind: Pod\nmetadata:\n  name: web\n")
        if scanner_name == "kubeconform"
        else ("test_target.py", "content = True\n")
    )
    target = tmp_path / name
    target.write_text(text, encoding="utf-8")
    return target


def test_all_11_scanners_dry_run_simulation(tmp_path: Path) -> None:
    """Verify all 11 scanners handle dry-run execution by returning simulated findings."""
    set_dry_run(True)
    for name in ALL_EXPECTED_SCANNER_NAMES:
        scanner = global_scanner_registry.get(name)
        assert scanner is not None
        test_file = _sample_target(name, tmp_path)
        findings = scanner.scan(test_file, image="ubuntu:latest", context="test-cluster")
        assert isinstance(findings, list)
        assert len(findings) >= 1
        assert any("DRY-RUN" in f.title.upper() or "SIMULATED" in f.title.upper() for f in findings)


def test_scanner_fallback_when_binary_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify all 11 scanners gracefully execute fallback when their external binary is missing."""
    test_file = tmp_path / "test.yaml"
    test_file.write_text("apiVersion: v1\nkind: Pod\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(tmp_path / "no-programs"))

    for name in ALL_EXPECTED_SCANNER_NAMES:
        scanner = global_scanner_registry.get(name)
        assert scanner is not None
        assert scanner.name == name
        findings = scanner.scan(test_file)
        assert isinstance(findings, list)


_SAMPLE_STDOUTS: dict[str, str] = {
    "bandit": json.dumps(
        {
            "results": [
                {
                    "test_id": "B101",
                    "filename": "app.py",
                    "line_number": 10,
                    "issue_severity": "HIGH",
                    "issue_text": "assert used",
                    "more_info": "",
                }
            ]
        }
    ),
    "gitleaks": json.dumps(
        [
            {
                "RuleID": "generic-api-key",
                "File": "secret.py",
                "StartLine": 5,
                "Secret": "abc",
                "Description": "Secret leaked",
            }
        ]
    ),
    "kubeconform": json.dumps(
        {
            "resources": [
                {
                    "filename": "pod.yaml",
                    "kind": "Pod",
                    "name": "web",
                    "version": "v1",
                    "status": "statusInvalid",
                    "msg": "schema error",
                    "validationErrors": [{"path": "/spec", "msg": "schema error"}],
                }
            ]
        }
    ),
    "kubelinter": json.dumps(
        {
            "Reports": [
                {
                    "Check": "no-read-only-root-fs",
                    "Object": {"K8sObject": {"GroupVersionKind": {"Kind": "Deployment"}}},
                    "Diagnostic": {"Message": "Root filesystem writeable"},
                }
            ],
            "Summary": {},
        }
    ),
    "pluto": json.dumps(
        {
            "items": [
                {
                    "name": "deprecated-deploy",
                    "filePath": "/srv/tree/k8s/deploy.yaml",
                    "namespace": "default",
                    "api": {
                        "version": "extensions/v1beta1",
                        "kind": "Deployment",
                        "deprecated-in": "v1.9.0",
                        "removed-in": "v1.16.0",
                        "replacement-api": "apps/v1",
                    },
                    "deprecated": True,
                    "removed": True,
                }
            ]
        }
    ),
    "popeye": json.dumps(
        {
            "popeye": {
                "sections": [
                    {
                        "linter": "deployments",
                        "gvr": "apps/v1/deployments",
                        "issues": {
                            "default/web": [
                                {
                                    "group": "__root__",
                                    "gvr": "apps/v1/deployments",
                                    "level": 2,
                                    "message": "Container has no resource limits",
                                }
                            ]
                        },
                    }
                ]
            }
        }
    ),
    "semgrep": json.dumps(
        {
            "results": [
                {
                    "check_id": "rules.exec",
                    "path": "test.py",
                    "start": {"line": 15},
                    "end": {"line": 15},
                    "extra": {"message": "Dynamic code execution", "severity": "ERROR"},
                }
            ]
        }
    ),
    "tflint": json.dumps(
        {
            "issues": [
                {
                    "rule": {"name": "terraform_deprecated_syntax"},
                    "message": "Deprecated syntax",
                    "range": {"filename": "main.tf", "start": {"line": 20}},
                    "call": None,
                }
            ]
        }
    ),
    "trivy": json.dumps(
        {
            "Results": [
                {
                    "Target": "Dockerfile",
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2023-1234",
                            "PkgName": "curl",
                            "InstalledVersion": "7.68.0",
                            "Severity": "CRITICAL",
                            "Title": "Curl buffer overflow",
                        }
                    ],
                }
            ]
        }
    ),
    "trivy-config": json.dumps(
        {
            "Results": [
                {
                    "Target": "Dockerfile",
                    "Misconfigurations": [
                        {
                            "ID": "DS-0002",
                            "Title": "Image user should not be 'root'",
                            "Severity": "HIGH",
                        }
                    ],
                }
            ]
        }
    ),
}


@pytest.mark.parametrize("scanner_name", ALL_EXPECTED_SCANNER_NAMES)
def test_scanner_contract_execution_and_parsing(
    scanner_name: str, tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """Verify binary-present contract execution and output parsing for all 11 adapters."""
    scanner = global_scanner_registry.get(scanner_name)
    assert scanner is not None

    test_file = _sample_target(scanner_name, tmp_path)

    scanner_fake.script(
        scanner.binary_name, ToolAnswer(stdout=_SAMPLE_STDOUTS.get(scanner_name, "[]"))
    )
    findings = scanner.scan(test_file, image="ubuntu:latest", context="test-cluster")
    assert isinstance(findings, list)
    assert len(findings) >= 1, (
        f"Scanner '{scanner_name}' failed to produce normalized findings from sample output"
    )


def test_kubelinter_contract_finding_names_its_check(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """kube-linter writes `Check` beside `Diagnostic`, and the title names it."""
    scanner = global_scanner_registry.get("kubelinter")
    assert scanner is not None
    test_file = tmp_path / "test_target.py"
    test_file.write_text("content = True\n", encoding="utf-8")
    scanner_fake.script(scanner.binary_name, ToolAnswer(stdout=_SAMPLE_STDOUTS["kubelinter"]))

    findings = scanner.scan(test_file)

    assert [finding.title for finding in findings] == [
        "[no-read-only-root-fs] Root filesystem writeable"
    ]


def test_materialized_targets_are_hard_links_else_copies_and_replace_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A target is hard-linked under the working directory at its path in the tree, or copied
    when the link fails, as across filesystems; a file already there, such as one devops-cli
    handed the scanner, is never replaced (#1079). Each is named `./<its path>`, and a result
    reported with or without the `./` maps back to the tree's file."""
    tree = tmp_path / "tree"
    (tree / "src").mkdir(parents=True)
    linked, copied, taken = (tree / "src" / name for name in ("linked.py", "copied.py", "taken.py"))
    for target in (linked, copied, taken):
        target.write_text(target.name, encoding="utf-8")
    workdir = tmp_path / "work"
    (workdir / "src").mkdir(parents=True)
    (workdir / "src" / "taken.py").write_text("devops-cli's own", encoding="utf-8")
    link = os.link

    def cross_device_for_copied(source: Any, destination: Any, **kwargs: Any) -> None:
        if Path(source).name == "copied.py":
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        link(source, destination, **kwargs)

    monkeypatch.setattr(os, "link", cross_device_for_copied)
    staged = materialize_targets([linked, copied, taken], tree, workdir)

    assert (
        staged.names,
        [staged.origin(name) for name in ("src/linked.py", "./src/copied.py")],
        (workdir / "src" / "linked.py").samefile(linked),
        (workdir / "src" / "copied.py").samefile(copied),
        (workdir / "src" / "copied.py").read_text(encoding="utf-8"),
        (workdir / "src" / "taken.py").read_text(encoding="utf-8"),
    ) == (
        [os.path.join(os.curdir, "src", name) for name in ("linked.py", "copied.py")],
        [str(linked), str(copied)],
        True,
        False,
        "copied.py",
        "devops-cli's own",
    )
