"""In-memory document tokenization, semantic chunking, and section retrieval benchmarks."""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.defaults import DEFAULT_MAX_AST_FILE_SIZE_BYTES
from devops_cli.core.draws import seeded_sample

logger = logging.getLogger(__name__)


def get_builtin_test_document() -> str:
    """Load built-in test document specification from tasks/benchmark_builtin_spec.md."""
    return load_task_prompt("benchmark_builtin_spec.md")


# Built-in comprehensive DevOps specification used when no document path is provided
BUILTIN_TEST_DOCUMENT: str = get_builtin_test_document()


class DocumentSectionChunk(BaseModel):
    """A tokenized and chunked section of a test document."""

    model_config = ConfigDict(frozen=True)

    id: str
    section_index: int
    heading: str
    text: str
    token_count: int
    char_count: int


class SectionRetrievalTask(BaseModel):
    """An evaluation retrieval task sampled from a document section."""

    model_config = ConfigDict(frozen=True)

    id: str
    target_section_index: int
    target_heading: str
    query: str
    target_passage: str
    category: str


# The docs pages that hold the vocabulary of each domain, relative to the repository root. The
# benchmark labels its evaluation tasks from these pages, so a removal of the bundled knowledge
# base folder changes no category (#3902).
_DOMAIN_DOCS_TOPIC_MAP: dict[str, list[str]] = {
    "security": [
        "docs/commands/scan.md",
        "docs/commands/vault.md",
        "docs/commands/tls.md",
        "docs/commands/ssh.md",
        "docs/commands/cloudflare.md",
    ],
    "kubernetes": [
        "docs/CLUSTER.md",
        "docs/guidelines/kubernetes.md",
        "docs/commands/k8s.md",
        "docs/commands/kustomize.md",
        "docs/commands/argo.md",
    ],
    "architecture": [
        "docs/DESIGN.md",
        "docs/SERVICE_PATTERNS.md",
        "docs/MCP_TOOLS.md",
        "docs/commands/new.md",
        "docs/commands/serve.md",
        "docs/cheatsheets/ai_and_rag.md",
    ],
    "ci_cd": [
        "docs/commands/ci.md",
        "docs/commands/test.md",
        "docs/commands/lint.md",
        "docs/commands/pr.md",
        "docs/TESTING.md",
    ],
    "infrastructure": [
        "docs/TELEMETRY.md",
        "docs/CONFIGURATION.md",
        "docs/ENV_VARS.md",
        "docs/DEVCONTAINER_USAGE.md",
        "docs/commands/infra.md",
        "docs/commands/tf.md",
        "docs/commands/grafana.md",
        "docs/commands/prometheus.md",
        "docs/commands/docker.md",
        "docs/commands/telemetry.md",
        "docs/commands/devcontainer.md",
    ],
}

# The top-level documents of the repository that the benchmark corpus reads beside the docs pages.
_CORPUS_TOP_LEVEL_DOCUMENTS: tuple[str, ...] = ("AGENTS.md", "README.md")

# The directory of the task prompts that the benchmark corpus reads.
_CORPUS_PROMPTS_DIR = "src/devops_cli/ai/tasks"

_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "in",
        "on",
        "at",
        "to",
        "for",
        "with",
        "by",
        "from",
        "of",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "that",
        "this",
        "it",
        "as",
        "all",
        "can",
        "must",
        "should",
        "will",
        "used",
        "using",
        "use",
        "into",
        "when",
        "how",
        "devops",
        "md",
        "about",
        "such",
        "than",
        "then",
        "more",
        "most",
        "also",
        "other",
        "prevent",
        "increase",
        "ensuring",
        "ensure",
        "providing",
        "provide",
        "best",
        "practice",
    }
)


def _read_domain_docs(repo_root: Path, rel_paths: Sequence[str]) -> list[str]:
    """Read the docs pages of one domain under the root, with path containment."""
    root_resolved = repo_root.resolve()
    doc_texts: list[str] = []
    for rel in rel_paths:
        path = repo_root / rel
        try:
            resolved = path.resolve()
            if not resolved.is_relative_to(root_resolved) or path.is_symlink():
                continue
            if resolved.is_file() and resolved.stat().st_size <= DEFAULT_MAX_AST_FILE_SIZE_BYTES:
                doc_texts.append(resolved.read_text(encoding="utf-8", errors="replace"))
        except OSError, RuntimeError:
            continue
    return doc_texts


