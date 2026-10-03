"""Unit tests for Semgrep multilingual static AST pattern matching scanner."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.review import pipeline
from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review_schema import SavedFinding
from devops_cli.commands.scan import app as scan_app
from devops_cli.security.base import ScanOutcome
from devops_cli.security.semgrep import (
    parse_semgrep_json,
    run_semgrep_scan,
)

runner = CliRunner()


def test_parse_semgrep_json() -> None:
    raw_data = {
        "results": [
            {
                "check_id": "python.lang.security.deserialization.pickle.avoid-pickle",
                "path": "src/cache.py",
                "start": {"line": 20, "col": 5},
                "end": {"line": 20, "col": 25},
                "extra": {
                    "message": "Avoid using pickle for untrusted deserialization",
                    "severity": "ERROR",
                    "metadata": {"cve": "CVE-2023-XXXX", "owasp": "A08:2021"},
                },
            },
            {
                "check_id": "python.flask.security.audit.xss.direct-use-of-jinja2",
                "path": "src/views.py",
                "start": {"line": 40, "col": 1},
                "end": {"line": 45, "col": 1},
                "extra": {
                    "message": "Potential XSS via unescaped template string",
                    "severity": "WARNING",
                },
            },
        ]
    }

    findings = parse_semgrep_json(raw_data)
    assert len(findings) == 2
    assert findings[0].location == "src/cache.py:20"
    assert findings[0].severity == "HIGH"
    assert "CVE: CVE-2023-XXXX" in (findings[0].fix or "")
    assert findings[1].location == "src/views.py:40-45"
    assert findings[1].severity == "MEDIUM"

    # Fallback to lang catalog message when extra.message is absent
    from devops_cli.lang import MESSAGES

    data_no_msg = {"results": [{"check_id": "test-check", "extra": {}}]}
    findings_no_msg = parse_semgrep_json(data_no_msg)
    assert MESSAGES.scan.semgrep_default_message in findings_no_msg[0].description
    assert MESSAGES.scan.semgrep_default_message in findings_no_msg[0].title


def test_run_semgrep_scan_subprocess_mock(tmp_path: Path) -> None:
    test_file = tmp_path / "app.py"
    test_file.write_text("import pickle\npickle.loads(b'...')\n", encoding="utf-8")

    mock_stdout = json.dumps(
        {
            "results": [
                {
                    "check_id": "avoid-pickle",
                    "path": str(test_file),
                    "start": {"line": 2},
                    "end": {"line": 2},
                    "extra": {
                        "message": "Avoid using pickle",
                        "severity": "ERROR",
                    },
                }
            ]
        }
    )

    with patch("devops_cli.security.semgrep.run_subprocess") as mock_proc:
        mock_proc.return_value = subprocess.CompletedProcess(
            args=["semgrep"], returncode=0, stdout=mock_stdout, stderr=""
        )
        findings = run_semgrep_scan(test_file)
        assert len(findings) == 1
        assert "[avoid-pickle]" in findings[0].title
        assert findings[0].location == f"{test_file}:2"


def test_run_semgrep_scan_dry_run(tmp_path: Path) -> None:
    with patch("devops_cli.security.semgrep.is_dry_run", return_value=True):
        findings = run_semgrep_scan(tmp_path / "main.py")
        assert len(findings) == 1
        assert "[DRY-RUN]" in findings[0].title


def test_scan_semgrep_cli(tmp_path: Path) -> None:
    test_file = tmp_path / "test.py"
    test_file.write_text("x = 1\n", encoding="utf-8")

    clean_outcome = ScanOutcome(status="ran", findings=[], reason="")
    with patch("devops_cli.commands.scan.run_semgrep_scan", return_value=clean_outcome):
        res = runner.invoke(scan_app, ["sast", str(test_file)])
        assert (res.exit_code, "No static AST pattern flaws detected" in res.stdout) == (0, True)

        res_json = runner.invoke(scan_app, ["sast", str(test_file), "--json"])
        assert (res_json.exit_code, "[]" in res_json.stdout) == (0, True)


def test_semgrep_build_scan_command_target_filtering(tmp_path: Path) -> None:
    """_build_scan_command filters out doc, lockfile, and binary extensions."""
    from devops_cli.config.defaults import DEFAULT_SEMGREP_CONFIG
    from devops_cli.security.semgrep import _build_scan_command

    py_file = tmp_path / "service.py"
    yaml_file = tmp_path / "deploy.yaml"
    md_file = tmp_path / "README.md"
    lock_file = tmp_path / "uv.lock"
    bin_file = tmp_path / "image.png"

    for f in (py_file, yaml_file, md_file, lock_file, bin_file):
        f.write_text("content", encoding="utf-8")

    cmd = _build_scan_command(
        [py_file, yaml_file, md_file, lock_file, bin_file], DEFAULT_SEMGREP_CONFIG
    )
    assert cmd is not None
    assert (
        str(py_file.resolve()) in cmd,
        str(yaml_file.resolve()) in cmd,
        str(md_file.resolve()) in cmd,
        str(lock_file.resolve()) in cmd,
        str(bin_file.resolve()) in cmd,
    ) == (True, True, False, False, False)

    none_cmd = _build_scan_command([md_file, lock_file, bin_file], DEFAULT_SEMGREP_CONFIG)
    assert none_cmd is None


def test_resolve_cwd_commonpath(tmp_path: Path) -> None:
    """BaseSecurityScanner._resolve_cwd returns common ancestor directory for file lists."""
    from devops_cli.security.semgrep import SemgrepScanner

    scanner = SemgrepScanner()
    sub_a = tmp_path / "src" / "pkg"
    sub_b = tmp_path / "tests" / "unit"
    sub_a.mkdir(parents=True)
    sub_b.mkdir(parents=True)

    file_a = sub_a / "a.py"
    file_b = sub_b / "b.py"
    file_a.write_text("a", encoding="utf-8")
    file_b.write_text("b", encoding="utf-8")

    resolved_cwd = scanner._resolve_cwd([file_a, file_b])
    assert resolved_cwd == tmp_path


# =============================================================================
# A review's Semgrep scan names only targets under its working directory (#1079)
# =============================================================================

# The files of a review as large as the loop's: 333 paths in nine packages.
_REVIEWED_FILES = [f"pkg{index % 9}/mod_{index}.py" for index in range(333)]
_REVIEWED_SOURCE = "import json\n\nvalue = json.loads('1')\n"


@pytest.fixture(scope="module")
def checkout_of_333_files(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A checkout holding the 333 files; the scans only read it, so the tests share it."""
    tree = tmp_path_factory.mktemp("reviewed") / "tree"
    for name in _REVIEWED_FILES:
        (tree / name).parent.mkdir(parents=True, exist_ok=True)
        (tree / name).write_text(_REVIEWED_SOURCE, encoding="utf-8")
    subprocess.run(["git", "init", "--quiet", str(tree)], check=True, capture_output=True)
    return tree


