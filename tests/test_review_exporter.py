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
