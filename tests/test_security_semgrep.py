"""Unit tests for Semgrep multilingual static AST pattern matching scanner."""

from __future__ import annotations

import json
import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.review import pipeline
from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review.profile import profiling
from devops_cli.ai.review_schema import SavedFinding
from devops_cli.commands.scan import app as scan_app
from devops_cli.review.rules_pack import RULE_PACK_DIR
from devops_cli.security.base import MaterializedTargets, ScanOutcome
from devops_cli.security.registry import global_scanner_registry
from devops_cli.security.semgrep import (
    SemgrepScanner,
    parse_semgrep_json,
    run_semgrep_scan,
)
from devops_cli.security.semgrep_registry import cached_ruleset
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.scanners import ScannerFake
from tests.support.registry_cache import (
    CACHED_RULESET,
    CACHED_RULESET_FILE_NAME,
    CACHED_RULESET_WORKDIR_NAME,
    REPLACED_RULESET,
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


@pytest.mark.usefixtures("cached_default_ruleset")
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

    assert {name: [f.location for f in found] for name, found in findings.items()} == {
        "pkg7/mod_7.py": ["pkg7/mod_7.py:3"]
    }


@pytest.mark.usefixtures("cached_default_ruleset")
def test_a_semgrep_timeout_loses_only_its_batch(
    reviewed_checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A review scans its targets in batches, each with its own timeout. A batch that runs out of
    time loses its own files and says which batch it was; the other batches' findings stay. Ten
    files in batches of four make three batches."""
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


def test_semgrep_findings_carry_paths_relative_to_scan_root(tmp_path: Path) -> None:
    """Semgrep findings carry paths relative to scan root rather than absolute paths."""

    fixture_tree = tmp_path / "tree"
    app_dir = fixture_tree / "app"
    app_dir.mkdir(parents=True)
    x_file = app_dir / "x.py"
    x_file.write_text("import pickle\n", encoding="utf-8")

    fake_output = {
        "results": [
            {
                "check_id": "generic-ast-flaw",
                "path": str(x_file.resolve()),
                "start": {"line": 15},
                "end": {"line": 15},
                "extra": {
                    "message": f"Insecure pattern in {x_file.resolve()}",
                    "severity": "WARNING",
                },
            }
        ]
    }
    with patch("devops_cli.security.semgrep.run_subprocess") as mock_proc:
        mock_proc.return_value = subprocess.CompletedProcess(
            args=["semgrep"], returncode=0, stdout=json.dumps(fake_output), stderr=""
        )
        outcome = run_semgrep_scan([x_file], reviewed_tree=fixture_tree)

    assert len(outcome) == 1
    f = outcome[0]
    assert (
        f.location,
        str(fixture_tree) in f.location,
        str(fixture_tree) in f.description,
    ) == ("app/x.py:15", False, False)


def test_a_review_runs_the_rule_pack_whatever_config_it_names(
    scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    """The pack's rules run next to the config a review names, not only next to `p/default`,
    and the scan sends no metrics and checks no version (#1144)."""
    tree = (tmp_path / "tree").resolve()
    tree.mkdir()
    target = tree / "app.py"
    target.write_text('print("hello")\n', encoding="utf-8")

    run_semgrep_scan([target], config="./local-rules", reviewed_tree=tree)

    assert [run.argv for run in scanner_fake.runs] == [
        [
            "semgrep",
            "scan",
            "--json",
            "--metrics",
            "off",
            "--disable-version-check",
            "--config",
            "./local-rules",
            "--config",
            str(RULE_PACK_DIR),
            "--disable-nosem",
            "--quiet",
            "./app.py",
        ]
    ]


def test_scan_sast_runs_the_rule_pack_next_to_the_config_it_names(
    cli: Callable[..., Any], scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    """`devops scan sast --config ./local-rules` scans the directory with the same flags as a
    review, excluding what a checkout holds that is not its code, and still adds the pack."""
    result = cli("scan", "sast", str(tmp_path), "--config", "./local-rules")

    assert (result.exit_code, [run.argv for run in scanner_fake.runs]) == (
        0,
        [
            [
                "semgrep",
                "scan",
                "--json",
                "--metrics",
                "off",
                "--disable-version-check",
                "--config",
                "./local-rules",
                "--config",
                str(RULE_PACK_DIR),
                "--disable-nosem",
                *("--exclude", ".venv"),
                *("--exclude", "venv"),
                *("--exclude", "node_modules"),
                *("--exclude", ".data"),
                *("--exclude", "repos"),
                *("--exclude", ".git"),
                "--quiet",
                str(tmp_path.resolve()),
            ]
        ],
    )


# =============================================================================
# The registry ruleset a scan reads from the cache, offline (#1144)
# =============================================================================

OLD_CACHE_WARNING = (
    "! The cached registry rules p/default are 25 hours old, and the scan uses them. "
    "Run `devops review rules fetch --ruleset p/default` to refresh them.\n"
)
NOT_CACHED = (
    "The registry rules p/default are not cached, or the cached file is not a Semgrep ruleset. "
    "Run `devops review rules fetch --ruleset p/default`."
)


def _review_inputs(tmp_path: Path) -> tuple[Path, Path]:
    """A checkout holding `app.py`, and that file."""
    tree = (tmp_path / "tree").resolve()
    tree.mkdir()
    target = tree / "app.py"
    target.write_text('print("hello")\n', encoding="utf-8")
    return tree, target


def test_a_review_scans_with_the_cached_registry_ruleset_written_into_its_working_directory(
    scanner_fake: ScannerFake, cached_default_ruleset: Path, tmp_path: Path
) -> None:
    tree, target = _review_inputs(tmp_path)
    scanner_fake.snapshot_workdirs = True

    outcome = run_semgrep_scan([target], reviewed_tree=tree, ruleset=cached_ruleset("p/default"))

    assert outcome.status == "ran"
    assert [run.argv for run in scanner_fake.runs] == [
        [
            "semgrep",
            "scan",
            "--json",
            "--metrics",
            "off",
            "--disable-version-check",
            "--config",
            f"./{CACHED_RULESET_WORKDIR_NAME}",
            "--config",
            str(RULE_PACK_DIR),
            "--disable-nosem",
            "--quiet",
            "./app.py",
        ]
    ]
    assert [run.workdir_files for run in scanner_fake.runs] == [
        {"app.py": b'print("hello")\n', CACHED_RULESET_WORKDIR_NAME: CACHED_RULESET}
    ]


def test_a_reviewed_file_named_like_the_written_ruleset_does_not_replace_it(
    scanner_fake: ScannerFake, cached_default_ruleset: Path, tmp_path: Path
) -> None:
    """The ruleset is written before the reviewed files are placed, so a file of the tree cannot
    take its place as the config."""
    tree, target = _review_inputs(tmp_path)
    planted = tree / CACHED_RULESET_WORKDIR_NAME
    planted.write_text("rules:\n- id: planted\n  pattern: $X\n", encoding="utf-8")
    scanner_fake.snapshot_workdirs = True

    run_semgrep_scan([target, planted], reviewed_tree=tree, ruleset=cached_ruleset("p/default"))

    assert [run.workdir_files for run in scanner_fake.runs] == [
        {"app.py": b'print("hello")\n', CACHED_RULESET_WORKDIR_NAME: CACHED_RULESET}
    ]


def test_every_batch_of_a_review_scans_with_the_bytes_that_were_read_when_the_cache_is_replaced(
    scanner_fake: ScannerFake,
    cached_default_ruleset: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `devops review rules fetch` can replace the cached file while a review runs. The review
    recorded the digest of the bytes it read, so each batch scans with those bytes and no other."""
    tree, _ = _review_inputs(tmp_path)
    files = []
    for number in range(3):
        files.append(tree / f"module_{number}.py")
        files[-1].write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr("devops_cli.security.semgrep.DEFAULT_SEMGREP_REVIEW_BATCH_FILES", 1)
    scanner_fake.snapshot_workdirs = True
    read = cached_ruleset("p/default")
    cached_default_ruleset.write_bytes(REPLACED_RULESET)

    run_semgrep_scan(files, reviewed_tree=tree, ruleset=read)

    assert [run.workdir_files[CACHED_RULESET_WORKDIR_NAME] for run in scanner_fake.runs] == [
        CACHED_RULESET
    ] * 3


def test_a_review_without_the_cached_ruleset_runs_the_rule_pack_alone_and_reports_a_coverage_gap(
    scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    tree, target = _review_inputs(tmp_path)

    outcome = run_semgrep_scan([target], reviewed_tree=tree)

    assert (outcome.status, outcome.reason) == ("coverage_gap", NOT_CACHED)
    assert [run.argv for run in scanner_fake.runs] == [
        [
            "semgrep",
            "scan",
            "--json",
            "--metrics",
            "off",
            "--disable-version-check",
            "--config",
            str(RULE_PACK_DIR),
            "--disable-nosem",
            "--quiet",
            "./app.py",
        ]
    ]


def test_a_scan_through_the_scanner_registry_reads_the_cached_ruleset_it_finds(
    scanner_fake: ScannerFake, cached_default_ruleset: Path, tmp_path: Path
) -> None:
    """`devops scan report` runs every registered scanner with its default config, which for
    Semgrep is `p/default`; the scanner reads the cache without being handed it. It runs from the
    cache directory and names the file there, so that Semgrep returns plain rule ids."""
    outcomes = global_scanner_registry.scan_all(tmp_path, names=["semgrep"])

    (semgrep_run,) = scanner_fake.runs
    assert (
        outcomes["semgrep"].status,
        semgrep_run.argv[semgrep_run.argv.index("--config") + 1],
        semgrep_run.cwd,
    ) == ("ran", f"./{CACHED_RULESET_FILE_NAME}", str(cached_default_ruleset.parent))


def test_a_scan_through_the_scanner_registry_warns_when_the_cached_ruleset_is_older_than_a_day(
    scanner_fake: ScannerFake,
    cached_default_ruleset: Path,
    clock: ClockFake,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    aged = time.time() - 25 * 3600
    os.utime(cached_default_ruleset, (aged, aged))

    outcomes = global_scanner_registry.scan_all(tmp_path, names=["semgrep"])

    assert (outcomes["semgrep"].status, len(scanner_fake.runs)) == ("ran", 1)
    assert capsys.readouterr().err == OLD_CACHE_WARNING


def test_a_scan_through_the_scanner_registry_warns_of_nothing_when_the_cached_ruleset_is_current(
    scanner_fake: ScannerFake,
    cached_default_ruleset: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    global_scanner_registry.scan_all(tmp_path, names=["semgrep"])

    assert capsys.readouterr().err == ""


def test_a_scan_through_the_scanner_registry_without_the_cache_is_a_coverage_gap(
    scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    outcomes = global_scanner_registry.scan_all(tmp_path, names=["semgrep"])

    (semgrep_run,) = scanner_fake.runs
    assert (
        outcomes["semgrep"].status,
        outcomes["semgrep"].reason,
        semgrep_run.argv.count("--config"),
    ) == ("coverage_gap", NOT_CACHED, 1)


def test_a_review_of_a_local_config_needs_no_cached_ruleset(
    scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    tree, target = _review_inputs(tmp_path)

    outcome = run_semgrep_scan([target], config="./local-rules", reviewed_tree=tree)

    assert (outcome.status, outcome.reason) == ("ran", "")


def test_a_dry_run_review_scan_is_no_coverage_gap_for_a_missing_cache(
    scanner_fake: ScannerFake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree, target = _review_inputs(tmp_path)
    monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "true")

    outcome = run_semgrep_scan([target], reviewed_tree=tree)

    assert (outcome.status, scanner_fake.runs) == ("dry-run", [])


def test_scan_sast_scans_from_the_cache_directory_with_the_cached_ruleset_named_there(
    cli: Callable[..., Any],
    scanner_fake: ScannerFake,
    cached_default_ruleset: Path,
    tmp_path: Path,
) -> None:
    """Semgrep returns plain rule ids for a config in its working directory and ids led by the
    dotted path of the directory for any other, so the scan runs from the cache directory."""
    result = cli("scan", "sast", str(tmp_path))

    assert result.exit_code == 0
    assert [(run.argv, run.cwd) for run in scanner_fake.runs] == [
        (
            [
                "semgrep",
                "scan",
                "--json",
                "--metrics",
                "off",
                "--disable-version-check",
                "--config",
                f"./{CACHED_RULESET_FILE_NAME}",
                "--config",
                str(RULE_PACK_DIR),
                "--disable-nosem",
                *("--exclude", ".venv"),
                *("--exclude", "venv"),
                *("--exclude", "node_modules"),
                *("--exclude", ".data"),
                *("--exclude", "repos"),
                *("--exclude", ".git"),
                "--quiet",
                str(tmp_path.resolve()),
            ],
            str(cached_default_ruleset.parent),
        )
    ]


def test_scan_sast_of_a_file_scans_from_the_cache_directory_with_an_absolute_target(
    cli: Callable[..., Any], scanner_fake: ScannerFake, cached_default_ruleset: Path, tmp_path: Path
) -> None:
    target = tmp_path / "app.py"
    target.write_text("x = 1\n", encoding="utf-8")

    result = cli("scan", "sast", str(target))

    (semgrep_run,) = scanner_fake.runs
    assert (result.exit_code, semgrep_run.argv[-1], semgrep_run.cwd) == (
        0,
        str(target.resolve()),
        str(cached_default_ruleset.parent),
    )


def test_scan_sast_without_the_cached_ruleset_exits_1_and_names_the_fetch_command(
    cli: Callable[..., Any], scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    result = cli("scan", "sast", str(tmp_path))

    assert (result.exit_code, result.output, scanner_fake.runs) == (1, f"✗ {NOT_CACHED}\n", [])


@pytest.mark.parametrize("output_format", ["json", "yaml"])
def test_scan_sast_without_the_cached_ruleset_prints_no_report(
    output_format: str, cli: Callable[..., Any], scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    result = cli("scan", "sast", str(tmp_path), "--format", output_format)

    assert (result.exit_code, result.stdout, result.output, scanner_fake.runs) == (
        1,
        "",
        f"✗ {NOT_CACHED}\n",
        [],
    )


def test_scan_sast_of_a_local_config_needs_no_cached_ruleset_and_runs_from_its_target(
    cli: Callable[..., Any], scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    result = cli("scan", "sast", str(tmp_path), "--config", "./local-rules")

    assert (result.exit_code, [run.cwd for run in scanner_fake.runs]) == (0, [str(tmp_path)])


def test_scan_sast_dry_run_needs_no_cached_ruleset(
    cli: Callable[..., Any], scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    result = cli("scan", "sast", str(tmp_path), "--dry-run")

    assert (result.exit_code, scanner_fake.runs) == (0, [])


def test_scan_sast_warns_when_the_cached_ruleset_is_older_than_a_day_and_uses_it(
    cli: Callable[..., Any],
    scanner_fake: ScannerFake,
    cached_default_ruleset: Path,
    clock: ClockFake,
    tmp_path: Path,
) -> None:
    aged = time.time() - 25 * 3600
    os.utime(cached_default_ruleset, (aged, aged))

    result = cli("scan", "sast", str(tmp_path), "--json")

    assert (result.exit_code, len(scanner_fake.runs)) == (0, 1)
    assert result.stderr == OLD_CACHE_WARNING
    assert json.loads(result.stdout.splitlines()[-1]) == []


def test_scan_sast_warns_of_nothing_when_the_cached_ruleset_is_current(
    cli: Callable[..., Any],
    scanner_fake: ScannerFake,
    cached_default_ruleset: Path,
    tmp_path: Path,
) -> None:
    result = cli("scan", "sast", str(tmp_path), "--json")

    assert (result.exit_code, result.stderr) == (0, "")


# =============================================================================
# The files Semgrep did not scan (#1144)
# =============================================================================

# What a review says of a file its Semgrep command named and its report left out of
# `paths.scanned`. The recorded run lists `app.py` and no other file.
NOT_LISTED = "Semgrep did not list the file as scanned"


def _write_files(tree: Path, *names: str) -> list[Path]:
    """Files with some content, one for each of `names`, in `tree`."""
    paths = [tree / name for name in names]
    for path in paths:
        path.write_text("body\n", encoding="utf-8")
    return paths


def test_a_review_lists_the_files_semgrep_does_not_list_as_scanned_and_reports_a_coverage_gap(
    scanner_fake: ScannerFake, cached_default_ruleset: Path, tmp_path: Path
) -> None:
    """Semgrep scans a file it is named only when a rule applies to its language, and reports the
    files it scanned in `paths.scanned`. The recorded run lists `app.py`; the review also named
    `style.css`, so that file is left out and the outcome is a coverage gap."""
    tree, target = _review_inputs(tmp_path)
    stylesheet = _write_files(tree, "style.css")

    outcome = run_semgrep_scan(
        [target, *stylesheet], reviewed_tree=tree, ruleset=cached_ruleset("p/default")
    )

    assert [run.argv[-2:] for run in scanner_fake.runs] == [["./app.py", "./style.css"]]
    assert (outcome.status, outcome.reason, outcome.unscanned) == (
        "coverage_gap",
        "",
        {"style.css": NOT_LISTED},
    )


def test_a_review_whose_files_semgrep_lists_as_scanned_has_no_coverage_gap(
    scanner_fake: ScannerFake, cached_default_ruleset: Path, tmp_path: Path
) -> None:
    tree, target = _review_inputs(tmp_path)

    outcome = run_semgrep_scan([target], reviewed_tree=tree, ruleset=cached_ruleset("p/default"))

    assert (outcome.status, outcome.unscanned) == ("ran", {})


def test_the_files_each_batch_of_a_review_leaves_out_are_all_listed(
    scanner_fake: ScannerFake,
    cached_default_ruleset: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The recorded run lists `app.py` for each batch. With one file in each batch the first
    batch is complete and the other two each leave out their file; the merged outcome lists both."""
    tree, target = _review_inputs(tmp_path)
    stylesheets = _write_files(tree, "first.css", "second.css")
    monkeypatch.setattr("devops_cli.security.semgrep.DEFAULT_SEMGREP_REVIEW_BATCH_FILES", 1)

    outcome = run_semgrep_scan(
        [target, *stylesheets], reviewed_tree=tree, ruleset=cached_ruleset("p/default")
    )

    assert (len(scanner_fake.runs), outcome.status, outcome.unscanned) == (
        3,
        "coverage_gap",
        {"first.css": NOT_LISTED, "second.css": NOT_LISTED},
    )


def test_a_review_without_the_cached_ruleset_still_lists_the_files_semgrep_left_out(
    scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    """The missing ruleset is the scan's own gap and keeps its reason; the files stay listed."""
    tree, target = _review_inputs(tmp_path)
    stylesheet = _write_files(tree, "style.css")

    outcome = run_semgrep_scan([target, *stylesheet], reviewed_tree=tree)

    assert (outcome.status, outcome.reason, outcome.unscanned) == (
        "coverage_gap",
        NOT_CACHED,
        {"style.css": NOT_LISTED},
    )


def test_a_scan_of_a_directory_names_no_files_and_so_leaves_none_out(
    scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    """Semgrep walks a directory and reports what it found there; no named file is missing."""
    tree, _ = _review_inputs(tmp_path)
    _write_files(tree, "style.css")

    outcome = run_semgrep_scan(tree, config="./local-rules")

    assert (outcome.status, outcome.unscanned) == ("ran", {})


def test_a_report_without_a_list_of_scanned_paths_leaves_no_file_unscanned() -> None:
    """Only the list of scanned paths can show a file missing. A report with no such list says
    nothing of the files, and an empty list says that Semgrep scanned none of them."""
    staged = MaterializedTargets({"app.py": Path("/tree/app.py")})
    scanner = SemgrepScanner()

    assert (
        scanner.unscanned_files({"results": []}, staged),
        scanner.unscanned_files({"results": [], "paths": {"scanned": []}}, staged),
        scanner.unscanned_files({"paths": {"scanned": ["./app.py"]}}, staged),
    ) == ({}, {"app.py": NOT_LISTED}, {})


def test_a_review_shows_the_files_semgrep_left_out_in_its_coverage_and_analyzer_sections(
    reviewed_checkout: Path, cached_default_ruleset: Path
) -> None:
    """Semgrep scanned two of the four files. The coverage matrix names the two files it left
    out, and the other files stay scanned. Review.md and the profile give the count of two in the
    Static Analyzers section, and review.md lists the files in the Coverage section."""
    files = _REVIEWED_FILES[:4]
    left_out = {"pkg2/mod_2.py", "pkg3/mod_3.py"}
    count_text = "Files not scanned: 2. The Coverage section lists them."

    def semgrep(cmd: list[str], cwd: Path | None = None, **_: Any) -> Any:
        scanned = [os.path.normpath(name) for name in _named_targets(cmd)]
        report = {"results": [], "paths": {"scanned": [n for n in scanned if n not in left_out]}}
        return subprocess.CompletedProcess(cmd, 0, json.dumps(report), "")

    orchestrator = ReviewPipelineOrchestrator(session_id="semgrep", target_dir=reviewed_checkout)
    with (
        profiling() as profiler,
        patch("devops_cli.security.base.run_subprocess", MagicMock(side_effect=semgrep)),
    ):
        orchestrator._run_static_scanners(files)
    profile = profiler.build(session_id="semgrep", target=str(reviewed_checkout))
    coverage = "\n".join(orchestrator._build_coverage_section())
    analyzers = "\n".join(orchestrator._build_static_analyzers_section())

    assert orchestrator.static_analyzers["Semgrep"] == "coverage_gap"
    assert orchestrator.coverage["Semgrep"] == {
        "pkg0/mod_0.py": "scanned",
        "pkg1/mod_1.py": "scanned",
        "pkg2/mod_2.py": f"not scanned({NOT_LISTED})",
        "pkg3/mod_3.py": f"not scanned({NOT_LISTED})",
    }
    assert f"| Semgrep | `pkg2/mod_2.py` | not scanned({NOT_LISTED}) |" in coverage
    assert f"| Semgrep | `pkg3/mod_3.py` | not scanned({NOT_LISTED}) |" in coverage
    assert f"| Semgrep | coverage_gap: {count_text} |" in analyzers
    assert profile.static_analyzer_reasons == {"Semgrep": count_text}
