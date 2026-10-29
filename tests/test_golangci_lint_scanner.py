"""Unit tests for GolangciLintScanner integration (#603).

golangci-lint loads the packages of a module through the `go` command. In the review sandbox the
scanner gives it the toolchain and the module cache of the host and no network (#2129). These
cases answer `go env` through the process fake and golangci-lint through `ToolExecutorFake`, so
no `go` and no golangci-lint start.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from devops_cli.ai.review_schema import Finding
from devops_cli.config.commands import BIN_GOLANGCI_LINT
from devops_cli.security.base import ScanOutcome
from devops_cli.security.golangci_lint import (
    DEFAULT_LINTERS,
    OPTIONAL_LINTERS,
    GolangciLintScanner,
)
from devops_cli.security.registry import ScannerRegistry
from devops_cli.security.tool_executor import RecordingToolExecutor
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.fakes.scanners import ScannerFake
from tests.support.fakes.tool_executor import ToolAnswer, ToolExecutorFake

# What golangci-lint 1.64.6 writes when go/packages cannot load the packages: its own text,
# measured on 2026-10-29, then the standard error of the `go` command.
_LOAD_ERROR = (
    'level=error msg="Running error: context loading failed: failed to load packages: failed to '
    'load packages: failed to load with go/packages: err: exit status 1: stderr: {go_error}"\n'
)
# The error of the `go` command for a module that is not in the module cache when GOPROXY=off
# (`errProxyOff`, cmd/go/internal/modfetch/proxy.go).
_MODULE_NOT_IN_CACHE = "go: example.com/dep@v1.0.0: module lookup disabled by GOPROXY=off"
_NO_RESULTS = json.dumps(
    {"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "golangci-lint"}}, "results": []}]}
)


def _go_module(directory: Path) -> Path:
    """A Go module that requires one other module, so the `go` command needs the module cache."""
    directory.mkdir()
    (directory / "go.mod").write_text(
        "module example.com/m\n\ngo 1.23\n\nrequire example.com/dep v1.0.0\n", encoding="utf-8"
    )
    (directory / "main.go").write_text("package main\n\nfunc main() {}\n", encoding="utf-8")
    return directory


def _is_go_env(call: ProcessCall) -> bool:
    return Path(call.argv[0]).name == "go" and call.argv[1:2] == ("env",)


def _answer_go_env(process_fake: ProcessFake, root: Path, module_cache: Path) -> None:
    """`go env -json GOROOT GOMODCACHE` names `root` and `module_cache`."""
    names = {"GOROOT": str(root), "GOMODCACHE": str(module_cache)}
    process_fake.answer(_is_go_env, ProcessAnswer(stdout=json.dumps(names)))


def _toolchain(directory: Path) -> Path:
    (directory / "bin").mkdir(parents=True)
    return directory


def test_golangci_lint_scanner_registered_in_registry() -> None:
    """GolangciLintScanner exists in security.registry and is in default registry."""
    from devops_cli.security.registry import GolangciLintScanner as RegistryScanner

    assert RegistryScanner is GolangciLintScanner

    registry = ScannerRegistry(auto_load_defaults=True)
    scanner = registry.get("golangci-lint")
    assert scanner is not None
    assert isinstance(scanner, GolangciLintScanner)
    assert "golangci-lint" in registry.list_scanners()


def test_golangci_lint_default_linters_and_ordering() -> None:
    """Default linters are errcheck, govet, and staticcheck in that order."""
    assert DEFAULT_LINTERS == ("errcheck", "govet", "staticcheck")
    assert OPTIONAL_LINTERS == ("contextcheck",)

    scanner = GolangciLintScanner()
    assert scanner.linters == ["errcheck", "govet", "staticcheck"]
    assert tuple(scanner.DEFAULT_LINTERS) == ("errcheck", "govet", "staticcheck")
    assert tuple(scanner.OPTIONAL_LINTERS) == ("contextcheck",)


def test_golangci_lint_contextcheck_optional() -> None:
    """contextcheck is properly configured as opt-in."""
    scanner_default = GolangciLintScanner()
    assert "contextcheck" not in scanner_default.linters

    scanner_opt_in = GolangciLintScanner(enable_contextcheck=True)
    assert "contextcheck" in scanner_opt_in.linters
    assert scanner_opt_in.linters == ["errcheck", "govet", "staticcheck", "contextcheck"]


def test_golangci_lint_build_command() -> None:
    """build_command constructs the argument list with SARIF output and enabled linters."""
    scanner = GolangciLintScanner()
    cmd = scanner.build_command(Path("."))
    assert cmd[:3] == ["golangci-lint", "run", "--out-format"]
    assert cmd[3] == "sarif"
    assert "--disable-all" in cmd

    enable_indices = [i for i, arg in enumerate(cmd) if arg == "--enable"]
    enabled = [cmd[i + 1] for i in enable_indices]
    assert enabled == ["errcheck", "govet", "staticcheck"]


def test_golangci_lint_build_command_with_contextcheck() -> None:
    """build_command includes contextcheck when enabled."""
    scanner = GolangciLintScanner(enable_contextcheck=True)
    cmd = scanner.build_command(Path("."))
    enable_indices = [i for i, arg in enumerate(cmd) if arg == "--enable"]
    enabled = [cmd[i + 1] for i in enable_indices]
    assert enabled == ["errcheck", "govet", "staticcheck", "contextcheck"]


def test_golangci_lint_sarif_output_conversion() -> None:
    """SARIF output is parsed into Finding models using from_sarif and to_finding."""
    sample_sarif = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "golangci-lint",
                        "version": "1.64.6",
                        "rules": [
                            {
                                "id": "govet",
                                "shortDescription": {"text": "govet analysis issue"},
                                "properties": {"security-severity": "7.5"},
                            }
                        ],
                    }
                },
                "results": [
                    {
                        "ruleId": "govet",
                        "level": "error",
                        "message": {"text": "cancel function not called on all paths"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "pkg/worker/worker.go"},
                                    "region": {"startLine": 42},
                                }
                            }
                        ],
                    }
                ],
            }
        ],
    }

    scanner = GolangciLintScanner()
    findings = scanner.parse_output(sample_sarif, Path("."))
    assert len(findings) == 1
    finding = findings[0]
    assert isinstance(finding, Finding)
    assert finding.location == "pkg/worker/worker.go:42"
    assert "cancel function not called" in finding.title
    assert finding.severity == "HIGH"


def test_golangci_lint_missing_binary_records_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing golangci-lint binary records unavailable state."""
    (tmp_path / "go.mod").write_text("module example.com/test\ngo 1.23\n", encoding="utf-8")
    (tmp_path / "main.go").write_text("package main\nfunc main() {}\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(tmp_path / "no-programs"))

    outcome = GolangciLintScanner().scan(tmp_path)

    assert isinstance(outcome, ScanOutcome)
    assert outcome.status == "unavailable"
    assert outcome.findings == []
    assert "golangci-lint" in outcome.reason


def test_golangci_lint_missing_go_records_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scanner_fake: ScannerFake
) -> None:
    """Missing go toolchain records failed state, never zero findings."""
    (tmp_path / "go.mod").write_text("module example.com/test\ngo 1.23\n", encoding="utf-8")
    (tmp_path / "main.go").write_text("package main\nfunc main() {}\n", encoding="utf-8")
    scanner_fake.script(BIN_GOLANGCI_LINT, ToolAnswer())
    # golangci-lint is installed, and go is not: PATH holds only the fake's programs.
    monkeypatch.setenv("PATH", str(scanner_fake.bin_dir))

    outcome = GolangciLintScanner().scan(tmp_path)

    assert isinstance(outcome, ScanOutcome)
    assert outcome.status == "failed"
    assert outcome.findings == []
    assert "go" in outcome.reason


