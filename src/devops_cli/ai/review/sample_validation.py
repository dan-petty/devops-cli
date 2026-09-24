"""Validation of devops ai tooling across the pinned sample repositories.

devops ai is meant for any technical project, but nothing showed whether its tooling works on
projects that are not Python. For each category of sample (#502), a report records:

- which parser read each file and the symbols it found;
- what file analysis made of each file: its language, symbols and dependencies;
- what the repository map shows of each sample;
- optionally, how a review scored on the category's synthetic defect corpus (#503, #504).

Its problems name what did not work, so each can be followed up as an issue.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from devops_cli.ai.ast.engine import TreeSitterEngine
from devops_cli.ai.review.chunker import find_repo_files
from devops_cli.ai.review.defects import CorpusScore
from devops_cli.ai.review.samples import SampleRepository

TREE_SITTER = "tree-sitter"
NO_AST = "none"
# Python's fallback is the standard library's own parser, as exact as tree-sitter.
_EXACT_FALLBACKS = frozenset({"python"})
# The file types the sample categories are about; licences and ignore files are not expected
# to parse.
_CODE_SUFFIXES = frozenset(
    {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs", ".java", ".cs"}
    | {".c", ".h", ".cc", ".cpp", ".cxx", ".hh", ".hpp", ".hxx", ".tf", ".hcl"}
    | {".sh", ".bash", ".envsh", ".yaml", ".yml", ".tpl", ".md", ".markdown", ".rst", "Dockerfile"}
)
_CPP_SUFFIXES = frozenset({".cc", ".cpp", ".cxx", ".hh", ".hpp", ".hxx"})


class FileResult(BaseModel):
    """What the AST engine and file analysis made of one sample file."""

    path: str
    ast_language: str | None = None
    parser: str = NO_AST
    symbols: int = 0
    analysis_language: str = ""
    analysis_symbols: int = 0
    dependencies: int = 0


class RepoMapResult(BaseModel):
    """What the repository map shows of one sample."""

    sample: str
    files_mapped: int = 0
    symbols: int = 0
    rendered_chars: int = 0


class CorpusReview(BaseModel):
    """A review of the category's synthetic defect corpus, and its score."""

    corpus_dir: str
    injections: int = 0
    session_id: str | None = None
    score: CorpusScore | None = None
    error: str = ""


class CategoryReport(BaseModel):
    """The tooling's results on one category of sample repositories."""

    category: str
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    samples: dict[str, str] = Field(default_factory=dict)
    files: list[FileResult] = Field(default_factory=list)
    parsers: dict[str, int] = Field(default_factory=dict)
    repomaps: list[RepoMapResult] = Field(default_factory=list)
    review: CorpusReview | None = None
    problems: list[str] = Field(default_factory=list)

    def write(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.category}.json"
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return path


def sample_files(sample: SampleRepository, checkout: Path) -> list[Path]:
    """The reviewable files under a sample's paths, as a review of them would read them."""
    files: list[Path] = []
    for rel in sample.paths:
        target = checkout / rel
        if target.exists():
            files.extend(find_repo_files(target, repo_root=checkout))
    return list(dict.fromkeys(files))


def inspect_file(path: Path, checkout: Path, sample: str, engine: TreeSitterEngine) -> FileResult:
    """Parse one file with the AST engine and analyse it as the review's pre-analysis would."""
    from devops_cli.ai.analyze.outlines import analyze_single_file

    rel = path.relative_to(checkout).as_posix()
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return FileResult(path=f"{sample}/{rel}")
    parsed = engine.parse_file(path)
    meta = analyze_single_file(rel, content, len(content.encode()), enhanced=False)
    return FileResult(
        path=f"{sample}/{rel}",
        ast_language=parsed.language if parsed else None,
        parser=parsed.parse_engine if parsed else NO_AST,
        symbols=len(parsed.symbols) if parsed else 0,
        analysis_language=meta.language,
        analysis_symbols=len(meta.key_symbols),
        dependencies=len(meta.dependencies),
    )


