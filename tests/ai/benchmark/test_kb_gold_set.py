"""The gold set of knowledge base facts and the marking of its stale entries (#3902).

Each test imports the loader and the marker inside its own body, so the module runs on a checkout
that holds neither: a test then fails at its own call rather than the whole module failing to
collect.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devops_cli.exceptions import ValidationError
from tests.support.paths import FIXTURES, REPO_ROOT

GOLD_SET = FIXTURES / "kb_gold_set" / "gold_set.json"
FACT_TYPES = ("tool", "library", "project")
STALE_ENTRY_ID = "stale-bandit-version"
BANDIT_ARTICLE = "src/devops_cli/ai/knowledge_base/it_domains/tools/bandit.md"


def _raw_entry(**overrides: str) -> dict[str, str]:
    """A valid entry of the gold set, with the fields of `overrides` replaced."""
    entry = {
        "id": "sample-entry",
        "question": "Which version of the sample tool is pinned?",
        "expected_source": "ARCHITECTURE.md",
        "expected_answer": "## 1. High-Level System Architecture",
        "fact_type": "tool",
        "reference": "https://example.com/sample-tool",
    }
    entry.update(overrides)
    return entry


def _write_gold_set(path: Path, entries: list[dict[str, str]]) -> Path:
    """Write `entries` as the gold set file at `path` and return it."""
    path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return path


def test_every_entry_is_loaded() -> None:
    """The loader returns each entry of the checked-in gold set with its four fields."""
    from devops_cli.ai.benchmark.gold_set import load_gold_set

    gold_set = load_gold_set(GOLD_SET)

    checked_in = json.loads(GOLD_SET.read_text(encoding="utf-8"))
    assert len(gold_set.entries) == len(checked_in)
    for entry in gold_set.entries:
        assert entry.id
        assert entry.question.endswith("?")
        assert entry.expected_source
        assert entry.expected_answer
        assert entry.fact_type in FACT_TYPES
        assert entry.reference.startswith("https://example.com/")
        assert entry.stale is False
        assert entry.stale_reason is None
    assert len({entry.id for entry in gold_set.entries}) == len(gold_set.entries)


def test_all_three_fact_types_are_present() -> None:
    """The checked-in gold set holds at least one entry of each fact type."""
    from devops_cli.ai.benchmark.gold_set import load_gold_set

    gold_set = load_gold_set(GOLD_SET)

    assert {entry.fact_type for entry in gold_set.entries} == set(FACT_TYPES)


def test_incomplete_entry_is_rejected(tmp_path: Path) -> None:
    """An entry that omits its expected source is refused, and the error names it and the field."""
    from devops_cli.ai.benchmark.gold_set import load_gold_set

    path = _write_gold_set(
        tmp_path / "gold_set.json",
        [_raw_entry(id="no-source", expected_source="")],
    )

    with pytest.raises(ValidationError, match=r"no-source.*expected_source"):
        load_gold_set(path)


def test_entry_with_an_unknown_fact_type_is_rejected(tmp_path: Path) -> None:
    """An entry whose fact type is not tool, library or project is refused."""
    from devops_cli.ai.benchmark.gold_set import load_gold_set

    path = _write_gold_set(
        tmp_path / "gold_set.json",
        [_raw_entry(id="bad-type", fact_type="opinion")],
    )

    with pytest.raises(ValidationError, match=r"bad-type.*fact_type"):
        load_gold_set(path)


def test_stale_entry_against_the_checked_in_folder_is_marked(tmp_path: Path) -> None:
    """The entry whose answer the checked-in article no longer holds is stale, and its reason names
    the article."""
    from devops_cli.ai.benchmark.gold_set import load_gold_set, mark_stale_entries

    marked = mark_stale_entries(
        load_gold_set(GOLD_SET),
        repo_root=REPO_ROOT,
        kb_dir=tmp_path / "kb",
        tool_versions={},
    )

    stale = [entry for entry in marked.entries if entry.stale]
    assert [entry.id for entry in stale] == [STALE_ENTRY_ID]
    assert BANDIT_ARTICLE in (stale[0].stale_reason or "")


def test_absent_expected_source_is_marked_stale(tmp_path: Path) -> None:
    """An entry whose expected source is absent is stale, and its reason names the absent path."""
    from devops_cli.ai.benchmark.gold_set import load_gold_set, mark_stale_entries

    gold_set = load_gold_set(
        _write_gold_set(
            tmp_path / "gold_set.json",
            [_raw_entry(expected_source="docs/absent-page.md")],
        )
    )

    marked = mark_stale_entries(
        gold_set,
        repo_root=tmp_path,
        kb_dir=tmp_path / "kb",
        tool_versions={},
    )

    assert marked.entries[0].stale is True
    assert "docs/absent-page.md" in (marked.entries[0].stale_reason or "")


def test_expected_answer_that_the_source_lost_is_marked_stale(tmp_path: Path) -> None:
    """An entry whose expected answer is gone from a present source is stale, and its reason names
    the source path."""
    from devops_cli.ai.benchmark.gold_set import load_gold_set, mark_stale_entries

    page = tmp_path / "docs" / "page.md"
    page.parent.mkdir(parents=True)
    page.write_text("# Page\n\nThe tool is pinned to 2.0.0.\n", encoding="utf-8")
    gold_set = load_gold_set(
        _write_gold_set(
            tmp_path / "gold_set.json",
            [_raw_entry(expected_source="docs/page.md")],
        )
    )

    marked = mark_stale_entries(
        gold_set,
        repo_root=tmp_path,
        kb_dir=tmp_path / "kb",
        tool_versions={},
    )

    assert marked.entries[0].stale is True
    assert "docs/page.md" in (marked.entries[0].stale_reason or "")


def test_a_source_that_holds_the_answer_is_not_stale(tmp_path: Path) -> None:
    """An entry whose source holds the expected answer is not stale."""
    from devops_cli.ai.benchmark.gold_set import load_gold_set, mark_stale_entries

    page = tmp_path / "docs" / "page.md"
    page.parent.mkdir(parents=True)
    page.write_text("# Page\n\nThe tool is pinned to 2.0.0.\n", encoding="utf-8")
    gold_set = load_gold_set(
        _write_gold_set(
            tmp_path / "gold_set.json",
            [
                _raw_entry(
                    expected_source="docs/page.md",
                    expected_answer="The tool is pinned to 2.0.0.",
                )
            ],
        )
    )

    marked = mark_stale_entries(
        gold_set,
        repo_root=tmp_path,
        kb_dir=tmp_path / "kb",
        tool_versions={},
    )

    assert marked.entries[0].stale is False
    assert marked.entries[0].stale_reason is None


def test_mismatched_version_marks_an_entry_stale(tmp_path: Path) -> None:
    """A knowledge base article whose front matter names another version is stale, with the drift
    reason of that article."""
    from devops_cli.ai.benchmark.gold_set import load_gold_set, mark_stale_entries

    kb_dir = tmp_path / "kb"
    tools_dir = kb_dir / "it_domains" / "tools"
    tools_dir.mkdir(parents=True)
    (tools_dir / "ruff.md").write_text(
        "---\n"
        "applies_to:\n"
        '  - "tool:ruff@0.1.0"\n'
        "sources:\n"
        '  - "https://example.com/ruff"\n'
        'reviewed: "2026-01-01"\n'
        "---\n"
        "\n"
        "# Ruff\n"
        "\n"
        "Ruff is pinned to 0.1.0.\n",
        encoding="utf-8",
    )
    gold_set = load_gold_set(
        _write_gold_set(
            tmp_path / "gold_set.json",
            [
                _raw_entry(
                    expected_source="it_domains/tools/ruff.md",
                    expected_answer="Ruff is pinned to 0.1.0.",
                )
            ],
        )
    )

    marked = mark_stale_entries(
        gold_set,
        repo_root=kb_dir,
        kb_dir=kb_dir,
        tool_versions={"ruff": "0.2.0"},
    )

    assert marked.entries[0].stale is True
    assert "mismatched tool ruff" in (marked.entries[0].stale_reason or "")