def test_golangci_lint_typecheck_failure_records_failed(
    tmp_path: Path, process_fake: ProcessFake, tool_executor_fake: ToolExecutorFake
) -> None:
    """Typecheck or package loading error records failed state."""
    module = _go_module(tmp_path / "module")
    _answer_go_env(process_fake, _toolchain(tmp_path / "go"), tmp_path / "gomodcache")
    tool_executor_fake.script(
        BIN_GOLANGCI_LINT,
        ToolAnswer(exit_code=1, stderr="typechecking error: expected declaration, found 'EOF'"),
    )

    outcome = GolangciLintScanner(tool_executor=tool_executor_fake).scan(module)

    assert isinstance(outcome, ScanOutcome)
    assert outcome.status == "failed"
    assert outcome.findings == []
    assert "typechecking error" in outcome.reason


def test_a_scan_gets_the_go_toolchain_and_the_module_cache_read_only_and_no_network(
    tmp_path: Path, process_fake: ProcessFake, tool_executor_fake: ToolExecutorFake
) -> None:
    """The sandbox has no network, a read-only tree and a PATH of system directories (#2129). So
    the request binds the toolchain and the module cache that `go env` names, leads the PATH with
    the toolchain, keeps the Go caches outside the tree, and lets the `go` command fetch no module
    and no toolchain. It sets no GOFLAGS: the default of the `go` command never writes `go.mod`."""
    module = _go_module(tmp_path / "module")
    root = _toolchain(tmp_path / "go")
    module_cache = tmp_path / "gomodcache"
    module_cache.mkdir()
    _answer_go_env(process_fake, root, module_cache)
    tool_executor_fake.script(BIN_GOLANGCI_LINT, ToolAnswer(stdout=_NO_RESULTS))

    outcome = GolangciLintScanner(tool_executor=tool_executor_fake).scan(module)

    (go_env,) = [call for call in process_fake.calls if _is_go_env(call)]
    (request,) = tool_executor_fake.requests
    env = request.env
    caches = (Path(env["GOCACHE"]), Path(env["GOLANGCI_LINT_CACHE"]))
    assert outcome.status == "ran"
    assert go_env.argv[1:] == ("env", "-json", "GOROOT", "GOMODCACHE")
    assert go_env.cwd is not None
    assert not go_env.cwd.is_relative_to(module)
    assert (go_env.env or {}).get("GOTOOLCHAIN") == "local"
    assert {root, module_cache} <= set(request.read_only_binds)
    assert (env["GOROOT"], env["GOMODCACHE"]) == (str(root), str(module_cache))
    assert env["PATH"].split(os.pathsep)[0] == str(root / "bin")
    assert (env["GOPROXY"], env["GOTOOLCHAIN"]) == ("off", "local")
    assert "GOFLAGS" not in env
    assert request.writable_dirs == caches
    assert [cache.is_dir() and not cache.is_relative_to(module) for cache in caches] == [True] * 2
    assert request.network is None


