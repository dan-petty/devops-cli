"""Tests for review finding feedback dataset exporter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.review.exporter import export_invalidated_feedback
from devops_cli.ai.review.history import subject_key
from devops_cli.exceptions import SecurityError
from tests.support.paths import REPO_ROOT


def test_export_invalidated_feedback_empty_dir(tmp_path: Path) -> None:
    reviews_dir = tmp_path / "reviews"
    output_file = tmp_path / "output.jsonl"
    count, out_path = export_invalidated_feedback(
        reviews_dir=reviews_dir, output_file=output_file, workspace_root=tmp_path
    )
    assert count == 0
    assert out_path == output_file


def test_the_working_directory_of_the_process_allows_no_reviews_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the workspace that the command gives, the data root and the temporary directory hold
    a reviews directory to export. From `/`, the working directory of the process held every path,
    so a reviews directory outside the workspace was read (#2098)."""
    monkeypatch.chdir("/")
    outside = Path("/devops-cli-test-reviews-outside-the-workspace")

    with pytest.raises(SecurityError) as refused:
        export_invalidated_feedback(reviews_dir=outside, workspace_root=tmp_path)

    assert (
        refused.value.exit_code,
        refused.value.error_code,
        str(outside) in str(refused.value),
    ) == (1, "SECURITY_ERROR", True)


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
    count, out_path = export_invalidated_feedback(
        reviews_dir=reviews_dir, output_file=output_file, workspace_root=tmp_path
    )

    assert count == 1
    assert out_path.exists()

    lines = out_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["session_id"] == "session-1"
    assert record["producer"] == "devsecops"
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
        reviews_dir=reviews_dir,
        output_file=out_verified,
        status_filter="VERIFIED",
        workspace_root=tmp_path,
    )
    assert count_v == 1
    v_lines = out_verified.read_text(encoding="utf-8").strip().splitlines()
    assert len(v_lines) == 1
    assert json.loads(v_lines[0])["status"] == "VERIFIED"

    # Export ALL via None
    out_all = tmp_path / "all.jsonl"
    count_all, _ = export_invalidated_feedback(
        reviews_dir=reviews_dir,
        output_file=out_all,
        status_filter=None,
        workspace_root=tmp_path,
    )
    assert count_all == 2

    # Export ALL via string "ALL"
    out_all_str = tmp_path / "all_str.jsonl"
    count_all_str, _ = export_invalidated_feedback(
        reviews_dir=reviews_dir,
        output_file=out_all_str,
        status_filter="ALL",
        workspace_root=tmp_path,
    )
    assert count_all_str == 2


# =============================================================================
# The export appends, keeps every verdict, and documents one path (#950)
# =============================================================================

_SUBJECT = {"type": "branch", "ref": "feat/review-export", "input": "181bdf9d63c60ce5"}


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

    first, _ = export_invalidated_feedback(
        reviews_dir=reviews_dir, output_file=output_file, workspace_root=tmp_path
    )
    second, _ = export_invalidated_feedback(
        reviews_dir=reviews_dir, output_file=output_file, workspace_root=tmp_path
    )

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

    count, _ = export_invalidated_feedback(
        reviews_dir=reviews_dir, output_file=output_file, workspace_root=tmp_path
    )

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

    export_invalidated_feedback(
        reviews_dir=reviews_dir, output_file=output_file, workspace_root=tmp_path
    )
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

    count, _ = export_invalidated_feedback(
        reviews_dir=reviews_dir, output_file=output_file, workspace_root=tmp_path
    )

    assert (count, [r["title"] for r in _lines(output_file)]) == (0, ["Kept"])


def test_the_documentation_names_one_dataset_path() -> None:
    """Verify every document that names a path to the feedback dataset names the configured one.

    The docs named three, so an export to one fed none of the readers of another."""
    import re

    from devops_cli.config.defaults import DEFAULT_FEEDBACK_DATASET_PATH

    # The archive records what was, not what is.
    records = (REPO_ROOT / "docs" / "agent" / "archive",)
    documents = [
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / "README.md",
        *(
            d
            for d in (REPO_ROOT / "docs").rglob("*.md")
            if not any(d.is_relative_to(r) for r in records)
        ),
        *(REPO_ROOT / "src/devops_cli/ai/knowledge_base").rglob("*.md"),
    ]
    named = {
        match
        for document in documents
        for match in re.findall(r"[\w.-]+/[\w./-]*feedback\w*\.jsonl", document.read_text("utf-8"))
    }

    assert named == {DEFAULT_FEEDBACK_DATASET_PATH.as_posix()}


# =============================================================================
# The export counts each subject once and keeps every human verdict (#877)
# =============================================================================


