"""Verdicts land on the finding shown, and are a person's labels on the session (#949, #1150).

`devops review findings` numbers each finding by its place in findings.json, or with
`--candidates` in candidates.json, whatever filter it applies, and `devops review verify` takes
the same numbers. A candidate the review left out can be judged, and a VERIFIED or MITIGATED
verdict moves it into findings.json. Every verdict is a person's, records `verified_by="human"`
and ranks review history; it writes the session files and nothing else.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, sentinel

import pytest
from typer.testing import CliRunner

from devops_cli.ai.review.exporter import FeedbackRecord, export_invalidated_feedback
from devops_cli.ai.review.history import load_review_history, review_subject
from devops_cli.ai.review_schema import ReviewSessionPayload, SavedFinding
from devops_cli.commands import review as review_cli
from devops_cli.commands.review import app

runner = CliRunner()

_SUBJECT = review_subject("path", "/repo/src", ["diff --git a/mod.py b/mod.py\n"])
_OLDER = "2026-10-01T09:00:00+00:00"
_NEWER = "2026-10-01T10:00:00+00:00"


def _finding(title: str, line: int, status: str = "UNVERIFIED") -> SavedFinding:
    verdict: dict[str, Any] = {}
    if status in {"VERIFIED", "MITIGATED"}:
        verdict = {"verified": True, "verified_by": "llm", "mitigated": status == "MITIGATED"}
    elif status == "INVALIDATED":
        verdict = {"reportable": False, "verified_by": "deterministic:missing_symbol"}
    return SavedFinding(
        title=title,
        location=f"mod.py:{line}",
        description=f"{title} described.",
        severity="HIGH",
        persona="devsecops",
        status=status,
        **verdict,
    )


def _saved(path: Path) -> list[SavedFinding]:
    return ReviewSessionPayload.model_validate_json(path.read_text(encoding="utf-8")).findings


def _listed_numbers(output: str, titles: tuple[str, ...]) -> tuple[str, ...]:
    """The number in the first column of the table row naming each title; "" when not listed."""
    rows = output.splitlines()
    return tuple(next((row.split()[0] for row in rows if title in row), "") for title in titles)


def test_a_filtered_listing_numbers_findings_as_verify_does(
    isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify `findings --verified` over statuses [UNVERIFIED, VERIFIED, VERIFIED] shows #2 and
    #3, and that `verify --index` with the number shown changes the second finding."""
    session = write_review_session(
        isolate_data_dir / "reviews" / "20261001-090000",
        generated_at=_OLDER,
        subject=_SUBJECT,
        findings=[
            _finding("First open finding", 1),
            _finding("Second confirmed finding", 2, "VERIFIED"),
            _finding("Third confirmed finding", 3, "VERIFIED"),
        ],
    )
    titles = ("First open finding", "Second confirmed finding", "Third confirmed finding")

    listed = runner.invoke(app, ["findings", session.name, "--verified"], env={"COLUMNS": "200"})
    shown = _listed_numbers(listed.output, titles)
    verdict = runner.invoke(
        app,
        ["verify", session.name, "--index", shown[1] or "0", "--status", "INVALIDATED"],
    )

    after = _saved(session / "findings.json")
    assert (listed.exit_code, shown, verdict.exit_code, [f.status for f in after]) == (
        0,
        ("", "2", "3"),
        0,
        ["UNVERIFIED", "INVALIDATED", "VERIFIED"],
    )


