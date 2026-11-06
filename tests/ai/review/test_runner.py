"""What the review runner reads: the target's analysis metadata (#1100), the review.toml
suppressions a branch or PR change touches, and what a model's reply may not set (#1150)."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.analyze.symbols import BaseRevision
from devops_cli.ai.review.flags import resolve_stage_flags
from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review.runner import (
    ReviewClients,
    check_and_warn_perimeter_changes,
    execute_review_workflow,
    format_pr_review_comment,
    record_review_metrics,
    run_orchestrator_review,
)
from devops_cli.ai.review_schema import (
    FileReviewPayload,
    SavedFinding,
    derive_recommendation,
)
from devops_cli.config.constants import CONST_REVIEW_CONFIG_FILE
from devops_cli.review.session import ReviewSessionStore
from tests.support.fakes.git import GitFake
from tests.support.fakes.model import ModelFake
from tests.support.fakes.process import ProcessAnswer, ProcessCall
from tests.support.fakes.scanners import ScannerFake
from tests.support.fakes.tool_executor import ToolAnswer

_RUNNER = """import textwrap


def run_snippet(source, namespace):
    code = compile(textwrap.dedent(source), "doc", "exec")
    exec(code, {"__name__": "count"})
    return namespace
"""

_REVIEW_TOML = """\
[[suppressions]]
rule = "B602"
path = "src/a.py"
reason = "The argv is a constant list"
expiry = "2099-12-31"

[[suppressions]]
rule = "B603"
path = "src/b.py"
reason = "Expired reason"
expiry = "2020-01-01"
"""


def _base_revision() -> BaseRevision:
    """A base revision whose review.toml holds the two suppressions; the checkout holds none,
    so a warning can only come from the base revision."""
    return BaseRevision(
        changes=(),
        read=lambda path: _REVIEW_TOML if path == CONST_REVIEW_CONFIG_FILE else None,
    )


@pytest.mark.parametrize("target_type", ["branch", "pr"])
def test_a_change_review_names_the_unexpired_suppressions_it_touches(
    target_type: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Changing src/a.py and src/b.py names the unexpired suppression on src/a.py, read at the
    base revision, and not the expired one on src/b.py."""
    (tmp_path / ".git").mkdir()

    check_and_warn_perimeter_changes(
        target_type,
        ["src/a.py", "src/b.py"],
        base_revision=_base_revision(),
        target_dir=tmp_path,
    )

    output = " ".join(capsys.readouterr().out.split())
    assert (
        output.count("1 review.toml suppression"),
        "B602" in output,
        "src/a.py" in output,
        "The argv is a constant list" in output,
        "Expired reason" in output,
    ) == (1, True, True, True, False)


