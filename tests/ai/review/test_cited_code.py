"""A saved review records the code each finding's location cites, as evidence (#950, #1150)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from devops_cli.ai.review.cited_code import record_cited_code
from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review_schema import CitedCode, FileReviewPayload, SavedFinding
from devops_cli.config.defaults import DEFAULT_CITED_EXCERPT_MAX_LINES

_RUNNER = """import textwrap


def run_snippet(source, namespace):
    code = compile(textwrap.dedent(source), "doc", "exec")
    exec(code, {"__name__": "count"})
    return namespace
"""
_EXEC_LINE = '    exec(code, {"__name__": "count"})'


def _checkout(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text("[project]\nname = 'target'\n", encoding="utf-8")
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    return root


def _finding(location: str, title: str = "`exec` runs a compiled snippet") -> SavedFinding:
    return SavedFinding(severity="MEDIUM", location=location, title=title, description="d")


def test_a_finding_records_the_lines_its_location_cites_inside_the_checkout(
    tmp_path: Path,
) -> None:
    """A relative or absolute location records the project, file, line and the lines it cites,
    at most DEFAULT_CITED_EXCERPT_MAX_LINES of them, with a secret masked. A line the file does
    not hold, a location with no line, a file outside the checkout and a finding about a secret
    record none."""
    tree = _checkout(
        tmp_path / "repo",
        {
            "runner.py": _RUNNER,
            "long.py": "x = 1\n" * 100,
            "cfg.py": "client_secret=123456789012345678901234567890\n",
        },
    )
    outside = tmp_path / "elsewhere.py"
    outside.write_text("private = 1\n", encoding="utf-8")
    findings = [
        _finding("runner.py:5-6"),
        _finding(f"{tree / 'runner.py'}:6"),
        _finding("runner.py:90"),
        _finding("long.py:1-100"),
        _finding("k8s/deployment.yaml:Deployment/cloudflared"),
        _finding(f"{outside}:1"),
        _finding("cfg.py:1", title="Client configured"),
        _finding("cfg.py:1", title="Hardcoded password in the client"),
    ]

    record_cited_code(findings, lambda path: tree / path, tree)

    assert (findings[-1].category, [f.cited_code for f in findings]) == (
        "secret_exposure",
        [
            CitedCode(
                project="repo",
                file="runner.py",
                line=5,
                excerpt=f'    code = compile(textwrap.dedent(source), "doc", "exec")\n{_EXEC_LINE}',
            ),
            CitedCode(project="repo", file="runner.py", line=6, excerpt=_EXEC_LINE),
            None,
            CitedCode(
                project="repo",
                file="long.py",
                line=1,
                excerpt="\n".join(["x = 1"] * DEFAULT_CITED_EXCERPT_MAX_LINES),
            ),
            None,
            None,
            CitedCode(
                project="repo",
                file="cfg.py",
                line=1,
                excerpt="client_secret=<masked-client-secret>",
            ),
            None,
        ],
    )


def test_a_saved_session_carries_the_cited_code_of_its_findings_and_candidates(
    tmp_path: Path,
) -> None:
    """The orchestrator records the cited code when it writes findings.json and candidates.json,
    so `review score` and `review export-feedback` read it from new sessions."""
    tree = _checkout(tmp_path / "repo", {"runner.py": _RUNNER})
    session = tmp_path / "reviews" / "s1150-cited"
    orchestrator = ReviewPipelineOrchestrator(
        session_id="s1150-cited",
        llm_client=MagicMock(),
        target_dir=tree,
        session_dir=session,
    )

    with patch("devops_cli.ai.review.pipeline.print_table"):
        orchestrator.generate_consolidated_report(
            [FileReviewPayload(file_path="runner.py", findings=[_finding("runner.py:6")])],
            personas=["devsecops"],
        )

    expected = {"project": "repo", "file": "runner.py", "line": 6, "excerpt": _EXEC_LINE}
    assert [
        [
            f["cited_code"]
            for f in json.loads((session / name).read_text(encoding="utf-8"))["findings"]
        ]
        for name in ("findings.json", "candidates.json")
    ] == [[expected], [expected]]
