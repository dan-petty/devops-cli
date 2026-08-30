"""ConversationSearch and history inspection capabilities."""

from __future__ import annotations

import logging
import math
import re
import time
import warnings
from collections import defaultdict
from collections.abc import Callable
from typing import Any, Literal, Protocol, cast, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.ai.agents.pydantic_agent import AgentTool, BaseCapability, RunContext, Tool
from devops_cli.ai.harness.constants import HarnessDeprecationWarning
from devops_cli.models.ai import ChatMessage

logger = logging.getLogger(__name__)


class RunRecord(BaseModel):
    """Execution record for a single run containing message turns and metadata."""

    model_config = ConfigDict(extra="ignore")

    run_id: str
    conversation_id: str | None = None
    messages: list[ChatMessage] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)


@runtime_checkable
class HistorySource(Protocol):
    """Protocol for conversation history data sources."""

    def get_runs(
        self,
        conversation_id: str | None = None,
        run_id: str | None = None,
    ) -> list[RunRecord]: ...


class SnapshotHistorySource(BaseModel):
    """History source that reads runs and step snapshots from persistence stores."""

    model_config = ConfigDict(extra="ignore")

    store: Any = None
    runs: dict[str, RunRecord] = Field(default_factory=dict)

    def __init__(self, store: Any = None, **data: Any) -> None:
        super().__init__(store=store, **data)

    def record_run(
        self,
        run_id: str,
        conversation_id: str | None = None,
        messages: list[ChatMessage | Any] | None = None,
    ) -> RunRecord:
        """Record or update a run record."""
        norm_msgs = [
            m if isinstance(m, ChatMessage) else ChatMessage.model_validate(m)
            for m in (messages or [])
        ]
        rec = RunRecord(run_id=run_id, conversation_id=conversation_id, messages=norm_msgs)
        self.runs[run_id] = rec
        return rec

    def get_runs(
        self,
        conversation_id: str | None = None,
        run_id: str | None = None,
    ) -> list[RunRecord]:
        """Fetch all in-scope run records matching conversation_id or run_id."""
        if self.store and hasattr(self.store, "get_runs") and callable(self.store.get_runs):
            try:
                external_runs = self.store.get_runs(conversation_id=conversation_id, run_id=run_id)
                if isinstance(external_runs, list):
                    return external_runs
            except Exception as e:
                logger.debug("Store get_runs error: %s", e)

        results: list[RunRecord] = []
        for r_id, r in self.runs.items():
            if run_id is not None and r_id != run_id:
                continue
            if conversation_id is not None and r.conversation_id != conversation_id:
                continue
            results.append(r)
        return results


class ConversationSearchMatch(BaseModel):
    """Matched turn snippet from conversation search with BM25 score and provenance."""

    model_config = ConfigDict(extra="ignore")

    run_id: str
    conversation_id: str | None = None
    role: str
    content: str
    snippet: str
    score: float
    turn_index: int


def bm25_rank(
    query: str,
    documents: list[dict[str, Any]],
    *,
    k1: float = 1.5,
    b: float = 0.75,
    max_matches: int = 10,
    context_lines: int = 5,
) -> list[ConversationSearchMatch]:
    """Pure Python BM25 ranking algorithm over conversation messages."""
    clean_q = query.strip().lower()
    if not clean_q or not documents:
        return []

    terms = list(dict.fromkeys(re.findall(r"\w+", clean_q)))
    if not terms:
        return []

    doc_tokens: list[list[str]] = []
    doc_lens: list[int] = []
    for doc in documents:
        tokens = re.findall(r"\w+", str(doc.get("content", "")).lower())
        doc_tokens.append(tokens)
        doc_lens.append(len(tokens))

    n_docs = len(documents)
    avg_dl = sum(doc_lens) / max(1, n_docs)

    doc_freqs: dict[str, int] = {}
    for term in terms:
        doc_freqs[term] = sum(1 for tokens in doc_tokens if term in tokens)

    matches: list[ConversationSearchMatch] = []
    for idx, (doc, tokens, doc_len) in enumerate(zip(documents, doc_tokens, doc_lens, strict=True)):
        if doc_len == 0:
            continue
        score = 0.0
        term_counts: dict[str, int] = defaultdict(int)
        for t in tokens:
            term_counts[t] += 1

        for term in terms:
            tf = term_counts.get(term, 0)
            if tf == 0:
                continue
            df = doc_freqs.get(term, 0)
            idf = max(0.0, ((n_docs - df + 0.5) / (df + 0.5))) + 1.0
            idf_score = math.log(idf)
            denom = tf + k1 * (1.0 - b + b * (doc_len / max(0.0001, avg_dl)))
            score += idf_score * (tf * (k1 + 1.0)) / max(0.0001, denom)

        if score > 0.0:
            content_str = str(doc.get("content", ""))
            lines = content_str.splitlines()
            snippet = "\n".join(lines[: max(1, context_lines)])
            matches.append(
                ConversationSearchMatch(
                    run_id=str(doc.get("run_id", "")),
                    conversation_id=doc.get("conversation_id"),
                    role=str(doc.get("role", "assistant")),
                    content=content_str,
                    snippet=snippet,
                    score=float(score),
                    turn_index=int(doc.get("turn_index", idx)),
                )
            )

    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:max_matches]