def repomap_result(sample: SampleRepository, checkout: Path) -> RepoMapResult:
    """Map the sample's repository as `devops ai repomap --multilingual` would."""
    from devops_cli.ai.repomap import generate_repo_map, render_repo_map_text

    nodes = generate_repo_map(root_dir=checkout, multilingual=True)
    return RepoMapResult(
        sample=sample.name,
        files_mapped=len(nodes),
        symbols=sum(len(node.symbols) for node in nodes),
        rendered_chars=len(render_repo_map_text(nodes)),
    )


def _suffix(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    return f".{name.rsplit('.', 1)[-1].lower()}" if "." in name else name


def _parser_problems(files: Sequence[FileResult]) -> list[str]:
    """Languages the AST engine claims but read with its regex fallback, or found nothing in."""
    problems: list[str] = []
    by_language: dict[str, list[FileResult]] = {}
    for result in files:
        if result.ast_language:
            by_language.setdefault(result.ast_language, []).append(result)
    for language, results in sorted(by_language.items()):
        fallback = sum(r.parser != TREE_SITTER for r in results)
        if fallback and language not in _EXACT_FALLBACKS:
            problems.append(
                f"{language}: {fallback} of {len(results)} files read by the regex fallback, "
                "not tree-sitter"
            )
        if empty := sum(r.symbols == 0 for r in results):
            problems.append(f"{language}: {empty} of {len(results)} files yielded no symbols")
    return problems


def _coverage_problems(files: Sequence[FileResult]) -> list[str]:
    """Code types with no AST support, and code the file analysis cannot name or names wrong."""
    code = [(r, _suffix(r.path)) for r in files if _suffix(r.path) in _CODE_SUFFIXES]
    unsupported = Counter(suffix for r, suffix in code if r.parser == NO_AST)
    plain = Counter(suffix for r, suffix in code if r.analysis_language in ("plaintext", "text"))
    not_cpp = Counter(
        suffix for r, suffix in code if suffix in _CPP_SUFFIXES and r.analysis_language != "cpp"
    )
    return [
        *(f"no AST support for {s} ({_files(n)})" for s, n in sorted(unsupported.items())),
        *(f"file analysis reads {s} as plain text ({_files(n)})" for s, n in sorted(plain.items())),
        *(f"file analysis labels C++ {s} as C ({_files(n)})" for s, n in sorted(not_cpp.items())),
    ]


def _files(count: int) -> str:
    return f"{count} file{'s' if count != 1 else ''}"


def review_problems(review: CorpusReview | None) -> list[str]:
    """What the review of the category's corpus failed to do."""
    if review is None:
        return []
    if review.error:
        return [f"review failed: {review.error}"]
    if not review.injections:
        return ["no defect template applies to these files"]
    score = review.score
    if score is None:
        return ["review produced no scored session"]
    problems = []
    if not score.found:
        problems.append(f"review found none of {score.injections} injected defects")
    elif not score.reported:
        problems.append(f"verification dropped all {score.found} injected defects the review found")
    return problems


def validate_category(
    category: str,
    samples: Sequence[SampleRepository],
    root: Path,
    engine: TreeSitterEngine | None = None,
) -> CategoryReport:
    """Run AST parsing, file analysis and repository maps over a category's fetched samples."""
    engine = engine or TreeSitterEngine()
    report = CategoryReport(category=category)
    for sample in samples:
        checkout = root / sample.name
        report.samples[sample.name] = sample.commit
        report.files.extend(
            inspect_file(path, checkout, sample.name, engine)
            for path in sample_files(sample, checkout)
        )
        report.repomaps.append(repomap_result(sample, checkout))
    report.parsers = dict(Counter(result.parser for result in report.files))
    report.problems = [
        *_parser_problems(report.files),
        *_coverage_problems(report.files),
        *(f"repomap mapped no files of {m.sample}" for m in report.repomaps if not m.files_mapped),
    ]
    return report


__all__ = [
    "CategoryReport",
    "CorpusReview",
    "FileResult",
    "RepoMapResult",
    "inspect_file",
    "repomap_result",
    "review_problems",
    "sample_files",
    "validate_category",
]
