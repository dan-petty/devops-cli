"""`devops review verify` records a person's verdict as a label in the session (#1150).

A verdict changes findings.json and candidates.json and nothing else: no catalog learns from it
and no ledger records it. A known false positive becomes a `.devops/review.toml` suppression.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.ai.review_schema import CitedCode, ReviewSessionPayload, SavedFinding
from devops_cli.commands.review import app

runner = CliRunner()


def _finding() -> SavedFinding:
    return SavedFinding(
        title="Hardcoded token in config",
        location="src/config.py:4",
        description="A token is assigned a literal.",
        severity="HIGH",
        persona="devsecops",
        # The code the review read, which a learned catalog once keyed a person's verdict on.
        cited_code=CitedCode(
            project="app", file="src/config.py", line=4, excerpt='token = load("config")'
        ),
    )


def _saved(path: Path) -> list[tuple[str, str | None, str | None]]:
    findings = ReviewSessionPayload.model_validate_json(path.read_text(encoding="utf-8")).findings
    return [(f.status, f.verified_by, f.invalidation_reason) for f in findings]


def test_a_verdict_is_a_person_label_on_the_session_files_alone(
    tmp_path: Path, isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """An INVALIDATED verdict marks the finding in findings.json and candidates.json as a
    person's, leaves review.md as it was, and writes no catalog or ledger anywhere."""
    session = write_review_session(
        isolate_data_dir / "reviews" / "20261009-090000",
        generated_at="2026-10-09T09:00:00+00:00",
        findings=[_finding()],
        candidates=[_finding()],
    )
    (session / "review.md").write_text("# Report\n", encoding="utf-8")

    res = runner.invoke(
        app, ["verify", session.name, "--index", "1", "--status", "INVALIDATED", "--reason", "x"]
    )

    written = {p.name for p in tmp_path.rglob("*.json")}
    assert (
        res.exit_code,
        _saved(session / "findings.json"),
        _saved(session / "candidates.json"),
        (session / "review.md").read_text(encoding="utf-8"),
        written & {"common_hallucinations.json", "mitigated_findings.json"},
    ) == (
        0,
        [("INVALIDATED", "human", "x")],
        [("INVALIDATED", "human", "x")],
        "# Report\n",
        set(),
    )


@pytest.mark.parametrize(
    "option",
    [
        ["--adjudicator", "agent"],
        ["--perimeter", "src/config.py"],
        ["--regression-test", "tests/test_config.py"],
    ],
    ids=["adjudicator", "perimeter", "regression-test"],
)
def test_verify_has_no_agent_perimeter_or_regression_test_options(
    option: list[str], isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """The options that fed the agent path, the mitigations ledger and its perimeter are gone:
    Click refuses each as unknown and the finding is left as it was."""
    session = write_review_session(
        isolate_data_dir / "reviews" / "20261009-090000",
        generated_at="2026-10-09T09:00:00+00:00",
        findings=[_finding()],
    )

    res = runner.invoke(
        app, ["verify", session.name, "--index", "1", "--status", "MITIGATED", *option]
    )

    assert (res.exit_code, _saved(session / "findings.json")) == (
        2,
        [("UNVERIFIED", None, None)],
    )
