"""Hybrid search re-ranking combining vector similarity, lexical scoring, and metadata."""

from __future__ import annotations

import re

from devops_cli.ai.rag.models import SearchResult
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

        scored_results: list[SearchResult] = []

        for r in results:
            chunk = r.chunk
            chunk_tokens = set(re.findall(r"\w+", chunk.content.lower()))
            file_tokens = set(re.findall(r"\w+", chunk.file_path.lower()))

            # 1. Lexical Token Overlap Jaccard / Overlap Score
            if query_tokens:
                token_overlap = len(query_tokens & (chunk_tokens | file_tokens)) / len(query_tokens)
            else:
                token_overlap = 0.0

            # 2. Exact Symbol Match Bonus
            symbol_match = False
            symbols_lower = [s.lower() for s in chunk.symbol_names]
            for q_tok in query_tokens:
                if len(q_tok) > 2 and any(q_tok in s for s in symbols_lower):
                    symbol_match = True
                    break

            symbol_score = 1.0 if symbol_match else 0.0

            # 3. Declaration Primacy Bonus (actual definition site)
            declarations = [d.lower() for d in chunk.metadata.get("declarations", [])]
            declaration_match = False
            for q_tok in query_tokens:
                if len(q_tok) > 2 and any(q_tok == d or q_tok in d for d in declarations):
                    declaration_match = True
                    break

            decl_score = 1.0 if declaration_match else 0.0

            # 4. Intent Alignment Score
            intent_score = 0.0
            if is_doc_intent and chunk.category == "docs":
                intent_score += 1.0
            elif is_code_intent and chunk.category in ("code", "iac"):
                intent_score += 1.0

            # 5. Security Alignment Score
            sec_tags: list[str] = chunk.metadata.get("security_tags", [])
            sec_score = 0.0
            if sec_tags and any(
                tag in query.lower()
                for tag in ("sec", "auth", "token", "key", "cert", "tls", "crypto", "sql", "db")
            ):
                sec_score = 1.0

            # 6. Structural Domain / Framework Alignment
            struct_tags: list[str] = chunk.metadata.get("structural_tags", [])
            frameworks: list[str] = chunk.metadata.get("frameworks", [])
            struct_score = 0.0
            if struct_tags and any(st in query_tokens for st in struct_tags):
                struct_score += 0.5
            if frameworks and any(fw in query_tokens for fw in frameworks):
                struct_score += 0.5

            # 7. Test Alignment vs Production Code Prioritization
            is_test_chunk = (
                chunk.metadata.get("is_test", False) or "test_" in chunk.file_path.lower()
            )
            test_penalty = 0.0
            if is_test_chunk and not is_qa_intent:
                test_penalty = 0.10
            elif is_test_chunk and is_qa_intent:
                intent_score += 1.0

            # Composite hybrid score calculation
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

            factors: dict[str, float] = {
                "vector": round(base_vector_score, 4),
                "lexical": round(token_overlap, 4),
                "symbol": round(symbol_score, 4),
                "declaration": round(decl_score, 4),
                "intent": round(intent_score, 4),
                "security": round(sec_score, 4),
                "structural": round(struct_score, 4),
            }

            r.rerank_score = round(fused_score, 4)
            r.rank_factors = factors
            scored_results.append(r)

        # Sort descending by composite rerank score
        scored_results.sort(key=lambda x: x.rerank_score or 0.0, reverse=True)

        if top_k is not None and top_k > 0:
            return scored_results[:top_k]
        return scored_results


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
