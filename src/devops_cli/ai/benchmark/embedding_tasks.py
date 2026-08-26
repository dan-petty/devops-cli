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


def _parse_embedding_eval_pairs(md_text: str) -> list[EmbeddingEvalPair]:
    """Parse Markdown sections into structured EmbeddingEvalPair objects."""
    pairs: list[EmbeddingEvalPair] = []
    sections = re.split(r"(?m)^##\s+", md_text)
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        lines = sec.splitlines()
        pair_id = lines[0].strip()
        category = ""
        query = ""
        target_passage = ""
        for line in lines[1:]:
            line_str = line.strip()
            if line_str.startswith("- **Category:**"):
                category = line_str[len("- **Category:**") :].strip()
            elif line_str.startswith("- **Query:**"):
                query = line_str[len("- **Query:**") :].strip()
            elif line_str.startswith("- **Target Passage:**"):
                target_passage = line_str[len("- **Target Passage:**") :].strip()

        if pair_id and category and query and target_passage:
            pairs.append(
                EmbeddingEvalPair(
                    id=pair_id,
                    category=category,
                    query=query,
                    target_passage=target_passage,
                )
            )
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


# Expose module-level lists for backward compatibility
EMBEDDING_EVAL_PAIRS: list[EmbeddingEvalPair] = _load_eval_pairs()
EMBEDDING_DISTRACTORS: list[str] = _load_distractors()


def get_embedding_eval_dataset() -> tuple[list[EmbeddingEvalPair], list[str]]:
    """Return the paired evaluation items and the complete document corpus."""
    pairs = _load_eval_pairs()
    distractors = _load_distractors()
    corpus: list[str] = [p.target_passage for p in pairs] + list(distractors)
    return list(pairs), corpus
