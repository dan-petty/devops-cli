"""Unit tests for Bandit Python security scanner integration."""

from __future__ import annotations

import configparser
import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from devops_cli.ai.review_schema import Finding
from devops_cli.commands.ci import get_check_spec
from devops_cli.commands.scan import app as scan_app
from devops_cli.config.commands import BIN_BANDIT
from devops_cli.config.constants import CONST_BANDIT_INI_NAME
from devops_cli.dry_run.state import set_dry_run
from devops_cli.security.bandit import BanditScanner, parse_bandit_json, run_bandit_scan
from tests.support.fakes.scanners import ScannerFake
from tests.support.fakes.tool_executor import ToolAnswer
from tests.support.paths import REPO_ROOT

if TYPE_CHECKING:
    from devops_cli.security.tool_executor import ToolRequest

_EMPTY_BANDIT_REPORT = json.dumps({"errors": [], "results": []})


def test_parse_bandit_json_valid() -> None:
    """parse_bandit_json parses Bandit JSON issues correctly into Finding models."""
    sample_payload = {
        "results": [
            {
                "code": "subprocess.Popen(cmd, shell=True)",
                "filename": "src/devops_cli/core/process.py",
                "issue_confidence": "HIGH",
                "issue_severity": "HIGH",
                "issue_text": "Possible shell injection via subprocess",
                "line_number": 42,
                "more_info": "https://bandit.readthedocs.io/rules/B602",
                "test_id": "B602",
                "test_name": "subprocess_popen_with_shell_equals_true",
            }
        ]
    }
    findings = parse_bandit_json(sample_payload, target_path="src/devops_cli/core/process.py")
    assert len(findings) == 1
    f = findings[0]
    assert isinstance(f, Finding)
    assert f.severity == "HIGH"
    assert "B602" in f.title
    assert "B602" in f.fix
    assert f.confidence_score is None


def test_run_bandit_scan_dry_run(tmp_path: Path) -> None:
    """run_bandit_scan returns simulated finding under dry-run mode."""
    set_dry_run(True)
    try:
        findings = run_bandit_scan(tmp_path)
        assert len(findings) == 1
        assert "DRY-RUN" in findings[0].title
        assert findings[0].confidence_score is None
    finally:
        set_dry_run(False)


def test_run_bandit_scan_mocked(tmp_path: Path, scanner_fake: ScannerFake) -> None:
    """run_bandit_scan runs Bandit and parses its stdout results."""
    set_dry_run(False)
    fake_output = {
        "results": [
            {
                "filename": str(tmp_path / "app.py"),
                "issue_confidence": "MEDIUM",
                "issue_severity": "MEDIUM",
                "issue_text": "Hardcoded temporary file used",
                "line_number": 12,
                "test_id": "B108",
                "test_name": "hardcoded_tmp_directory",
            }
        ]
    }
    scanner_fake.script(BIN_BANDIT, ToolAnswer(stdout=json.dumps(fake_output)))
    app_file = tmp_path / "app.py"
    app_file.write_text("import tempfile\n")
    findings = run_bandit_scan(app_file)
    assert len(findings) == 1
    assert findings[0].severity == "MEDIUM"
    assert "B108" in findings[0].title
    assert findings[0].confidence_score is None


# Bandit 1.9 draws a progress bar over more than this many files (bandit/core/manager.py:29).
_BANDIT_PROGRESS_THRESHOLD = 50


def _bandit_1_9(request: ToolRequest) -> ToolAnswer:
    """Answer as Bandit 1.9 does: without -q, a progress bar ahead of the JSON past 50 files.

    It flags each file that calls a shell, at HIGH (above the -ll level the scanner passes), and
    exits 1 when it reports a result.
    """
    cmd = [request.tool, *request.arguments]
    if "-r" in cmd:
        files = sorted(Path(cmd[cmd.index("-r") + 1]).rglob("*.py"))
    else:
        files = [Path(arg) for arg in cmd if arg.endswith(".py")]
    results = [
        {
            "filename": str(path),
            "issue_severity": "HIGH",
            "issue_text": "subprocess call with shell=True identified, security issue.",
            "line_number": 2,
            "test_id": "B602",
            "test_name": "subprocess_popen_with_shell_equals_true",
        }
        for path in files
        if "shell=True" in path.read_text(encoding="utf-8")
    ]
    report = json.dumps({"errors": [], "results": results}, indent=2)
    quiet = "-q" in cmd
    progress = not quiet and len(files) > _BANDIT_PROGRESS_THRESHOLD
    bar = "Working... ━━━━ 100% 0:00:20\n" if progress else ""
    stderr = "" if quiet else "[main]\tINFO\tprofile include tests: None\n"
    return ToolAnswer(exit_code=1 if results else 0, stdout=bar + report, stderr=stderr)


