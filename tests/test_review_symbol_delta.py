"""Branch and PR reviews compute their own base-vs-head symbol delta and use only it (#593).

Pre-analysis records each changed Python file's delta from the review's own base. Verification
reads the session's metadata, not the newest cached analysis, and moves a finding that cites a
removed symbol to the file's diff hunk. The summary counts the reviewed files only.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.analyze.symbols import BaseRevision
from devops_cli.ai.client import LLMClient
from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator, _record_symbol_deltas
from devops_cli.ai.review.runner import (
    ReviewClients,
    _branch_base_revision,
    _execute_review_workflow,
    _prepare_branch_content,
)
from devops_cli.ai.review_schema import FileReviewPayload, SavedFinding
from devops_cli.models.ai import AnalysisMetadata, FileAnalysisMeta, ProjectAnalysisMeta
from devops_cli.models.git import ChangedFile

_MERGE_BASE = "c0ffee593"
_BASE_MOD = "def legacy_helper():\n    return 0\n\n\ndef keep():\n    return 1\n"
_HEAD_MOD = "def keep():\n    return 1\n"
_MOD_DIFF = (
    "diff --git a/mod.py b/mod.py\n--- a/mod.py\n+++ b/mod.py\n@@ -1,5 +1,2 @@\n"
    "-def legacy_helper():\n-    return 0\n-\n-\n def keep():\n     return 1\n"
)
_MOD_MODIFIED = ChangedFile(change_type="modified", path="mod.py")


class _NoModel:
    """A model client the deterministic checks must never reach."""

    backend_info = "no model"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def chat(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        pytest.fail("verification asked the model")


@pytest.fixture
def review_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A checkout whose `mod.py` dropped `legacy_helper` and whose `other.py` the diff left
    alone, with the analysis cache in an empty directory of its own."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_ANALYSIS_DIR", str(tmp_path / "analysis"))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "mod.py").write_text(_HEAD_MOD, encoding="utf-8")
    (repo / "other.py").write_text("def stay():\n    return 2\n", encoding="utf-8")
    return repo


def _orchestrator(repo: Path, model: _NoModel) -> ReviewPipelineOrchestrator:
    return ReviewPipelineOrchestrator(
        session_id="session",
        llm_client=model,  # type: ignore[arg-type]
        verification_client=model,  # type: ignore[arg-type]
        target_dir=repo,
        session_dir=repo.parent / "session",
        concurrency=1,
        parallel=False,
    )


def _pre_analysis(
    orchestrator: ReviewPipelineOrchestrator, repo: Path, base: BaseRevision | None
) -> dict[str, FileAnalysisMeta]:
    return orchestrator.run_pre_analysis_refresh(
        target_dir=repo, target_type="branch", target_ref="feature", base_revision=base
    )


def _mod_base() -> BaseRevision:
    return BaseRevision(changes=(_MOD_MODIFIED,), read={"mod.py": _BASE_MOD}.get)


def _delta(meta: FileAnalysisMeta) -> tuple[list[str], list[str], list[str]]:
    return meta.symbols_added, meta.symbols_removed, meta.symbols_retained


def _finding(location: str, symbol: str) -> SavedFinding:
    """A finding about a symbol, worded with no absence marker: those are checked first."""
    return SavedFinding(
        location=location,
        title=f"Removal of `{symbol}` breaks its callers",
        description=f"Callers of `{symbol}` raise NameError at import.",
        persona="architect",
    )


def _verify(
    orchestrator: ReviewPipelineOrchestrator,
    metadata: dict[str, FileAnalysisMeta],
    findings: dict[str, list[SavedFinding]],
) -> list[FileReviewPayload]:
    payloads = [
        FileReviewPayload(file_path=path, metadata=metadata[path], findings=file_findings)
        for path, file_findings in findings.items()
    ]
    orchestrator.execute_finding_verification(
        payloads, diff_text_by_file={"mod.py": _MOD_DIFF}, metadata_by_path=metadata
    )
    return payloads


def _report_summary(
    orchestrator: ReviewPipelineOrchestrator, payloads: list[FileReviewPayload]
) -> tuple[dict[str, Any], dict[str, str]]:
    """Generate the session report; return `findings.json` and the console summary's rows."""
    with patch("devops_cli.ai.review.pipeline.print_table") as tables:
        orchestrator.generate_consolidated_report(payloads)
    rows = {
        str(metric): str(value)
        for call in tables.call_args_list
        if call.kwargs.get("title") == "Review Summary"
        for metric, value in call.kwargs["rows"]
    }
    findings_json = (orchestrator.session_dir / "findings.json").read_text(encoding="utf-8")
    return json.loads(findings_json), rows


