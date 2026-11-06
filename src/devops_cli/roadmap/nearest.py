"""The nearest-item ranking that intake and the consolidation job share (#1127).

Intake ranks the items for one candidate, and the consolidation job ranks them for every open
item. Both embed an item as `embedding_text`, and both rank by `cosine_similarity`, so one
function holds the ranking and one function holds the text.
"""

from __future__ import annotations

from collections.abc import Sequence

from devops_cli.ai.vector_similarity import cosine_similarity
from devops_cli.config.defaults import DEFAULT_ROADMAP_INTAKE_TEXT_CHARS


def embedding_text(title: str, body: str) -> str:
    """The text of an item that the embedding model reads: its title and its body, cut at
    `DEFAULT_ROADMAP_INTAKE_TEXT_CHARS` characters."""
    return f"{title}\n\n{body}"[:DEFAULT_ROADMAP_INTAKE_TEXT_CHARS]


def nearest[KeyT](
    query: list[float], candidates: Sequence[tuple[KeyT, list[float]]], limit: int
) -> list[KeyT]:
    """The keys of the `limit` candidates whose vectors are the closest to `query` by cosine
    similarity, the closest first. Candidates with an equal score keep the order they have in
    `candidates`."""
    ranked = sorted(candidates, key=lambda pair: cosine_similarity(pair[1], query), reverse=True)
    return [key for key, _ in ranked[:limit]]