@pytest.mark.parametrize("shape", ["file list", "directory"])
def test_bandit_reports_its_findings_over_more_than_fifty_files(
    tmp_path: Path, shape: str, scanner_fake: ScannerFake
) -> None:
    """Verify a scan of 51 files reads Bandit's JSON and its exit 1 as findings, not a failure."""
    for n in range(_BANDIT_PROGRESS_THRESHOLD + 1):
        (tmp_path / f"m{n:02}.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "m07.py").write_text(
        "import subprocess\nsubprocess.call(cmd, shell=True)\n", encoding="utf-8"
    )
    target = sorted(tmp_path.glob("*.py")) if shape == "file list" else tmp_path

    scanner_fake.answer_with(BIN_BANDIT, _bandit_1_9)

    outcome = BanditScanner().scan(target)

    assert (outcome.status, outcome.reason, [(f.location, f.title) for f in outcome]) == (
        "ran",
        "",
        [
            (
                f"{(tmp_path / 'm07.py').resolve()}:2",
                "[B602] subprocess call with shell=True identified, security issue.",
            )
        ],
    )


def test_bandit_asks_for_quiet_output_in_every_command_shape(tmp_path: Path) -> None:
    """Verify each command shape passes -q, which keeps Bandit's progress bar off stdout."""
    app = tmp_path / "app.py"
    app.write_text("x = 1\n", encoding="utf-8")
    scanner = BanditScanner()

    commands = (
        scanner.build_command([app]),
        scanner.build_command(app),
        scanner.build_command(tmp_path),
    )

    assert tuple("-q" in cmd for cmd in commands) == (True, True, True)


def _bandit_runs(scanner_fake: ScannerFake) -> list[tuple[list[str], Path]]:
    """Each Bandit command the fake answered, with the directory it ran from."""
    return [(run.argv, Path(run.cwd).resolve()) for run in scanner_fake.runs]


def _what_bandit_reports(cmd: list[str], cwd: Path) -> list[str]:
    """The options of a Bandit command that decide what it reports, its `--ini` file resolved
    from the directory it runs in: all but `-q` and `-f json`, which only shape its output."""
    args = iter(cmd[cmd.index(BIN_BANDIT) + 1 :])
    kept: list[str] = []
    for arg in args:
        if arg == "-q":
            continue
        if arg == "-f":
            next(args)
            continue
        kept.append(arg)
        if arg == "--ini":
            kept.append(str((cwd / next(args)).resolve()))
    return kept


