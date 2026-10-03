"""Tests for review finding feedback dataset exporter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from devops_cli.ai.review.exporter import export_invalidated_feedback


def test_export_invalidated_feedback_empty_dir(tmp_path: Path) -> None:
    reviews_dir = tmp_path / "reviews"
    output_file = tmp_path / "output.jsonl"
    count, out_path = export_invalidated_feedback(reviews_dir=reviews_dir, output_file=output_file)
    assert count == 0
    assert out_path == output_file


def test_export_invalidated_feedback_records(tmp_path: Path) -> None:
    reviews_dir = tmp_path / "reviews"
    session_dir = reviews_dir / "session-1"
    session_dir.mkdir(parents=True)

    findings_payload: dict[str, Any] = {
        "session_id": "session-1",
        "findings": [
            {
                "title": "SQL Injection Risk",
                "status": "INVALIDATED",
                "persona": "devsecops",
                "severity": "high",
                "location": "src/db.py:45",
                "description": "Raw string formatting in query",
                "invalidation_reason": "Query uses parameterized statement builder",
                "verified_at": "2026-08-11T20:00:00Z",
                "verified_by": "human",
            },
            {
                "title": "Missing Docstring",
                "status": "VERIFIED",
                "persona": "qa",
                "severity": "low",
            },
        ],
    }
    (session_dir / "findings.json").write_text(json.dumps(findings_payload), encoding="utf-8")

    output_file = tmp_path / "dataset.jsonl"
    count, out_path = export_invalidated_feedback(reviews_dir=reviews_dir, output_file=output_file)

    assert count == 1
    assert out_path.exists()

    lines = out_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["session_id"] == "session-1"
    assert record["persona"] == "devsecops"
    assert record["title"] == "SQL Injection Risk"
    assert record["invalidation_reason"] == "Query uses parameterized statement builder"


def test_export_feedback_by_status_and_all(tmp_path: Path) -> None:
    reviews_dir = tmp_path / "reviews"
    session_dir = reviews_dir / "session-2"
    session_dir.mkdir(parents=True)

    findings_payload: dict[str, Any] = {
        "session_id": "session-2",
        "findings": [
            {
                "title": "Invalid Syntax",
                "status": "INVALIDATED",
                "persona": "devsecops",
                "severity": "critical",
                "location": "src/app.py:10",
                "description": "Claims syntax error on valid tuple",
                "invalidation_reason": "Valid Python 3 tuple exception",
                "verified_at": "2026-08-11T20:00:00Z",
                "verified_by": "human",
            },
            {
                "title": "Missing Timeout",
                "status": "VERIFIED",
                "persona": "devsecops",
                "severity": "medium",
                "location": "src/http.py:25",
                "description": "Network request lacks explicit timeout",
                "confidence_score": 0.95,
                "verified_at": "2026-08-11T20:05:00Z",
                "verified_by": "llm",
            },
        ],
    }
    (session_dir / "findings.json").write_text(json.dumps(findings_payload), encoding="utf-8")

    # Filter by VERIFIED
    out_verified = tmp_path / "verified.jsonl"
    count_v, _ = export_invalidated_feedback(
        reviews_dir=reviews_dir, output_file=out_verified, status_filter="VERIFIED"
    )
    assert count_v == 1
    v_lines = out_verified.read_text(encoding="utf-8").strip().splitlines()
    assert len(v_lines) == 1
    assert json.loads(v_lines[0])["status"] == "VERIFIED"

    # Export ALL via None
    out_all = tmp_path / "all.jsonl"
    count_all, _ = export_invalidated_feedback(
        reviews_dir=reviews_dir, output_file=out_all, status_filter=None
    )
    assert count_all == 2

    # Export ALL via string "ALL"
    out_all_str = tmp_path / "all_str.jsonl"
    count_all_str, _ = export_invalidated_feedback(
        reviews_dir=reviews_dir, output_file=out_all_str, status_filter="ALL"
    )
    assert count_all_str == 2


# =============================================================================
# The export appends, keeps every verdict, and documents one path (#950)
# =============================================================================

_SUBJECT = {"type": "branch", "ref": "release/v0.2.25", "input": "181bdf9d63c60ce5"}


def _session(
    reviews_dir: Path,
    name: str,
    findings: list[dict[str, Any]],
    candidates: list[dict[str, Any]] | None = None,
) -> Path:
    """A review session as the pipeline writes it: findings.json, and candidates.json."""
    session_dir = reviews_dir / name
    session_dir.mkdir(parents=True)
    for file_name, listed in (("findings.json", findings), ("candidates.json", candidates)):
        if listed is not None:
            payload = {"generated_at": "2026-10-02T22:01:34+00:00", "subject": _SUBJECT}
            (session_dir / file_name).write_text(
                json.dumps({**payload, "findings": listed}), encoding="utf-8"
            )
    return session_dir


def _judged(title: str, status: str = "INVALIDATED", **extra: Any) -> dict[str, Any]:
    return {
        "title": title,
        "status": status,
        "persona": "devsecops",
        "severity": "MEDIUM",
        "location": "tests/test_review_prompt_consistency.py:439",
        "description": "exec runs a snippet.",
        "verified_by": "human",
        **extra,
    }


def _lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_an_export_appends_and_skips_records_the_dataset_already_holds(tmp_path: Path) -> None:
    """Verify an export keeps the records already in the dataset and appends only new ones: a
    second export of the same sessions adds nothing."""
    reviews_dir = tmp_path / "reviews"
    _session(reviews_dir, "20261002-214641", [_judged("[B102] Use of exec detected.")])
    output_file = tmp_path / "dataset.jsonl"
    earlier = {"session_id": "20261001-224227", "title": "Earlier record", "status": "VERIFIED"}
    output_file.write_text(json.dumps(earlier) + "\n", encoding="utf-8")

    first, _ = export_invalidated_feedback(reviews_dir=reviews_dir, output_file=output_file)
    second, _ = export_invalidated_feedback(reviews_dir=reviews_dir, output_file=output_file)

    assert (first, second, [r["title"] for r in _lines(output_file)]) == (
        1,
        0,
        ["Earlier record", "[B102] Use of exec detected."],
    )


def test_an_export_reads_the_verdicts_in_candidates_json(tmp_path: Path) -> None:
    """Verify a candidate the review invalidated, which only candidates.json holds, is exported,
    and a reported finding's candidate is not exported twice."""
    reviews_dir = tmp_path / "reviews"
    reported = _judged("[B102] Use of exec detected.")
    dropped = _judged(
        "Hardcoded temp directory", location="tests/test_security_bandit.py:107", verified_by="llm"
    )
    _session(reviews_dir, "20261002-214641", [reported], candidates=[reported, dropped])
    output_file = tmp_path / "dataset.jsonl"

    count, _ = export_invalidated_feedback(reviews_dir=reviews_dir, output_file=output_file)

    assert (count, sorted(r["title"] for r in _lines(output_file))) == (
        2,
        ["Hardcoded temp directory", "[B102] Use of exec detected."],
    )