@pytest.fixture
def reviewed_checkout(checkout_of_333_files: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The checkout under review, with every review scanner but Semgrep stubbed out."""
    monkeypatch.setattr(
        "devops_cli.security.bandit.run_bandit_scan", lambda *_, **__: ScanOutcome("ran")
    )
    monkeypatch.setattr(pipeline, "_scan_secrets", lambda *_, **__: [])
    monkeypatch.setattr(pipeline, "print_info", lambda *_, **__: None)
    return checkout_of_333_files


def _named_targets(cmd: list[str]) -> list[str]:
    """The targets a review's Semgrep command names, after its last flag."""
    return cmd[cmd.index("--quiet") + 1 :]


def _a_regular_file_under(workdir: Path, name: str) -> bool:
    """Whether Semgrep 1.178.0 takes its fast path for `name` run from `workdir`: a relative
    path to a regular file that resolves inside it (`target_manager.py:716-727`)."""
    path = workdir / name
    return (
        not Path(name).is_absolute()
        and not path.is_symlink()
        and path.is_file()
        and path.resolve().is_relative_to(workdir.resolve())
    )


def _semgrep_result(name: str, line: int) -> dict[str, Any]:
    """A Semgrep JSON result for the target its command named `name`, at the path Semgrep
    reports it under: `pkg/mod.py` for `./pkg/mod.py`."""
    return {
        "check_id": "python.lang.json-loads",
        "path": os.path.normpath(name),
        "start": {"line": line},
        "end": {"line": line},
        "extra": {"message": "json.loads of untrusted input", "severity": "WARNING"},
    }


def _review_scan(
    tree: Path,
    semgrep: Callable[..., subprocess.CompletedProcess[str]],
    files: list[str] = _REVIEWED_FILES,
) -> dict[str, list[SavedFinding]]:
    """Run the review's static scanners over `files` with `semgrep` as the binary."""
    orchestrator = ReviewPipelineOrchestrator(session_id="semgrep", target_dir=tree)
    with patch("devops_cli.security.base.run_subprocess", MagicMock(side_effect=semgrep)):
        return orchestrator._run_static_scanners(list(files))


def test_a_reviews_semgrep_scan_names_only_targets_under_its_working_directory(
    reviewed_checkout: Path,
) -> None:
    """Semgrep 1.178.0 takes its fast path only for a regular file under its working directory;
    for each other target it starts a `semgrep-core -rpc` that walks the whole checkout. Since
    #972 a review named 333 absolute paths from a temporary directory, and Semgrep timed out in
    11 of 11 reviews. Each target is now a relative path to a regular file under the working
    directory, led by `./`, and every reviewed file is named once."""
    named: list[tuple[str, bool]] = []

    def semgrep(cmd: list[str], cwd: Path | None = None, **_: Any) -> Any:
        workdir = Path(cwd or ".")
        named.extend((name, _a_regular_file_under(workdir, name)) for name in _named_targets(cmd))
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"results": []}), "")

    _review_scan(reviewed_checkout, semgrep)

    assert sorted(named) == sorted(
        (os.path.join(os.curdir, name), True) for name in _REVIEWED_FILES
    )


