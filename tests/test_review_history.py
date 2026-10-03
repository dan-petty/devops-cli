"""Review history records what each session reviewed and counts each subject once (#607).

Both findings.json writers record the session's subject. The history reader leaves out the
session being compared, then keeps one session per subject: the one with the most human verdicts,
then the most verdicts of any kind, then the newest. Sessions without a subject count on their own.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from devops_cli.ai.personas import PERSONAS, Persona
from devops_cli.ai.review.category_metrics import (
    collect_historical_category_metrics,
    compute_category_metrics,
)
from devops_cli.ai.review.history import (
    ReviewHistory,
    load_review_history,
    review_subject,
    subject_key,
)
from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review.runner import (
    ReviewClients,
    _execute_review_workflow,
    _run_persona_loop,
    _save_findings_json,
)
from devops_cli.ai.review_schema import (
    FileReviewPayload,
    Finding,
    ReviewResult,
    ReviewSessionPayload,
    SavedFinding,
)

_PAGES = ["diff --git a/mod.py b/mod.py\n+x = 1\n", "diff --git a/b.py b/b.py\n+y = 2\n"]
_OLDER = "2026-10-01T09:00:00+00:00"
_NEWER = "2026-10-01T10:00:00+00:00"


def _secret(status: str, verified_by: str | None = None) -> SavedFinding:
    return SavedFinding(
        title=f"{status.title()} token in config",
        location="config.py:1",
        category="secret_exposure",
        status=status,
        verified_by=verified_by,
        reportable=status != "INVALIDATED",
    )


def _counts(history: ReviewHistory) -> tuple[int, int, int, int, int]:
    return (
        len(history.sessions),
        len(history.counted),
        history.repeats,
        history.target_only,
        history.unkeyed,
    )


def _counted(history: ReviewHistory) -> tuple[str, ...]:
    return tuple(session.path.name for session in history.counted)


def test_the_pipeline_records_its_subject_and_leaves_itself_out_of_its_baseline(
    tmp_path: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify `generate_consolidated_report` writes the orchestrator's subject to findings.json
    and candidates.json, and that the report's baseline, built after findings.json is on disk,
    counts the earlier session of that subject and not the session itself."""
    subject = review_subject("branch", "feature", _PAGES)
    reviews = tmp_path / "reviews"
    write_review_session(
        reviews / "earlier",
        generated_at=_OLDER,
        subject=subject,
        findings=[_secret("VERIFIED", "llm")],
        candidates=[_secret("INVALIDATED", "llm"), _secret("VERIFIED", "llm")],
    )
    orchestrator = ReviewPipelineOrchestrator(
        session_id="current",
        llm_client=MagicMock(),
        target_dir=tmp_path,
        session_dir=reviews / "current",
        subject=subject,
    )

    with patch("devops_cli.ai.review.pipeline.print_table"):
        orchestrator.generate_consolidated_report(
            [FileReviewPayload(file_path="config.py", findings=[_secret("INVALIDATED", "llm")])],
            personas=["devsecops"],
        )

    session = reviews / "current"
    report = (session / "review.md").read_text(encoding="utf-8")
    assert (
        json.loads((session / "findings.json").read_text(encoding="utf-8"))["subject"],
        json.loads((session / "candidates.json").read_text(encoding="utf-8"))["subject"],
        "| `secret_exposure` | 1 | 1 | 100.0% | 50.0% (1/2) |" in report,
        "_Baseline: 1 earlier session(s), 0 repeat session(s) collapsed, this session excluded._"
        in report,
    ) == (subject, subject, True, True)


def test_the_persona_loop_writer_records_the_subject_and_a_utc_time(tmp_path: Path) -> None:
    """Verify `_save_findings_json` writes the subject it is given and stamps `generated_at`
    with a UTC offset, as the pipeline does; it stamped local time without one."""
    subject = review_subject("path", str(tmp_path), _PAGES)
    finding = Finding(title="Token in config", location="config.py:1", description="leak")

    _save_findings_json(
        [(PERSONAS[Persona.DEVSECOPS], ReviewResult(findings=[finding]))],
        tmp_path,
        subject=subject,
    )

    saved = json.loads((tmp_path / "findings.json").read_text(encoding="utf-8"))
    assert (saved["subject"], datetime.fromisoformat(saved["generated_at"]).utcoffset()) == (
        subject,
        timedelta(0),
    )


def test_the_persona_loop_hands_its_subject_to_findings_json(tmp_path: Path) -> None:
    """Verify `_run_persona_loop` passes its subject through `_write_summary` to the
    findings.json it writes."""
    subject = review_subject("path", str(tmp_path), _PAGES)
    result = ReviewResult(findings=[Finding(title="Token in config", location="config.py:1")])
    client = MagicMock()

    with (
        patch("devops_cli.ai.review.runner._review_session_dir", return_value=tmp_path),
        patch("devops_cli.ai.review.runner._load_shared_metadata_for_pages", return_value={}),
        patch("devops_cli.ai.review.runner._run_review", return_value=result),
        patch("devops_cli.ai.review.runner._print_review"),
    ):
        _run_persona_loop(
            _PAGES,
            "Persona loop",
            MagicMock(),
            ReviewClients(analysis=client, compose=client),
            "",
            all_personas=False,
            persona=Persona.DEVSECOPS,
            subject=subject,
        )

    saved = json.loads((tmp_path / "findings.json").read_text(encoding="utf-8"))
    assert (saved["subject"], len(saved["findings"])) == (subject, 1)