def test_each_record_carries_its_subject_category_references_and_cited_excerpt(
    tmp_path: Path,
) -> None:
    """Verify a record says what the session reviewed and what the finding cited."""
    reviews_dir = tmp_path / "reviews"
    _session(
        reviews_dir,
        "20261002-214641",
        [
            _judged(
                "[B102] Use of exec detected.",
                category="security",
                references=["CWE-95"],
                cited_code={
                    "project": "devops-cli",
                    "file": "tests/test_review_prompt_consistency.py",
                    "line": 439,
                    "excerpt": '        exec(code, {"__name__": "count"})',
                },
            )
        ],
    )
    output_file = tmp_path / "dataset.jsonl"

    export_invalidated_feedback(reviews_dir=reviews_dir, output_file=output_file)
    record = _lines(output_file)[0]

    assert (
        record["subject"],
        record["category"],
        record["references"],
        record["cited_excerpt"],
    ) == (_SUBJECT, "security", ["CWE-95"], '        exec(code, {"__name__": "count"})')


def test_an_export_with_no_records_leaves_the_dataset_as_it_was(tmp_path: Path) -> None:
    """Verify an export that finds nothing never replaces the dataset with an empty file."""
    reviews_dir = tmp_path / "reviews"
    _session(reviews_dir, "20261002-214641", [_judged("Reported", status="VERIFIED")])
    output_file = tmp_path / "dataset.jsonl"
    output_file.write_text(json.dumps({"title": "Kept"}) + "\n", encoding="utf-8")

    count, _ = export_invalidated_feedback(reviews_dir=reviews_dir, output_file=output_file)

    assert (count, [r["title"] for r in _lines(output_file)]) == (0, ["Kept"])


def test_the_documentation_names_one_dataset_path() -> None:
    """Verify every document that names a path to the feedback dataset names the configured one.

    The docs named three, so an export to one fed none of the readers of another."""
    import re

    from devops_cli.config.defaults import DEFAULT_FEEDBACK_DATASET_PATH

    root = Path(__file__).resolve().parent.parent
    # Task files and the archive record what was, not what is.
    records = (root / "docs" / "agent" / "tasks", root / "docs" / "agent" / "archive")
    documents = [
        root / "AGENTS.md",
        root / "README.md",
        *(
            d
            for d in (root / "docs").rglob("*.md")
            if not any(d.is_relative_to(r) for r in records)
        ),
        *(root / "src/devops_cli/ai/knowledge_base").rglob("*.md"),
    ]
    named = {
        match
        for document in documents
        for match in re.findall(r"[\w.-]+/[\w./-]*feedback\w*\.jsonl", document.read_text("utf-8"))
    }

    assert named == {DEFAULT_FEEDBACK_DATASET_PATH.as_posix()}
