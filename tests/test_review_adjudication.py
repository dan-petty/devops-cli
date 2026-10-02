"""Verdicts land on the finding shown, and record who gave them (#949).

`devops review findings` numbers each finding by its place in findings.json, or with
`--candidates` in candidates.json, whatever filter it applies, and `devops review verify` takes
the same numbers. A candidate the review left out can be judged, and a VERIFIED or MITIGATED
verdict moves it into findings.json. Each verdict records its adjudicator: `human` or `agent`,
and the MCP tool always records `agent`. Only a person's verdict ranks review history or writes
the learned catalog and the mitigations ledger, and resetting it to UNVERIFIED removes the
entries it created.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, sentinel

import pytest
from typer.testing import CliRunner

from devops_cli.ai.mcp.server import verify_finding
from devops_cli.ai.review.common_hallucinations import (
    CommonHallucinationEntry,
    HallucinationCategory,
    auto_record_invalidated_finding,
    load_common_hallucinations,
    register_common_hallucination,
)
from devops_cli.ai.review.exporter import FeedbackRecord, export_invalidated_feedback
from devops_cli.ai.review.history import load_review_history, review_subject
from devops_cli.ai.review.mitigations import (
    MitigatedFindingEntry,
    load_mitigated_findings,
    record_mitigated_finding,
    save_mitigated_findings,
)
from devops_cli.ai.review_schema import ReviewSessionPayload, SavedFinding
from devops_cli.commands import review as review_cli
from devops_cli.commands.review import app
from devops_cli.exceptions.validation import ValidationError

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


def _template_finding() -> SavedFinding:
    """A finding a person's INVALIDATED verdict teaches the learned catalog."""
    return SavedFinding(
        title="Quirky Framework Obsolete Artifact Warning",
        description="Flagged obsolete widget architecture in template engine.",
        location="templates/view.html:4",
        persona="qa",
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


@pytest.mark.parametrize(
    "with_candidates",
    [
        pytest.param(True, id="with-candidates-json"),
        # The persona loop writes no candidates.json, so history reads findings.json, where the
        # agent's verdict lands.
        pytest.param(False, id="without-candidates-json"),
    ],
)
def test_the_mcp_tool_records_an_agent_verdict_that_history_ranking_ignores(
    with_candidates: bool, isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify the MCP tool, numbering from 1 as the CLI does, records `verified_by="agent"` on
    the finding it names, and that review history still counts the newer session of the
    subject: an agent's verdict is not a person's."""
    reviews = isolate_data_dir / "reviews"
    for name, generated_at in (("20261001-090000", _OLDER), ("20261001-100000", _NEWER)):
        open_finding = _finding("Open token leak", 4)
        write_review_session(
            reviews / name,
            generated_at=generated_at,
            subject=_SUBJECT,
            findings=[open_finding],
            candidates=[open_finding] if with_candidates else None,
        )
    commands: list[list[str]] = []

    def run_through_cli(cmd: list[str], **_: object) -> str:
        commands.append(cmd)
        return runner.invoke(app, cmd[4:]).output

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd", side_effect=run_through_cli):
        verify_finding("20261001-090000", 1, "VERIFIED", "Token is live")

    judged = _saved(reviews / "20261001-090000" / "findings.json")[0]
    counted = load_review_history(reviews).counted
    assert (
        commands[0][-2:],
        (judged.status, judged.verified_by),
        tuple(s.path.name for s in counted),
    ) == (["--adjudicator", "agent"], ("VERIFIED", "agent"), ("20261001-100000",))


def test_an_agent_verdict_on_a_candidate_leaves_history_ranking_alone(
    isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify an agent's verdict on an open candidate does not make its session outrank a newer
    session of the subject: history counts no agent verdict, as a person's or as any other."""
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
            "1",
            "--status",
            "INVALIDATED",
            "--adjudicator",
            "agent",
        ],
    )

    judged = _saved(reviews / "20261001-090000" / "candidates.json")[0]
    counted = load_review_history(reviews).counted
    assert (
        res.exit_code,
        (judged.status, judged.verified_by),
        tuple(s.path.name for s in counted),
    ) == (0, ("INVALIDATED", "agent"), ("20261001-100000",))