def _fetch_conversation_runs(
    source: Any, effective_scope: str, target_conv_id: str | None, run_id: str | None
) -> list[RunRecord]:
    """Fetch runs from source given scope and identifiers."""
    get_runs_fn = getattr(source, "get_runs", None)
    if not callable(get_runs_fn):
        return []
    conv_filter = target_conv_id if effective_scope == "conversation" else None
    res = get_runs_fn(conversation_id=conv_filter, run_id=run_id)
    return cast(list[RunRecord], res) if isinstance(res, list) else []


def _extract_conversation_documents(runs: list[RunRecord]) -> list[dict[str, Any]]:
    """Extract message turn records into searchable document dictionaries."""
    docs: list[dict[str, Any]] = []
    for r in runs:
        for turn_idx, m in enumerate(r.messages):
            c = getattr(m, "content", "") or ""
            if not c:
                continue
            docs.append(
                {
                    "run_id": r.run_id,
                    "conversation_id": r.conversation_id,
                    "role": getattr(m, "role", "user"),
                    "content": c,
                    "turn_index": turn_idx,
                }
            )
    return docs


class ConversationSearch(BaseCapability):
    """Capability providing BM25-ranked search over persisted conversation history."""

    id: str = "conversation_search"
    source: Any = None
    scope: Literal["conversation", "all"] | None = None
    max_matches: int = 10
    context_lines: int = 5
    bm25_k1: float = 1.5
    bm25_b: float = 0.75
    add_instructions: bool = True
    tool_id: str = "conversation-search"

    def __init__(
        self,
        source: Any,
        *,
        scope: Literal["conversation", "all"] | None = None,
        max_matches: int = 10,
        context_lines: int = 5,
        bm25_k1: float = 1.5,
        bm25_b: float = 0.75,
        add_instructions: bool = True,
        tool_id: str = "conversation-search",
        id: str | None = None,
    ) -> None:
        effective_scope = "conversation"
        if scope is not None:
            effective_scope = scope
        else:
            warnings.warn(
                "ConversationSearch scope was unset; defaulting to 'conversation'.",
                category=HarnessDeprecationWarning,
                stacklevel=2,
            )

        super().__init__(
            id=str(id or "conversation_search"),
            source=source,
            scope=effective_scope,
            max_matches=max_matches,
            context_lines=context_lines,
            bm25_k1=bm25_k1,
            bm25_b=bm25_b,
            add_instructions=add_instructions,
            tool_id=tool_id,
        )

    @property
    def effective_scope(self) -> Literal["conversation", "all"]:
        return self.scope or "conversation"

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        if not self.add_instructions:
            return []
        scope_note = (
            "within this conversation"
            if self.effective_scope == "conversation"
            else "across all recorded conversations"
        )
        return [
            f"You have access to the search_conversation_history tool to search past interaction turns {scope_note}."
        ]

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        source = self.source
        effective_scope = self.effective_scope
        k1 = self.bm25_k1
        b = self.bm25_b
        max_k = self.max_matches
        ctx_lines = self.context_lines

        def search_conversation_history(
            query: str,
            run_id: str | None = None,
            conversation_id: str | None = None,
        ) -> str:
            """Search earlier turns from persisted conversation history using BM25 relevance."""
            try:
                target_conv_id = (
                    conversation_id if effective_scope == "all" else (conversation_id or "default")
                )
                runs = _fetch_conversation_runs(source, effective_scope, target_conv_id, run_id)
                if not runs:
                    return f"No persisted conversation history found for search query '{query}'."

                documents = _extract_conversation_documents(runs)
                matches = bm25_rank(
                    query=query,
                    documents=documents,
                    k1=k1,
                    b=b,
                    max_matches=max_k,
                    context_lines=ctx_lines,
                )

                if not matches:
                    return f"No matching conversation turns found for '{query}'."

                results = [f"Found {len(matches)} historical match(es):"]
                results.extend(
                    f"--- [run: {m.run_id}{f' | conversation: {m.conversation_id}' if m.conversation_id else ''} | role: {m.role} | score: {m.score:.2f}] ---\n{m.snippet}"
                    for m in matches
                )
                return "\n\n".join(results)
            except Exception as e:
                return f"Error searching conversation history: {e}"

        return [
            Tool.from_function(
                search_conversation_history,
                name="search_conversation_history",
                description="Search earlier conversation history and past runs with BM25 keyword matching.",
            )
        ]
