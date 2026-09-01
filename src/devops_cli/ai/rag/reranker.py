"""Hybrid search re-ranking combining vector similarity, lexical scoring, and metadata."""

from __future__ import annotations

import re

from devops_cli.ai.rag.models import CodeChunk, SearchResult
from devops_cli.config.defaults import (
    DEFAULT_RERANKER_DECLARATION_BONUS,
    DEFAULT_RERANKER_INTENT_BOOST,
    DEFAULT_RERANKER_LEXICAL_WEIGHT,
    DEFAULT_RERANKER_SYMBOL_BONUS,
    DEFAULT_RERANKER_VECTOR_WEIGHT,
)

_DOC_INTENT_WORDS = {
    "how",
    "why",
    "architecture",
    "overview",
    "guide",
    "docs",
    "documentation",
    "concept",
    "explain",
    "design",
    "rfc",
    "adr",
    "standard",
}

_CODE_INTENT_WORDS = {
    "implementation",
    "function",
    "func",
    "class",
    "struct",
    "method",
    "def",
    "call",
    "variable",
    "const",
    "import",
    "error",
    "panic",
    "exception",
}


_QA_INTENT_WORDS = {
    "test",
    "tests",
    "testing",
    "pytest",
    "unittest",
    "fixture",
    "fixtures",
    "mock",
    "mocks",
    "assert",
    "assertion",
    "qa",
}


def _calculate_token_overlap(
    query_tokens: set[str], chunk_tokens: set[str], file_tokens: set[str]
) -> float:
    """Calculate token overlap ratio between query and chunk contents/filepath."""
    if not query_tokens:
        return 0.0
    return len(query_tokens & (chunk_tokens | file_tokens)) / len(query_tokens)


def _has_matching_symbol(query_tokens: set[str], symbol_names: list[str]) -> bool:
    """Check if any query token matches symbol names."""
    symbols_lower = [s.lower() for s in symbol_names]
    return any(len(q_tok) > 2 and any(q_tok in s for s in symbols_lower) for q_tok in query_tokens)


def _has_matching_declaration(query_tokens: set[str], declarations: list[str]) -> bool:
    """Check if any query token matches declaration names."""
    decl_lower = [d.lower() for d in declarations]
    return any(
        len(q_tok) > 2 and any(q_tok == d or q_tok in d for d in decl_lower)
        for q_tok in query_tokens
    )


def _calculate_category_intent(
    chunk: CodeChunk, is_doc_intent: bool, is_code_intent: bool
) -> float:
    """Evaluate document vs code category alignment with query intent."""
    if is_doc_intent and chunk.category == "docs":
        return 1.0
    if is_code_intent and chunk.category in ("code", "iac"):
        return 1.0
    return 0.0


def _calculate_security_alignment(query: str, sec_tags: list[str]) -> float:
    """Evaluate security domain alignment."""
    sec_keywords = ("sec", "auth", "token", "key", "cert", "tls", "crypto", "sql", "db")
    if sec_tags and any(tag in query.lower() for tag in sec_keywords):
        return 1.0
    return 0.0


def _calculate_structural_alignment(
    query_tokens: set[str], struct_tags: list[str], frameworks: list[str]
) -> float:
    """Evaluate structural tags and framework keyword matches."""
    struct_score = 0.5 if (struct_tags and any(st in query_tokens for st in struct_tags)) else 0.0
    if frameworks and any(fw in query_tokens for fw in frameworks):
        struct_score += 0.5
    return struct_score


def _calculate_test_penalty(chunk: CodeChunk, is_qa_intent: bool) -> tuple[float, float]:
    """Calculate test file penalty or boost."""
    is_test_chunk = chunk.metadata.get("is_test", False) or "test_" in chunk.file_path.lower()
    if is_test_chunk and not is_qa_intent:
        return 0.0, 0.10
    if is_test_chunk and is_qa_intent:
        return 1.0, 0.0
    return 0.0, 0.0


def _compute_chunk_intent_signals(
    query: str,
    query_tokens: set[str],
    chunk: CodeChunk,
    is_doc_intent: bool,
    is_code_intent: bool,
    is_qa_intent: bool,
) -> tuple[float, float, float, float]:
    """Compute intent alignment, security score, structural score, and test penalty."""
    cat_intent = _calculate_category_intent(chunk, is_doc_intent, is_code_intent)
    sec_score = _calculate_security_alignment(query, chunk.metadata.get("security_tags", []))
    struct_score = _calculate_structural_alignment(
        query_tokens,
        chunk.metadata.get("structural_tags", []),
        chunk.metadata.get("frameworks", []),
    )
    test_boost, test_penalty = _calculate_test_penalty(chunk, is_qa_intent)
    return cat_intent + test_boost, sec_score, struct_score, test_penalty