def _subject_session(
    reviews_dir: Path,
    name: str,
    findings: list[dict[str, Any]],
    *,
    subject: dict[str, str] | None = _SUBJECT,
    target: str | None = None,
) -> Path:
    """A review session of `subject` (none when None) with one findings.json, and a profile.json
    naming `target` when one is given."""
    session_dir = reviews_dir / name
    session_dir.mkdir(parents=True)
    payload: dict[str, Any] = {"generated_at": "2026-10-02T22:01:34+00:00", "findings": findings}
    if subject is not None:
        payload["subject"] = subject
    (session_dir / "findings.json").write_text(json.dumps(payload), encoding="utf-8")
    if target is not None:
        profile = {"session_id": name, "target": target}
        (session_dir / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    return session_dir


def _tool_finding(fingerprint: str, status: str = "UNVERIFIED", **verdict: Any) -> dict[str, Any]:
    """An admitted tool finding as a session saves it, with its fingerprint v2."""
    return {
        "title": f"[B102] Use of exec detected ({fingerprint}).",
        "status": status,
        "producer": "bandit",
        "severity": "MEDIUM",
        "location": f"src/devops_cli/{fingerprint}.py:12",
        "description": "exec runs a snippet.",
        "fingerprint": fingerprint,
        **verdict,
    }


def _person(status: str, at: str) -> dict[str, Any]:
    """The fields `devops review verify` writes for a person's verdict."""
    return {"status": status, "verified_by": "human", "verified_at": at}


def _export_all(reviews_dir: Path, output_file: Path) -> int:
    count, _ = export_invalidated_feedback(
        reviews_dir=reviews_dir,
        output_file=output_file,
        status_filter=None,
        workspace_root=reviews_dir.parent,
    )
    return count


def test_a_subject_reviewed_three_times_exports_each_finding_once(tmp_path: Path) -> None:
    """Verify three sessions of one subject that hold the same two findings export two records,
    each with its subject key and fingerprint v2."""
    reviews_dir = tmp_path / "reviews"
    for name in ("20261002-210000", "20261002-220000", "20261002-230000"):
        _subject_session(reviews_dir, name, [_tool_finding("fp-a"), _tool_finding("fp-b")])
    output_file = tmp_path / "dataset.jsonl"

    count = _export_all(reviews_dir, output_file)
    records = _lines(output_file)

    assert (
        count,
        sorted(r["fingerprint_v2"] for r in records),
        {r["subject_key"] for r in records},
    ) == (2, ["fp-a", "fp-b"], {subject_key(_SUBJECT)})


def test_the_human_verdicts_of_every_session_of_a_subject_are_exported(tmp_path: Path) -> None:
    """Verify a person's verdict on a finding is exported when another session of its subject
    holds a person's verdict on a different finding."""
    reviews_dir = tmp_path / "reviews"
    _subject_session(
        reviews_dir,
        "20261002-210000",
        [
            _tool_finding("fp-a", **_person("INVALIDATED", "2026-10-02T21:30:00+00:00")),
            _tool_finding("fp-b"),
        ],
    )
    _subject_session(
        reviews_dir,
        "20261002-220000",
        [
            _tool_finding("fp-a"),
            _tool_finding("fp-b", **_person("VERIFIED", "2026-10-02T22:30:00+00:00")),
        ],
    )
    output_file = tmp_path / "dataset.jsonl"

    count = _export_all(reviews_dir, output_file)

    assert (
        count,
        sorted((r["fingerprint_v2"], r["status"], r["verified_by"]) for r in _lines(output_file)),
    ) == (2, [("fp-a", "INVALIDATED", "human"), ("fp-b", "VERIFIED", "human")])


def test_the_newer_of_two_human_verdicts_on_one_finding_is_exported(tmp_path: Path) -> None:
    """Verify two sessions of one subject with different human verdicts on one finding export one
    record, the verdict with the newer verified_at, whichever session is newer."""
    reviews_dir = tmp_path / "reviews"
    newer_verdict = _person("INVALIDATED", "2026-10-03T09:00:00+00:00")
    older_verdict = _person("VERIFIED", "2026-10-02T23:00:00+00:00")
    _subject_session(reviews_dir, "20261002-210000", [_tool_finding("fp-a", **newer_verdict)])
    _subject_session(reviews_dir, "20261002-220000", [_tool_finding("fp-a", **older_verdict)])
    output_file = tmp_path / "dataset.jsonl"

    count = _export_all(reviews_dir, output_file)

    assert (
        count,
        [(r["status"], r["verified_at"], r["session_id"]) for r in _lines(output_file)],
    ) == (1, [("INVALIDATED", "2026-10-03T09:00:00+00:00", "20261002-210000")])


def test_the_status_filter_reads_the_finding_s_newest_human_verdict(tmp_path: Path) -> None:
    """Verify an export of INVALIDATED verdicts skips a finding whose newer human verdict is
    VERIFIED, so a verdict a person overturned is not exported."""
    reviews_dir = tmp_path / "reviews"
    _subject_session(
        reviews_dir,
        "20261002-210000",
        [_tool_finding("fp-a", **_person("INVALIDATED", "2026-10-02T21:30:00+00:00"))],
    )
    _subject_session(
        reviews_dir,
        "20261002-220000",
        [_tool_finding("fp-a", **_person("VERIFIED", "2026-10-02T22:30:00+00:00"))],
    )
    output_file = tmp_path / "dataset.jsonl"

    count, _ = export_invalidated_feedback(
        reviews_dir=reviews_dir, output_file=output_file, workspace_root=tmp_path
    )

    assert (count, output_file.exists()) == (0, False)


def test_sessions_without_a_subject_each_export_all_their_findings(tmp_path: Path) -> None:
    """Verify a target-only session and an unkeyed session each export their findings, also a
    finding with the fingerprint v2 of a finding the other one holds."""
    reviews_dir = tmp_path / "reviews"
    _subject_session(
        reviews_dir,
        "20261001-210000",
        [_tool_finding("fp-a"), _tool_finding("fp-b")],
        subject=None,
        target="src/devops_cli",
    )
    _subject_session(reviews_dir, "20261001-220000", [_tool_finding("fp-a")], subject=None)
    output_file = tmp_path / "dataset.jsonl"

    count = _export_all(reviews_dir, output_file)

    assert (
        count,
        sorted(
            (r["session_id"], r["fingerprint_v2"], r["subject_key"]) for r in _lines(output_file)
        ),
    ) == (
        3,
        [
            ("20261001-210000", "fp-a", None),
            ("20261001-210000", "fp-b", None),
            ("20261001-220000", "fp-a", None),
        ],
    )


def test_findings_without_a_fingerprint_are_not_matched_across_sessions(tmp_path: Path) -> None:
    """Verify two sessions of one subject that hold a finding with no fingerprint v2 under the
    same title and location export it once for each session: no title or location match."""
    reviews_dir = tmp_path / "reviews"
    for name in ("20261002-210000", "20261002-220000"):
        _subject_session(reviews_dir, name, [_judged("[B102] Use of exec detected.")])
    output_file = tmp_path / "dataset.jsonl"

    count = _export_all(reviews_dir, output_file)

    assert (count, sorted(r["session_id"] for r in _lines(output_file))) == (
        2,
        ["20261002-210000", "20261002-220000"],
    )


def test_a_later_session_of_an_exported_subject_appends_nothing(tmp_path: Path) -> None:
    """Verify a session that repeats an exported subject with the same verdicts adds no record,
    and a person's later verdict on one of its findings adds one."""
    reviews_dir = tmp_path / "reviews"
    _subject_session(reviews_dir, "20261002-210000", [_tool_finding("fp-a")])
    output_file = tmp_path / "dataset.jsonl"
    first = _export_all(reviews_dir, output_file)

    _subject_session(reviews_dir, "20261002-220000", [_tool_finding("fp-a")])
    repeat = _export_all(reviews_dir, output_file)

    _subject_session(
        reviews_dir,
        "20261002-230000",
        [_tool_finding("fp-a", **_person("VERIFIED", "2026-10-02T23:30:00+00:00"))],
    )
    judged = _export_all(reviews_dir, output_file)

    assert (
        first,
        repeat,
        judged,
        [(r["status"], r["verified_by"]) for r in _lines(output_file)],
    ) == (1, 0, 1, [("UNVERIFIED", "unknown"), ("VERIFIED", "human")])


def test_export_feedback_prints_the_count_of_each_subject_s_findings(tmp_path: Path) -> None:
    """Verify `devops review export-feedback` reports one record for a finding that three
    sessions of one subject hold."""
    from typer.testing import CliRunner

    from devops_cli.commands.review import app as review_app

    reviews_dir = tmp_path / "reviews"
    for name in ("20261002-210000", "20261002-220000", "20261002-230000"):
        _subject_session(reviews_dir, name, [_tool_finding("fp-a")])
    output_file = tmp_path / "dataset.jsonl"

    result = CliRunner().invoke(
        review_app,
        [
            "export-feedback",
            "--reviews-dir",
            str(reviews_dir),
            "--output",
            str(output_file),
            "--status",
            "ALL",
        ],
    )

    assert (
        result.exit_code,
        "Appended 1 ALL finding(s)" in result.output,
        len(_lines(output_file)),
    ) == (
        0,
        True,
        1,
    )