def test_a_review_hands_one_subject_to_both_findings_writers(tmp_path: Path) -> None:
    """Verify `_execute_review_workflow` builds the subject from its target and pages once, and
    gives it to the orchestrator and to the persona loop, which a client that is not an
    `LLMClient` takes."""
    client = MagicMock()

    with (
        patch("devops_cli.ai.review.pipeline.ReviewPipelineOrchestrator") as orchestrator,
        patch("devops_cli.ai.review.runner._run_persona_loop", return_value=[]) as persona_loop,
    ):
        _execute_review_workflow(
            _PAGES,
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
        )

    expected = {
        "type": "branch",
        "ref": "feature",
        "input": hashlib.sha256("\n".join(_PAGES).encode()).hexdigest()[:16],
    }
    assert (
        orchestrator.call_args.kwargs["subject"],
        persona_loop.call_args.kwargs["subject"],
        review_subject("branch", "feature", _PAGES),
    ) == (expected, expected, expected)


def test_a_subject_key_follows_the_reviewed_pages() -> None:
    """Verify the same target and pages give the same key, one changed byte in a page gives
    another, and an empty subject gives none, so older sessions never collapse into one."""
    changed = [_PAGES[0].replace("x = 1", "x = 2"), _PAGES[1]]
    key = subject_key(review_subject("branch", "feature", _PAGES))

    assert (
        key is not None and key == subject_key(review_subject("branch", "feature", list(_PAGES))),
        key != subject_key(review_subject("branch", "feature", changed)),
        subject_key({}),
    ) == (True, True, None)


def test_history_counts_each_subject_once_and_every_session_without_one(
    review_history: Path,
) -> None:
    """Verify the reader lists the five sessions with a findings.json, counts one of the three
    with a subject and both without one, and drops an excluded session before repeats collapse,
    so the next session by rank counts: `same-1`, whose finding has a verdict, not the newer
    `same-2`."""
    full = load_review_history(review_history)
    without_newest = load_review_history(review_history, exclude=review_history / "same-3")

    assert (_counts(full), _counted(full), _counts(without_newest), _counted(without_newest)) == (
        (5, 3, 2, 1, 1),
        ("same-3", "target-only", "unkeyed"),
        (4, 3, 1, 1, 1),
        ("same-1", "target-only", "unkeyed"),
    )


def test_the_counted_session_ranks_human_verdicts_then_any_verdict_then_the_newest(
    tmp_path: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify a person's verdict outranks newer machine verdicts, machine verdicts outrank a
    newer run that verified nothing (`--no-verification`), and otherwise the newest counts. The
    older stamps have no offset, as the persona loop wrote them before #607, and a month's gap
    keeps them older in any local time zone."""
    subject = review_subject("pr", "42", _PAGES)
    older_local = "2026-09-01T09:00:00"
    cases = {
        "human": (
            [_secret("INVALIDATED", "human")],
            [_secret("VERIFIED", "llm"), _secret("INVALIDATED", "llm")],
        ),
        "machine": ([_secret("VERIFIED", "llm")], [_secret("UNVERIFIED")]),
        "newest": ([_secret("VERIFIED", "llm")], [_secret("VERIFIED", "llm")]),
    }
    for case, (older, newer) in cases.items():
        for name, generated_at, findings in (
            ("older", older_local, older),
            ("newer", _NEWER, newer),
        ):
            write_review_session(
                tmp_path / case / name,
                generated_at=generated_at,
                subject=subject,
                findings=findings,
            )

    assert tuple(_counted(load_review_history(tmp_path / case)) for case in cases) == (
        ("older",),
        ("older",),
        ("newer",),
    )


def test_the_slim_parse_gives_the_figures_of_a_full_parse(tmp_path: Path) -> None:
    """Verify the reader's per-category figures equal `compute_category_metrics` over a full
    `ReviewSessionPayload` parse of the same files, for statuses in any case or unknown and for
    findings whose category is inferred."""
    raised = [
        {
            "title": "Token in config",
            "location": "a.py:1",
            "category": "secret_scanning",
            "status": "invalidated",
        },
        {"title": "Masked value flagged", "location": "a.py:2", "status": "Verified "},
        {"title": "Unbounded read_text", "location": "b.py:3", "status": "bogus"},
        {"title": "Loop", "location": "c.py:4", "category": " General ", "status": "mitigated"},
    ]
    reviews = tmp_path / "reviews"
    files = {
        reviews / "pipeline" / "candidates.json": raised[:2],
        reviews / "pipeline" / "findings.json": raised[1:2],
        reviews / "persona-loop" / "findings.json": raised[2:],
    }
    for path, findings in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"generated_at": _OLDER, "findings": findings}), "utf-8")
    raised_files = [
        reviews / "pipeline" / "candidates.json",
        reviews / "persona-loop" / "findings.json",
    ]

    slim, _ = collect_historical_category_metrics(reviews)
    full = compute_category_metrics(
        [
            finding
            for path in raised_files
            for finding in ReviewSessionPayload.model_validate_json(
                path.read_text("utf-8")
            ).findings
        ]
    )

    assert (slim, list(slim), slim["secret_exposure"].invalidated) == (
        full,
        ["other", "resource_exhaustion", "secret_exposure"],
        1,
    )