def test_the_scan_report_runs_bandit_on_this_repository_with_the_gate_s_config(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """Verify `devops scan report` on this repository runs Bandit with the `.bandit` that both of
    the gate's runs read, over the targets it names, at medium severity, honouring `# nosec`. The
    gate scans `src` at low severity as well (#1538), so it fails on a low finding in the product,
    which the report does not show."""
    scanner_fake.script(BIN_BANDIT, ToolAnswer(stdout=_EMPTY_BANDIT_REPORT))
    sarif = tmp_path / "scan.sarif"
    result = CliRunner().invoke(
        scan_app, ["report", "--scanner", "bandit", "--sarif", str(sarif), str(REPO_ROOT)]
    )

    [(scan_cmd, scan_cwd)] = _bandit_runs(scanner_fake)
    ini = str(REPO_ROOT / CONST_BANDIT_INI_NAME)
    gate = [_what_bandit_reports(cmd, REPO_ROOT) for cmd in get_check_spec("security").commands]
    assert (
        result.exit_code,
        sarif.is_file(),
        scan_cwd,
        _what_bandit_reports(scan_cmd, scan_cwd),
        gate,
    ) == (
        0,
        True,
        REPO_ROOT,
        ["-r", "--ini", ini, "--severity-level", "medium"],
        [
            ["-r", "src", "--ini", ini, "--severity-level", "low"],
            ["-r", "tests", "--ini", ini, "--severity-level", "medium"],
        ],
    )


def test_the_bandit_targets_hold_every_python_file_the_repository_tracks() -> None:
    """Verify the targets `.bandit` names, which the gate and the code-scanning upload both scan,
    are src and tests, scanned recursively, and hold every tracked Python file, so none goes
    unscanned."""
    ini = configparser.ConfigParser()
    ini.read(REPO_ROOT / CONST_BANDIT_INI_NAME, encoding="utf-8")
    targets = ini["bandit"]["targets"].split(",")
    tracked = subprocess.run(
        ["git", "ls-files", "--", "*.py", "*.pyw"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    outside = [name for name in tracked if not any(Path(name).is_relative_to(t) for t in targets)]

    assert (targets, ini["bandit"].getboolean("recursive"), bool(tracked), outside) == (
        ["src", "tests"],
        True,
        True,
        [],
    )


def test_only_an_unisolated_scan_runs_bandit_as_the_tree_s_own_bandit_file_says(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """Verify an unisolated scan of a tree with a `.bandit` runs Bandit from the tree on that file,
    honouring the tree's `# nosec` markers. A review's isolated scan of the same tree, and an
    unisolated scan of a tree without one, name the tree, ignore `# nosec`, and the review hands
    Bandit its own empty file from outside the tree, so the reviewed tree's file cannot narrow
    what the review sees (#972)."""
    own = tmp_path / "own"
    own.mkdir()
    (own / CONST_BANDIT_INI_NAME).write_text(
        "[bandit]\ntargets = src\nrecursive = true\nskips = B602\n", encoding="utf-8"
    )
    bare = tmp_path / "bare"
    bare.mkdir()
    scanner_fake.script(BIN_BANDIT, ToolAnswer(stdout=_EMPTY_BANDIT_REPORT))

    for target, isolated in ((own, False), (own, True), (bare, False)):
        BanditScanner().scan(target, isolated=isolated)

    [(unisolated, unisolated_cwd), (review, review_cwd), (untold, untold_cwd)] = _bandit_runs(
        scanner_fake
    )
    assert (
        (_what_bandit_reports(unisolated, unisolated_cwd), unisolated_cwd),
        (review[review.index("-r") + 1], "--ignore-nosec" in review),
        (review[-2:], review_cwd.is_relative_to(own)),
        (_what_bandit_reports(untold, untold_cwd)[:2], "--ignore-nosec" in untold),
    ) == (
        (["-r", "--ini", str(own / CONST_BANDIT_INI_NAME), "--severity-level", "medium"], own),
        (str(own), True),
        (["--ini", str(review_cwd / CONST_BANDIT_INI_NAME)], False),
        (["-r", str(bare)], True),
    )


@pytest.mark.parametrize(
    ("ini_text", "reads_the_file"),
    [
        pytest.param("[bandit]\ntargets = src\n", True, id="targets without recursive"),
        pytest.param("[bandit]\nexclude = tests\nskips = B101\n", False, id="no targets"),
        pytest.param("[bandit]\ntargets =\n", False, id="empty targets"),
        pytest.param("targets = src\n", False, id="no section"),
    ],
)
def test_an_unisolated_scan_runs_bandit_on_the_tree_s_bandit_file_only_when_it_names_targets(
    tmp_path: Path, ini_text: str, reads_the_file: bool, scanner_fake: ScannerFake
) -> None:
    """Verify an unisolated scan hands Bandit the tree's `.bandit` only when the file names its
    targets, and then with `-r`, so Bandit walks a directory target the file does not mark
    recursive. Bandit exits 2 on a file that names none, such as its own documented example, or
    that it cannot parse, so such a tree is scanned whole, ignoring `# nosec`, as a tree without
    one is."""
    (tmp_path / CONST_BANDIT_INI_NAME).write_text(ini_text, encoding="utf-8")
    scanner_fake.script(BIN_BANDIT, ToolAnswer(stdout=_EMPTY_BANDIT_REPORT))

    BanditScanner().scan(tmp_path)

    [(cmd, cwd)] = _bandit_runs(scanner_fake)
    head = _what_bandit_reports(cmd, cwd)[:3]
    whole_tree = ["-r", str(tmp_path), "--exclude"]
    own_file = ["-r", "--ini", str(tmp_path / CONST_BANDIT_INI_NAME)]
    assert (head, "--ignore-nosec" in cmd) == (
        (own_file, False) if reads_the_file else (whole_tree, True)
    )


def test_bandit_findings_carry_paths_relative_to_scan_root(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """Bandit findings carry paths relative to scan root rather than absolute paths."""
    fixture_tree = tmp_path / "tree"
    app_dir = fixture_tree / "app"
    app_dir.mkdir(parents=True)
    x_file = app_dir / "x.py"
    x_file.write_text("import tempfile\n", encoding="utf-8")

    fake_output = {
        "results": [
            {
                "filename": str(x_file.resolve()),
                "issue_confidence": "MEDIUM",
                "issue_severity": "MEDIUM",
                "issue_text": f"Temporary file in {x_file.resolve()}",
                "line_number": 12,
                "test_id": "B108",
                "test_name": "hardcoded_tmp_directory",
            }
        ]
    }
    scanner_fake.script(BIN_BANDIT, ToolAnswer(stdout=json.dumps(fake_output)))

    outcome = run_bandit_scan([x_file], tree=fixture_tree)

    assert len(outcome) == 1
    f = outcome[0]
    assert (
        f.location,
        str(fixture_tree) in f.location,
        str(fixture_tree) in f.description,
    ) == ("app/x.py:12", False, False)