def test_the_mcp_tool_counts_findings_from_one() -> None:
    """Verify the MCP tool refuses index 0, which the CLI has never accepted."""
    with (
        patch("devops_cli.ai.mcp.server._run_mcp_cmd") as run,
        pytest.raises(ValidationError, match="index"),
    ):
        verify_finding("20261001-090000", 0, "VERIFIED")

    assert run.call_count == 0


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


def _catalog_learned_ids() -> list[str]:
    return [e.id for e in load_common_hallucinations(include_builtin=False)]


def _ledger_titles() -> list[str]:
    return [e.title for e in load_mitigated_findings()]


def test_a_reset_removes_the_catalog_and_ledger_entries_its_verdict_created(
    isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify a person's INVALIDATED verdict teaches the learned catalog and a MITIGATED one
    writes the mitigations ledger, and that resetting each finding to UNVERIFIED removes the
    entries its verdict created and leaves every other entry alone."""
    register_common_hallucination(
        CommonHallucinationEntry(
            id="HALLUCINATION-AUTO-00000001",
            name="Earlier learned entry",
            category=HallucinationCategory.GENERAL,
            description="Kept",
            pattern_keywords=["earlier", "entry"],
            resolution="Kept",
            source="auto_learned",
        )
    )
    save_mitigated_findings(
        [MitigatedFindingEntry(title="Earlier mitigation", location="other.py:1")]
    )
    session = write_review_session(
        isolate_data_dir / "reviews" / "20261001-090000",
        generated_at=_OLDER,
        subject=_SUBJECT,
        findings=[
            _template_finding(),
            _finding("Unbounded upload buffer", 12),
        ],
    )
    verdicts = (
        ["--index", "1", "--status", "INVALIDATED", "--reason", "Engine supports widget syntax"],
        ["--index", "2", "--status", "MITIGATED", "--reason", "Gateway caps bodies at 10 MB"],
    )
    resets = (
        ["--index", "1", "--status", "UNVERIFIED"],
        ["--index", "2", "--status", "UNVERIFIED"],
    )

    judged = [runner.invoke(app, ["verify", session.name, *args]).exit_code for args in verdicts]
    learned, ledger = len(_catalog_learned_ids()), _ledger_titles()
    reset = [runner.invoke(app, ["verify", session.name, *args]).exit_code for args in resets]

    after = _saved(session / "findings.json")
    assert (
        judged,
        learned,
        ledger,
        reset,
        _catalog_learned_ids(),
        _ledger_titles(),
        [(f.status, f.learned_catalog_ids, f.mitigation_ledger_ids) for f in after],
    ) == (
        [0, 0],
        2,
        ["Earlier mitigation", "Unbounded upload buffer"],
        [0, 0],
        ["HALLUCINATION-AUTO-00000001"],
        ["Earlier mitigation"],
        [("UNVERIFIED", [], []), ("UNVERIFIED", [], [])],
    )


def test_an_agent_verdict_writes_neither_the_catalog_nor_the_ledger(
    isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify `--adjudicator agent` records the verdict as the agent's, and that it teaches the
    learned catalog nothing and writes no mitigation to the ledger."""
    session = write_review_session(
        isolate_data_dir / "reviews" / "20261001-090000",
        generated_at=_OLDER,
        subject=_SUBJECT,
        findings=[
            _template_finding(),
            _finding("Unbounded upload buffer", 12),
        ],
    )

    codes = [
        runner.invoke(
            app,
            [
                "verify",
                session.name,
                "--index",
                index,
                "--status",
                status,
                "--adjudicator",
                "agent",
            ],
        ).exit_code
        for index, status in (("1", "INVALIDATED"), ("2", "MITIGATED"))
    ]

    after = _saved(session / "findings.json")
    assert (
        codes,
        [(f.status, f.verified_by) for f in after],
        _catalog_learned_ids(),
        _ledger_titles(),
    ) == ([0, 0], [("INVALIDATED", "agent"), ("MITIGATED", "agent")], [], [])


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
    "path": ("_prepare_path_content", (["page"], "Path Review", "")),
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
        patch("devops_cli.config.settings.get_github_token", return_value="ghp_test"),
    ):
        target = [str(tmp_path)] if command == "path" else []
        res = runner.invoke(app, [*args, *target, "--no-logfire"])

    assert (res.exit_code, load.call_count) == (0, 1)


