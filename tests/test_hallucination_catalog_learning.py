"""The hallucinations catalog learns only from evidence and never rewrites its builtin entries (#514)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.ai.review.common_hallucinations import (
    CommonHallucinationEntry,
    HallucinationCategory,
    _build_builtin_hallucinations,
    auto_record_invalidated_finding,
    catalog_learning_disabled,
    get_common_hallucinations_file_path,
    load_common_hallucinations,
    render_negative_exemplars,
    verify_ground_truth_hallucination,
)
from devops_cli.ai.review.verification import _apply_single_finding_verification
from devops_cli.ai.review_schema import Finding
from devops_cli.main import app

cli = CliRunner(env={"COLUMNS": "250", "NO_COLOR": "1", "TERM": "dumb"})


def _finding(title: str, description: str = "d", location: str = "app.py:3") -> Finding:
    return Finding(severity="HIGH", location=location, title=title, description=description)


def _learned(entry_id: str = "HALLUCINATION-AUTO-00000001") -> CommonHallucinationEntry:
    return CommonHallucinationEntry(
        id=entry_id,
        name="Auto-learned: Directory created world-writable",
        category=HallucinationCategory.GENERAL,
        description="The `append_entry` function creates the directory with mode `0o777`.",
        pattern_keywords=["append_entry", "directory"],
        resolution="Invalidated during review verification",
        source="auto_learned",
    )


def _write(path: Path, entries: list[CommonHallucinationEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([e.model_dump(mode="json") for e in entries]), encoding="utf-8")


def test_a_model_invalidation_does_not_teach_the_catalog() -> None:
    """Verify an LLM verdict invalidates the finding but records nothing."""
    ledger = get_common_hallucinations_file_path()
    finding = _finding("Directory created world-writable", "mkdir(mode=0o777) in append_entry")

    result = _apply_single_finding_verification(
        finding, {"verified": False, "invalidated_criteria_matched": ["Mode is intended"]}, "t"
    )

    assert (result.status, ledger.exists()) == ("INVALIDATED", False)


def test_no_learning_inside_a_disabled_block() -> None:
    """Verify an evaluation replay records nothing, while ordinary invalidations still teach."""
    finding = _finding("Quirky framework obsolete artifact warning", "The frobnicator is stale.")
    with catalog_learning_disabled():
        replayed = auto_record_invalidated_finding(finding, reason="Replayed verdict")
    learned = auto_record_invalidated_finding(finding, reason="Parser accepted the file")

    assert (replayed, learned is not None and learned.source) == (None, "auto_learned")


def test_a_persisted_copy_of_a_builtin_entry_is_ignored() -> None:
    """Verify a learned copy cannot shadow the shipped entry or its later fixes."""
    builtin = _build_builtin_hallucinations()[0]
    polluted = builtin.model_copy(
        update={"pattern_keywords": ["missing", "validation"], "occurrence_count": 225}
    )
    _write(get_common_hallucinations_file_path(), [polluted, _learned()])

    loaded = {e.id: e for e in load_common_hallucinations()}

    assert (loaded[builtin.id] == builtin, "HALLUCINATION-AUTO-00000001" in loaded) == (True, True)


def _entry(
    category: HallucinationCategory, entry_id: str = "HALLUCINATION-TEST"
) -> CommonHallucinationEntry:
    return CommonHallucinationEntry(
        id=entry_id, name="n", category=category, description="d", resolution="r"
    )


@pytest.mark.parametrize(
    ("category", "source", "location", "title", "description", "expected"),
    [
        pytest.param(
            HallucinationCategory.SYNTAX_GRAMMAR,
            "x = 1\n",
            "a.py:1",
            "Syntax error: invalid Python 2 syntax",
            "except A, B:",
            True,
            id="syntax-claim",
        ),
        pytest.param(
            HallucinationCategory.SYNTAX_GRAMMAR,
            "x = eval(input())\n",
            "a.py:1",
            "getattr RCE via resource name",
            "Arbitrary code runs.",
            False,
            id="not-a-syntax-claim",
        ),
        pytest.param(
            HallucinationCategory.BOUNDARY_ERRORS,
            "data = Path(p).read_text()\n",
            "a.py:1",
            "CWE-400 unbounded read_text of a user-uploaded file",
            "handle_upload reads it whole.",
            False,
            id="untrusted-input",
        ),
        pytest.param(
            HallucinationCategory.MUTABLE_DEFAULTS,
            "from pydantic import Field\nx: list = Field(default_factory=list)\n\n\n\n\ndef merge(items=[]):\n    return items\n",
            "a.py:7",
            "Mutable default argument in merge",
            "items=[] is shared.",
            False,
            id="default-factory-elsewhere",
        ),
    ],
)
def test_ground_truth_checks_the_claim(
    tmp_path: Path,
    category: HallucinationCategory,
    source: str,
    location: str,
    title: str,
    description: str,
    expected: bool,
) -> None:
    """Verify a catalog match invalidates only when the file refutes that specific claim."""
    target = tmp_path / "a.py"
    target.write_text(source, encoding="utf-8")

    result = verify_ground_truth_hallucination(
        _finding(title, description, location), _entry(category), target
    )

    assert result is expected


def test_learned_entries_are_not_shown_to_reviewers() -> None:
    """Verify the prompt block lists curated builtin entries only."""
    _write(get_common_hallucinations_file_path(), [_learned()])

    block = render_negative_exemplars()

    assert ("append_entry" in block, bool(block)) == (False, True)


def test_learned_entries_can_be_listed_and_removed() -> None:
    """Verify a learned entry shows in the catalog listing and can be removed; builtins cannot."""
    _write(
        get_common_hallucinations_file_path(), [_learned(), _learned("HALLUCINATION-AUTO-00000002")]
    )
    builtin_id = _build_builtin_hallucinations()[0].id

    listed = cli.invoke(app, ["review", "hallucinations", "list", "--learned", "--json"])
    refused = cli.invoke(app, ["review", "hallucinations", "remove", builtin_id])
    removed = cli.invoke(app, ["review", "hallucinations", "remove", "HALLUCINATION-AUTO-00000001"])
    left = [e.id for e in load_common_hallucinations(include_builtin=False)]

    assert (
        sorted(e["id"] for e in json.loads(listed.output)),
        refused.exit_code,
        removed.exit_code,
        left,
    ) == (
        ["HALLUCINATION-AUTO-00000001", "HALLUCINATION-AUTO-00000002"],
        1,
        0,
        ["HALLUCINATION-AUTO-00000002"],
    )


@pytest.mark.parametrize(
    ("source", "location", "title", "description"),
    [
        pytest.param(
            "def handle_upload(path):\n    return Path(path).read_text()\n",
            "upload.py:2",
            "CWE-400: unbounded read_text() of user-uploaded file",
            "handle_upload reads an attacker-supplied file with no size cap, exhausting memory.",
            id="cwe400-upload",
        ),
        pytest.param(
            "def build(items):\n    for item in items:\n        system_prompt = item\n    return system_prompt\n",
            "prompt.py:4",
            "`system_prompt` may be unbound (UnboundLocalError) when the list is empty",
            "If items is empty the loop never assigns system_prompt.",
            id="unbound-local",
        ),
        pytest.param(
            "def retry():\n    return timeout * 2\n",
            "retry.py:2",
            "NameError: undefined variable `timeout` in retry handler",
            "timeout is referenced before any assignment in retry.",
            id="real-nameerror",
        ),
        pytest.param(
            "def load(name):\n    return getattr(module, name)()\n",
            "loader.py:2",
            "getattr on a user-controlled resource name enables code execution",
            "The resource name comes from the request and selects any attribute to call.",
            id="getattr-resource",
        ),
    ],
)
def test_real_defects_pass_the_builtin_catalog(
    tmp_path: Path, source: str, location: str, title: str, description: str
) -> None:
    """Verify the shipped catalog invalidates none of these real defects."""
    from devops_cli.ai.review.verification import _check_catalog_hallucination

    target = tmp_path / location.split(":")[0]
    target.write_text(source, encoding="utf-8")
    finding = _finding(title, description, location)

    assert _check_catalog_hallucination(finding, target).status == "UNVERIFIED"
