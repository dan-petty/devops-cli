"""Tests for the shared citation parser, digest, verifier, re-anchor, and permalink helpers (#6440)."""

from __future__ import annotations

import hashlib
from dataclasses import is_dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from devops_cli.citation import (
    LineCitation,
    StructuredCitation,
    SymbolCitation,
    parse_citation,
    read_at_commit,
    reanchor_span,
    render_permalink,
    span_hash,
    verify_citation,
)
from devops_cli.config.constants import CONST_KB_SHA_DIGEST_LENGTH
from tests.support.fakes.process import ProcessAnswer

if TYPE_CHECKING:
    from tests.support.fakes.process import ProcessFake


def test_parse_citation_handles_line_symbol_and_structured_forms() -> None:
    """parse_citation returns typed frozen dataclasses for line, symbol, and ADR 0025 citations."""
    line = parse_citation("src/devops_cli/ai/kb.py:614:sha = hashlib.sha256(...)")
    symbol = parse_citation("src/devops_cli/ai/kb.py:def load_matched_kb_manuals")
    structured = parse_citation(
        {
            "path": "docs/CLI_REFERENCE.md",
            "commit": "abc123def456",
            "lines": [10, 14],
            "span_hash": span_hash("line one\nline two"),
            "doc_class": "generated",
            "generated_from": "src/devops_cli/commands/repos.py",
            "adr_status": "in-force",
            "as_of": "2026-11-25",
        }
    )

    assert is_dataclass(line)
    assert is_dataclass(symbol)
    assert is_dataclass(structured)
    assert line == LineCitation(
        path="src/devops_cli/ai/kb.py",
        line=614,
        text="sha = hashlib.sha256(...)",
    )
    assert symbol == SymbolCitation(
        path="src/devops_cli/ai/kb.py",
        kind="def",
        symbol="load_matched_kb_manuals",
    )
    assert structured == StructuredCitation(
        path="docs/CLI_REFERENCE.md",
        commit="abc123def456",
        lines=(10, 14),
        span_hash=span_hash("line one\nline two"),
        doc_class="generated",
        generated_from="src/devops_cli/commands/repos.py",
        adr_status="in-force",
        as_of="2026-11-25",
    )


def test_span_hash_matches_kb_digest_prefix() -> None:
    """span_hash matches the 16-char UTF-8 SHA-256 prefix used by devops_cli.ai.kb."""
    sample = "sha = hashlib.sha256(content.encode('utf-8')).hexdigest()"
    expected = hashlib.sha256(sample.encode("utf-8")).hexdigest()[:CONST_KB_SHA_DIGEST_LENGTH]

    digest = span_hash(sample)

    assert digest == expected
    assert len(digest) == 16


def test_local_commit_verifies_without_remote_request(
    process_fake: ProcessFake, tmp_path: Path
) -> None:
    """When git holds the commit locally, verification runs git show with zero remote calls."""
    sha = "a1b2c3d4e5f6"
    path = "src/devops_cli/ai/kb.py"
    text = "alpha\nbeta\ngamma\n"
    process_fake.answer(
        ["git", "-C", str(tmp_path), "cat-file", "-e", f"{sha}^{{commit}}"],
        ProcessAnswer(returncode=0),
    )
    process_fake.answer(
        ["git", "-C", str(tmp_path), "show", f"{sha}:{path}"],
        ProcessAnswer(returncode=0, stdout=text),
    )

    def _forbid_remote(commit: str, target: str) -> str | None:
        raise AssertionError(f"unexpected remote read for {commit}:{target}")

    cited = StructuredCitation(
        path=path,
        commit=sha,
        lines=(1, 2),
        span_hash=span_hash("alpha\nbeta"),
        doc_class="hand-written",
        as_of="2026-11-25",
    )
    result = verify_citation(cited, repo_root=tmp_path, fetch_contents=_forbid_remote)

    assert result.valid is True
    assert result.used_remote is False
    assert result.content == text


def test_missing_local_commit_calls_remote_contents_once(
    process_fake: ProcessFake, tmp_path: Path
) -> None:
    """When the commit is absent locally, read_at_commit calls the contents callback once."""
    sha = "deadbeef1234"
    path = "docs/ARCHITECTURE.md"
    calls: list[tuple[str, str]] = []
    process_fake.answer(
        ["git", "-C", str(tmp_path), "cat-file", "-e", f"{sha}^{{commit}}"],
        ProcessAnswer(returncode=128, stderr="Not a valid object name"),
    )

    def _fetch(commit: str, target: str) -> str | None:
        calls.append((commit, target))
        return "header\nbody\n"

    content, used_remote = read_at_commit(tmp_path, sha, path, fetch_contents=_fetch)

    assert content == "header\nbody\n"
    assert used_remote is True
    assert calls == [(sha, path)]


def test_reanchor_span_moves_unique_match_and_refuses_zero_or_multiple() -> None:
    """reanchor_span moves a moved span on 1 match and refuses 0 matches and 2+ matches."""
    content = "\n".join(
        [
            "first line",
            "duplicate line",
            "unique moved target",
            "duplicate line",
            "last line",
        ]
    )

    moved = reanchor_span(content, "unique moved target", expected_lines=(1, 1))
    missing = reanchor_span(content, "absent line", expected_lines=(1, 1))
    ambiguous = reanchor_span(content, "duplicate line", expected_lines=(1, 1))

    assert (moved.matched, moved.lines, moved.re_anchored) == (True, (3, 3), True)
    assert missing.matched is False
    assert "0" in missing.reason
    assert ambiguous.matched is False
    assert "2" in ambiguous.reason


def test_render_permalink_formats_commit_path_and_line_range() -> None:
    """render_permalink formats a canonical GitHub blob URL with commit, path, and lines."""
    single = render_permalink("dan-petty/devops-cli", "deadbeef", "src/a.py", (7, 7))
    ranged = render_permalink("dan-petty/devops-cli", "deadbeef", "src/a.py", (7, 12))

    assert single == "https://github.com/dan-petty/devops-cli/blob/deadbeef/src/a.py#L7"
    assert ranged == "https://github.com/dan-petty/devops-cli/blob/deadbeef/src/a.py#L7-L12"
