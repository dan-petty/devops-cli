"""Agentic information foraging crawler following semantic scent across repository edges."""

from __future__ import annotations

import heapq
from pathlib import Path

from devops_cli.ai.lexical import bm25_scores, tokenize
from devops_cli.ai.research.edges import (
    extract_git_co_changes,
    extract_markdown_links,
    extract_python_imports,
)
from devops_cli.ai.research.models import (
    BacktrackEvent,
    ForageEdge,
    ForageNode,
    ForageTrail,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_FORAGE_FILE_READ_CAP_BYTES,
    DEFAULT_AI_FORAGE_MAX_NODES,
    DEFAULT_AI_FORAGE_MIN_SCORE,
)
from devops_cli.core.repo import find_repo_root, find_worktree_root


def _is_valid_candidate(p: Path) -> bool:
    return not p.is_symlink() and ".git" not in p.parts


def _iter_candidates(repo_root: Path) -> list[Path]:
    found: list[Path] = []
    for ext in ("*.py", "*.md"):
        for path in repo_root.rglob(ext):
            if _is_valid_candidate(path):
                found.append(path)
    return found


def _find_text_candidates(repo_root: Path, limit: int = 100) -> list[Path]:
    candidates: list[Path] = []
    for path in _iter_candidates(repo_root):
        candidates.append(path)
        if len(candidates) >= limit:
            break
    return candidates


def _search_keyword_anchor(repo_root: Path, keyword: str) -> str | None:
    kw_lower = keyword.lower()
    candidates = _find_text_candidates(repo_root, limit=100)

    exact_stem_matches = [
        p.relative_to(repo_root).as_posix() for p in candidates if kw_lower in p.stem.lower()
    ]
    if exact_stem_matches:
        return sorted(exact_stem_matches)[0]

    docs: list[str] = []
    rel_paths: list[str] = []
    for p in candidates:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")[
                :DEFAULT_AI_FORAGE_FILE_READ_CAP_BYTES
            ]
            docs.append(text)
            rel_paths.append(p.relative_to(repo_root).as_posix())
        except OSError:
            continue

    matches = bm25_scores(keyword, docs, limit=1)
    if matches:
        return rel_paths[matches[0].index]
    return rel_paths[0] if rel_paths else None


def _resolve_anchor_path(repo_root: Path, anchor: str) -> str:
    direct = (repo_root / anchor).resolve()
    if direct.is_file() and direct.is_relative_to(repo_root):
        return direct.relative_to(repo_root).as_posix()

    if direct.is_dir() and direct.is_relative_to(repo_root):
        for candidate in ("__init__.py", "README.md"):
            cand_file = direct / candidate
            if cand_file.is_file():
                return cand_file.relative_to(repo_root).as_posix()
        files = sorted(p for p in direct.glob("*.py") if p.is_file())
        if files:
            return files[0].relative_to(repo_root).as_posix()

    matched = _search_keyword_anchor(repo_root, anchor)
    if matched:
        return matched

    raise ValueError(f"Anchor '{anchor}' could not be resolved to any repository file.")


def _score_document_scent(repo_root: Path, rel_path: str, query: str) -> float:
    clean_query = query.strip()
    if not clean_query:
        return 0.0

    target = repo_root / rel_path
    try:
        content = target.read_text(encoding="utf-8", errors="replace")[
            :DEFAULT_AI_FORAGE_FILE_READ_CAP_BYTES
        ]
    except OSError:
        return 0.0

    matches = bm25_scores(clean_query, [content])
    base_score = matches[0].score if matches else 0.0

    path_lower = target.name.lower()
    query_tokens = tokenize(clean_query)
    name_bonus = sum(1.0 for token in query_tokens if token in path_lower)
    return round(base_score + name_bonus, 3)


