"""Local Context Budgeting & Token Counting using tiktoken and BPE tokenizers."""

from __future__ import annotations

import functools
import logging
import math
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.config.defaults import (
    DEFAULT_DIFF_CHUNK_BUDGET,
    DEFAULT_MAX_CONTEXT_TOKENS,
    DEFAULT_TIKTOKEN_MODEL,
)

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=16)
def _get_tiktoken_encoding(model: str = DEFAULT_TIKTOKEN_MODEL) -> Any:
    """Retrieve cached tiktoken encoding instance with graceful fallback."""
    try:
        import tiktoken

        try:
            return tiktoken.encoding_for_model(model)
        except KeyError, ValueError:
            return tiktoken.get_encoding("cl100k_base")
    except Exception as exc:
        logger.debug("Failed to initialize tiktoken encoding for model %s: %s", model, exc)
        return None


def count_tokens(text: str, model: str = DEFAULT_TIKTOKEN_MODEL) -> int:
    """Count exact BPE tokens for text, with robust heuristic fallback."""
    if not text:
        return 0

    encoding = _get_tiktoken_encoding(model)
    if encoding is not None:
        try:
            return len(encoding.encode(text, disallowed_special=()))
        except Exception:
            pass

    # Heuristic fallback (average 4 characters per token in code/prose)
    return max(1, math.ceil(len(text) / 4))


def count_file_tokens(file_path: Path, model: str = DEFAULT_TIKTOKEN_MODEL) -> int:
    """Count token usage of a local file."""
    if not file_path.exists() or not file_path.is_file():
        return 0
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        return count_tokens(content, model=model)
    except Exception as exc:
        logger.debug("Failed reading file %s for token counting: %s", file_path, exc)
        return 0


def truncate_to_token_limit(
    text: str,
    max_tokens: int,
    model: str = DEFAULT_TIKTOKEN_MODEL,
    suffix: str = "\n...[truncated due to context budget]",
) -> str:
    """Truncate text to strictly fit within specified token budget."""
    if not text or max_tokens <= 0:
        return ""

    curr_tokens = count_tokens(text, model=model)
    if curr_tokens <= max_tokens:
        return text

    encoding = _get_tiktoken_encoding(model)
    if encoding is not None:
        try:
            tokens = encoding.encode(text, disallowed_special=())
            suffix_tokens = encoding.encode(suffix, disallowed_special=())
            budget = max(0, max_tokens - len(suffix_tokens))
            truncated_tokens = tokens[:budget]
            decoded_str = str(encoding.decode(truncated_tokens))
            return f"{decoded_str}{suffix}"
        except Exception:
            pass

    # Character fallback truncation
    char_budget = max(0, (max_tokens * 4) - len(suffix))
    return text[:char_budget] + suffix


def validate_and_budget_prompt(
    text: str,
    max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
    model: str = DEFAULT_TIKTOKEN_MODEL,
    warn_threshold: float = 0.85,
    suffix: str = "\n\n...[content condensed to fit context window budget]",
) -> tuple[str, bool]:
    """Validate prompt against token budget; log warning or condense payload if it exceeds context limit.

    Returns:
        tuple[str, bool]: The (possibly condensed) prompt text and a boolean indicating if it was condensed.
    """
    if not text:
        return text, False

    tok_count = count_tokens(text, model=model)
    if tok_count > max_tokens:
        logger.warning(
            "Prompt size (%d tokens) exceeds maximum context budget (%d tokens). Condensing payload.",
            tok_count,
            max_tokens,
        )
        condensed = truncate_to_token_limit(text, max_tokens=max_tokens, model=model, suffix=suffix)
        return condensed, True

    if tok_count >= int(max_tokens * warn_threshold):
        logger.warning(
            "Prompt size (%d tokens) is approaching context budget limit (%d tokens, %.0f%% capacity).",
            tok_count,
            max_tokens,
            (tok_count / max_tokens) * 100.0,
        )

    return text, False


def budget_diff_chunks(
    diff_text: str,
    max_tokens: int = DEFAULT_DIFF_CHUNK_BUDGET,
    model: str = "gpt-4o",
) -> list[str]:
    """Partition a large unified git diff into cohesive chunks respecting token budget."""
    if not diff_text.strip():
        return []

    total_tokens = count_tokens(diff_text, model=model)
    if total_tokens <= max_tokens:
        return [diff_text]

    # Split diff along file boundaries: "diff --git "
    file_diffs: list[str] = []
    raw_splits = diff_text.split("diff --git ")
    for split in raw_splits:
        if not split.strip():
            continue
        file_diffs.append("diff --git " + split if not split.startswith("diff --git ") else split)

    chunks: list[str] = []
    current_chunk: list[str] = []
    current_tokens = 0

    for fdiff in file_diffs:
        fdiff_tokens = count_tokens(fdiff, model=model)

        if fdiff_tokens > max_tokens:
            # If a single file diff exceeds the entire budget, split by hunk ("@@ -")
            if current_chunk:
                chunks.append("".join(current_chunk))
                current_chunk = []
                current_tokens = 0

            hunks = fdiff.split("\n@@ ")
            header = hunks[0] if hunks else ""
            hunk_chunk: list[str] = [header]
            hunk_tokens = count_tokens(header, model=model)

            for hunk in hunks[1:]:
                full_hunk = "\n@@ " + hunk
                h_tokens = count_tokens(full_hunk, model=model)

                if hunk_tokens + h_tokens > max_tokens and len(hunk_chunk) > 1:
                    chunks.append("".join(hunk_chunk))
                    hunk_chunk = [header, full_hunk]
                    hunk_tokens = count_tokens(header, model=model) + h_tokens
                else:
                    hunk_chunk.append(full_hunk)
                    hunk_tokens += h_tokens

            if hunk_chunk:
                chunks.append("".join(hunk_chunk))
        elif current_tokens + fdiff_tokens > max_tokens:
            if current_chunk:
                chunks.append("".join(current_chunk))
            current_chunk = [fdiff]
            current_tokens = fdiff_tokens
        else:
            current_chunk.append(fdiff)
            current_tokens += fdiff_tokens

    if current_chunk:
        chunks.append("".join(current_chunk))

    return chunks if chunks else [diff_text]


class TokenBudgetReport(BaseModel):
    """Pydantic model representing token consumption and context budget analysis."""

    text_length: int = Field(..., description="Raw character length of input")
    estimated_tokens: int = Field(..., description="BPE token count")
    max_budget: int = Field(
        default=DEFAULT_MAX_CONTEXT_TOKENS, description="Maximum context token budget"
    )
    fits_budget: bool = Field(..., description="Whether input fits in specified budget")
    model: str = Field(default="gpt-4o", description="Target model encoding")
    chunk_count: int = Field(default=1, description="Calculated diff/context chunk count")
