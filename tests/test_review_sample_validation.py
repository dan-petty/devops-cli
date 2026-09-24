"""Validation of devops ai tooling across the pinned sample repositories (#505).

A category's report records the parser that read each file and what it found, the file analysis,
the repository map and, with `--review`, a scored review of the category's defect corpus. Its
problems name what did not work.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.ai.ast.engine import TreeSitterEngine
from devops_cli.ai.review.defects import CORPUS_FILES_DIR, CorpusScore, DefectCorpus
from devops_cli.ai.review.profile import ReviewProfile, report_profile
from devops_cli.ai.review.sample_validation import (
    CorpusReview,
    review_problems,
    validate_category,
)
from devops_cli.ai.review.samples import SampleCatalog, SampleRepository, fetch_sample
from devops_cli.ai.review_schema import ReviewSessionPayload, SavedFinding
from devops_cli.commands import review as review_commands
from devops_cli.main import app

cli = CliRunner(env={"COLUMNS": "250", "NO_COLOR": "1", "TERM": "dumb"})

TAKE = """def take(items, n):
    if n > len(items):
        raise ValueError("too many")
    return items[:n]
"""


class _RegexOnlyEngine(TreeSitterEngine):
    """The AST engine as it runs without tree-sitter installed."""

    def _check_native_tree_sitter(self) -> bool:
        return False


def _sample(root: Path, name: str = "demo", commit: str = "a" * 40) -> SampleRepository:
    return SampleRepository(
        name=name,
        category="python",
        languages=["python"],
        repository=(root / "upstream").as_uri(),
        commit=commit,
        license="MIT",
        license_files=["LICENSE"],
        paths=["pkg"],
    )


def _write(checkout: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        (checkout / rel).parent.mkdir(parents=True, exist_ok=True)
        (checkout / rel).write_text(text, encoding="utf-8")


def test_a_category_report_names_what_the_tooling_could_not_do(tmp_path: Path) -> None:
    """Verify parsers, symbols and the problems: regex fallback, empty files, unsupported types."""
    _write(
        tmp_path / "demo",
        {
            "pkg/main.py": TAKE,
            "pkg/server.go": "package main\n\nfunc Serve() error {\n\treturn nil\n}\n",
            "pkg/empty.ts": "// nothing exported yet\n",
            "pkg/Program.cs": "class Program { static void Main() {} }\n",
            "pkg/format.cc": "int answer() { return 42; }\n",
            "pkg/LICENSE": "MIT License\n",
        },
    )

    report = validate_category("python", [_sample(tmp_path)], tmp_path, _RegexOnlyEngine())

    assert (report.samples, report.parsers) == (
        {"demo": "a" * 40},
        {"fallback-ast": 3, "none": 3},
    )
    assert report.problems == [
        "go: 1 of 1 files read by the regex fallback, not tree-sitter",
        "typescript: 1 of 1 files read by the regex fallback, not tree-sitter",
        "typescript: 1 of 1 files yielded no symbols",
        "no AST support for .cc (1 file)",
        "no AST support for .cs (1 file)",
        "file analysis labels C++ .cc as C (1 file)",
    ]
    assert [(m.sample, m.files_mapped) for m in report.repomaps] == [("demo", 2)]


def _score(found: int, reported: int) -> CorpusScore:
    return CorpusScore(
        session_id="s",
        injections=3,
        found=found,
        found_by_line=found,
        reported=reported,
        in_file=3,
        dropped=found - reported,
        unmatched_findings=0,
    )


@pytest.mark.parametrize(
    ("review", "expected"),
    [
        (None, []),
        (
            CorpusReview(corpus_dir="c", injections=3, error="the review exited with 1"),
            ["review failed: the review exited with 1"],
        ),
        (CorpusReview(corpus_dir="c"), ["no defect template applies to these files"]),
        (CorpusReview(corpus_dir="c", injections=3), ["review produced no scored session"]),
        (
            CorpusReview(corpus_dir="c", injections=3, score=_score(0, 0)),
            ["review found none of 3 injected defects"],
        ),
        (
            CorpusReview(corpus_dir="c", injections=3, score=_score(2, 0)),
            ["verification dropped all 2 injected defects the review found"],
        ),
        (CorpusReview(corpus_dir="c", injections=3, score=_score(2, 1)), []),
    ],
)
def test_review_problems(review: CorpusReview | None, expected: list[str]) -> None:
    """Verify each way a corpus review can fail is named."""
    assert review_problems(review) == expected


@pytest.fixture
def fetched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SampleRepository:
    """One local sample, fetched at its commit into the data directory the commands read."""
    upstream = tmp_path / "upstream"
    _write(upstream, {"LICENSE": "MIT License\n", "pkg/take.py": TAKE})
    git = ["git", "-C", str(upstream), "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run([*git, "init", "--quiet"], check=True)
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "--quiet", "-m", "pinned"], check=True)
    commit = subprocess.run(
        [*git, "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    data = tmp_path / "data"
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(data))
    sample = _sample(tmp_path, commit=commit)
    assert fetch_sample(sample, data / "samples") == []
    monkeypatch.setattr(
        review_commands, "load_sample_catalog", lambda: SampleCatalog(samples=[sample])
    )
    return sample


def _reports(data: Path) -> dict[str, Any]:
    (run,) = (data / "reviews" / "sample-validations").iterdir()
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in run.glob("*.json")}


def test_validate_saves_a_report_per_category(tmp_path: Path, fetched: SampleRepository) -> None:
    """Verify `devops review samples validate` writes each category's JSON report."""
    result = cli.invoke(app, ["review", "samples", "validate"])

    assert result.exit_code == 0, result.output
    report = _reports(tmp_path / "data")["python"]
    assert (report["samples"], [f["path"] for f in report["files"]], report["review"]) == (
        {"demo": fetched.commit},
        ["demo/pkg/take.py"],
        None,
    )


