"""The security scanners start their tools through the tool executor they are given (#772).

A scanner builds the command of its tool and hands it to a `ToolExecutor`, which starts it. These
cases give the scanners `ToolExecutorFake`. It starts nothing and keeps every request, so each case
reads what a scanner asked of its tool and how it read the answer. A case that gives a scanner no
executor runs it on the default executor, which `scanner_fake` answers with the runs recorded from
the real tools. `tests/test_scanner_contract.py` holds the adapters to those recorded commands.
"""

from __future__ import annotations

import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.review import ReviewPipelineOrchestrator, resolve_stage_flags
from devops_cli.config.commands import build_gitleaks_cmd
from devops_cli.config.constants import CONST_CANARY_WORKDIR_PREFIX
from devops_cli.security.bandit import run_bandit_scan
from devops_cli.security.base import ScanOutcome
from devops_cli.security.gitleaks import GitleaksScanner, run_gitleaks_scan
from devops_cli.security.kubelinter import run_kubelinter_scan
from devops_cli.security.mypy import run_mypy_scan
from devops_cli.security.osv_scanner import run_osv_scan
from devops_cli.security.pluto import run_pluto_scan
from devops_cli.security.ruff import run_ruff_scan
from devops_cli.security.semgrep import run_semgrep_scan
from devops_cli.security.tool_executor import ToolExecutor, ToolLimits, ToolRequest
from devops_cli.security.trivy import run_trivy_scan
from tests.support.fakes.scanners import ScannerFake
from tests.support.fakes.tool_executor import ToolAnswer, ToolExecutorFake

_RULES = "rules:\n  - id: any\n    languages: [python]\n    severity: ERROR\n    message: m\n    pattern: eval(...)\n"
_MANIFEST = "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: web\n"
_GITLEAKS_REPORT = (
    '[{"RuleID": "generic-api-key", "Description": "key", "File": "app.py", "StartLine": 1}]'
)

# What a review scan hands each tool: the tool that starts, and the scan as a review starts it.
ScanOver = Callable[[Path, ToolExecutor], ScanOutcome]


@pytest.fixture(autouse=True)
def scanners_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every review tool is on PATH, so the scanners start theirs. Nothing starts: the fake runs."""
    real_which = shutil.which
    installed = {tool for tool, _ in _REVIEW_SCANS}

    def which(cmd: str, *args: Any, **kwargs: Any) -> str | None:
        return f"/opt/scanners/{cmd}" if cmd in installed else real_which(cmd, *args, **kwargs)

    monkeypatch.setattr(shutil, "which", which)


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A tree holding one file for each review tool to read."""
    root = (tmp_path / "tree").resolve()
    (root / ".devops").mkdir(parents=True)
    (root / ".devops" / "review.toml").write_text(
        '[review]\nkubernetes_version = "v1.31.0"\n', encoding="utf-8"
    )
    (root / "app.py").write_text('print("hello")\n', encoding="utf-8")
    (root / "deploy.yaml").write_text(_MANIFEST, encoding="utf-8")
    (root / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nrequires-python = ">=3.14"\n\n[tool.mypy]\npython_version = "3.14"\n',
        encoding="utf-8",
    )
    (root / "rules.yaml").write_text(_RULES, encoding="utf-8")
    return root


def _semgrep(tree: Path, executor: ToolExecutor) -> ScanOutcome:
    return run_semgrep_scan(
        [tree / "app.py"],
        config=str(tree / "rules.yaml"),
        reviewed_tree=tree,
        tool_executor=executor,
    )


# Each scan as a review's scanner stage starts it (`devops_cli.ai.review.pipeline`).
_REVIEW_SCANS: list[tuple[str, ScanOver]] = [
    (
        "bandit",
        lambda t, x: run_bandit_scan([t / "app.py"], isolated=True, tree=t, tool_executor=x),
    ),
    (
        "gitleaks",
        lambda t, x: run_gitleaks_scan([t / "app.py"], isolated=True, tool_executor=x),
    ),
    ("semgrep", _semgrep),
    (
        "trivy",
        lambda t, x: run_trivy_scan(
            t / "Dockerfile", scan_type="config", isolated=True, tool_executor=x
        ),
    ),
    (
        "kube-linter",
        lambda t, x: run_kubelinter_scan(t / "deploy.yaml", isolated=True, tool_executor=x),
    ),
    (
        "pluto",
        lambda t, x: run_pluto_scan(
            t / "deploy.yaml", isolated=True, tree=t, kubernetes_version="v1.31.0", tool_executor=x
        ),
    ),
    (
        "osv-scanner",
        lambda t, x: run_osv_scan([t / "uv.lock"], tree=t, isolated=True, tool_executor=x),
    ),
    (
        "ruff",
        lambda t, x: run_ruff_scan(
            [t / "app.py"], isolated=True, tree=t, require_version=True, tool_executor=x
        ),
    ),
    (
        "mypy",
        lambda t, x: run_mypy_scan([t / "app.py"], tree=t, checkout_root=t, tool_executor=x),
    ),
]