def test_semgrep_findings_carry_the_reviewed_trees_paths_and_lines(
    reviewed_checkout: Path,
) -> None:
    """Semgrep reports a target under the name its command gave it. Named relative to its
    working directory, a finding still lands on the reviewed file at its line, located in the
    reviewed tree. The fake Semgrep runs out of time when a target lies outside its working
    directory, as the real one did in the 11 reviews."""

    def semgrep(cmd: list[str], cwd: Path | None = None, **_: Any) -> Any:
        names = _named_targets(cmd)
        if not all(_a_regular_file_under(Path(cwd or "."), name) for name in names):
            raise subprocess.TimeoutExpired(cmd, 300.0)
        results = [_semgrep_result(name, 3) for name in names if name.endswith("/mod_7.py")]
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"results": results}), "")

    findings = _review_scan(reviewed_checkout, semgrep, _REVIEWED_FILES[:12])

    reviewed = (reviewed_checkout / "pkg7" / "mod_7.py").resolve()
    assert {name: [f.location for f in found] for name, found in findings.items()} == {
        "pkg7/mod_7.py": [f"{reviewed}:3"]
    }


def test_a_semgrep_timeout_loses_only_its_batch(
    reviewed_checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """At p/default's measured rate a review's targets took more than half Semgrep's 300 s
    timeout in one run, so a review scans them in batches, each with its own timeout. A batch
    that runs out of time loses its own files and says which batch it was; the other batches'
    findings stay. Ten files in batches of four make three batches."""
    monkeypatch.setattr("devops_cli.security.semgrep.DEFAULT_SEMGREP_REVIEW_BATCH_FILES", 4)
    batch_sizes: list[int] = []

    def semgrep(cmd: list[str], cwd: Path | None = None, **_: Any) -> Any:
        names = [os.path.normpath(name) for name in _named_targets(cmd)]
        batch_sizes.append(len(names))
        if "pkg0/mod_0.py" in names:
            raise subprocess.TimeoutExpired(cmd, 300.0)
        kept = ("pkg1/mod_1.py", "pkg7/mod_7.py", "pkg0/mod_9.py")
        results = [_semgrep_result(name, 3) for name in names if name in kept]
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"results": results}), "")

    orchestrator = ReviewPipelineOrchestrator(session_id="semgrep", target_dir=reviewed_checkout)
    with patch("devops_cli.security.base.run_subprocess", MagicMock(side_effect=semgrep)):
        findings = orchestrator._run_static_scanners(_REVIEWED_FILES[:10])

    assert (
        batch_sizes,
        sorted(findings),
        orchestrator.static_analyzers["Semgrep"],
        orchestrator.static_analyzer_reasons["Semgrep"],
    ) == (
        [4, 4, 2],
        ["pkg0/mod_9.py", "pkg7/mod_7.py"],
        "failed",
        "batch 1 of 3, 4 files: timed out after 300 s",
    )