def document_corpus_paths(repo_root: Path) -> list[Path]:
    """The Markdown pages of the benchmark corpus under the root: the docs directory, which holds
    the generated knowledge base index, the top-level documents and the task prompts (#3902)."""
    paths = [
        path
        for path in sorted((repo_root / "docs").rglob("*.md"))
        if path.is_file() and not path.is_symlink()
    ]
    paths.extend(
        repo_root / name for name in _CORPUS_TOP_LEVEL_DOCUMENTS if (repo_root / name).is_file()
    )
    paths.extend(
        path
        for path in sorted((repo_root / _CORPUS_PROMPTS_DIR).glob("*.md"))
        if path.is_file() and not path.is_symlink()
    )
    return paths


@lru_cache(maxsize=8)
def document_domain_index(repo_root: Path) -> dict[str, tuple[set[str], set[str]]]:
    """Index the phrases and the distinctive terms of each domain from its docs pages (#3902)."""
    domain_texts: dict[str, str] = {}
    domain_word_counts: dict[str, Counter[str]] = {}

    for domain, rel_paths in _DOMAIN_DOCS_TOPIC_MAP.items():
        full_text = " ".join(_read_domain_docs(repo_root, rel_paths)).lower()
        domain_texts[domain] = full_text
        words = re.findall(r"\b[a-z0-9_-]{2,}\b", full_text)
        filtered_words = [w for w in words if w not in _STOPWORDS]
        domain_word_counts[domain] = Counter(filtered_words)

    num_domains = len(_DOMAIN_DOCS_TOPIC_MAP)
    domain_index: dict[str, tuple[set[str], set[str]]] = {}

    for domain, counts in domain_word_counts.items():
        text = domain_texts.get(domain, "")
        phrases: set[str] = set()
        for match in re.finditer(r"(?m)^#{1,4}\s+(.+)$|\*\*([^*]+)\*\*", text):
            phrase_cand = (match.group(1) or match.group(2) or "").strip().lower()
            if 3 <= len(phrase_cand) <= 40 and not any(
                ch in phrase_cand for ch in ("`", "[", "]", "(", ")")
            ):
                phrases.add(phrase_cand)

        scores: dict[str, float] = {}
        for word, count in counts.items():
            doc_freq = sum(1 for d in domain_word_counts if word in domain_word_counts[d])
            idf = math.log((num_domains + 1) / (doc_freq + 0.5)) + 1.0
            scores[word] = count * idf

        top_terms = set(sorted(scores, key=lambda w: scores.get(w, 0.0), reverse=True)[:1000])
        domain_index[domain] = (phrases, top_terms)

    return domain_index


def reset_document_chunker_cache() -> None:
    """Clear the cached docs domain vocabulary index."""
    document_domain_index.cache_clear()


def _build_section_chunk(
    words_slice: list[str], heading: str, source_name: str, s_idx: int, chunk_counter: int
) -> DocumentSectionChunk:
    """Construct DocumentSectionChunk from word slice."""
    chunk_text = " ".join(words_slice)
    return DocumentSectionChunk(
        id=f"{source_name}-sec{s_idx + 1}-chunk{chunk_counter + 1}",
        section_index=chunk_counter,
        heading=heading,
        text=chunk_text,
        token_count=len(words_slice),
        char_count=len(chunk_text),
    )


