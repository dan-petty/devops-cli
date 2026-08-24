"""Hybrid search re-ranking combining vector similarity, lexical scoring, and metadata."""

from __future__ import annotations

import re

from devops_cli.ai.rag.models import SearchResult

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
        vector_weight: float = 0.50,
        lexical_weight: float = 0.20,
        symbol_bonus: float = 0.15,
        declaration_bonus: float = 0.15,
        doc_intent_boost: float = 0.10,
        security_intent_boost: float = 0.10,
        structural_intent_boost: float = 0.10,
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