class ForageCrawler:
    """Best-first information foraging crawler tracking semantic scent across code edges."""

    def __init__(
        self,
        repo_root: Path | None = None,
        max_nodes: int = DEFAULT_AI_FORAGE_MAX_NODES,
        min_score: float = DEFAULT_AI_FORAGE_MIN_SCORE,
    ) -> None:
        self.repo_root = (
            repo_root or find_worktree_root(Path.cwd()) or find_repo_root(Path.cwd()) or Path.cwd()
        )
        self.max_nodes = max_nodes
        self.min_score = min_score

    def extract_edges(self, rel_path: str) -> list[ForageEdge]:
        """Extract outbound edges from a file across all supported edge types."""
        full_path = self.repo_root / rel_path
        if not full_path.is_file():
            return []

        edges: list[ForageEdge] = []
        edges.extend(extract_python_imports(full_path, self.repo_root))
        edges.extend(extract_markdown_links(full_path, self.repo_root))
        edges.extend(extract_git_co_changes(full_path, self.repo_root))

        deduped: list[ForageEdge] = []
        seen: set[tuple[str, str, str]] = set()
        for edge in edges:
            key = (edge.source, edge.target, edge.edge_type)
            if key not in seen:
                seen.add(key)
                deduped.append(edge)
        return deduped

    def forage(self, anchor: str, query: str) -> ForageTrail:
        """Execute best-first information foraging traversal from anchor node."""
        start_node = _resolve_anchor_path(self.repo_root, anchor)
        start_score = _score_document_scent(self.repo_root, start_node, query)

        visited: set[str] = set()
        frontier: list[tuple[float, int, str, int, ForageEdge | None]] = []
        ledger_edges: list[ForageEdge] = []
        backtrack_events: list[BacktrackEvent] = []
        cycles_detected: list[list[str]] = []
        visited_nodes: list[ForageNode] = []

        counter = 0
        heapq.heappush(frontier, (-start_score, counter, start_node, 0, None))

        while frontier and len(visited_nodes) < self.max_nodes:
            neg_score, _, current_node, depth, inbound_edge = heapq.heappop(frontier)
            if current_node in visited:
                continue

            visited.add(current_node)
            score = -neg_score
            visited_nodes.append(
                ForageNode(
                    path=current_node,
                    score=score,
                    depth=depth,
                    edge_type=inbound_edge.edge_type if inbound_edge else None,
                    detail=inbound_edge.detail if inbound_edge else "",
                )
            )
            if inbound_edge:
                ledger_edges.append(inbound_edge)

            out_edges = self.extract_edges(current_node)
            unvisited_neighbors: list[tuple[str, ForageEdge, float]] = []

            for edge in out_edges:
                tgt = edge.target
                if tgt in visited:
                    cycles_detected.append([current_node, tgt])
                else:
                    counter += 1
                    neighbor_score = _score_document_scent(self.repo_root, tgt, query)
                    unvisited_neighbors.append((tgt, edge, neighbor_score))
                    heapq.heappush(frontier, (-neighbor_score, counter, tgt, depth + 1, edge))

            best_neighbor_score = (
                max(s for _, _, s in unvisited_neighbors) if unvisited_neighbors else 0.0
            )

            if best_neighbor_score < self.min_score and frontier:
                next_cand = frontier[0][2]
                unvisited_targets = {t for t, _, _ in unvisited_neighbors}
                if next_cand not in unvisited_targets:
                    backtrack_events.append(
                        BacktrackEvent(
                            from_node=current_node,
                            to_node=next_cand,
                            reason="low_scent",
                            score=best_neighbor_score,
                            threshold=self.min_score,
                        )
                    )

        ranked = sorted(visited_nodes, key=lambda n: (-n.score, n.path))
        return ForageTrail(
            anchor=start_node,
            query=query,
            visited_nodes=visited_nodes,
            edges=ledger_edges,
            backtrack_events=backtrack_events,
            cycles_detected=cycles_detected,
            ranked_trail=ranked,
        )