def test_validate_scores_a_review_of_the_category_corpus(
    tmp_path: Path, fetched: SampleRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify --review injects defects into the samples, reviews the corpus and scores it."""
    reviewed: list[Path] = []

    def review_that_finds_the_defect(targets: list[Path], **_: object) -> None:
        files_dir = targets[0]
        reviewed.append(files_dir)
        (injection,) = DefectCorpus.load(files_dir.parent).injections
        finding = SavedFinding(
            severity="HIGH",
            location=f"{files_dir}/{injection.file}:{injection.line}",
            title="Missing bounds check in take",
            description="n is never checked against len(items).",
            persona="devsecops",
        )
        session = tmp_path / "data" / "reviews" / "session-1"
        session.mkdir(parents=True)
        payload = ReviewSessionPayload(findings=[finding]).model_dump_json()
        (session / "findings.json").write_text(payload, encoding="utf-8")
        report_profile(ReviewProfile(session_id="session-1", target=str(files_dir)))

    monkeypatch.setattr(review_commands, "path", review_that_finds_the_defect)

    result = cli.invoke(app, ["review", "samples", "validate", "--review"])

    assert result.exit_code == 0, result.output
    review = _reports(tmp_path / "data")["python"]["review"]
    assert reviewed[0].name == CORPUS_FILES_DIR
    assert (review["injections"], review["session_id"], review["score"]["found"]) == (
        1,
        "session-1",
        1,
    )


def test_a_review_that_exits_is_recorded_as_a_failure(
    tmp_path: Path, fetched: SampleRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a failed review becomes the category's problem instead of aborting the run."""

    def failing_review(**_: object) -> None:
        raise review_commands.typer.Exit(2)

    monkeypatch.setattr(review_commands, "path", failing_review)

    result = cli.invoke(app, ["review", "samples", "validate", "--review"])

    assert result.exit_code == 0, result.output
    report = _reports(tmp_path / "data")["python"]
    assert report["problems"][-1] == "review failed: the review exited with 2"


def test_validate_refuses_samples_that_are_not_fetched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify validation names the samples to fetch first."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))

    result = cli.invoke(app, ["review", "samples", "validate", "cobra"])

    assert (result.exit_code, "devops review samples fetch cobra" in result.output) == (1, True)


def test_categories_can_be_repeated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify --category takes several categories; it used to keep only the last."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))

    result = cli.invoke(app, ["review", "samples", "list", "-c", "go", "-c", "rust"])

    assert result.exit_code == 0, result.output
    assert ("cobra" in result.output, "serde-json" in result.output, "click" in result.output) == (
        True,
        True,
        False,
    )
