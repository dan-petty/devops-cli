"""Local Context Budgeting & Token Counting using tiktoken and BPE tokenizers."""

from __future__ import annotations

import contextlib
import functools
import logging
import math
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.config.defaults import (
    DEFAULT_MAX_CONTEXT_TOKENS,
    DEFAULT_TIKTOKEN_CACHE_ENV_VARS,
    DEFAULT_TIKTOKEN_FALLBACK_CACHE_DIRS,
    DEFAULT_TIKTOKEN_MODEL,
)

logger = logging.getLogger(__name__)


def _resolve_tiktoken_cache_dir() -> Path:
    """Resolve the local directory tiktoken reads its cached BPE files from."""
    for env_var in DEFAULT_TIKTOKEN_CACHE_ENV_VARS:
        if configured := os.environ.get(env_var):
            return Path(configured)
    candidates = (
        Path.home() / ".cache" / "tiktoken",
        *(Path(p) for p in DEFAULT_TIKTOKEN_FALLBACK_CACHE_DIRS),
    )
    for candidate in candidates:
        if candidate.is_dir() and any(candidate.iterdir()):
            return candidate
    return Path(tempfile.gettempdir()) / "data-gym-cache"


@contextlib.contextmanager
def _tiktoken_cache_env(cache_dir: Path) -> Iterator[None]:
    """Point tiktoken at `cache_dir` for the duration of an encoding load."""
    if any(os.environ.get(var) for var in DEFAULT_TIKTOKEN_CACHE_ENV_VARS):
        yield
        return
    os.environ["TIKTOKEN_CACHE_DIR"] = str(cache_dir)
    try:
        yield
    finally:
        os.environ.pop("TIKTOKEN_CACHE_DIR", None)


@functools.lru_cache(maxsize=16)
def _get_tiktoken_encoding(model: str = DEFAULT_TIKTOKEN_MODEL) -> Any:
    """Retrieve cached tiktoken encoding instance with graceful fallback."""
    cache_dir = _resolve_tiktoken_cache_dir()
    try:
        import tiktoken

        if not cache_dir.is_dir() or not any(cache_dir.iterdir()):
            raise FileNotFoundError(f"tiktoken cache directory is missing or empty: {cache_dir}")
        with _tiktoken_cache_env(cache_dir):
            try:
                return tiktoken.encoding_for_model(model)
            except KeyError, ValueError:
                return tiktoken.get_encoding("cl100k_base")
    except Exception as exc:
        logger.warning(
            "Failed to load tiktoken encoding for model %s from cache directory %s (%s); "
            "falling back to character heuristic.",
            model,
            cache_dir,
            exc,
        )
        return None


def reset_tiktoken_encoding_cache() -> None:
    """Clear cached tiktoken encoding instances."""
    _get_tiktoken_encoding.cache_clear()


def get_tiktoken_encoding(model: str = DEFAULT_TIKTOKEN_MODEL) -> Any:
    """Retrieve cached tiktoken encoding instance with graceful fallback."""
    return _get_tiktoken_encoding(model)


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
