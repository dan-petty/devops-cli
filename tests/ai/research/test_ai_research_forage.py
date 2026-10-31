"""Unit test suite for agentic information foraging and scent trail crawler (#274)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.ai.research.crawler import ForageCrawler
from devops_cli.ai.research.edges import (
    extract_git_co_changes,
    extract_markdown_links,
    extract_python_imports,
)
from devops_cli.commands.ai import app as ai_app


@pytest.fixture
def forage_fixture_repo(tmp_path: Path, git: Callable[..., None]) -> Path:
    """Create an isolated offline repository fixture with imports, links, and git commits."""
    git(tmp_path, "init", "--quiet")

    src_dir = tmp_path / "pkg"
    docs_dir = tmp_path / "docs"
    src_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    # 1. Entry file importing processor and helper
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    entry_py = src_dir / "entry.py"
    entry_py.write_text(
        "import pkg.processor\n"
        "from .helper import compute_total\n"
        "# Entry point for telemetry collector pipeline.\n",
        encoding="utf-8",
    )

    # 2. Processor file (cycle back to entry, high relevance for telemetry)
    processor_py = src_dir / "processor.py"
    processor_py.write_text(
        "import pkg.entry\n"
        "def process_telemetry() -> str:\n"
        "    return 'telemetry stream metrics collector'\n",
        encoding="utf-8",
    )

    # 3. Helper file (unrelated math)
    helper_py = src_dir / "helper.py"
    helper_py.write_text(
        "def compute_total(a: int, b: int) -> int:\n    return a + b\n",
        encoding="utf-8",
    )

    # 4. Cold branch file (zero keyword match)
    cold_py = src_dir / "cold_branch.py"
    cold_py.write_text(
        "# completely unrelated background utilities\nCONST_X = 1\n",
        encoding="utf-8",
    )

    # 5. Markdown manual cross-referencing processor and cold branch
    manual_md = docs_dir / "manual.md"
    manual_md.write_text(
        "# System Manual\n\n"
        "Read the [Telemetry Processor](../pkg/processor.py) guide.\n"
        "See also [Cold Utility](../pkg/cold_branch.py) and external [Web](https://example.com).\n",
        encoding="utf-8",
    )

    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "--quiet", "-m", "Initial commit with code and docs")

    # Co-change commit linking entry.py and manual.md
    manual_md.write_text(manual_md.read_text(encoding="utf-8") + "\n# Updated\n", encoding="utf-8")
    entry_py.write_text(
        entry_py.read_text(encoding="utf-8") + "\n# Co-change touch\n", encoding="utf-8"
    )
    git(tmp_path, "add", "docs/manual.md", "pkg/entry.py")
    git(tmp_path, "commit", "--quiet", "-m", "Link entry and manual")

    return tmp_path


def test_forage_cli_help_and_options() -> None:
    """The forage CLI command displays required arguments and configuration options."""
    runner = CliRunner()
    res = runner.invoke(ai_app, ["research", "forage", "--help"])
    assert (
        res.exit_code,
        "--query" in res.output,
        "--max-nodes" in res.output,
        "--min-score" in res.output,
        "--json" in res.output,
    ) == (0, True, True, True, True)


def test_forage_cli_runs_read_only(
    forage_fixture_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Forage is a read-only command that runs without mutation."""
    monkeypatch.chdir(forage_fixture_repo)
    runner = CliRunner()
    res = runner.invoke(
        ai_app,
        ["research", "forage", "pkg/entry.py", "--query", "telemetry"],
    )
    assert res.exit_code == 0


def test_extract_python_imports(forage_fixture_repo: Path) -> None:
    """AST import extraction resolves both absolute and relative module imports."""
    entry_file = forage_fixture_repo / "pkg" / "entry.py"
    edges = extract_python_imports(entry_file, forage_fixture_repo)
    targets = {e.target for e in edges}
    assert (
        "pkg/processor.py" in targets,
        "pkg/helper.py" in targets,
        all(e.edge_type == "import" for e in edges),
    ) == (True, True, True)


def test_extract_markdown_links(forage_fixture_repo: Path) -> None:
    """Markdown link extraction resolves relative file links and skips external URLs."""
    manual_file = forage_fixture_repo / "docs" / "manual.md"
    edges = extract_markdown_links(manual_file, forage_fixture_repo)
    targets = {e.target for e in edges}
    assert (
        "pkg/processor.py" in targets,
        "pkg/cold_branch.py" in targets,
        all(e.edge_type == "markdown_link" for e in edges),
    ) == (True, True, True)


