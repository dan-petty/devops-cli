"""Cross-domain analogical pattern retriever and topological clustering engine."""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

from devops_cli.ai.research.models import CrossDomainAnalogy
from devops_cli.config.constants import (
    CONST_RAG_KB_PROJECT,
    CONST_STRUCTURAL_PATTERN_DEFINITIONS,
    CONST_STRUCTURAL_PATTERNS,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_ANALOGIES_LIMIT,
    DEFAULT_AI_ANALOGIES_MIN_SCORE,
    DEFAULT_RAG_DOCS_COLLECTION,
)
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.output import Table

logger = logging.getLogger(__name__)


def _extract_kb_section_domain(parts: list[str]) -> str | None:
    """Extract domain from structured knowledge base section path parts."""
    for section in ("topics", "tools", "tasks"):
        if section in parts:
            idx = parts.index(section)
            if idx + 1 < len(parts):
                stem = Path(parts[idx + 1]).stem
                if section == "topics":
                    return stem.split("_")[0] if "_" in stem else stem
                if section == "tools":
                    return stem.replace("_", "")
                return f"task/{stem}"
    return None


def _clean_repo_relative_path(file_path: str) -> list[str]:
    """Strip known prefixes and split path into normalized posix segments."""
    clean = file_path.replace("\\", "/").strip("./")
    for prefix in ("src/devops_cli/ai/knowledge_base/", "src/devops_cli/"):
        if clean.startswith(prefix):
            clean = clean[len(prefix) :]
    return [p for p in clean.split("/") if p]


def extract_domain(file_path: str, category: str = "", domain: str = "") -> str:
    """Derive the functional or IT domain classification for a module or document."""
    if domain:
        return domain
    if category and category not in ("code", "docs", "workspace"):
        return category

    parts = _clean_repo_relative_path(file_path)
    if not parts:
        return "general"

    section_domain = _extract_kb_section_domain(parts)
    if section_domain is not None:
        return section_domain

    first_part = parts[0]
    return Path(first_part).stem if len(parts) == 1 else first_part


def _count_pattern_mechanisms(clean_text: str, mechanisms: tuple[str, ...]) -> int:
    """Count keyword occurrences of architectural mechanisms within lowercased text."""
    total = 0
    for mech in mechanisms:
        total += clean_text.count(mech)
        if "_" in mech:
            total += clean_text.count(mech.replace("_", " "))
    return total


def compute_structural_vector(content: str) -> dict[str, float]:
    """Compute an L2-normalized structural pattern vector across canonical mechanisms."""
    clean_text = content.lower()
    raw_scores: dict[str, float] = {}

    for pattern in CONST_STRUCTURAL_PATTERNS:
        defn = CONST_STRUCTURAL_PATTERN_DEFINITIONS.get(pattern, {})
        mechanisms: tuple[str, ...] = defn.get("mechanisms", ())
        matches = _count_pattern_mechanisms(clean_text, mechanisms)
        if matches > 0:
            raw_scores[pattern] = float(matches)

    norm_sq = sum(score**2 for score in raw_scores.values())
    if norm_sq <= 0.0:
        return {}

    inv_l2 = 1.0 / math.sqrt(norm_sq)
    return {pattern: score * inv_l2 for pattern, score in raw_scores.items()}


