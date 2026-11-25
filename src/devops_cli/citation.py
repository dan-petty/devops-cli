"""Shared citation types, hashing, commit verification, re-anchoring, and permalinks (#6440).

Imported by both `devops_cli.roadmap.stage` and `devops_cli.ai`, with zero dependency between
`ai` and `roadmap`. Supports:

- Line citations (`path:line:text`) and symbol citations (`path:def name` / `path:class name`)
- ADR 0025 structured citations (`{path, commit, lines, span_hash, doc_class, generated_from?, adr_status?, as_of}`)
- 16-character SHA-256 span digests matching `devops_cli.ai.kb` (`CONST_KB_SHA_DIGEST_LENGTH`)
- Local-git-first commit reads (`git cat-file` + `git show`) with single remote fallback
- Unique-match span re-anchoring (refusing 0 or 2+ matches) and GitHub blob permalinks
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from devops_cli.config.constants import CONST_GIT_CLI, CONST_KB_SHA_DIGEST_LENGTH
from devops_cli.core.process import run_subprocess

CITED_PATH_PATTERN: Final[str] = r"[A-Za-z0-9_][A-Za-z0-9_./-]*\.[A-Za-z0-9_]+"
LINE_CITATION_RE: Final[re.Pattern[str]] = re.compile(
    rf"(?<![\w./-])(?P<path>{CITED_PATH_PATTERN}):(?P<line>\d+):(?P<text>[^`]*)"
)
SYMBOL_CITATION_RE: Final[re.Pattern[str]] = re.compile(
    rf"(?<![\w./-])(?P<path>{CITED_PATH_PATTERN}):(?P<kind>def|class)\s+(?P<symbol>[A-Za-z_]\w*)"
)
FOLLOWING_QUOTE_RE: Final[re.Pattern[str]] = re.compile(r"`?\s*`(?P<quote>[^`]+)`")
CITATION_MIN_CHARS: Final[int] = 3


@dataclass(frozen=True)
class LineCitation:
    """Parsed `path:line:text` citation."""

    path: str
    line: int
    text: str


@dataclass(frozen=True)
class SymbolCitation:
    """Parsed `path:def name` or `path:class name` citation."""

    path: str
    kind: str
    symbol: str


@dataclass(frozen=True)
class StructuredCitation:
    """Parsed ADR 0025 structured document citation."""

    path: str
    commit: str
    lines: tuple[int, int]
    span_hash: str
    doc_class: str
    generated_from: str | None = None
    adr_status: str | None = None
    as_of: str = ""


type ParsedCitation = LineCitation | SymbolCitation | StructuredCitation


@dataclass(frozen=True)
class ReanchorResult:
    """Outcome of matching or re-anchoring a cited span inside file content."""

    matched: bool
    lines: tuple[int, int] | None
    re_anchored: bool
    reason: str = ""


@dataclass(frozen=True)
class VerificationResult:
    """Outcome of verifying a parsed citation against repository contents."""

    valid: bool
    content: str | None
    reanchor: ReanchorResult | None
    used_remote: bool
    reason: str = ""


def squash_whitespace(text: str) -> str:
    """Collapse whitespace runs into single spaces."""
    return " ".join(text.split())


def normalize_cited_text(text: str) -> str:
    """Normalize cited line text (strip backticks, trailing period, and extra whitespace)."""
    return squash_whitespace(text.replace("`", "").strip().removesuffix("."))


def span_hash(text: str) -> str:
    """Return the first `CONST_KB_SHA_DIGEST_LENGTH` hex chars of UTF-8 SHA-256."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:CONST_KB_SHA_DIGEST_LENGTH]


def quoted_line_text(text: str, match: re.Match[str]) -> str:
    """Extract the cited line quote from the inline match or following code span."""
    quoted = match.group("text")
    if normalize_cited_text(quoted):
        return quoted
    following = FOLLOWING_QUOTE_RE.match(text, match.end())
    return following["quote"] if following else quoted


def _parse_lines_range(raw_lines: Any) -> tuple[int, int]:
    if isinstance(raw_lines, int):
        return (raw_lines, raw_lines)
    if isinstance(raw_lines, (list, tuple)) and len(raw_lines) == 2:
        return (int(raw_lines[0]), int(raw_lines[1]))
    raise ValueError(f"Expected 1 int or 2-element line range, got {raw_lines!r}")


def parse_citation(raw: str | Mapping[str, Any]) -> ParsedCitation:
    """Parse a line citation, symbol citation, or ADR 0025 structured mapping."""
    if isinstance(raw, Mapping):
        return StructuredCitation(
            path=str(raw["path"]),
            commit=str(raw["commit"]),
            lines=_parse_lines_range(raw["lines"]),
            span_hash=str(raw["span_hash"]),
            doc_class=str(raw["doc_class"]),
            generated_from=(
                str(raw["generated_from"]) if raw.get("generated_from") is not None else None
            ),
            adr_status=str(raw["adr_status"]) if raw.get("adr_status") is not None else None,
            as_of=str(raw.get("as_of", "")),
        )
    if line_match := LINE_CITATION_RE.match(raw):
        return LineCitation(
            path=line_match["path"],
            line=int(line_match["line"]),
            text=line_match["text"],
        )
    if sym_match := SYMBOL_CITATION_RE.match(raw):
        return SymbolCitation(
            path=sym_match["path"],
            kind=sym_match["kind"],
            symbol=sym_match["symbol"],
        )
    raise ValueError(f"Unrecognized citation format: {raw!r}")