def test_a_host_whose_go_env_fails_gives_a_failed_scan(
    tmp_path: Path, process_fake: ProcessFake, tool_executor_fake: ToolExecutorFake
) -> None:
    """Without the toolchain and the module cache, the request cannot give golangci-lint what it
    needs in the sandbox, so the scan fails and starts no golangci-lint (#2129)."""
    module = _go_module(tmp_path / "module")
    process_fake.answer(
        _is_go_env, ProcessAnswer(returncode=1, stderr="go: cannot find GOROOT directory")
    )

    outcome = GolangciLintScanner(tool_executor=tool_executor_fake).scan(module)

    assert (outcome.status, outcome.findings, tool_executor_fake.requests) == ("failed", [], [])
    assert "go env" in outcome.reason
    assert "cannot find GOROOT directory" in outcome.reason


def test_a_module_whose_modules_are_not_in_the_cache_is_a_coverage_gap(
    tmp_path: Path, process_fake: ProcessFake, tool_executor_fake: ToolExecutorFake
) -> None:
    """With GOPROXY=off, the `go` command stops when a module is not in the module cache. The scan
    did not fail: the host lacks what the sandbox cannot fetch, so it is a coverage gap whose
    reason tells the person how to fill the cache (#2129). The record of the run says that it
    succeeded, as for every coverage gap (#2100)."""
    module = _go_module(tmp_path / "module")
    module_cache = tmp_path / "gomodcache"
    _answer_go_env(process_fake, _toolchain(tmp_path / "go"), module_cache)
    tool_executor_fake.script(
        BIN_GOLANGCI_LINT,
        ToolAnswer(exit_code=3, stderr=_LOAD_ERROR.format(go_error=_MODULE_NOT_IN_CACHE)),
    )

    recording = RecordingToolExecutor(tool_executor_fake)

    outcome = GolangciLintScanner(tool_executor=recording).scan(module)

    (request,) = tool_executor_fake.requests
    (run,) = recording.runs
    assert (outcome.status, outcome.findings) == ("coverage_gap", [])
    assert (run.exit_code, run.success) == (3, True)
    assert module_cache not in request.read_only_binds
    assert "GOMODCACHE" not in request.env
    assert str(module_cache) in outcome.reason
    assert "go mod download" in outcome.reason


def test_golangci_lint_is_applicable(tmp_path: Path) -> None:
    """Scanner is applicable only when Go files or go.mod exist."""
    scanner = GolangciLintScanner()
    app, reason = scanner.is_applicable(tmp_path)
    assert not app
    assert "No Go source files" in reason

    (tmp_path / "main.go").write_text("package main\n", encoding="utf-8")
    app2, reason2 = scanner.is_applicable(tmp_path)
    assert app2
    assert reason2 == ""