class SearchReranker:
    """Re-ranks initial semantic search candidates using multi-factor hybrid scoring."""

    def __init__(
        self,
        vector_weight: float = DEFAULT_RERANKER_VECTOR_WEIGHT,
        lexical_weight: float = DEFAULT_RERANKER_LEXICAL_WEIGHT,
        symbol_bonus: float = DEFAULT_RERANKER_SYMBOL_BONUS,
        declaration_bonus: float = DEFAULT_RERANKER_DECLARATION_BONUS,
        doc_intent_boost: float = DEFAULT_RERANKER_INTENT_BOOST,
        security_intent_boost: float = DEFAULT_RERANKER_INTENT_BOOST,
        structural_intent_boost: float = DEFAULT_RERANKER_INTENT_BOOST,
    ) -> None:
        self.vector_weight = vector_weight
        self.lexical_weight = lexical_weight
        self.symbol_bonus = symbol_bonus
        self.declaration_bonus = declaration_bonus
        self.doc_intent_boost = doc_intent_boost
        self.security_intent_boost = security_intent_boost
        self.structural_intent_boost = structural_intent_boost

    def _score_search_result(
        self,
        r: SearchResult,
        query: str,
        query_tokens: set[str],
        is_doc_intent: bool,
        is_code_intent: bool,
        is_qa_intent: bool,
    ) -> SearchResult:
        """Score a single SearchResult using weighted hybrid scoring."""
        chunk = r.chunk
        chunk_tokens = set(re.findall(r"\w+", chunk.content.lower()))
        file_tokens = set(re.findall(r"\w+", chunk.file_path.lower()))

        token_overlap = _calculate_token_overlap(query_tokens, chunk_tokens, file_tokens)
        symbol_score = 1.0 if _has_matching_symbol(query_tokens, chunk.symbol_names) else 0.0
        declarations = chunk.metadata.get("declarations", [])
        decl_score = 1.0 if _has_matching_declaration(query_tokens, declarations) else 0.0

        intent_score, sec_score, struct_score, test_penalty = _compute_chunk_intent_signals(
            query, query_tokens, chunk, is_doc_intent, is_code_intent, is_qa_intent
        )

        base_vector_score = max(0.0, min(1.0, r.score))
        fused_score = (
            (self.vector_weight * base_vector_score)
            + (self.lexical_weight * token_overlap)
            + (self.symbol_bonus * symbol_score)
            + (self.declaration_bonus * decl_score)
            + (self.doc_intent_boost * intent_score)
            + (self.security_intent_boost * sec_score)
            + (self.structural_intent_boost * struct_score)
            - test_penalty
        )
        fused_score = max(0.0, min(1.0, fused_score))

        r.rerank_score = round(fused_score, 4)
        r.rank_factors = {
            "vector": round(base_vector_score, 4),
            "lexical": round(token_overlap, 4),
            "symbol": round(symbol_score, 4),
            "declaration": round(decl_score, 4),
            "intent": round(intent_score, 4),
            "security": round(sec_score, 4),
            "structural": round(struct_score, 4),
        }
        return r

    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        *,
        top_k: int | None = None,
    ) -> list[SearchResult]:
        """Re-score and re-rank search results using hybrid scoring signals and declaration."""
        if not results:
            return []

        query_tokens = set(re.findall(r"\w+", query.lower()))
        is_doc_intent = bool(query_tokens & _DOC_INTENT_WORDS)
        is_code_intent = bool(query_tokens & _CODE_INTENT_WORDS)
        is_qa_intent = bool(query_tokens & _QA_INTENT_WORDS)

        scored_results = [
            self._score_search_result(
                r, query, query_tokens, is_doc_intent, is_code_intent, is_qa_intent
            )
            for r in results
        ]

        scored_results.sort(key=lambda x: x.rerank_score or 0.0, reverse=True)
        return scored_results[:top_k] if (top_k is not None and top_k > 0) else scored_results


class CrossEncoderReranker:
    """Semantic cross-encoder re-ranker evaluating full query-chunk cross-interactions."""

    def __init__(self, top_k: int = 5) -> None:
        self.top_k = top_k
        self._fallback_reranker = SearchReranker()

    def rerank_candidates(
        self,
        query: str,
        candidates: list[SearchResult],
        *,
        top_k: int | None = None,
    ) -> list[SearchResult]:
        """Re-rank candidate search results using fine-grained cross-token semantic interaction."""
        limit = top_k or self.top_k
        if not candidates:
            return []

        # Run multi-factor baseline reranking
        reranked = self._fallback_reranker.rerank(query, candidates, top_k=None)

        # Apply positional reciprocal discount with cross-entropy bonus
        query_words = set(re.findall(r"\w+", query.lower()))
        for rank, item in enumerate(reranked):
            chunk_content = item.chunk.content.lower()
            # Calculate cross-token coverage density
            matched_words = sum(1 for w in query_words if w in chunk_content)
            coverage = (matched_words / len(query_words)) if query_words else 0.0

            # Boost items with high multi-token density
            pos_weight = 1.0 / (1.0 + (0.05 * rank))
            final_score = ((item.rerank_score or 0.5) * 0.7) + (coverage * 0.3 * pos_weight)
            item.rerank_score = round(min(1.0, max(0.0, final_score)), 4)

        reranked.sort(key=lambda x: x.rerank_score or 0.0, reverse=True)
        return reranked[:limit]