def _write_cached_analysis(path: Path, removed: dict[str, list[str]], repo: Path) -> Path:
    """An analysis another run saved, its files reusable by pre-analysis while unchanged."""
    files = [
        FileAnalysisMeta(
            path=name,
            size_bytes=(repo / name).stat().st_size,
            pseudocode=["cached outline"],
            last_analyzed="2999-01-01T00:00:00+00:00",
            symbols_removed=symbols,
        )
        for name, symbols in removed.items()
    ]
    project = ProjectAnalysisMeta(
        title="cached",
        target_type="branch",
        target_reference="elsewhere",
        timestamp="2026-10-01T00:00:00+00:00",
        total_files=len(files),
        total_lines=0,
        total_chars=0,
        languages=["python"],
        primary_purpose="cached",
        key_symbols=[],
        dependencies=[],
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(AnalysisMetadata(project=project, files=files).model_dump_json(), "utf-8")
    return path


def _fake_git_cli(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """`git diff` prints the reviewed diff; any other git call fails."""
    if args[:2] == ["git", "diff"]:
        return subprocess.CompletedProcess(args, 0, stdout=_MOD_DIFF, stderr="")
    return subprocess.CompletedProcess(args, 1, stdout="", stderr="")


def _branch_review_metadata(
    repo: Path,
    targets: tuple[str, str, bool],
    changes: list[ChangedFile],
    texts: dict[tuple[str, str], str],
) -> tuple[dict[str, list[tuple[Any, ...]]], dict[str, FileAnalysisMeta]]:
    """Prepare a branch review through fake git helpers, whose files have `texts` by (revision,
    path), and run its pre-analysis; every git question the review asks is logged."""
    asked: dict[str, list[tuple[Any, ...]]] = {"merge_base": [], "changes": [], "reads": []}

    def merge_base(repo_dir: Path, base: str, head: str = "HEAD") -> str:
        asked["merge_base"].append((base, head))
        return _MERGE_BASE

    def list_changes(repo_dir: Path, base: str, head: str | None = None) -> list[ChangedFile]:
        asked["changes"].append((base, head))
        return changes

    def read(repo_dir: Path, revision: str, rel_path: str) -> str | None:
        asked["reads"].append((revision, rel_path))
        return texts.get((revision, rel_path))

    with (
        patch("devops_cli.ai.review.runner._resolve_branch_targets", return_value=targets),
        patch("devops_cli.ai.review.runner._is_allowed_review_boundary", return_value=True),
        patch("devops_cli.ai.review.runner._run_subprocess", side_effect=_fake_git_cli),
        patch("devops_cli.git.operations.resolve_merge_base", side_effect=merge_base),
        patch("devops_cli.git.operations.list_changed_files", side_effect=list_changes),
        patch("devops_cli.git.operations.read_file_at_revision", side_effect=read),
    ):
        *_, base_revision = _prepare_branch_content(targets[0], "main", repo)
        metadata = _pre_analysis(_orchestrator(repo, _NoModel()), repo, base_revision)
    return asked, metadata


def test_a_branch_review_reads_each_changed_file_at_the_merge_base(review_repo: Path) -> None:
    """Verify a branch review's pre-analysis gets the delta with no earlier `devops ai analyze
    branch` run: `mod.py` is read at the merge base, not the base branch's name, a renamed file
    at its old path, and an added file never, all of its symbols being added. Each head is read
    at the reviewed branch."""
    new_name = "def moved():\n    return 2\n\n\ndef fresh():\n    pass\n"
    fresh = "class Brand:\n    def new(self):\n        pass\n"
    (review_repo / "new_name.py").write_text(new_name, encoding="utf-8")
    (review_repo / "fresh.py").write_text(fresh, encoding="utf-8")
    changes = [
        _MOD_MODIFIED,
        ChangedFile(change_type="renamed", path="new_name.py", old_path="old_name.py"),
        ChangedFile(change_type="added", path="fresh.py"),
    ]
    texts = {
        (_MERGE_BASE, "mod.py"): _BASE_MOD,
        (_MERGE_BASE, "old_name.py"): "def moved():\n    return 2\n\n\ndef dropped():\n    pass\n",
        ("feature", "mod.py"): _HEAD_MOD,
        ("feature", "new_name.py"): new_name,
        ("feature", "fresh.py"): fresh,
    }

    asked, metadata = _branch_review_metadata(
        review_repo, ("feature", "main", False), changes, texts
    )

    assert (
        asked["merge_base"],
        asked["changes"],
        sorted(asked["reads"]),
        {path: _delta(meta) for path, meta in metadata.items()},
    ) == (
        [("main", "feature")],
        [(_MERGE_BASE, "feature")],
        [
            (_MERGE_BASE, ".devops/review.toml"),
            (_MERGE_BASE, "mod.py"),
            (_MERGE_BASE, "old_name.py"),
            ("feature", "fresh.py"),
            ("feature", "mod.py"),
            ("feature", "new_name.py"),
        ],
        {
            "mod.py": ([], ["legacy_helper"], ["keep"]),
            "new_name.py": (["fresh"], ["dropped"], ["moved"]),
            "fresh.py": (["Brand", "Brand.new", "new"], [], []),
            "other.py": ([], [], []),
        },
    )


def test_a_branch_review_takes_its_head_from_the_branch_not_the_checkout(
    review_repo: Path,
) -> None:
    """Verify a branch reviewed while `main` is checked out compares the merge base with the
    branch: `legacy_helper`, which `main` dropped after the branch point and `feature` kept, is
    not listed as removed though the file on disk lacks it. A checkout of the branch with an
    uncommitted deletion, which the diff leaves out, reads the same way."""
    feature_mod = "def legacy_helper():\n    return 0\n\n\ndef keep():\n    return 2\n"
    texts = {(_MERGE_BASE, "mod.py"): _BASE_MOD, ("feature", "mod.py"): feature_mod}
    reads: list[tuple[str, str]] = []

    def read(repo_dir: Path, revision: str, rel_path: str) -> str | None:
        reads.append((revision, rel_path))
        return texts.get((revision, rel_path))

    with (
        patch("devops_cli.git.operations.resolve_merge_base", return_value=_MERGE_BASE),
        patch("devops_cli.git.operations.list_changed_files", return_value=[_MOD_MODIFIED]),
        patch("devops_cli.git.operations.read_file_at_revision", side_effect=read),
    ):
        base = _branch_base_revision(review_repo, "main", "feature", is_working_tree=False)
        [meta] = _record_symbol_deltas([FileAnalysisMeta(path="mod.py")], review_repo, base)

    assert (
        (review_repo / "mod.py").read_text(encoding="utf-8"),
        sorted(reads),
        _delta(meta),
    ) == (
        _HEAD_MOD,
        [(_MERGE_BASE, "mod.py"), ("feature", "mod.py")],
        ([], [], ["keep", "legacy_helper"]),
    )


def test_a_working_tree_review_reads_head(review_repo: Path) -> None:
    """Verify a review of uncommitted changes compares the files on disk with `HEAD`, with no
    merge base."""
    asked, metadata = _branch_review_metadata(
        review_repo, ("main", "HEAD", True), [_MOD_MODIFIED], {("HEAD", "mod.py"): _BASE_MOD}
    )

    assert (asked, _delta(metadata["mod.py"])) == (
        {
            "merge_base": [],
            "changes": [("HEAD", None)],
            "reads": [("HEAD", ".devops/review.toml"), ("HEAD", "mod.py")],
        },
        ([], ["legacy_helper"], ["keep"]),
    )


def test_verification_exempts_only_a_real_removal_and_the_summary_counts_it(
    review_repo: Path,
) -> None:
    """Verify a finding citing the removed `legacy_helper` stays UNVERIFIED, noted and moved to
    the diff hunk, while one citing `ghost_fn`, in neither base nor head, is INVALIDATED, and the
    model is never asked. The summary counts this review's delta and its one exemption."""
    model = _NoModel()
    orchestrator = _orchestrator(review_repo, model)
    metadata = _pre_analysis(orchestrator, review_repo, _mod_base())

    payloads = _verify(
        orchestrator,
        metadata,
        {"mod.py": [_finding("mod.py:1", "legacy_helper"), _finding("mod.py:1", "ghost_fn")]},
    )
    findings_json, summary_rows = _report_summary(orchestrator, payloads)

    legacy, ghost = payloads[0].findings
    assert (
        model.calls,
        (legacy.status, legacy.verification_note, legacy.location, legacy.relocated_from),
        ghost.status,
        findings_json["symbol_delta_summary"],
        findings_json["removed_symbol_findings_count"],
        summary_rows.get("Symbol Delta"),
    ) == (
        [],
        ("UNVERIFIED", "cites removed symbol", "mod.py:1-2", "mod.py:1"),
        "INVALIDATED",
        {"added": 0, "removed": 1, "retained": 1},
        1,
        "+0 / -1 / =1",
    )


def test_only_the_sessions_own_delta_counts(review_repo: Path, tmp_path: Path) -> None:
    """Verify neither a delta cached for a file the diff left alone nor a newer analysis saved
    by another run exempts a finding: `other.py` is reused from the cache with no symbol lists,
    `foo` is invalidated, and the newer file listing `ghost_fn` as removed changes nothing."""
    model = _NoModel()
    orchestrator = _orchestrator(review_repo, model)
    analysis_dir = tmp_path / "analysis"
    _write_cached_analysis(
        analysis_dir / "branch-old-metadata.json", {"other.py": ["foo"]}, review_repo
    )
    metadata = _pre_analysis(orchestrator, review_repo, _mod_base())
    newer = _write_cached_analysis(
        analysis_dir / "branch-concurrent-metadata.json",
        {"mod.py": ["ghost_fn"], "other.py": ["foo"]},
        review_repo,
    )
    os.utime(newer, (4_000_000_000, 4_000_000_000))

    payloads = _verify(
        orchestrator,
        metadata,
        {
            "mod.py": [_finding("mod.py:1", "legacy_helper"), _finding("mod.py:1", "ghost_fn")],
            "other.py": [_finding("other.py:1", "foo")],
        },
    )

    statuses = [(f.location, f.status, f.verification_note) for p in payloads for f in p.findings]
    assert (
        metadata["other.py"].pseudocode,
        _delta(metadata["other.py"]),
        statuses,
        model.calls,
    ) == (
        ["cached outline"],
        ([], [], []),
        [
            ("mod.py:1-2", "UNVERIFIED", "cites removed symbol"),
            ("mod.py:1", "INVALIDATED", None),
            ("other.py:1", "INVALIDATED", None),
        ],
        [],
    )


def test_a_review_hands_its_base_and_diff_to_pre_analysis_and_verification(
    tmp_path: Path,
) -> None:
    """Verify the review workflow gives pre-analysis the base revision it was handed, and gives
    verification the diff map persona review got and the metadata pre-analysis returned.
    Without them a real review would compute no delta and exempt nothing."""
    base = _mod_base()
    metadata = {"mod.py": FileAnalysisMeta(path="mod.py", symbols_removed=["legacy_helper"])}
    orchestrator = MagicMock(session_id="wiring", session_dir=tmp_path)
    orchestrator.run_pre_analysis_refresh.return_value = metadata
    orchestrator.init_per_file_payloads.return_value = []
    orchestrator.generate_consolidated_report.return_value = ({}, "report")
    # The orchestrated path runs for an LLMClient; this one is never set up or called.
    client = LLMClient.__new__(LLMClient)

    with patch(
        "devops_cli.ai.review.pipeline.ReviewPipelineOrchestrator", return_value=orchestrator
    ):
        _execute_review_workflow(
            [_MOD_DIFF],
            "Branch `feature` vs `main`",
            MagicMock(),
            "",
            all_personas=False,
            persona=None,
            summary_only=False,
            clients=ReviewClients(analysis=client, compose=client),
            target_type="branch",
            target_ref="feature",
            target_dir=tmp_path,
            base_revision=base,
        )

    persona_review = orchestrator.execute_multi_persona_review.call_args.kwargs
    verification = orchestrator.execute_finding_verification.call_args.kwargs
    assert (
        orchestrator.run_pre_analysis_refresh.call_args.kwargs["base_revision"] is base,
        verification["diff_text_by_file"],
        verification["diff_text_by_file"] == persona_review["diff_text_by_file"],
        verification["metadata_by_path"] is metadata,
    ) == (True, {"mod.py": _MOD_DIFF}, True, True)


@pytest.mark.parametrize(
    "base",
    [
        BaseRevision(changes=(_MOD_MODIFIED,), read=lambda path: None),
        BaseRevision(
            changes=(_MOD_MODIFIED,), read={"mod.py": _BASE_MOD}.get, read_head=lambda path: None
        ),
    ],
    ids=["base", "head"],
)
def test_a_failed_read_leaves_the_delta_empty(review_repo: Path, base: BaseRevision) -> None:
    """Verify a modified file whose base or head cannot be read records no delta, replacing any
    it had: comparing with nothing would list every head symbol as added (#787's wrong number),
    or every base symbol as removed, widening the exemption."""
    stale = FileAnalysisMeta(path="mod.py", symbols_added=["keep"], symbols_removed=["gone"])

    [meta] = _record_symbol_deltas([stale], review_repo, base)

    assert _delta(meta) == ([], [], [])


def test_a_review_with_no_delta_shows_no_symbol_delta_row(
    review_repo: Path, tmp_path: Path
) -> None:
    """Verify a review whose files have no delta reports a zero delta and no Symbol Delta row,
    though a cached analysis on disk lists a removal."""
    _write_cached_analysis(
        tmp_path / "analysis" / "branch-x-metadata.json", {"mod.py": ["gone"]}, review_repo
    )
    orchestrator = _orchestrator(review_repo, _NoModel())

    findings_json, summary_rows = _report_summary(
        orchestrator, [FileReviewPayload(file_path="mod.py")]
    )

    assert (
        findings_json["symbol_delta_summary"],
        "Symbol Delta" in summary_rows,
        "Symbol Delta" in (orchestrator.session_dir / "review.md").read_text(encoding="utf-8"),
        "Session ID" in summary_rows,
    ) == ({"added": 0, "removed": 0, "retained": 0}, False, False, True)