def test_a_path_review_lists_no_suppressions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A path review has no change to compare, so it prints nothing."""
    (tmp_path / ".git").mkdir()

    check_and_warn_perimeter_changes(
        "path", ["src/a.py"], base_revision=_base_revision(), target_dir=tmp_path
    )

    assert capsys.readouterr().out == ""


_RUNNER_DIFF_TEXT = (
    "diff --git a/deleted.yaml b/deleted.yaml\n"
    "deleted file mode 100644\n"
    "--- a/deleted.yaml\n"
    "+++ /dev/null\n"
    "@@ -1,2 +0,0 @@\n"
    "-apiVersion: v1\n"
    "-kind: Secret\n"
    "diff --git a/keep.yaml b/keep.yaml\n"
    "--- a/keep.yaml\n"
    "+++ b/keep.yaml\n"
    "@@ -1,2 +1,4 @@\n"
    " apiVersion: v1\n"
    " kind: ConfigMap\n"
    "+data:\n"
    "+  key: val\n"
)


def _runner_rev_parse(argv: tuple[str, ...], cwd: Path | None) -> ProcessAnswer:
    if "--abbrev-ref" in argv:
        return ProcessAnswer(returncode=0, stdout="main\n")
    if "--show-toplevel" in argv:
        return ProcessAnswer(returncode=0, stdout=f"{cwd or ''}\n")
    return ProcessAnswer(returncode=0, stdout="1111111111111111111111111111111111111111\n")


def _runner_diff(argv: tuple[str, ...]) -> ProcessAnswer:
    if "--name-status" in argv:
        if "-z" in argv:
            return ProcessAnswer(returncode=0, stdout="D\0deleted.yaml\0M\0keep.yaml\0")
        return ProcessAnswer(returncode=0, stdout="D\tdeleted.yaml\nM\tkeep.yaml\n")
    return ProcessAnswer(returncode=0, stdout=_RUNNER_DIFF_TEXT)


def _runner_git_answer(call: ProcessCall) -> ProcessAnswer:
    argv = call.argv or []
    if "rev-parse" in argv:
        return _runner_rev_parse(argv, call.cwd)
    if "merge-base" in argv:
        return ProcessAnswer(returncode=0, stdout="1111111111111111111111111111111111111111\n")
    if "diff" in argv:
        return _runner_diff(argv)
    if "log" in argv:
        out = (
            "2026-10-01T12:00:00Z\n"
            if "%cI" in str(argv)
            else "2222222222222222222222222222222222222222\n"
        )
        return ProcessAnswer(returncode=0, stdout=out)
    return ProcessAnswer(returncode=0, stdout="")


@pytest.fixture(autouse=True)
def _answer_git_fake(git_fake: GitFake) -> None:
    git_fake.answer(lambda _: True, _runner_git_answer)


def _checkout(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / ".git").mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text("[project]\nname = 'target'\n", encoding="utf-8")
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    return root


def test_no_review_layer_falls_back_to_the_working_directory_for_its_target() -> None:
    """Verify every layer that carries a review's target down to the personas requires it
    (#1100). A default of the working directory let a new caller that left the target out
    type-check and review the working directory's files, one layer above the fix. The
    orchestrator takes the target through its constructor alone: no stage takes another (#2098)."""
    layers = {
        "execute_review_workflow": execute_review_workflow,
        "ReviewPipelineOrchestrator": ReviewPipelineOrchestrator.__init__,
    }
    targets = {name: inspect.signature(fn).parameters["target_dir"] for name, fn in layers.items()}
    stages = (
        ReviewPipelineOrchestrator.run_pre_analysis_refresh,
        ReviewPipelineOrchestrator.init_per_file_payloads,
    )

    assert {
        name: (p.kind, p.default is inspect.Parameter.empty) for name, p in targets.items()
    } == dict.fromkeys(layers, (inspect.Parameter.KEYWORD_ONLY, True))
    assert ["target_dir" in inspect.signature(stage).parameters for stage in stages] == [
        False,
        False,
    ]


def test_a_review_outside_the_working_directory_reads_its_targets_analysis_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    model_fake: ModelFake,
) -> None:
    """Verify a review whose target is not the working directory loads analysis metadata from
    the target's repository in the summary (#1100)."""
    from devops_cli.ai.analyze.cache import save_analysis_metadata
    from devops_cli.models.ai import FileAnalysisMeta

    here = _checkout(tmp_path / "here", {"runner.py": _RUNNER})
    target = _checkout(tmp_path / "target", {"runner.py": _RUNNER})
    monkeypatch.chdir(here)
    for repo, purpose in (
        (here, "Purpose of the working directory"),
        (target, "Purpose of target"),
    ):
        meta = FileAnalysisMeta(path="runner.py", language="python", primary_purpose=purpose)
        save_analysis_metadata("path", str(target), repo.name, [meta], repo)

    execute_review_workflow(
        [f"### File: runner.py\n{_RUNNER}"],
        "Path review",
        True,
        ReviewClients(analysis=model_fake),
        target_type="path",
        target_ref=str(target),
        target_dir=target,
    )

    printed = " ".join(capsys.readouterr().out.split())
    assert ("Purpose of target" in printed, "Purpose of the working directory" in printed) == (
        True,
        False,
    )


def test_summary_only_exits_before_orchestrator_construction(
    tmp_path: Path, model_fake: ModelFake
) -> None:
    """Verify --summary prints metadata and returns before the review pipeline starts, making
    zero model calls and creating no session directory (#995)."""
    target = _checkout(tmp_path / "target", {"app.py": "def foo(): pass\n"})

    result = execute_review_workflow(
        ["### File: app.py\ndef foo(): pass\n"],
        "Path review",
        True,
        ReviewClients(analysis=model_fake),
        target_type="path",
        target_ref=str(target),
        target_dir=target,
    )

    assert (result, model_fake.call_count, (target / ".data" / "reviews").exists()) == (
        [],
        0,
        False,
    )


@pytest.mark.usefixtures("scanner_fake")
def test_routed_files_only_branch_diff_makes_no_model_calls(
    tmp_path: Path, model_fake: ModelFake
) -> None:
    """Verify a review of routed files only (such as uv.lock) invokes _review_routed_files_only
    with zero model calls and succeeds (#948, #995)."""
    target = _checkout(tmp_path / "target", {"uv.lock": "version = 1\n"})

    result = execute_review_workflow(
        [],
        "Branch `feature` vs `main`",
        False,
        ReviewClients(analysis=model_fake),
        target_type="branch",
        target_ref="feature",
        target_dir=target,
        routed_files=["uv.lock"],
    )

    assert (len(result) == 1, model_fake.call_count) == (True, 0)


@pytest.mark.usefixtures("scanner_fake")
def test_a_routed_files_only_review_publishes_its_session_without_a_profile(
    tmp_path: Path, review_store: type[ReviewSessionStore], model_fake: ModelFake
) -> None:
    """Verify a review that writes a report but no profile still publishes its session, whole
    and with the files it wrote (#771)."""
    target = _checkout(tmp_path / "target", {"uv.lock": "version = 1\n"})

    execute_review_workflow(
        [],
        "Branch `feature` vs `main`",
        False,
        ReviewClients(analysis=model_fake),
        target_type="branch",
        target_ref="feature",
        target_dir=target,
        routed_files=["uv.lock"],
        session_id="20261001-120000",
    )

    latest = review_store.latest()
    assert latest is not None
    assert (
        latest.name,
        sorted(path.name for path in latest.directory.iterdir()),
        review_store.in_flight(),
    ) == (
        "20261001-120000",
        ["candidates.json", "files", "findings.json", "findings.sarif", "review.md"],
        [],
    )


@pytest.mark.usefixtures("scanner_fake")
def test_a_review_publishes_its_session_after_it_writes_the_profile(
    tmp_path: Path, review_store: type[ReviewSessionStore], model_fake: ModelFake
) -> None:
    """Verify the session is published last: it holds profile.json, which is written after the
    report, and no staging directory is left (#771)."""
    target = _checkout(tmp_path / "target", {"runner.py": _RUNNER})

    execute_review_workflow(
        [f"### File: runner.py\n{_RUNNER}"],
        "Path review",
        False,
        ReviewClients(analysis=model_fake),
        target_type="path",
        target_ref=str(target),
        target_dir=target,
        session_id="20261001-120000",
    )

    latest = review_store.latest()
    assert latest is not None
    assert (
        latest.name,
        "profile.json" in {path.name for path in latest.directory.iterdir()},
        review_store.in_flight(),
    ) == ("20261001-120000", True, [])


@pytest.mark.usefixtures("scanner_fake")
@pytest.mark.parametrize(
    ("files", "pages", "routed_files"),
    [
        pytest.param(
            {"runner.py": _RUNNER}, [f"### File: runner.py\n{_RUNNER}"], [], id="profiled"
        ),
        pytest.param({"uv.lock": "version = 1\n"}, [], ["uv.lock"], id="routed-files-only"),
    ],
)
def test_a_review_without_a_report_keeps_no_session(
    tmp_path: Path,
    review_store: type[ReviewSessionStore],
    files: dict[str, str],
    pages: list[str],
    routed_files: list[str],
    model_fake: ModelFake,
) -> None:
    """Verify a review run with `--no-reporting` keeps no session: it writes no findings.json,
    which every reader of a session needs, so nothing is published and no staging directory is
    left for the dashboard to show as unfinished (#771)."""
    target = _checkout(tmp_path / "target", files)

    execute_review_workflow(
        pages,
        "Path review",
        False,
        ReviewClients(analysis=model_fake),
        target_type="path",
        target_ref=str(target),
        target_dir=target,
        stage_flags=resolve_stage_flags(no_reporting=True),
        routed_files=routed_files,
        session_id="20261001-120000",
    )

    assert (
        review_store.sessions(),
        review_store.in_flight(),
        [entry.name for entry in review_store.root().iterdir()],
    ) == ([], [], [".staging"])


def test_unverified_high_findings_stay_in_report_with_request_changes(
    tmp_path: Path, model_fake: ModelFake
) -> None:
    """Verify #789 constraint: unverified HIGH findings remain in the report and findings.json
    with REQUEST CHANGES recommendation; only INVALIDATED findings leave the report."""
    orchestrator = ReviewPipelineOrchestrator(
        session_id="test-789",
        session_dir=tmp_path / "session",
        llm_client=model_fake,
        target_dir=tmp_path,
    )
    unverified_high = SavedFinding(
        title="Unverified SQL Injection",
        severity="HIGH",
        status="UNVERIFIED",
        reportable=True,
        location="app.py:10",
        description="Possible injection",
        fix="Use parameters",
    )
    invalidated_high = SavedFinding(
        title="False Positive Overflow",
        severity="HIGH",
        status="INVALIDATED",
        reportable=False,
        location="app.py:20",
        description="Not reachable",
        fix="None",
    )
    payload = FileReviewPayload(
        file_path="app.py",
        findings=[unverified_high, invalidated_high],
    )
    data, _ = orchestrator.generate_consolidated_report([payload])

    findings_in_report = data.get("findings", [])
    assert (
        len(findings_in_report),
        findings_in_report[0]["title"],
        findings_in_report[0]["status"],
        derive_recommendation([unverified_high]),
        derive_recommendation([invalidated_high]),
    ) == (1, "Unverified SQL Injection", "UNVERIFIED", "REQUEST CHANGES", "APPROVE")


def _bandit_report(path: Path) -> str:
    """Bandit's JSON report with one HIGH finding on line 2 of `path`."""
    return json.dumps(
        {
            "results": [
                {
                    "filename": str(path),
                    "line_number": 2,
                    "test_id": "B602",
                    "test_name": "subprocess_popen_with_shell_equals_true",
                    "issue_text": "subprocess shell=True",
                    "issue_severity": "HIGH",
                    "issue_confidence": "HIGH",
                }
            ],
            "errors": [],
        }
    )


def _review_with_findings(
    orchestrator: ReviewPipelineOrchestrator, stage_flags: Any
) -> tuple[Any, str]:
    """Run the orchestrator review of `app.py` and format its PR comment."""
    results = run_orchestrator_review(
        orchestrator, ["app.py"], {}, ["app.py"], stage_flags=stage_flags
    )
    return results, format_pr_review_comment(results, files=["app.py"])


def test_orchestrator_review_feeds_comment_and_metrics_with_and_without_reporting(
    tmp_path: Path, model_fake: ModelFake, scanner_fake: ScannerFake, otlp: Any
) -> None:
    """Verify #791: real run_orchestrator_review output feeds PR comment and metrics
    with and without --no-reporting, preserving the producer labels."""
    repo = _checkout(
        tmp_path / "repo", {"app.py": "import subprocess\nsubprocess.call('ls', shell=True)\n"}
    )
    scanner_fake.script("bandit", ToolAnswer(stdout=_bandit_report(repo / "app.py")))
    orchestrator = ReviewPipelineOrchestrator(
        session_id="test-791-rep",
        session_dir=tmp_path / "session",
        llm_client=model_fake,
        target_dir=repo,
        tool_executor=scanner_fake,
    )

    results_no_rep, comment_no_rep = _review_with_findings(
        orchestrator, resolve_stage_flags(no_reporting=True)
    )
    otlp.clear()
    record_review_metrics(results_no_rep, 12.0, "pr")
    metrics_no_rep = otlp.points("devops_cli_findings_total")

    results_rep, comment_rep = _review_with_findings(
        orchestrator, resolve_stage_flags(no_reporting=False)
    )
    otlp.clear()
    record_review_metrics(results_rep, 15.0, "pr")
    metrics_rep = otlp.points("devops_cli_findings_total")

    bandit_point = ({"producer": "bandit", "severity": "HIGH", "status": "UNVERIFIED"}, 1)
    assert (
        "Zero findings identified." in comment_no_rep,
        "B602" in comment_no_rep,
        [(point[0], point[1]) for point in metrics_no_rep],
        "Zero findings identified." in comment_rep,
        "B602" in comment_rep,
        [(point[0], point[1]) for point in metrics_rep],
    ) == (False, True, [bandit_point], False, True, [bandit_point])


def test_orchestrator_review_no_static_scan_reports_analyzers_none_when_empty(
    tmp_path: Path, model_fake: ModelFake
) -> None:
    """Verify #657 constraint via real run_orchestrator_review: --no-static-scan with zero
    findings emits Analyzers: None."""
    repo = _checkout(tmp_path / "repo", {"app.py": "x = 1\n"})
    orchestrator = ReviewPipelineOrchestrator(
        session_id="test-791-scanners",
        session_dir=tmp_path / "session",
        llm_client=model_fake,
        target_dir=repo,
    )
    flags = resolve_stage_flags(no_static_scan=True, no_reporting=True)
    results = run_orchestrator_review(
        orchestrator,
        ["app.py"],
        {},
        ["app.py"],
        stage_flags=flags,
    )
    comment = format_pr_review_comment(results, files=["app.py"])

    assert (
        "Zero findings identified." in comment,
        "- **Analyzers:** None" in comment,
    ) == (True, True)


def test_branch_review_excludes_deleted_files_from_pages_and_targets(tmp_path: Path) -> None:
    """A branch review leaves the files it deletes out of persona pages and scanners (#1140)."""
    from devops_cli.ai.review.runner import prepare_branch_content
    from devops_cli.review.diff import diff_file_names

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "keep.yaml").write_text(
        "apiVersion: v1\nkind: ConfigMap\ndata:\n  key: val\n", encoding="utf-8"
    )

    pages, _title, _target_branch, _base_rev = prepare_branch_content(
        "feat/delete-manifest", "main", repo, working_directory=repo
    )

    page_files = [f for p in pages for f in diff_file_names(p)]
    assert "deleted.yaml" not in page_files
    assert "keep.yaml" in page_files
