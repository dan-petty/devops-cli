"""Review regression harness: real defects survive every layer between a reply and the report.

The golden set (`tests/golden/review_findings.json`) holds findings whose truth does not come
from the review under test: defects injected into the synthetic corpus (#415) and reproductions
written for the #509 audit. Each real defect is driven through the layers that run without a
model:

1. parsing a persona reply that also carries a malformed field;
2. resetting the verification state a persona may have written;
3. consolidating duplicates;
4. the report's own filter.

It must come out reported. A change that makes any layer discard a real finding fails here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.review import ReviewPipelineOrchestrator
from devops_cli.ai.review_schema import (
    FileReviewPayload,
    SavedFinding,
    consolidate_duplicate_findings,
    parse_review_response,
    reset_verification_state,
)

_GOLDEN = json.loads(
    (Path(__file__).parent / "golden" / "review_findings.json").read_text(encoding="utf-8")
)
_DISMISSED = {"INVALIDATED", "MITIGATED"}
# A dependency given as a bare name instead of an object fails the reply's validation.
_MALFORMED_FIELD = {"external_dependencies": ["requests"]}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """The golden source files, in a project that declares Python 3.14."""
    root = tmp_path / "project"
    for rel, source in _GOLDEN["files"].items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
    (root / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.14"\n', "utf-8")
    return root


def _finding(case: dict[str, Any]) -> dict[str, Any]:
    """A persona's finding, with any verification state the persona wrote itself."""
    return (
        {k: case[k] for k in ("location", "severity", "title", "description")}
        | {"fix": "See the description."}
        | case.get("persona_fields", {})
    )


def _through_the_pipeline(findings: list[dict[str, Any]], project: Path) -> list[SavedFinding]:
    """Drive persona findings through every deterministic layer to the report."""
    reply = json.dumps({"findings": findings} | _MALFORMED_FIELD)
    parsed = parse_review_response(reply)
    assert parsed is not None, "the reply lost every finding to one malformed field"
    saved = [
        SavedFinding(**reset_verification_state(f).model_dump(), persona="devsecops")
        for f in parsed.findings
    ]
    checked = consolidate_duplicate_findings(saved)
    orchestrator = ReviewPipelineOrchestrator(session_id="harness", target_dir=project)
    payloads = [
        FileReviewPayload(file_path=f.location.split(":")[0], findings=[f]) for f in checked
    ]
    return orchestrator._collect_and_deduplicate_findings(payloads)


@pytest.mark.parametrize("case", _GOLDEN["real_defects"], ids=lambda c: c["id"])
def test_a_real_defect_reaches_the_report(case: dict[str, Any], project: Path) -> None:
    """Verify a real defect survives parsing, consolidation and the report."""
    reported = _through_the_pipeline([_finding(case)], project)

    assert [(f.title, f.status in _DISMISSED) for f in reported] == [(case["title"], False)]


@pytest.mark.parametrize("group", _GOLDEN["distinct_groups"], ids=lambda g: g["id"])
def test_distinct_real_defects_stay_distinct(group: dict[str, Any], project: Path) -> None:
    """Verify different defects in one file are not merged on the way to the report."""
    reported = _through_the_pipeline([_finding(f) for f in group["findings"]], project)

    assert len(reported) == len(group["findings"])
