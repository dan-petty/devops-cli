"""Collect `devops` command lines in Markdown documentation and resolve them statically.

Extracts command lines from fenced code blocks and inline code spans across the
bundled AI knowledge base (`src/devops_cli/ai/knowledge_base/**/*.md`) and verifies
that every command, subcommand, and option resolves against the live Typer command tree.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Sequence
from pathlib import Path

from devops_cli.config.constants import (
    CONST_DOCS_ARGV_KNOWN_PLACEHOLDERS,
    CONST_HANDWRITTEN_DOCS_PATHS,
)
from devops_cli.core.command_resolver import ArgvPlaceholder, ArgvToken
from devops_cli.core.repo import find_repo_root
from devops_cli.docs.source_argv_collector import (
    DevopsArgvReference,
    describe_unresolved_references,
)

_PREFIX_RE = re.compile(r"^\s*\$?\s*(?:uv\s+run\s+)?devops(?:\s+(.*)|$)")
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_FENCE_PREFIXES = ("```", "~~~")
_MARKDOWN_OWNER = "<markdown>"
_KNOWLEDGE_BASE_SUBDIR = Path("src/devops_cli/ai/knowledge_base")


def is_placeholder(token: str) -> bool:
    """Whether a token represents a computed expression or placeholder."""
    if token in CONST_DOCS_ARGV_KNOWN_PLACEHOLDERS:
        return True
    if token.startswith("[") or token.endswith("]"):
        return True
    return (
        ("<" in token and ">" in token)
        or ("{" in token and "}" in token)
        or ("[" in token and "]" in token)
    )


def _is_unquoted_pipeline_cut(char: str, next_char: str | None) -> bool:
    """Check if character initiates an unquoted comment, pipe, or compound operator."""
    return char in ("#", "|", ";") or (char == "&" and next_char == "&")


def cut_trailing_pipeline(line: str) -> str:
    """Strip comments, pipes, and compound shell operators while respecting quotes."""
    in_single = False
    in_double = False
    for i, char in enumerate(line):
        if char == "'" and not in_double:
            in_single = not in_single
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            continue
        if in_single or in_double:
            continue
        next_char = line[i + 1] if i + 1 < len(line) else None
        if _is_unquoted_pipeline_cut(char, next_char):
            return line[:i].strip()
    return line.strip()


def _tokenize_command(raw_args: str) -> tuple[ArgvToken, ...]:
    """Tokenize arguments and map placeholders to ArgvPlaceholder."""
    cleaned = cut_trailing_pipeline(raw_args)
    if not cleaned:
        return ()
    try:
        parts = shlex.split(cleaned, comments=True)
    except ValueError:
        parts = cleaned.split()
    return tuple(_argv_token(part) for part in parts)


def _argv_token(part: str) -> ArgvToken:
    """The token a document's word stands for.

    An option written inside a synopsis optional group (`[-v`, `[--json]`) is that option, so
    the check validates it.
    """
    option = part.removeprefix("[").removesuffix("]")
    if option.startswith("-"):
        return option
    return ArgvPlaceholder(expression=part) if is_placeholder(part) else part


def _extract_fenced_references(lines: Sequence[str], path: str) -> list[DevopsArgvReference]:
    """Extract devops command lines from fenced code blocks."""
    references: list[DevopsArgvReference] = []
    in_fence = False
    fence_marker: str | None = None
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith(_FENCE_PREFIXES):
            marker = stripped[:3]
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif marker == fence_marker:
                in_fence = False
                fence_marker = None
            i += 1
            continue

        if in_fence:
            match = _PREFIX_RE.match(stripped)
            if match:
                start_line = i + 1
                cmd_chunks = [match.group(1) or ""]
                while cmd_chunks[-1].endswith("\\") and i + 1 < len(lines):
                    cmd_chunks[-1] = cmd_chunks[-1][:-1].strip()
                    i += 1
                    cmd_chunks.append(lines[i].strip())
                tokens = _tokenize_command(" ".join(cmd_chunks))
                references.append(
                    DevopsArgvReference(
                        path=path,
                        line=start_line,
                        owner=_MARKDOWN_OWNER,
                        tokens=tokens,
                    )
                )
        i += 1
    return references


def _extract_inline_references(lines: Sequence[str], path: str) -> list[DevopsArgvReference]:
    """Extract devops command lines from inline code spans outside code fences."""
    references: list[DevopsArgvReference] = []
    in_fence = False
    fence_marker: str | None = None
    for line_idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(_FENCE_PREFIXES):
            marker = stripped[:3]
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif marker == fence_marker:
                in_fence = False
                fence_marker = None
            continue

        if in_fence:
            continue

        for match_span in _INLINE_CODE_RE.finditer(line):
            span_text = match_span.group(1).strip()
            match = _PREFIX_RE.match(span_text)
            if match:
                tokens = _tokenize_command(match.group(1) or "")
                references.append(
                    DevopsArgvReference(
                        path=path,
                        line=line_idx + 1,
                        owner=_MARKDOWN_OWNER,
                        tokens=tokens,
                    )
                )
    return references


def collect_markdown_argv_references(content: str, path: str) -> list[DevopsArgvReference]:
    """Collect devops command invocations from fenced blocks and inline spans."""
    lines = content.splitlines()
    fenced = _extract_fenced_references(lines, path)
    inline = _extract_inline_references(lines, path)
    return sorted([*fenced, *inline], key=lambda ref: ref.line)


def collect_knowledge_base_argv_references(
    root_dir: Path | None = None,
) -> list[DevopsArgvReference]:
    """Collect devops command invocations across all knowledge base articles."""
    resolved_root = find_repo_root(root_dir) if root_dir else find_repo_root(Path.cwd())
    kb_path = resolved_root / _KNOWLEDGE_BASE_SUBDIR
    if not kb_path.is_dir():
        return []

    references: list[DevopsArgvReference] = []
    for file_path in sorted(kb_path.rglob("*.md")):
        rel_path = file_path.relative_to(resolved_root).as_posix()
        content = file_path.read_text(encoding="utf-8")
        references.extend(collect_markdown_argv_references(content, rel_path))
    return sorted(references, key=lambda ref: (ref.path, ref.line))


def check_knowledge_base_argv(root_dir: Path | None = None) -> list[str]:
    """Describe every knowledge base command line that fails CLI resolution."""
    references = collect_knowledge_base_argv_references(root_dir)
    return describe_unresolved_references(references)


def collect_handwritten_docs_argv_references(
    root_dir: Path | None = None,
) -> list[DevopsArgvReference]:
    """Collect devops command invocations across hand-written repository docs and k8s READMEs."""
    resolved_root = find_repo_root(root_dir) if root_dir else find_repo_root(Path.cwd())
    doc_paths: list[Path] = [resolved_root / rel_path for rel_path in CONST_HANDWRITTEN_DOCS_PATHS]

    k8s_dir = resolved_root / "k8s"
    if k8s_dir.is_dir():
        doc_paths.extend(sorted(k8s_dir.rglob("README.md")))

    references: list[DevopsArgvReference] = []
    for file_path in doc_paths:
        if not file_path.is_file():
            continue
        rel_path = file_path.relative_to(resolved_root).as_posix()
        content = file_path.read_text(encoding="utf-8")
        references.extend(collect_markdown_argv_references(content, rel_path))
    return sorted(references, key=lambda ref: (ref.path, ref.line))


def check_handwritten_docs_argv(root_dir: Path | None = None) -> list[str]:
    """Describe every hand-written doc command line that fails CLI resolution."""
    references = collect_handwritten_docs_argv_references(root_dir)
    return describe_unresolved_references(references)
