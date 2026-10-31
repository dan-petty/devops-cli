"""The text of a file in the inputs of an implement step (#2838).

The step packs each file that its group names to at most `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS`
tokens, and opens the rest with its tools. The stage job measures a task group with the same
text, so a group costs in the plan what its step reads.
"""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.context_budget import truncate_to_token_limit
from devops_cli.ai.context_packer import ContextPacker, PackingConfig
from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS


def packed_file(path: Path) -> str:
    """A file for the inputs: a Python file as its signatures, any other as its start."""
    if path.suffix == ".py":
        config = PackingConfig(
            max_tokens=CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS, strip_private=False
        )
        return ContextPacker().pack_file(path, config=config).content
    text = path.read_text(encoding="utf-8", errors="replace")
    return truncate_to_token_limit(text, CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS)


__all__ = ["packed_file"]