def compute_dense_similarity(v1: list[float] | None, v2: list[float] | None) -> float:
    """Calculate cosine similarity between two dense embedding vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2, strict=False))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _find_shared_mechanisms(text_a: str, text_b: str, pattern: str) -> list[str]:
    """Identify invariant structural mechanisms actively present in both texts."""
    clean_a, clean_b = text_a.lower(), text_b.lower()
    defn = CONST_STRUCTURAL_PATTERN_DEFINITIONS.get(pattern, {})
    mechanisms: tuple[str, ...] = defn.get("mechanisms", ())
    shared: list[str] = []
    for mech in mechanisms:
        mech_space = mech.replace("_", " ") if "_" in mech else mech
        in_a = mech in clean_a or mech_space in clean_a
        in_b = mech in clean_b or mech_space in clean_b
        if in_a and in_b:
            shared.append(mech)
    return shared


def _is_pair_admissible(
    domain_a: str,
    domain_b: str,
    source_domain: str | None,
    target_domain: str | None,
) -> bool:
    """Evaluate whether candidate modules satisfy cross-domain constraints."""
    if domain_a == domain_b:
        return False
    if source_domain and source_domain not in (domain_a, domain_b):
        return False
    if target_domain and target_domain not in (domain_a, domain_b):
        return False
    return True


def _matches_query(
    query: str | None, pattern: str, node_a: dict[str, Any], node_b: dict[str, Any]
) -> bool:
    """Check whether candidate analogy matches an optional user query."""
    if not query:
        return True
    q = query.lower()
    if q in pattern.lower():
        return True
    path_a, path_b = (
        str(node_a.get("file_path", "")).lower(),
        str(node_b.get("file_path", "")).lower(),
    )
    return q in path_a or q in path_b


def _score_node_pair(
    node_a: dict[str, Any],
    node_b: dict[str, Any],
    min_score: float,
    query: str | None,
    source_domain: str | None,
    target_domain: str | None,
) -> CrossDomainAnalogy | None:
    """Evaluate structural isomorphism between two cross-domain nodes."""
    domain_a = extract_domain(str(node_a.get("file_path", "")), str(node_a.get("category", "")))
    domain_b = extract_domain(str(node_b.get("file_path", "")), str(node_b.get("category", "")))

    if not _is_pair_admissible(domain_a, domain_b, source_domain, target_domain):
        return None

    s_vec_a = node_a.get("struct_vec") or compute_structural_vector(str(node_a.get("content", "")))
    s_vec_b = node_b.get("struct_vec") or compute_structural_vector(str(node_b.get("content", "")))
    if not s_vec_a or not s_vec_b:
        return None

    best_pattern = ""
    best_joint = 0.0
    dot_sum = 0.0
    for pattern in CONST_STRUCTURAL_PATTERNS:
        w_a, w_b = s_vec_a.get(pattern, 0.0), s_vec_b.get(pattern, 0.0)
        joint = w_a * w_b
        dot_sum += joint
        if joint > best_joint:
            best_joint = joint
            best_pattern = pattern

    if not best_pattern or dot_sum <= 0.0:
        return None

    if not _matches_query(query, best_pattern, node_a, node_b):
        return None

    dense_sim = compute_dense_similarity(node_a.get("vector"), node_b.get("vector"))
    score = (
        round(0.85 * dot_sum + 0.15 * max(0.0, dense_sim), 4)
        if dense_sim > 0.0
        else round(dot_sum, 4)
    )
    if score < min_score:
        return None

    shared_mechs = _find_shared_mechanisms(
        str(node_a.get("content", "")), str(node_b.get("content", "")), best_pattern
    )
    explanation = (
        f"Structural pattern isomorphism matching '{best_pattern}' across domains "
        f"'{domain_a}' and '{domain_b}' with invariant mechanisms: {', '.join(shared_mechs)}."
    )
    return CrossDomainAnalogy(
        source=str(node_a.get("file_path", "")),
        target=str(node_b.get("file_path", "")),
        pattern=best_pattern,
        score=min(1.0, max(0.0, score)),
        source_domain=domain_a,
        target_domain=domain_b,
        shared_mechanisms=shared_mechs,
        explanation=explanation,
    )


def multi_vector_clustering(
    nodes: list[dict[str, Any]],
    *,
    min_score: float = DEFAULT_AI_ANALOGIES_MIN_SCORE,
    limit: int = DEFAULT_AI_ANALOGIES_LIMIT,
    query: str | None = None,
    source_domain: str | None = None,
    target_domain: str | None = None,
) -> list[CrossDomainAnalogy]:
    """Perform multi-vector topological clustering to surface cross-domain analogies."""
    for node in nodes:
        if "struct_vec" not in node:
            node["struct_vec"] = compute_structural_vector(str(node.get("content", "")))

    analogies: list[CrossDomainAnalogy] = []
    n = len(nodes)
    for i in range(n):
        for j in range(i + 1, n):
            match = _score_node_pair(
                nodes[i],
                nodes[j],
                min_score=min_score,
                query=query,
                source_domain=source_domain,
                target_domain=target_domain,
            )
            if match is not None:
                analogies.append(match)

    analogies.sort(key=lambda a: (-a.score, a.pattern, a.source, a.target))
    return analogies[:limit]


def _fetch_kb_points_from_qdrant(
    qdrant: Any,
    collection_name: str = DEFAULT_RAG_DOCS_COLLECTION,
    limit: int = 250,
) -> list[dict[str, Any]]:
    """Query existing Knowledge Base RAG collection points via Qdrant query seam."""
    if not hasattr(qdrant, "scroll_points"):
        return []
    try:
        points = qdrant.scroll_points(
            collection_name,
            filter_payload={"project_name": CONST_RAG_KB_PROJECT},
            limit=limit,
            with_payload=True,
            with_vectors=True,
        )
        return points if isinstance(points, list) else []
    except (DevOpsCLIError, OSError, RuntimeError, ValueError) as exc:
        logger.debug("Failed querying Qdrant for KB points: %s", exc)
        return []


def _load_bundled_knowledge_base_nodes() -> list[dict[str, Any]]:
    """Fallback: load bundled Knowledge Base markdown articles when vector store is empty."""
    from devops_cli.ai.kb import list_knowledge_base_articles

    nodes: list[dict[str, Any]] = []
    for article_path in list_knowledge_base_articles():
        try:
            content = article_path.read_text(encoding="utf-8", errors="replace")
            nodes.append(
                {
                    "file_path": article_path.as_posix(),
                    "content": content,
                    "category": article_path.parent.name,
                    "vector": None,
                }
            )
        except OSError:
            continue
    return nodes


class AnalogicalPatternRetriever:
    """Surfaces cross-domain analogies via multi-vector topological clustering over the Knowledge Base."""

    def __init__(
        self,
        qdrant: Any | None = None,
        embedder: Any | None = None,
        docs_collection: str = DEFAULT_RAG_DOCS_COLLECTION,
    ) -> None:
        self.qdrant = qdrant
        self.embedder = embedder
        self.docs_collection = docs_collection

    def retrieve_analogies(
        self,
        query: str | None = None,
        source_domain: str | None = None,
        target_domain: str | None = None,
        min_score: float = DEFAULT_AI_ANALOGIES_MIN_SCORE,
        limit: int = DEFAULT_AI_ANALOGIES_LIMIT,
        fixture_nodes: list[dict[str, Any]] | None = None,
    ) -> list[CrossDomainAnalogy]:
        """Retrieve cross-domain analogies matching pattern isomorphisms."""
        if fixture_nodes is not None:
            nodes = fixture_nodes
        else:
            qdrant_points = _fetch_kb_points_from_qdrant(self.qdrant, self.docs_collection)
            if qdrant_points:
                nodes = [
                    {
                        "file_path": pt.get("payload", {}).get("file_path", str(pt.get("id"))),
                        "content": pt.get("payload", {}).get("content", ""),
                        "category": pt.get("payload", {}).get("category", ""),
                        "vector": pt.get("vector"),
                    }
                    for pt in qdrant_points
                ]
            else:
                nodes = _load_bundled_knowledge_base_nodes()

        return multi_vector_clustering(
            nodes,
            min_score=min_score,
            limit=limit,
            query=query,
            source_domain=source_domain,
            target_domain=target_domain,
        )


def render_analogies_table(analogies: list[CrossDomainAnalogy]) -> Table:
    """Render Rich table visualizing cross-domain pattern analogies."""
    table = Table(
        title="Cross-Domain Analogical Pattern Isomorphisms",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("#", justify="right", style="dim")
    table.add_column("Pattern", style="bold yellow")
    table.add_column("Source Domain / Module", style="green")
    table.add_column("Target Domain / Module", style="magenta")
    table.add_column("Score", justify="right", style="bold cyan")
    table.add_column("Shared Mechanisms", style="dim")

    for i, a in enumerate(analogies, start=1):
        src_label = (
            f"[{a.source_domain}] {Path(a.source).name}" if a.source_domain else Path(a.source).name
        )
        tgt_label = (
            f"[{a.target_domain}] {Path(a.target).name}" if a.target_domain else Path(a.target).name
        )
        mechs = ", ".join(a.shared_mechanisms[:3])
        table.add_row(str(i), a.pattern, src_label, tgt_label, f"{a.score:.2f}", mechs)
    return table


def render_analogies_markdown(analogies: list[CrossDomainAnalogy]) -> str:
    """Render cross-domain analogies report in GitHub-flavored Markdown."""
    lines = [
        "# Cross-Domain Analogical Pattern Report",
        "",
        "| # | Pattern | Source Module | Target Module | Score | Shared Mechanisms |",
        "| -: | :--- | :--- | :--- | -: | :--- |",
    ]
    for i, a in enumerate(analogies, start=1):
        mechs = ", ".join(a.shared_mechanisms) if a.shared_mechanisms else "—"
        lines.append(
            f"| {i} | {a.pattern} | `{a.source}` | `{a.target}` | {a.score:.4f} | {mechs} |"
        )

    lines.append("")
    lines.append("## Structural Isomorphism Details")
    lines.append("")
    for i, a in enumerate(analogies, start=1):
        lines.append(f"### {i}. {a.pattern} (Score: {a.score:.2f})")
        lines.append(f"- **Source**: `{a.source}` ({a.source_domain or 'unknown'})")
        lines.append(f"- **Target**: `{a.target}` ({a.target_domain or 'unknown'})")
        if a.shared_mechanisms:
            lines.append(f"- **Shared Invariant Mechanisms**: {', '.join(a.shared_mechanisms)}")
        if a.explanation:
            lines.append(f"- **Rationale**: {a.explanation}")
        lines.append("")

    return "\n".join(lines).strip()