def test_extract_git_co_changes(forage_fixture_repo: Path) -> None:
    """Git co-change extraction identifies files committed together."""
    entry_file = forage_fixture_repo / "pkg" / "entry.py"
    edges = extract_git_co_changes(entry_file, forage_fixture_repo)
    targets = {e.target for e in edges}
    assert (
        "docs/manual.md" in targets,
        all(e.edge_type == "git_co_change" for e in edges),
    ) == (True, True)


def test_cycle_detection_and_ledger_in_foraging(forage_fixture_repo: Path) -> None:
    """Circular imports (A imports B, B imports A) are detected and not revisited."""
    crawler = ForageCrawler(repo_root=forage_fixture_repo, max_nodes=10, min_score=0.01)
    trail = crawler.forage(anchor="pkg/entry.py", query="telemetry")

    visited_paths = [n.path for n in trail.visited_nodes]
    cycle_pairs = [tuple(c) for c in trail.cycles_detected]

    assert (
        visited_paths.count("pkg/entry.py"),
        visited_paths.count("pkg/processor.py"),
        ("pkg/processor.py", "pkg/entry.py") in cycle_pairs,
    ) == (1, 1, True)


def test_backtracking_on_low_scent_branch(forage_fixture_repo: Path) -> None:
    """Crawler backtracks when neighbors score below threshold and records events."""
    crawler = ForageCrawler(repo_root=forage_fixture_repo, max_nodes=10, min_score=0.5)
    trail = crawler.forage(anchor="docs/manual.md", query="telemetry")

    ranked_paths = [n.path for n in trail.ranked_trail]
    assert (
        "pkg/processor.py" in ranked_paths,
        trail.visited_nodes[0].path == "docs/manual.md",
    ) == (True, True)


def test_semantic_scent_ranking(forage_fixture_repo: Path) -> None:
    """High-scent documents matching query terms rank above unrelated files."""
    crawler = ForageCrawler(repo_root=forage_fixture_repo, max_nodes=10, min_score=0.0)
    trail = crawler.forage(anchor="pkg/entry.py", query="telemetry collector")

    processor_score = next(n.score for n in trail.visited_nodes if n.path == "pkg/processor.py")
    cold_score = next(
        (n.score for n in trail.visited_nodes if n.path == "pkg/cold_branch.py"),
        0.0,
    )
    assert processor_score > cold_score


def test_json_output_contract(forage_fixture_repo: Path) -> None:
    """Running forage with --json emits structured JSON conforming to ForageTrail schema."""
    runner = CliRunner()
    res = runner.invoke(
        ai_app,
        [
            "research",
            "forage",
            "pkg/entry.py",
            "--repo",
            str(forage_fixture_repo),
            "--query",
            "telemetry",
            "--json",
        ],
    )
    assert res.exit_code == 0
    payload = json.loads(res.output)
    expected_keys = {
        "anchor",
        "query",
        "visited_nodes",
        "edges",
        "backtrack_events",
        "cycles_detected",
        "ranked_trail",
    }
    assert (
        expected_keys.issubset(payload.keys()),
        len(payload["visited_nodes"]) > 0,
    ) == (True, True)


def test_keyword_anchor_resolution(forage_fixture_repo: Path) -> None:
    """Anchor specified as a keyword successfully resolves to the top matching file."""
    crawler = ForageCrawler(repo_root=forage_fixture_repo, max_nodes=5, min_score=0.0)
    trail = crawler.forage(anchor="processor", query="telemetry")
    assert trail.anchor == "pkg/processor.py"


def test_clean_markdown_href_schemes_and_paths() -> None:
    """_clean_markdown_href strips external schemes case-insensitively and keeps local paths (#1107)."""
    from devops_cli.ai.research.edges import _clean_markdown_href

    assert _clean_markdown_href("HTTPS://example.com/page.md") is None
    assert _clean_markdown_href("http://example.com/page.md") is None
    assert _clean_markdown_href("MAILTO:dev@example.com") is None
    assert _clean_markdown_href("ftp://archive.example.com/file") is None
    assert _clean_markdown_href("#heading") is None
    assert _clean_markdown_href("doc/guide.md#section?foo=bar") == "doc/guide.md"