def test_a_machine_invalidated_candidate_a_person_verifies_moves_into_findings_json(
    isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify `findings --candidates` lists candidates.json by its own numbers, and that a
    candidate the machine invalidated, marked VERIFIED by a person, is added to findings.json
    with `verified_by="human"` and keeps its verdict in candidates.json."""
    reported = _finding("Reported token leak", 4, "VERIFIED")
    dropped = _finding("Dropped path traversal", 9, "INVALIDATED")
    session = write_review_session(
        isolate_data_dir / "reviews" / "20261001-090000",
        generated_at=_OLDER,
        subject=_SUBJECT,
        findings=[reported],
        candidates=[reported, dropped],
    )

    listed = runner.invoke(
        app, ["findings", session.name, "--candidates", "--invalidated"], env={"COLUMNS": "200"}
    )
    verdict = runner.invoke(
        app,
        [
            "verify",
            session.name,
            "--candidate",
            "2",
            "--status",
            "VERIFIED",
            "--reason",
            "The join takes the raw upload name",
        ],
    )

    findings = _saved(session / "findings.json")
    candidates = _saved(session / "candidates.json")
    assert (
        listed.exit_code,
        _listed_numbers(listed.output, ("Reported token leak", "Dropped path traversal")),
        verdict.exit_code,
        [(f.title, f.status, f.verified_by) for f in findings],
        [(f.title, f.status, f.verified_by) for f in candidates],
    ) == (
        0,
        ("", "2"),
        0,
        [
            ("Reported token leak", "VERIFIED", "llm"),
            ("Dropped path traversal", "VERIFIED", "human"),
        ],
        [
            ("Reported token leak", "VERIFIED", "llm"),
            ("Dropped path traversal", "VERIFIED", "human"),
        ],
    )


def test_a_candidate_judged_again_updates_its_copy_in_findings_json(
    isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify a second verdict on a candidate that was moved into findings.json changes that
    copy instead of adding another one."""
    dropped = _finding("Dropped path traversal", 9, "INVALIDATED")
    session = write_review_session(
        isolate_data_dir / "reviews" / "20261001-090000",
        generated_at=_OLDER,
        subject=_SUBJECT,
        findings=[],
        candidates=[dropped],
    )

    moved = runner.invoke(app, ["verify", session.name, "--candidate", "1", "--status", "VERIFIED"])
    reset = runner.invoke(
        app, ["verify", session.name, "--candidate", "1", "--status", "UNVERIFIED"]
    )

    findings = _saved(session / "findings.json")
    candidates = _saved(session / "candidates.json")
    assert (
        moved.exit_code,
        reset.exit_code,
        [(f.title, f.status, f.verified_by) for f in findings],
        [(f.status, f.verified_by) for f in candidates],
    ) == (0, 0, [("Dropped path traversal", "UNVERIFIED", None)], [("UNVERIFIED", None)])


def test_verify_requires_a_status(
    isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify `verify` without `--status` is refused and changes nothing: there is no default
    verdict for a careless call to apply."""
    session = write_review_session(
        isolate_data_dir / "reviews" / "20261001-090000",
        generated_at=_OLDER,
        subject=_SUBJECT,
        findings=[_finding("Open token leak", 4)],
    )

    res = runner.invoke(app, ["verify", session.name, "--index", "1"])

    after = _saved(session / "findings.json")[0]
    assert (res.exit_code, after.status, after.verified_by) == (2, "UNVERIFIED", None)


def test_a_title_matching_several_findings_is_refused(
    isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify `--title` that matches more than one finding names their numbers and changes
    nothing, instead of judging the first match."""
    session = write_review_session(
        isolate_data_dir / "reviews" / "20261001-090000",
        generated_at=_OLDER,
        subject=_SUBJECT,
        findings=[
            _finding("Hardcoded token in config", 4),
            _finding("Hardcoded password in tests", 8),
        ],
    )

    res = runner.invoke(
        app, ["verify", session.name, "--title", "hardcoded", "--status", "INVALIDATED"]
    )

    after = _saved(session / "findings.json")
    assert (
        res.exit_code,
        "#1, #2" in res.output,
        [f.status for f in after],
    ) == (1, True, ["UNVERIFIED", "UNVERIFIED"])


def test_the_exporter_labels_a_record_human_only_when_a_person_judged_it(tmp_path: Path) -> None:
    """Verify an exported agent verdict stays `agent`, and that a record built without an
    adjudicator is not counted as a person's."""
    session = tmp_path / "reviews" / "20261001-090000"
    session.mkdir(parents=True)
    payload = {
        "findings": [
            {"title": "Agent call", "status": "INVALIDATED", "verified_by": "agent"},
            {"title": "Person call", "status": "INVALIDATED", "verified_by": "human"},
        ]
    }
    (session / "findings.json").write_text(json.dumps(payload), encoding="utf-8")

    count, out = export_invalidated_feedback(
        reviews_dir=tmp_path / "reviews", output_file=tmp_path / "dataset.jsonl"
    )
    labels = [json.loads(line)["verified_by"] for line in out.read_text().splitlines()]
    bare = FeedbackRecord(
        session_id="s", persona="qa", title="t", severity="low", location="", description=""
    )

    assert (count, labels, bare.verified_by == "human") == (2, ["agent", "human"], False)


_PREPARED = {
    "path": ("_prepare_path_content", (["page"], "Path Review", "", [])),
    "branch": (
        "_prepare_branch_content",
        (["diff"], "Branch Review", "", "feature", sentinel.base_revision),
    ),
    "pr": (
        "_prepare_pr_content",
        (["diff"], "PR 10", "", MagicMock(), "org/repo", sentinel.base_revision),
    ),
}


@pytest.mark.parametrize(
    ("command", "args"),
    [("path", ["path"]), ("branch", ["branch", "feature"]), ("pr", ["pr", "10"])],
)
def test_each_review_command_loads_settings_once(
    command: str, args: list[str], tmp_path: Path
) -> None:
    """Verify `review path`, `branch` and `pr` read the configuration once per run."""
    preparer, prepared = _PREPARED[command]
    with (
        patch("devops_cli.commands.review.load_settings") as load,
        patch("devops_cli.commands.review._make_review_clients"),
        patch(f"devops_cli.commands.review.{preparer}", return_value=prepared),
        patch("devops_cli.commands.review._execute_review_workflow", return_value=[]),
    ):
        target = [str(tmp_path)] if command == "path" else []
        res = runner.invoke(app, [*args, *target, "--no-logfire"])

    assert (res.exit_code, load.call_count) == (0, 1)


_REPORTED_TRAVERSAL = SavedFinding(
    title="Path traversal in `save_upload`",
    location="mod.py:20-22",
    description="`save_upload` joins the upload name onto the storage root.",
    severity="HIGH",
    persona="devsecops",
    status="VERIFIED",
    verified=True,
    verified_by="llm",
)
_SECOND_TRAVERSAL = SavedFinding(
    title="Path traversal via upload name in `save_upload`",
    location="mod.py:21",
    description="The upload name reaches the path join in `save_upload` unchecked.",
    severity="HIGH",
    persona="qa",
)


@pytest.mark.parametrize(
    ("second", "status"),
    [
        pytest.param(
            _SECOND_TRAVERSAL.model_copy(
                update={"status": "INVALIDATED", "reportable": False, "verified_by": "llm"}
            ),
            "VERIFIED",
            id="invalidated-duplicate-verified",
        ),
        pytest.param(
            _SECOND_TRAVERSAL.model_copy(
                update={"status": "INVALIDATED", "reportable": False, "verified_by": "llm"}
            ),
            "MITIGATED",
            id="invalidated-duplicate-mitigated",
        ),
        pytest.param(
            _SECOND_TRAVERSAL.model_copy(
                update={"status": "VERIFIED", "verified": True, "verified_by": "llm"}
            ),
            "VERIFIED",
            id="candidate-consolidation-merged",
        ),
    ],
)
def test_a_candidate_whose_defect_is_reported_is_never_added_twice(
    second: SavedFinding,
    status: str,
    isolate_data_dir: Path,
    write_review_session: Callable[..., Path],
) -> None:
    """Verify a VERIFIED or MITIGATED verdict on a candidate whose defect findings.json already
    reports under another persona's title is refused and names that finding, so the report
    never holds the defect twice, and that neither file changes."""
    session = write_review_session(
        isolate_data_dir / "reviews" / "20261001-090000",
        generated_at=_OLDER,
        subject=_SUBJECT,
        findings=[_REPORTED_TRAVERSAL],
        candidates=[_REPORTED_TRAVERSAL, second],
    )

    res = runner.invoke(app, ["verify", session.name, "--candidate", "2", "--status", status])

    assert (
        res.exit_code,
        "--index 1" in res.output,
        [(f.title, f.status, f.verified_by) for f in _saved(session / "findings.json")],
        [(f.status, f.verified_by) for f in _saved(session / "candidates.json")],
    ) == (
        1,
        True,
        [("Path traversal in `save_upload`", "VERIFIED", "llm")],
        [("VERIFIED", "llm"), (second.status, "llm")],
    )


def _dropped(n: int) -> SavedFinding:
    """A candidate the machine invalidated, in a file of its own."""
    return SavedFinding(
        title=f"Unchecked redirect target in handler{n}",
        location=f"handler{n}.py:9",
        description=f"handler{n} redirects to a URL the request supplies.",
        severity="HIGH",
        persona="devsecops",
        status="INVALIDATED",
        reportable=False,
        verified_by="deterministic:missing_symbol",
    )


def test_verdicts_given_at_once_on_one_session_all_land(
    isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify verdicts given at the same time on one session all land: every `--index` and
    `--candidate` verdict is in the session files."""
    reported = [_finding("Open token leak", 4), _finding("Open path traversal", 8)]
    session = write_review_session(
        isolate_data_dir / "reviews" / "20261001-090000",
        generated_at=_OLDER,
        subject=_SUBJECT,
        findings=reported,
        candidates=[*reported, _dropped(1), _dropped(2)],
    )
    calls: list[dict[str, Any]] = [
        {"index": 1, "status": "INVALIDATED", "reason": "Engine supports widget syntax"},
        {"index": 2, "status": "INVALIDATED", "reason": "Engine supports widget syntax"},
        {"candidate": 3, "status": "VERIFIED"},
        {"candidate": 4, "status": "VERIFIED"},
    ]
    read = review_cli._read_session_file
    start = threading.Barrier(len(calls))
    failures: list[BaseException] = []

    def slow_read(*args: Any) -> Any:
        # Hold each read open long enough that every call reads before any call writes.
        got = read(*args)
        time.sleep(0.02)
        return got

    def give(kwargs: dict[str, Any]) -> None:
        start.wait()
        try:
            review_cli.verify_finding(session.name, **kwargs)
        except BaseException as exc:
            failures.append(exc)

    with patch("devops_cli.commands.review._read_session_file", side_effect=slow_read):
        threads = [threading.Thread(target=give, args=(kwargs,)) for kwargs in calls]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    findings = _saved(session / "findings.json")
    assert (
        failures,
        sorted((f.title, f.status, f.verified_by) for f in findings),
        [(f.status, f.verified_by) for f in _saved(session / "candidates.json")[2:]],
    ) == (
        [],
        [
            ("Open path traversal", "INVALIDATED", "human"),
            ("Open token leak", "INVALIDATED", "human"),
            ("Unchecked redirect target in handler1", "VERIFIED", "human"),
            ("Unchecked redirect target in handler2", "VERIFIED", "human"),
        ],
        [("VERIFIED", "human"), ("VERIFIED", "human")],
    )


_replace = os.replace


def _replace_all_but_findings(src: Any, dst: Any, *args: Any, **kwargs: Any) -> None:
    """`os.replace` on a disk with no room left for findings.json."""
    if Path(dst).name == "findings.json":
        raise OSError(28, "No space left on device")
    _replace(src, dst, *args, **kwargs)


@pytest.mark.parametrize("step", ["verdict", "reset"])
def test_a_failed_session_write_leaves_the_session_as_it_was(
    step: str, isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify a verdict whose findings.json cannot be written fails and leaves the session's
    verdicts as they were, whether it gives a verdict or resets one."""
    session = write_review_session(
        isolate_data_dir / "reviews" / "20261001-090000",
        generated_at=_OLDER,
        subject=_SUBJECT,
        findings=[_finding("Open token leak", 4), _finding("Unbounded upload buffer", 12)],
    )
    verdicts = (
        ["--index", "1", "--status", "INVALIDATED", "--reason", "Engine supports widget syntax"],
        ["--index", "2", "--status", "MITIGATED", "--reason", "Gateway caps bodies at 10 MB"],
    )
    if step == "reset":
        for args in verdicts:
            runner.invoke(app, ["verify", session.name, *args])
        verdicts = (
            ["--index", "1", "--status", "UNVERIFIED"],
            ["--index", "2", "--status", "UNVERIFIED"],
        )
    before = [(f.status, f.verified_by) for f in _saved(session / "findings.json")]

    with patch("os.replace", side_effect=_replace_all_but_findings):
        codes = [runner.invoke(app, ["verify", session.name, *args]).exit_code for args in verdicts]

    after = [(f.status, f.verified_by) for f in _saved(session / "findings.json")]
    assert (codes, after) == ([1, 1], before)


def test_a_verdict_by_number_reaches_the_candidate_the_finding_reports(
    isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify an `--index` verdict is recorded on the finding's candidate in candidates.json too:
    for a finding the review reported, and for a candidate a person's verdict moved into
    findings.json, whose reset leaves candidates.json no verdict findings.json withdrew."""
    reported = _finding("Reported token leak", 4, "VERIFIED")
    session = write_review_session(
        isolate_data_dir / "reviews" / "20261001-090000",
        generated_at=_OLDER,
        subject=_SUBJECT,
        findings=[reported],
        candidates=[reported, _finding("Dropped path traversal", 9, "INVALIDATED")],
    )
    steps = (
        ["--index", "1", "--status", "VERIFIED", "--reason", "The token is live"],
        ["--candidate", "2", "--status", "MITIGATED", "--reason", "Gateway caps"],
        ["--index", "2", "--status", "UNVERIFIED"],
    )

    codes = [runner.invoke(app, ["verify", session.name, *args]).exit_code for args in steps]

    def verdicts(name: str) -> list[tuple[str, str | None]]:
        return [(f.status, f.verified_by) for f in _saved(session / name)]

    assert (codes, verdicts("findings.json"), verdicts("candidates.json")) == (
        [0, 0, 0],
        [("VERIFIED", "human"), ("UNVERIFIED", None)],
        [("VERIFIED", "human"), ("UNVERIFIED", None)],
    )


def test_candidates_of_one_title_and_location_are_told_apart(
    isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify a verdict on one persona's candidate leaves alone the finding another persona
    reported with the same title at the same location."""
    reported = _finding("Missing input validation", 9, "VERIFIED")
    other = _finding("Missing input validation", 9, "INVALIDATED").model_copy(
        update={"persona": "qa", "description": "The handler trusts the form fields."}
    )
    session = write_review_session(
        isolate_data_dir / "reviews" / "20261001-090000",
        generated_at=_OLDER,
        subject=_SUBJECT,
        findings=[reported],
        candidates=[reported, other],
    )

    res = runner.invoke(app, ["verify", session.name, "--candidate", "2", "--status", "UNVERIFIED"])

    assert (
        res.exit_code,
        [(f.persona, f.status, f.verified_by) for f in _saved(session / "findings.json")],
        [(f.persona, f.status, f.verified_by) for f in _saved(session / "candidates.json")],
    ) == (
        0,
        [("devsecops", "VERIFIED", "llm")],
        [("devsecops", "VERIFIED", "llm"), ("qa", "UNVERIFIED", None)],
    )


def test_a_candidate_that_cannot_be_told_from_another_is_judged_through_its_finding(
    isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify a `--candidate` verdict is refused, naming the finding to judge with `--index`,
    when that finding reports another candidate of the same persona, title, location and
    description too, and that the finding's verdict then reaches both candidates."""
    reported = _finding("Missing input validation", 9, "VERIFIED")
    twin = _finding("Missing input validation", 9, "INVALIDATED")
    session = write_review_session(
        isolate_data_dir / "reviews" / "20261001-090000",
        generated_at=_OLDER,
        subject=_SUBJECT,
        findings=[reported],
        candidates=[reported, twin],
    )

    def verdicts() -> tuple[list[tuple[str, str | None]], ...]:
        return tuple(
            [(f.status, f.verified_by) for f in _saved(session / name)]
            for name in ("findings.json", "candidates.json")
        )

    refused = runner.invoke(
        app, ["verify", session.name, "--candidate", "2", "--status", "UNVERIFIED"]
    )
    unchanged = verdicts()
    judged = runner.invoke(
        app, ["verify", session.name, "--index", "1", "--status", "INVALIDATED", "-r", "Checked"]
    )

    assert (refused.exit_code, "--index 1" in refused.output, unchanged, judged.exit_code) + (
        verdicts()
    ) == (
        1,
        True,
        (
            [("VERIFIED", "llm")],
            [("VERIFIED", "llm"), ("INVALIDATED", "deterministic:missing_symbol")],
        ),
        0,
        [("INVALIDATED", "human")],
        [("INVALIDATED", "human"), ("INVALIDATED", "human")],
    )


def test_a_persons_verdict_on_a_candidate_kept_out_ranks_its_session(
    isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify a person's verdict on a candidate that stays out of findings.json counts as a
    person's in review history, so a newer machine re-run of the subject does not displace it."""
    reviews = isolate_data_dir / "reviews"
    for name, generated_at in (("20261001-090000", _OLDER), ("20261001-100000", _NEWER)):
        open_finding = _finding("Open token leak", 4)
        write_review_session(
            reviews / name,
            generated_at=generated_at,
            subject=_SUBJECT,
            findings=[open_finding],
            candidates=[open_finding, _finding("Dropped path traversal", 9, "INVALIDATED")],
        )

    res = runner.invoke(
        app,
        [
            "verify",
            "20261001-090000",
            "--candidate",
            "2",
            "--status",
            "INVALIDATED",
            "--reason",
            "The path is joined under a fixed root",
        ],
    )

    counted = load_review_history(reviews).counted
    assert (res.exit_code, tuple(s.path.name for s in counted)) == (0, ("20261001-090000",))


def test_a_stored_agent_verdict_leaves_history_ranking_alone(
    isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify an agent's verdict that a session saved before #1150 holds does not make that
    session outrank a newer one of the subject: history counts no agent verdict."""
    reviews = isolate_data_dir / "reviews"
    judged = _finding("Open token leak", 4).model_copy(
        update={"status": "INVALIDATED", "reportable": False, "verified_by": "agent"}
    )
    write_review_session(
        reviews / "20261001-090000",
        generated_at=_OLDER,
        subject=_SUBJECT,
        findings=[_finding("Open token leak", 4)],
        candidates=[judged],
    )
    write_review_session(
        reviews / "20261001-100000",
        generated_at=_NEWER,
        subject=_SUBJECT,
        findings=[_finding("Open token leak", 4)],
    )

    counted = load_review_history(reviews).counted

    assert tuple(s.path.name for s in counted) == ("20261001-100000",)