def test_a_candidate_reset_also_removes_entries_its_copy_was_given(
    isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify resetting a candidate removes the learned entry a person's `--index` verdict on
    its copy in findings.json created, so neither file keeps an id the catalog lost."""
    reported = _template_finding()
    session = write_review_session(
        isolate_data_dir / "reviews" / "20261001-090000",
        generated_at=_OLDER,
        subject=_SUBJECT,
        findings=[reported],
        candidates=[reported],
    )

    judged = runner.invoke(
        app,
        ["verify", session.name, "--index", "1", "--status", "INVALIDATED", "-r", "Valid syntax"],
    )
    learned = len(_catalog_learned_ids())
    reset = runner.invoke(
        app, ["verify", session.name, "--candidate", "1", "--status", "UNVERIFIED"]
    )

    copy = _saved(session / "findings.json")[0]
    assert (
        judged.exit_code,
        learned,
        reset.exit_code,
        _catalog_learned_ids(),
        (copy.status, copy.learned_catalog_ids),
    ) == (0, 1, 0, [], ("UNVERIFIED", []))


def _learned_counts() -> list[int]:
    return [e.occurrence_count for e in load_common_hallucinations(include_builtin=False)]


def test_an_agent_cannot_change_a_persons_verdict(
    isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify an agent's reset of a finding a person judged, by `--index` or through the MCP
    tool, is refused, and that the person's verdicts and the catalog and ledger entries they
    wrote all stay."""
    session = write_review_session(
        isolate_data_dir / "reviews" / "20261001-090000",
        generated_at=_OLDER,
        subject=_SUBJECT,
        findings=[_template_finding(), _finding("Unbounded upload buffer", 12)],
    )
    for args in (
        ["--index", "1", "--status", "INVALIDATED", "--reason", "Engine supports widget syntax"],
        ["--index", "2", "--status", "MITIGATED", "--reason", "Gateway caps bodies at 10 MB"],
    ):
        runner.invoke(app, ["verify", session.name, *args])

    refused = runner.invoke(
        app,
        [
            "verify",
            session.name,
            "--index",
            "1",
            "--status",
            "UNVERIFIED",
            "--adjudicator",
            "agent",
        ],
    )
    with patch(
        "devops_cli.ai.mcp.server._run_mcp_cmd",
        side_effect=lambda cmd, **_: runner.invoke(app, cmd[4:]).output,
    ):
        mcp_output = verify_finding(session.name, 2, "UNVERIFIED")

    assert (
        refused.exit_code,
        "an agent cannot change it" in mcp_output,
        [(f.status, f.verified_by) for f in _saved(session / "findings.json")],
        _learned_counts(),
        _ledger_titles(),
    ) == (
        1,
        True,
        [("INVALIDATED", "human"), ("MITIGATED", "human")],
        [1],
        ["Unbounded upload buffer"],
    )


def test_an_agent_cannot_change_a_persons_verdict_through_a_candidate(
    isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify an agent's verdict on a candidate whose copy in findings.json a person judged,
    which recorded the person's verdict on the candidate too, is refused before either file
    changes."""
    reported = _finding("Unbounded upload buffer", 12)
    session = write_review_session(
        isolate_data_dir / "reviews" / "20261001-090000",
        generated_at=_OLDER,
        subject=_SUBJECT,
        findings=[reported],
        candidates=[reported],
    )
    runner.invoke(app, ["verify", session.name, "--index", "1", "--status", "MITIGATED"])

    res = runner.invoke(
        app,
        [
            "verify",
            session.name,
            "--candidate",
            "1",
            "--status",
            "INVALIDATED",
            "--adjudicator",
            "agent",
        ],
    )

    assert (
        res.exit_code,
        [(f.status, f.verified_by) for f in _saved(session / "findings.json")],
        [(f.status, f.verified_by) for f in _saved(session / "candidates.json")],
        _ledger_titles(),
    ) == (1, [("MITIGATED", "human")], [("MITIGATED", "human")], ["Unbounded upload buffer"])


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


def test_a_reset_keeps_a_ledger_entry_another_verdict_still_records(
    isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify two findings of one title in one file, both MITIGATED by a person, share one
    ledger entry that resetting the first leaves for the second, and resetting both removes."""
    session = write_review_session(
        isolate_data_dir / "reviews" / "20261001-090000",
        generated_at=_OLDER,
        subject=_SUBJECT,
        findings=[_finding("Unbounded upload buffer", 12), _finding("Unbounded upload buffer", 40)],
    )

    def verify(index: str, status: str) -> list[str]:
        runner.invoke(app, ["verify", session.name, "--index", index, "--status", status])
        return _ledger_titles()

    steps = [
        verify("1", "MITIGATED"),
        verify("2", "MITIGATED"),
        verify("1", "UNVERIFIED"),
    ]
    still_judged = [(f.status, f.verified_by) for f in _saved(session / "findings.json")]
    steps.append(verify("2", "UNVERIFIED"))

    assert (steps, still_judged) == (
        [["Unbounded upload buffer"]] * 3 + [[]],
        [("UNVERIFIED", None), ("MITIGATED", "human")],
    )


def test_a_reset_keeps_a_learned_entry_another_sessions_verdict_still_teaches(
    isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify two sessions' INVALIDATED verdicts on one finding teach one learned entry twice,
    that a candidate's reset, which its copy in findings.json mirrors, withdraws its own
    verdict once, and that the entry goes with the last verdict behind it."""
    reviews = isolate_data_dir / "reviews"
    for name in ("20261001-090000", "20261001-100000"):
        write_review_session(
            reviews / name,
            generated_at=_OLDER,
            subject=_SUBJECT,
            findings=[_template_finding()],
            candidates=[_template_finding()],
        )

    def verify(session: str, which: str, status: str) -> list[int]:
        reason = ["--reason", "Engine supports widget syntax"] if status == "INVALIDATED" else []
        runner.invoke(app, ["verify", session, which, "1", "--status", status, *reason])
        return _learned_counts()

    steps = [
        verify("20261001-090000", "--index", "INVALIDATED"),
        verify("20261001-100000", "--candidate", "INVALIDATED"),
        verify("20261001-100000", "--candidate", "UNVERIFIED"),
        verify("20261001-090000", "--index", "UNVERIFIED"),
    ]

    assert steps == [[1], [2], [1], []]


def _teaching_finding(n: int) -> SavedFinding:
    """A reported finding whose INVALIDATED verdict by a person teaches the learned catalog."""
    return _template_finding().model_copy(
        update={
            "title": f"Quirky Framework Obsolete Artifact Warning in view{n}",
            "location": f"templates/view{n}.html:4",
        }
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
    """Verify verdicts given at the same time on one session, as an MCP client's parallel calls
    give them, all land: every `--index` and `--candidate` verdict is in the session files, and
    the learned catalog counts exactly the verdicts the findings record."""
    reported = [_teaching_finding(1), _teaching_finding(2)]
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
    held = Counter(i for f in findings for i in f.learned_catalog_ids)
    learned = Counter(
        {e.id: e.occurrence_count for e in load_common_hallucinations(include_builtin=False)}
    )
    assert (
        failures,
        sorted((f.title, f.status, f.verified_by) for f in findings),
        [(f.status, f.verified_by) for f in _saved(session / "candidates.json")[2:]],
        sum(held.values()),
        held == learned,
    ) == (
        [],
        [
            ("Quirky Framework Obsolete Artifact Warning in view1", "INVALIDATED", "human"),
            ("Quirky Framework Obsolete Artifact Warning in view2", "INVALIDATED", "human"),
            ("Unchecked redirect target in handler1", "VERIFIED", "human"),
            ("Unchecked redirect target in handler2", "VERIFIED", "human"),
        ],
        [("VERIFIED", "human"), ("VERIFIED", "human")],
        2,
        True,
    )


_replace = os.replace


def _replace_all_but_findings(src: Any, dst: Any, *args: Any, **kwargs: Any) -> None:
    """`os.replace` on a disk with no room left for findings.json."""
    if Path(dst).name == "findings.json":
        raise OSError(28, "No space left on device")
    _replace(src, dst, *args, **kwargs)


def _learned_entries() -> list[dict[str, Any]]:
    return [e.model_dump() for e in load_common_hallucinations(include_builtin=False)]


def _ledger_entries() -> list[dict[str, Any]]:
    return [e.model_dump() for e in load_mitigated_findings()]


@pytest.mark.parametrize("step", ["verdict", "reset"])
def test_a_failed_session_write_leaves_the_catalog_and_ledger_as_they_were(
    step: str, isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify a verdict whose findings.json cannot be written leaves the learned catalog and the
    ledger as they were: a person's verdict removes the entries it created, and a reset keeps
    the entries the unchanged findings still hold."""
    session = write_review_session(
        isolate_data_dir / "reviews" / "20261001-090000",
        generated_at=_OLDER,
        subject=_SUBJECT,
        findings=[_template_finding(), _finding("Unbounded upload buffer", 12)],
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
    before = (
        [(f.status, f.verified_by) for f in _saved(session / "findings.json")],
        _learned_counts(),
        _ledger_titles(),
    )

    with patch("os.replace", side_effect=_replace_all_but_findings):
        codes = [runner.invoke(app, ["verify", session.name, *args]).exit_code for args in verdicts]

    after = (
        [(f.status, f.verified_by) for f in _saved(session / "findings.json")],
        _learned_counts(),
        _ledger_titles(),
    )
    assert (codes, after) == ([1, 1], before)


def test_a_failed_session_write_leaves_entries_a_verdict_updated_as_they_were(
    isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """Verify a person's verdicts that update a learned-catalog entry and a ledger entry already
    on disk, and whose findings.json cannot be written, leave every field of both entries as it
    was: the resolution, keywords and last-seen time of the one, and the mechanism, perimeter,
    reason, regression test and time of the other, as well as their counts."""
    auto_record_invalidated_finding(_template_finding(), reason="Original resolution")
    record_mitigated_finding(
        _finding("Unbounded upload buffer", 12),
        reason="Gateway caps bodies at 1 MiB",
        perimeter_files=["gateway.py", "limits.py"],
        regression_test="tests/test_gateway.py",
    )
    widened = _template_finding().model_copy(
        update={"description": f"{_template_finding().description} Zephyrine quolloxite."}
    )
    session = write_review_session(
        isolate_data_dir / "reviews" / "20261001-090000",
        generated_at=_OLDER,
        subject=_SUBJECT,
        findings=[widened, _finding("Unbounded upload buffer", 12)],
    )
    verdicts = (
        ["--index", "1", "--status", "INVALIDATED", "--reason", "Brand new reason"],
        [
            *("--index", "2", "--status", "MITIGATED", "--reason", "Something else entirely"),
            *("--perimeter", "other.py", "--regression-test", "tests/test_other.py"),
        ],
    )
    before = (_learned_entries(), _ledger_entries())

    with patch("os.replace", side_effect=_replace_all_but_findings):
        failed = [
            runner.invoke(app, ["verify", session.name, *args]).exit_code for args in verdicts
        ]
    after = (_learned_entries(), _ledger_entries())
    # The same verdicts, once the files can be written, update those two entries.
    landed = [runner.invoke(app, ["verify", session.name, *args]).exit_code for args in verdicts]

    assert (
        failed,
        after,
        landed,
        [(e["id"], e["occurrence_count"]) for e in _learned_entries()],
        [(e["id"], e["verdict_count"]) for e in _ledger_entries()],
    ) == (
        [1, 1],
        before,
        [0, 0],
        [(e["id"], 2) for e in before[0]],
        [(e["id"], 2) for e in before[1]],
    )


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

    def verdicts(name: str) -> list[tuple[str, str | None, list[str]]]:
        saved = _saved(session / name)
        return [(f.status, f.verified_by, f.mitigation_ledger_ids) for f in saved]

    assert (codes, verdicts("findings.json"), verdicts("candidates.json"), _ledger_titles()) == (
        [0, 0, 0],
        [("VERIFIED", "human", []), ("UNVERIFIED", None, [])],
        [("VERIFIED", "human", []), ("UNVERIFIED", None, [])],
        [],
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