def defines_symbol(content: str, kind: str, symbol: str) -> bool:
    """Return True when `content` defines `kind symbol` (`def name` / `class name`)."""
    pattern = re.compile(rf"\b{re.escape(kind)}\s+{re.escape(symbol)}\b")
    return any(pattern.search(squash_whitespace(line)) for line in content.splitlines())


def _single_line_matches(lines: list[str], needle: str) -> list[tuple[int, int]]:
    return [(idx, idx) for idx, line in enumerate(lines, start=1) if needle in line]


def _multi_line_matches(lines: list[str], needle_lines: list[str]) -> list[tuple[int, int]]:
    height = len(needle_lines)
    return [
        (idx, idx + height - 1)
        for idx in range(1, len(lines) - height + 2)
        if all(needle_lines[offset] == lines[idx - 1 + offset] for offset in range(height))
    ]


def reanchor_span(
    content: str,
    span_text: str,
    *,
    expected_lines: tuple[int, int] | None = None,
) -> ReanchorResult:
    """Keep `expected_lines` when it matches, else move only if normalized text has 1 match."""
    lines = [squash_whitespace(line) for line in content.splitlines()]
    needle_lines = [normalize_cited_text(line) for line in span_text.splitlines()] or [""]
    if len(needle_lines) == 1:
        needle = needle_lines[0]
        if (
            expected_lines is not None
            and expected_lines[0] == expected_lines[1]
            and 1 <= expected_lines[0] <= len(lines)
            and needle in lines[expected_lines[0] - 1]
        ):
            return ReanchorResult(matched=True, lines=expected_lines, re_anchored=False)
        hits = _single_line_matches(lines, needle)
    else:
        hits = _multi_line_matches(lines, needle_lines)
        if expected_lines is not None and expected_lines in hits:
            return ReanchorResult(matched=True, lines=expected_lines, re_anchored=False)

    if len(hits) == 1:
        return ReanchorResult(matched=True, lines=hits[0], re_anchored=hits[0] != expected_lines)
    return ReanchorResult(
        matched=False,
        lines=None,
        re_anchored=False,
        reason=f"expected 1 unique match, found {len(hits)} matches",
    )


def render_permalink(repo: str, commit: str, path: str, lines: tuple[int, int]) -> str:
    """Render a GitHub blob permalink for commit, path, and 1-based line range."""
    clean_path = path.lstrip("/")
    anchor = f"L{lines[0]}" if lines[0] == lines[1] else f"L{lines[0]}-L{lines[1]}"
    return f"https://github.com/{repo}/blob/{commit}/{clean_path}#{anchor}"


def read_at_commit(
    repo_root: Path,
    commit: str,
    path: str,
    *,
    fetch_contents: Callable[[str, str], str | None] | None = None,
) -> tuple[str | None, bool]:
    """Read `path` at `commit` via local git first, falling back to `fetch_contents` once."""
    exists = run_subprocess(
        [CONST_GIT_CLI, "-C", str(repo_root), "cat-file", "-e", f"{commit}^{{commit}}"],
        check=False,
        quiet=True,
    )
    if exists.returncode == 0:
        shown = run_subprocess(
            [CONST_GIT_CLI, "-C", str(repo_root), "show", f"{commit}:{path}"],
            check=False,
            quiet=True,
        )
        return (shown.stdout if shown.returncode == 0 else None), False
    if fetch_contents is None:
        return None, False
    return fetch_contents(commit, path), True


def verify_citation(
    cited: StructuredCitation,
    *,
    repo_root: Path,
    fetch_contents: Callable[[str, str], str | None] | None = None,
) -> VerificationResult:
    """Verify an ADR 0025 structured citation at its recorded commit."""
    content, used_remote = read_at_commit(
        repo_root, cited.commit, cited.path, fetch_contents=fetch_contents
    )
    if content is None:
        return VerificationResult(
            valid=False,
            content=None,
            reanchor=None,
            used_remote=used_remote,
            reason=f"file {cited.path} missing at {cited.commit}",
        )
    all_lines = content.splitlines()
    start, end = cited.lines
    if start < 1 or end < start or end > len(all_lines):
        return VerificationResult(
            valid=False,
            content=content,
            reanchor=None,
            used_remote=used_remote,
            reason=f"line range {cited.lines} out of bounds",
        )
    actual_hash = span_hash("\n".join(all_lines[start - 1 : end]))
    if actual_hash != cited.span_hash:
        return VerificationResult(
            valid=False,
            content=content,
            reanchor=None,
            used_remote=used_remote,
            reason=f"span hash mismatch: expected {cited.span_hash}, got {actual_hash}",
        )
    return VerificationResult(
        valid=True,
        content=content,
        reanchor=ReanchorResult(matched=True, lines=cited.lines, re_anchored=False),
        used_remote=used_remote,
    )


__all__ = [
    "CITATION_MIN_CHARS",
    "CITED_PATH_PATTERN",
    "FOLLOWING_QUOTE_RE",
    "LINE_CITATION_RE",
    "SYMBOL_CITATION_RE",
    "LineCitation",
    "ParsedCitation",
    "ReanchorResult",
    "StructuredCitation",
    "SymbolCitation",
    "VerificationResult",
    "defines_symbol",
    "normalize_cited_text",
    "parse_citation",
    "quoted_line_text",
    "read_at_commit",
    "reanchor_span",
    "render_permalink",
    "span_hash",
    "squash_whitespace",
    "verify_citation",
]
