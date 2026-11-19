"""The offline scorer of the gold set: hit rate at k=5 and the stale share (#3902).

Each test imports the scorer inside its own body, so the module runs on a checkout that holds no
scorer: a test then fails at its own call rather than the whole module failing to collect. Both
tests read Qdrant and the embedding model through the `qdrant` and `embedder` fakes, so no network
call runs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from devops_cli.ai.kb import get_knowledge_base_dir
from tests.support.paths import FIXTURES, REPO_ROOT

GOLD_SET = FIXTURES / "kb_gold_set" / "gold_set.json"

# The text that the gold set expects, and the exact text of the question that asks for it: the fake
# embedder gives both the same vector, so the document that holds it ranks first.
ANSWER = "The sample tool is pinned to 2.0.0 for every job."
# Documents that fill the ranked list past k, so a hit needs the ranking of the retriever.
FILLERS = (
    "The gateway retries a failed request.",
    "The cluster runs one replica of the service.",
    "The pipeline builds the image once.",
    "The dashboard shows the error budget.",
)


def _entry(
    entry_id: str, question: str, source: str, answer: str, fact_type: str
) -> dict[str, str]:
    """One entry of a gold set file, with the fields that the scorer reads."""
    return {
        "id": entry_id,
        "question": question,
        "expected_source": source,
        "expected_answer": answer,
        "fact_type": fact_type,
        "reference": "https://example.com/sample",
    }


def _write_gold_set(path: Path, entries: list[dict[str, str]]) -> Path:
    """Write `entries` as the gold set file at `path` and return it."""
    path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return path


def _cells(block: str, source: str) -> list[str]:
    """The cells of the score block row of `source`."""
    for line in block.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and cells[0] == source:
            return cells
    return []


def test_scorer_counts_one_hit_and_one_miss(tmp_path: Path, qdrant: Any, embedder: Any) -> None:
    """One of two entries is in the top five of its question, so the hit rate is 0.5, and the entry
    whose source the folder does not hold is stale, so the stale share is 0.5."""
    from devops_cli.ai.benchmark.gold_set import load_gold_set, mark_stale_entries
    from devops_cli.ai.benchmark.gold_set_scorer import GoldSetDocument, score_gold_set

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "sample.md").write_text(f"# Sample\n\n{ANSWER}\n", encoding="utf-8")
    (docs / "other.md").write_text(
        "# Other\n\nNothing here answers the question.\n", encoding="utf-8"
    )
    gold_set = load_gold_set(
        _write_gold_set(
            tmp_path / "gold_set.json",
            [
                _entry("sample-tool", ANSWER, "docs/sample.md", ANSWER, "tool"),
                _entry(
                    "missing-tool",
                    "Which tool does the corpus not hold?",
                    "docs/missing.md",
                    "The missing tool is pinned to 9.9.9.",
                    "tool",
                ),
            ],
        )
    )
    marked = mark_stale_entries(
        gold_set,
        repo_root=tmp_path,
        kb_dir=tmp_path / "kb",
        tool_versions={},
    )
    documents = [
        GoldSetDocument(path="docs/sample.md", text=ANSWER),
        *(
            GoldSetDocument(path=f"docs/filler-{index}.md", text=text)
            for index, text in enumerate(FILLERS)
        ),
        GoldSetDocument(path="docs/other.md", text="Nothing here answers the question."),
    ]

    score = score_gold_set(
        marked,
        documents,
        source="knowledge_base",
        qdrant=qdrant,
        embedder=embedder,
        collection="gold_set_hits",
    )

    assert (score.hits, score.entries) == (1, 2)
    assert score.hit_rate_at_5 == 0.5
    assert (score.stale, score.stale_share) == (1, 0.5)


def test_a_source_with_no_document_scores_zero(tmp_path: Path, qdrant: Any, embedder: Any) -> None:
    """A source that holds no document hits no entry, and it reports no error and no share over
    zero entries."""
    from devops_cli.ai.benchmark.gold_set import load_gold_set, mark_stale_entries
    from devops_cli.ai.benchmark.gold_set_scorer import score_gold_set

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "sample.md").write_text(f"# Sample\n\n{ANSWER}\n", encoding="utf-8")
    gold_set = load_gold_set(
        _write_gold_set(
            tmp_path / "gold_set.json",
            [
                _entry("sample-tool", ANSWER, "docs/sample.md", ANSWER, "tool"),
                _entry(
                    "missing-tool",
                    "Which tool does the corpus not hold?",
                    "docs/missing.md",
                    "The missing tool is pinned to 9.9.9.",
                    "tool",
                ),
            ],
        )
    )
    marked = mark_stale_entries(
        gold_set,
        repo_root=tmp_path,
        kb_dir=tmp_path / "kb",
        tool_versions={},
    )

    score = score_gold_set(
        marked,
        [],
        source="knowledge_base",
        qdrant=qdrant,
        embedder=embedder,
        collection="gold_set_empty",
    )

    assert (score.hits, score.entries) == (0, 2)
    assert score.hit_rate_at_5 == 0.0
    assert (score.stale, score.stale_share) == (1, 0.5)


def test_knowledge_base_source_skips_an_empty_page_outside_the_root(tmp_path: Path) -> None:
    """A page that holds no text becomes no document, and a folder that is not below the repository
    root keeps the path of its own folder, which no checked-in entry names."""
    from devops_cli.ai.benchmark.gold_set_scorer import knowledge_base_source

    kb_dir = tmp_path / "kb"
    tools_dir = kb_dir / "it_domains" / "tools"
    tools_dir.mkdir(parents=True)
    article = tools_dir / "ruff.md"
    article.write_text("# Ruff\n\nRuff is pinned to 0.1.0.\n", encoding="utf-8")
    (tools_dir / "empty.md").write_text("  \n", encoding="utf-8")

    documents = knowledge_base_source(kb_dir, repo_root=tmp_path / "repo")

    assert [document.path for document in documents] == [article.as_posix()]


def test_score_block_holds_both_rows(tmp_path: Path, qdrant: Any, embedder: Any) -> None:
    """Both built-in sources produce a row with a hit rate at k=5 and a stale share."""
    from devops_cli.ai.benchmark.gold_set import load_gold_set, mark_stale_entries
    from devops_cli.ai.benchmark.gold_set_scorer import (
        format_score_block,
        knowledge_base_source,
        project_digest_source,
        score_gold_set,
    )

    gold_set = mark_stale_entries(
        load_gold_set(GOLD_SET),
        repo_root=REPO_ROOT,
        kb_dir=tmp_path / "kb",
        tool_versions={},
    )

    block = format_score_block(
        [
            score_gold_set(
                gold_set,
                knowledge_base_source(get_knowledge_base_dir(), repo_root=REPO_ROOT),
                source="knowledge_base",
                qdrant=qdrant,
                embedder=embedder,
                collection="gold_set_knowledge_base",
            ),
            score_gold_set(
                gold_set,
                project_digest_source(REPO_ROOT),
                source="project_digest",
                qdrant=qdrant,
                embedder=embedder,
                collection="gold_set_project_digest",
            ),
        ]
    )

    header = block.splitlines()[0].lower()
    assert "hit rate at k=5" in header
    assert "stale share" in header
    for source in ("knowledge_base", "project_digest"):
        cells = _cells(block, source)
        assert cells, f"the score block holds no {source} row"
        assert 0.0 <= float(cells[1]) <= 1.0
        assert 0.0 <= float(cells[2]) <= 1.0