@pytest.mark.parametrize(("tool", "scan"), _REVIEW_SCANS, ids=[tool for tool, _ in _REVIEW_SCANS])
def test_each_review_scan_starts_its_tool_through_the_executor_it_is_given(
    tool: str, scan: ScanOver, tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """The fake saw one start of the tool, and the scan read the empty success it answered."""
    outcome = scan(tree, tool_executor_fake)

    assert ([request.tool for request in tool_executor_fake.requests], outcome.status) == (
        [tool],
        "ran",
    )


def test_a_request_names_the_command_the_tree_the_directory_and_the_time_of_the_scan(
    tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """A review's scan runs in a scratch directory of its own, outside the tree, so that the tool
    reads no config of the tree. The request keeps the tree and the file the scan reads."""
    target = tree / "app.py"

    GitleaksScanner(tool_executor_fake).scan(target, timeout=7.0, isolated=True)

    [request] = tool_executor_fake.requests
    command = build_gitleaks_cmd(target)
    assert (
        request.tool,
        request.arguments[: len(command) - 1],
        request.workdir,
        request.targets,
        request.limits.wall_seconds,
        request.cwd is not None and not request.cwd.is_relative_to(tree),
    ) == ("gitleaks", tuple(command[1:]), tree, (target,), 7.0, True)


def test_the_tree_of_a_request_is_the_checkout_that_holds_the_targets(
    tree: Path, tool_executor_fake: ToolExecutorFake, git: Callable[..., None]
) -> None:
    """The commit of a run is the commit of the checkout, so the tree is the checkout and not the
    directory of the file."""
    git(tree, "init", "--quiet")
    (tree / "src").mkdir()
    target = tree / "src" / "lib.py"
    target.write_text("x = 1\n", encoding="utf-8")

    GitleaksScanner(tool_executor_fake).scan(target, isolated=True)

    assert [(request.workdir, request.targets) for request in tool_executor_fake.requests] == [
        (tree, (target,))
    ]


def test_the_request_of_an_isolated_semgrep_scan_names_the_files_of_the_tree_not_their_links(
    tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """A review links its files under the scratch directory that Semgrep starts in. The record
    must name the files of the tree that were scanned."""
    target = tree / "app.py"

    _semgrep(tree, tool_executor_fake)

    [request] = tool_executor_fake.requests
    assert (request.workdir, request.targets, request.cwd.is_relative_to(tree)) == (
        tree,
        (target,),
        False,
    )


def test_a_scan_reads_the_report_a_tool_prints_whatever_its_exit_code_is(
    tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """Gitleaks ends with exit code 1 when it found a secret; the report is on its stdout."""
    tool_executor_fake.script("gitleaks", ToolAnswer(exit_code=1, stdout=_GITLEAKS_REPORT))

    outcome = run_gitleaks_scan([tree / "app.py"], isolated=True, tool_executor=tool_executor_fake)

    assert (outcome.status, [finding.location for finding in outcome.findings]) == (
        "ran",
        ["app.py:1"],
    )


@pytest.mark.parametrize("stdout", ["", "[]"], ids=["no output", "an empty report"])
def test_a_scan_of_a_tool_that_failed_says_its_exit_code_and_its_standard_error(
    stdout: str, tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """The reason of a failed scan holds the exit code and the standard error that the executor
    answers, whether the tool printed a report or not."""
    tool_executor_fake.script("gitleaks", ToolAnswer(exit_code=2, stdout=stdout, stderr="boom"))

    outcome = run_gitleaks_scan([tree / "app.py"], isolated=True, tool_executor=tool_executor_fake)

    assert (outcome.status, outcome.reason) == ("failed", "Scanner exited with code 2: boom")


def test_a_scan_whose_tool_runs_out_of_time_says_how_long_it_had(
    tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """The executor answers a timeout as a result. The scan reports it as it reported a timeout
    of the process: it names the time, never the command."""
    tool_executor_fake.script("gitleaks", ToolAnswer(exit_code=124, timed_out=True))

    outcome = GitleaksScanner(tool_executor_fake).scan(tree / "app.py", timeout=5.0)

    assert (outcome.status, outcome.reason) == ("failed", "timed out after 5 s")


def test_mypy_starts_the_interpreter_of_the_venv_of_the_checkout_through_the_executor(
    tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """Mypy must import what the reviewed project imports, so it runs as `python -I -m mypy` with
    the interpreter of the `.venv` of the checkout, which the PATH of the host does not name. The
    request names that interpreter as its program and its `.venv` as a read-only bind. It names the
    config file of the tree, and the cache directory through `MYPY_CACHE_DIR`, outside the tree. So
    the command names no path but the config file and the targets."""
    venv = tree / ".venv"
    python = venv / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")

    run_mypy_scan(
        [tree / "app.py"],
        tree=tree,
        checkout_root=tree,
        timeout=7.0,
        tool_executor=tool_executor_fake,
    )

    [request] = tool_executor_fake.requests
    cache = Path(request.env.get("MYPY_CACHE_DIR", ""))
    assert (request.model_copy(update={"env": {}}), list(request.env), cache.is_dir()) == (
        ToolRequest(
            tool="mypy",
            program=python,
            arguments=(
                "-I",
                "-m",
                "mypy",
                "--python-version=3.14",
                "--config-file",
                str(tree / "pyproject.toml"),
                "--no-error-summary",
                "{targets}",
            ),
            workdir=tree,
            targets=(tree / "app.py",),
            config_files=(tree / "pyproject.toml",),
            read_only_binds=(venv,),
            limits=ToolLimits(wall_seconds=7.0),
        ),
        ["MYPY_CACHE_DIR"],
        True,
    )
    assert not cache.is_relative_to(tree)


def test_mypy_of_a_checkout_with_no_venv_starts_the_interpreter_of_devops_cli(
    tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """A checkout without a `.venv` has no interpreter of its own. Mypy runs with the interpreter
    that runs devops-cli, and the request binds the environment of that interpreter."""
    run_mypy_scan(
        [tree / "app.py"], tree=tree, checkout_root=tree, tool_executor=tool_executor_fake
    )

    [request] = tool_executor_fake.requests
    interpreter = Path(sys.executable)
    assert (request.program, request.read_only_binds) == (
        interpreter,
        (interpreter.parent.parent,),
    )


def test_mypy_reads_its_findings_from_the_answer_of_the_executor(
    tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """Mypy ends with exit code 1 when it finds an error. The scan reads the error lines that the
    executor answers, from both output streams."""
    error = f"{tree / 'app.py'}:1: error: Incompatible types in assignment  [assignment]"
    tool_executor_fake.script("mypy", ToolAnswer(exit_code=1, stdout=f"{error}\n"))

    outcome = run_mypy_scan(
        [tree / "app.py"], tree=tree, checkout_root=tree, tool_executor=tool_executor_fake
    )

    assert (outcome.status, [finding.title for finding in outcome.findings]) == (
        "ran",
        ["[assignment] Incompatible types in assignment"],
    )


def test_a_mypy_scan_that_runs_out_of_time_says_how_long_it_had(
    tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """The executor answers a timeout as a result. Mypy reports it as the other scans do: it names
    the time, never the command."""
    tool_executor_fake.script("mypy", ToolAnswer(exit_code=124, timed_out=True))

    outcome = run_mypy_scan(
        [tree / "app.py"],
        tree=tree,
        checkout_root=tree,
        timeout=5.0,
        tool_executor=tool_executor_fake,
    )

    assert (outcome.status, outcome.findings, outcome.reason) == (
        "failed",
        [],
        "timed out after 5 s",
    )


def test_a_mypy_scan_that_the_executor_refuses_reports_the_refusal(
    tree: Path, tmp_path: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """A file outside the tree starts no run. The scan fails with the reason, as a scanner does, so
    the other evidence of the review stays."""
    outside = tmp_path / "outside" / "app.py"
    outside.parent.mkdir()
    outside.write_text("x = 1\n", encoding="utf-8")

    outcome = run_mypy_scan(
        [outside], tree=tree, checkout_root=tree, tool_executor=tool_executor_fake
    )

    assert (outcome.status, outcome.reason.startswith("Scanner execution failed: The target")) == (
        "failed",
        True,
    )


def test_a_scan_of_a_checkout_that_git_cannot_read_still_runs(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """Git refuses a checkout that another user owns. A scan ran there before the executor existed.
    The default executor records no commit for it, and the scan still starts its tool."""
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / ".git").mkdir()
    (broken / "app.py").write_text("x = 1\n", encoding="utf-8")

    outcome = run_gitleaks_scan([broken / "app.py"], isolated=True)

    assert (outcome.status, [run.argv[0] for run in scanner_fake.runs]) == ("ran", ["gitleaks"])


def test_a_scan_of_an_image_name_outside_a_checkout_runs_in_the_directory_it_started_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tool_executor_fake: ToolExecutorFake
) -> None:
    """`devops scan trivy ghcr.io/org/img:latest --type image` names no path. The name stands in
    the current directory as a path that does not exist, and the tree is the nearest directory
    that does."""
    start = tmp_path.resolve()
    monkeypatch.chdir(start)

    outcome = run_trivy_scan(
        Path("ghcr.io/org/img:latest"), scan_type="image", tool_executor=tool_executor_fake
    )

    [request] = tool_executor_fake.requests
    assert (outcome.status, request.workdir, request.targets) == (
        "ran",
        start,
        (start / "ghcr.io" / "org" / "img:latest",),
    )


def test_a_request_names_every_lockfile_that_osv_scanner_reads(
    tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """The command of osv-scanner names all the lockfiles. So does the request."""
    (tree / "pkg").mkdir()
    (tree / "pkg" / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    lockfiles = [tree / "uv.lock", tree / "pkg" / "uv.lock"]

    run_osv_scan(lockfiles, tree=tree, isolated=True, tool_executor=tool_executor_fake)

    [request] = tool_executor_fake.requests
    assert (request.workdir, request.targets) == (tree, tuple(lockfiles))


def test_a_request_names_a_relative_target_by_its_absolute_path(
    tree: Path,
    tool_executor_fake: ToolExecutorFake,
    monkeypatch: pytest.MonkeyPatch,
    git: Callable[..., None],
) -> None:
    """The executor reads a target against the tree. A relative target is a path from the current
    directory, which is not the tree."""
    git(tree, "init", "--quiet")
    (tree / "sub").mkdir()
    (tree / "sub" / "b.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.chdir(tree / "sub")

    GitleaksScanner(tool_executor_fake).scan(Path("b.py"))

    [request] = tool_executor_fake.requests
    assert (request.workdir, request.targets) == (tree, (tree / "sub" / "b.py",))


def _is_canary(request: ToolRequest) -> bool:
    """Whether `request` runs the canary of a tool, on a fixture of its own, not on the review."""
    return request.workdir.name.startswith(CONST_CANARY_WORKDIR_PREFIX)


def test_a_review_starts_every_analyzer_through_its_executor(
    tree: Path, tmp_path: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """The orchestrator hands its executor to each analyzer it starts for the files of a review,
    and to the evidence scans of Ruff and mypy."""
    orchestrator = ReviewPipelineOrchestrator(
        session_id="s772",
        session_dir=tmp_path / "session",
        target_dir=tree,
        tool_executor=tool_executor_fake,
    )

    orchestrator.init_per_file_payloads(["app.py", "deploy.yaml", "Dockerfile", "uv.lock"], {})

    assert {request.tool for request in tool_executor_fake.requests if not _is_canary(request)} == {
        "bandit",
        "gitleaks",
        "kube-linter",
        "mypy",
        "osv-scanner",
        "pluto",
        "ruff",
        "semgrep",
        "trivy",
    }


class _Revision:
    """The base revision of a review: the content of a file at the commit it is compared with."""

    def read(self, path: str) -> str | None:
        return 'print("base")\n' if path == "app.py" else None


def test_the_scan_of_the_base_revision_starts_its_analyzers_through_the_same_executor(
    tree: Path, tmp_path: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """A review of a branch scans the base revision too, for the findings it already held. That
    scan runs in a directory of its own, outside the reviewed tree."""
    orchestrator = ReviewPipelineOrchestrator(
        session_id="s772",
        session_dir=tmp_path / "session",
        target_dir=tree,
        base_revision=_Revision(),
        tool_executor=tool_executor_fake,
    )

    orchestrator.init_per_file_payloads(["app.py"], {})

    assert {
        request.tool
        for request in tool_executor_fake.requests
        if not (request.workdir.is_relative_to(tree) or _is_canary(request))
    } == {"bandit", "gitleaks", "semgrep"}


@pytest.mark.parametrize(
    "options",
    [{"pre_analysis_only": True}, {"no_static_scan": True}, {"reporting_only": True}],
    ids=["pre-analysis-only", "no-static-scan", "reporting-only"],
)
def test_a_review_with_the_static_scan_off_starts_no_analyzer_and_no_evidence_tool(
    tree: Path, tmp_path: Path, tool_executor_fake: ToolExecutorFake, options: dict[str, bool]
) -> None:
    """`--pre-analysis-only` starts no tool after the pre-analysis (#2007). It turns off the
    static scan, as `--no-static-scan` and `--reporting-only` do. The static scan holds the
    analyzers and the Ruff, mypy and complexity evidence. The tree holds what Ruff and mypy need
    to start, and both start through the executor, as the canaries of the tools do."""
    orchestrator = ReviewPipelineOrchestrator(
        session_id="s2007",
        session_dir=tmp_path / "session",
        target_dir=tree,
        tool_executor=tool_executor_fake,
    )

    orchestrator.init_per_file_payloads(
        ["app.py", "deploy.yaml", "Dockerfile", "uv.lock"],
        {},
        stage_flags=resolve_stage_flags(**options),
    )

    assert (tool_executor_fake.requests, orchestrator.canary_results) == ([], {})