class InMemoryDocumentTokenizer:
    """Performs in-memory tokenization, semantic chunking, and evaluation task generation."""

    def __init__(
        self,
        chunk_size_words: int = 100,
        chunk_overlap_words: int = 20,
        min_chunk_words: int = 25,
    ) -> None:
        self.chunk_size_words = chunk_size_words
        self.chunk_overlap_words = chunk_overlap_words
        self.min_chunk_words = min_chunk_words

    def tokenize_and_chunk(
        self,
        document_text: str,
        source_name: str = "document",
    ) -> list[DocumentSectionChunk]:
        """Split document text into heading-aware semantic chunks."""
        sections = re.split(r"(?m)(?=^#{1,3}\s+)", document_text)
        chunks: list[DocumentSectionChunk] = []
        chunk_counter = 0

        for s_idx, sec in enumerate(sections):
            sec_text = sec.strip()
            if not sec_text:
                continue

            lines = sec_text.splitlines()
            heading = lines[0].lstrip("#").strip() if lines else f"Section {s_idx + 1}"

            words = sec_text.split()
            if not words:
                continue

            step = max(1, self.chunk_size_words - self.chunk_overlap_words)
            effective_min = min(self.min_chunk_words, max(5, self.chunk_size_words // 4))
            for w_idx in range(0, len(words), step):
                chunk_slice = words[w_idx : w_idx + self.chunk_size_words]
                if (len(chunk_slice) < effective_min and w_idx > 0 and chunks) or not chunk_slice:
                    continue

                chunks.append(
                    _build_section_chunk(chunk_slice, heading, source_name, s_idx, chunk_counter)
                )
                chunk_counter += 1

        return chunks

    def sample_evaluation_tasks(
        self,
        chunks: list[DocumentSectionChunk],
        sample_count: int = 15,
        random_seed: int = 42,
        repo_root: Path | None = None,
    ) -> list[SectionRetrievalTask]:
        """Sample random sections and synthesize high-signal semantic retrieval queries."""
        if not chunks:
            return []

        # Stratified sampling across detected domain categories for balanced evaluation
        cat_to_indices: dict[str, list[int]] = {}
        for c_i, c in enumerate(chunks):
            cat = self._infer_category(c.heading, c.text, repo_root)
            cat_to_indices.setdefault(cat, []).append(c_i)

        selected_indices: list[int] = []
        # Sample evenly across all detected categories first; the seed repeats the sample.
        cats = list(cat_to_indices.keys())
        per_cat = max(1, sample_count // len(cats)) if cats else 1
        for cat, idxs in cat_to_indices.items():
            k = min(per_cat, len(idxs))
            selected_indices.extend(seeded_sample(idxs, k, f"{random_seed}:{cat}"))

        # Fill remaining slots up to sample_count
        remaining_slots = sample_count - len(selected_indices)
        all_remaining = [i for i in range(len(chunks)) if i not in selected_indices]
        if remaining_slots > 0 and all_remaining:
            selected_indices.extend(
                seeded_sample(
                    all_remaining, min(remaining_slots, len(all_remaining)), f"{random_seed}:rest"
                )
            )

        selected_indices = sorted(set(selected_indices))[:sample_count]

        tasks: list[SectionRetrievalTask] = []
        for task_idx, chunk_idx in enumerate(selected_indices):
            chunk = chunks[chunk_idx]
            query = self._synthesize_section_query(chunk)
            category = self._infer_category(chunk.heading, chunk.text, repo_root)

            tasks.append(
                SectionRetrievalTask(
                    id=f"eval-task-{task_idx + 1}",
                    target_section_index=chunk_idx,
                    target_heading=chunk.heading,
                    query=query,
                    target_passage=chunk.text,
                    category=category,
                )
            )

        return tasks

    def _synthesize_section_query(self, chunk: DocumentSectionChunk) -> str:
        """Synthesize natural semantic query from section heading and technical content."""
        sentences = [
            s.strip() for s in re.split(r"(?<=[.!?])\s+", chunk.text) if len(s.strip()) > 20
        ]

        # Extract primary technical assertion
        if sentences:
            first_sentence = sentences[0]
            # Clean leading markdown headers from sentence
            first_sentence = re.sub(r"^#+\s*[^.]*?\n+", "", first_sentence).strip()
            if len(first_sentence) > 30:
                return f"{chunk.heading}: {first_sentence}"

        return f"Retrieve section regarding {chunk.heading}"

    @classmethod
    def _infer_category(cls, heading: str, text: str = "", repo_root: Path | None = None) -> str:
        """Categorize section heading and text content into standard DevOps domains."""
        norm_heading = heading.lower()
        norm_body = text.lower()
        norm_full = f"{norm_heading} {norm_body}"
        heading_words = set(re.findall(r"\b[a-z0-9_-]{2,}\b", norm_heading)) - _STOPWORDS
        body_words = set(re.findall(r"\b[a-z0-9_-]{2,}\b", norm_body)) - _STOPWORDS

        domain_index = document_domain_index(repo_root or Path.cwd())
        scores: dict[str, int] = {}
        for domain, (phrases, terms) in domain_index.items():
            phrase_score = sum(3 for p in phrases if p in norm_full)
            h_score = len(heading_words & terms) * 2
            b_score = len(body_words & terms)
            total = phrase_score + h_score + b_score
            if total > 0:
                scores[domain] = total

        if not scores:
            return "infrastructure"

        return max(scores.items(), key=lambda item: item[1])[0]


def _collect_chunks_from_path(
    document_path: Path, safe_base: Path, tokenizer: InMemoryDocumentTokenizer
) -> list[DocumentSectionChunk]:
    """Safely traverse and tokenize markdown files under document_path."""
    resolved_doc = document_path.resolve()
    if not (resolved_doc == safe_base or resolved_doc.is_relative_to(safe_base)):
        return []

    chunks: list[DocumentSectionChunk] = []
    if document_path.is_file() and not document_path.is_symlink():
        try:
            txt = document_path.read_text(encoding="utf-8", errors="replace")
            chunks.extend(tokenizer.tokenize_and_chunk(txt, source_name=document_path.stem))
        except Exception:
            pass
        return chunks

    if document_path.is_dir():
        for p in sorted(document_path.rglob("*.md")):
            try:
                if p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(safe_base):
                    continue
                txt = p.read_text(encoding="utf-8", errors="replace")
                if txt.strip():
                    chunks.extend(tokenizer.tokenize_and_chunk(txt, source_name=p.stem))
            except Exception:
                continue
    return chunks


def load_test_document_corpus(
    document_path: Path | None = None,
    repo_root: Path | None = None,
    chunk_size_words: int = 100,
    chunk_overlap_words: int = 20,
    sample_count: int = 20,
    random_seed: int = 42,
) -> tuple[list[SectionRetrievalTask], list[str], list[DocumentSectionChunk]]:
    """Load test document corpus, tokenize in memory, and generate evaluation tasks."""
    tokenizer = InMemoryDocumentTokenizer(
        chunk_size_words=chunk_size_words,
        chunk_overlap_words=chunk_overlap_words,
    )

    all_chunks: list[DocumentSectionChunk] = []
    safe_base = (
        repo_root
        or (
            document_path
            if (document_path and document_path.is_dir())
            else (document_path.parent if document_path else Path.cwd())
        )
    ).resolve()

    if document_path and document_path.exists():
        all_chunks.extend(_collect_chunks_from_path(document_path, safe_base, tokenizer))
    elif repo_root:
        for p in document_corpus_paths(repo_root):
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
                if txt.strip():
                    all_chunks.extend(tokenizer.tokenize_and_chunk(txt, source_name=p.stem))
            except OSError:
                continue

    if not all_chunks:
        chunks = tokenizer.tokenize_and_chunk(BUILTIN_TEST_DOCUMENT, source_name="builtin-spec")
        all_chunks.extend(chunks)

    # Re-index section indices monotonically
    indexed_chunks: list[DocumentSectionChunk] = []
    for i, c in enumerate(all_chunks):
        indexed_chunks.append(
            DocumentSectionChunk(
                id=f"{c.id}-{i + 1}",
                section_index=i,
                heading=c.heading,
                text=c.text,
                token_count=c.token_count,
                char_count=c.char_count,
            )
        )

    eval_tasks = tokenizer.sample_evaluation_tasks(
        indexed_chunks,
        sample_count=sample_count,
        random_seed=random_seed,
        repo_root=(repo_root or Path.cwd()),
    )
    corpus = [c.text for c in indexed_chunks]

    return eval_tasks, corpus, indexed_chunks
