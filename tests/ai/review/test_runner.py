"""What the review runner reads: the target's analysis metadata (#1100), the review.toml
suppressions a branch or PR change touches, and what a model's reply may not set (#1150)."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.analyze.symbols import BaseRevision
from devops_cli.ai.personas import PERSONAS, Persona
from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review.runner import (
    ReviewClients,
    _check_and_warn_perimeter_changes,
    _execute_final_recompose,
    _execute_review_workflow,
    _parse_reply,
    _run_persona_loop,
    _run_review,
)
from devops_cli.config.constants import CONST_REVIEW_CONFIG_FILE

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

    _check_and_warn_perimeter_changes(
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

    _check_and_warn_perimeter_changes(
        "path", ["src/a.py"], base_revision=_base_revision(), target_dir=tmp_path
    )

    assert capsys.readouterr().out == ""


def _checkout(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text("[project]\nname = 'target'\n", encoding="utf-8")
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    return root


def test_no_review_layer_falls_back_to_the_working_directory_for_its_target() -> None:
    """Verify every layer that carries a review's target down to the personas requires it
    (#1100). A default of the working directory let a new caller that left the target out
    type-check and review the working directory's files, one layer above the fix."""
    layers = {
        "_execute_review_workflow": _execute_review_workflow,
        "ReviewPipelineOrchestrator": ReviewPipelineOrchestrator.__init__,
        "_run_persona_loop": _run_persona_loop,
        "_run_review": _run_review,
    }
    targets = {name: inspect.signature(fn).parameters["target_dir"] for name, fn in layers.items()}
    refresh = inspect.signature(ReviewPipelineOrchestrator.run_pre_analysis_refresh)

    assert {
        name: (p.kind, p.default is inspect.Parameter.empty) for name, p in targets.items()
    } == dict.fromkeys(layers, (inspect.Parameter.KEYWORD_ONLY, True))
    assert refresh.parameters["target_dir"].default is inspect.Parameter.empty


@pytest.mark.parametrize("summary_only", [True, False])
def test_a_review_outside_the_working_directory_reads_its_targets_analysis_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, summary_only: bool
) -> None:
    """Verify a review whose target is not the working directory loads analysis metadata from
    the target's repository, in the summary and down the persona loop (#1100). Both read the
    repository the working directory belongs to, so another checkout's files were described
    by this one's metadata."""
    here = _checkout(tmp_path / "here", {"runner.py": _RUNNER})
    target = _checkout(tmp_path / "target", {"runner.py": _RUNNER})
    monkeypatch.chdir(here)
    roots: list[object] = []

    def metas(_files: object, repo_root: object = None) -> dict[str, object]:
        roots.append(repo_root)
        return {}

    with (
        patch("devops_cli.ai.review.runner._load_file_analysis_metas", side_effect=metas),
        patch("devops_cli.ai.review.runner._execute_review_segments", return_value=[""]),
        patch("devops_cli.ai.review.runner._print_analysis_metadata"),
    ):
        _execute_review_workflow(
            [f"### File: runner.py\n{_RUNNER}"],
            "Path review",
            MagicMock(),
            "",
            False,
            Persona.DEVSECOPS,
            summary_only,
            ReviewClients(analysis=MagicMock(), compose=MagicMock()),
            target_type="path",
            target_ref=str(target),
            target_dir=target,
        )

    assert (len(roots) > 0, set(roots)) == (True, {target.resolve()})


class _Compose:
    """The compose model's edge: it answers the recompose prompt with a canned reply."""

    def __init__(self, reply: str) -> None:
        self.reply = reply

    def chat(self, **_: object) -> str:
        return self.reply


def _reply(*findings: dict[str, object]) -> str:
    return json.dumps(
        {"findings": list(findings), "recommendation": "REQUEST CHANGES", "summary": "s"}
    )


_SELF_JUDGED = {
    "severity": "HIGH",
    "location": "src/a.py:3",
    "title": "Shell injection",
    "description": "d",
    "status": "INVALIDATED",
    "verified_by": "llm",
    "confidence_score": 0.9,
}


@pytest.mark.parametrize(
    ("recompose", "expected"),
    [
        (_reply(_SELF_JUDGED), [("Shell injection", "UNVERIFIED", None, None)]),
        (_reply(), [("Segment finding", "UNVERIFIED", None, None)]),
    ],
    ids=["self-judged", "empty-recompose"],
)
def test_a_legacy_review_saves_no_status_a_model_wrote_and_keeps_the_segments_findings(
    recompose: str, expected: list[tuple[object, ...]]
) -> None:
    """A model's reply cannot settle its own finding: a status, an adjudicator and a confidence
    it wrote are cleared, as the orchestrator clears them. A recompose that lists no finding
    keeps the segments' findings rather than dropping them (#1150)."""
    segment = _reply({**_SELF_JUDGED, "title": "Segment finding", "location": "src/b.py:1"})
    segments = [_parse_reply(segment), _parse_reply(_reply())]

    result = _execute_final_recompose(
        "Path review",
        {},
        [segment, _reply()],
        segments,
        PERSONAS[Persona.DEVSECOPS],
        ReviewClients(analysis=MagicMock(), compose=_Compose(recompose)),
        "system",
        "",
        2,
    )

    assert not isinstance(result, str)
    assert [
        (f.title, f.status, f.verified_by, f.confidence_score) for f in result.findings
    ] == expected
