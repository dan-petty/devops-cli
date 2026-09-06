"""Curated evaluation dataset for embedding model semantic retrieval benchmarking."""

from __future__ import annotations

import re
from functools import lru_cache

from pydantic import BaseModel, ConfigDict

from devops_cli.ai.task_loader import load_task_prompt


class EmbeddingEvalPair(BaseModel):
    """Query, matching target document passage, and metadata category."""

    model_config = ConfigDict(frozen=True)

    id: str
    category: str
    query: str
    target_passage: str


def _parse_single_eval_pair(sec: str) -> EmbeddingEvalPair | None:
    lines = sec.strip().splitlines()
    if not lines:
        return None
    pair_id = lines[0].strip()
    fields: dict[str, str] = {}
    prefixes = {
        "- **Category:**": "category",
        "- **Query:**": "query",
        "- **Target Passage:**": "target_passage",
    }
    for line in lines[1:]:
        line_str = line.strip()
        for prefix, field_name in prefixes.items():
            if line_str.startswith(prefix):
                fields[field_name] = line_str[len(prefix) :].strip()
                break

    if pair_id and "category" in fields and "query" in fields and "target_passage" in fields:
        return EmbeddingEvalPair(
            id=pair_id,
            category=fields["category"],
            query=fields["query"],
            target_passage=fields["target_passage"],
        )
    return None


def _parse_embedding_eval_pairs(md_text: str) -> list[EmbeddingEvalPair]:
    """Parse Markdown sections into structured EmbeddingEvalPair objects."""
    pairs: list[EmbeddingEvalPair] = []
    sections = re.split(r"(?m)^##\s+", md_text)
    for sec in sections:
        pair = _parse_single_eval_pair(sec)
        if pair is not None:
            pairs.append(pair)
    return pairs


def _parse_embedding_distractors(md_text: str) -> list[str]:
    """Parse distractor bullet lines from Markdown text."""
    distractors: list[str] = []
    for line in md_text.splitlines():
        line_str = line.strip()
        if line_str.startswith("- "):
            distractors.append(line_str[2:].strip())
    return distractors


@lru_cache(maxsize=1)
def _load_eval_pairs() -> list[EmbeddingEvalPair]:
    md_text = load_task_prompt("benchmark_embedding_eval_pairs.md")
    return _parse_embedding_eval_pairs(md_text)


@lru_cache(maxsize=1)
def _load_distractors() -> list[str]:
    md_text = load_task_prompt("benchmark_embedding_distractors.md")
    return _parse_embedding_distractors(md_text)


# Module-level evaluated benchmark fixtures
EMBEDDING_EVAL_PAIRS: list[EmbeddingEvalPair] = _load_eval_pairs()
EMBEDDING_DISTRACTORS: list[str] = _load_distractors()


def get_embedding_eval_dataset() -> tuple[list[EmbeddingEvalPair], list[str]]:
    """Return the paired evaluation items and the complete document corpus."""
    pairs = _load_eval_pairs()
    distractors = _load_distractors()
    corpus: list[str] = [p.target_passage for p in pairs] + list(distractors)
    return list(pairs), corpus
