"""In-memory document tokenization, semantic chunking, and section retrieval benchmarks."""

from __future__ import annotations

import logging
import math
import random
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from devops_cli.ai.kb import get_knowledge_base_dir, list_knowledge_base_articles
from devops_cli.ai.task_loader import load_task_prompt

logger = logging.getLogger(__name__)


def get_builtin_test_document() -> str:
    """Load built-in test document specification from tasks/benchmark_builtin_spec.md."""
    return load_task_prompt("benchmark_builtin_spec.md")


# Built-in comprehensive DevOps specification used when no document path is provided
BUILTIN_TEST_DOCUMENT: str = get_builtin_test_document()


@dataclass(frozen=True)
class DocumentSectionChunk:
    """A tokenized and chunked section of a test document."""

    id: str
    section_index: int
    heading: str
    text: str
    token_count: int
    char_count: int


@dataclass(frozen=True)
class SectionRetrievalTask:
    """An evaluation retrieval task sampled from a document section."""

    id: str
    target_section_index: int
    target_heading: str
    query: str
    target_passage: str
    category: str


_DOMAIN_KB_TOPIC_MAP: dict[str, list[str]] = {
    "security": [
        "it_domains/topics/zero_trust_security_and_compliance.md",
        "devops_cli/tasks/security_audit_and_scanning.md",
        "it_domains/tools/bandit.md",
        "it_domains/tools/trivy.md",
        "it_domains/tools/keyring.md",
    ],
    "kubernetes": [
        "it_domains/topics/cloud_native_kubernetes_and_gitops.md",
        "devops_cli/tasks/k8s_stack_deployment.md",
        "it_domains/tools/kubectl.md",
        "it_domains/tools/helm.md",
        "it_domains/tools/kustomize.md",
        "it_domains/tools/minikube.md",
        "it_domains/tools/argocd.md",
        "it_domains/tools/kubelinter_popeye_pluto.md",
    ],
    "architecture": [
        "devops_cli/architecture.md",
        "it_domains/topics/modern_python_runtime_and_ecosystem.md",
        "it_domains/topics/agentic_ai_and_code_reviews.md",
        "it_domains/topics/rest_api_architecture_and_service_engineering.md",
        "devops_cli/tasks/ai_code_review.md",
        "devops_cli/tasks/agent_instructions_scaffolding.md",
        "it_domains/tools/fastapi_uvicorn.md",
        "it_domains/tools/ruff_mypy_pytest.md",
    ],
    "ci_cd": [
        "it_domains/topics/continuous_integration_and_progressive_verification.md",
        "it_domains/topics/release_engineering_and_semver_governance.md",
        "devops_cli/tasks/ci_quality_gate.md",
        "devops_cli/tasks/release_management.md",
        "it_domains/tools/github_cli.md",
        "it_domains/tools/actionlint.md",
    ],
    "infrastructure": [
        "devops_cli/configuration_and_settings.md",
        "it_domains/topics/infrastructure_as_code_and_cloud_automation.md",
        "it_domains/topics/observability_and_distributed_tracing.md",
        "it_domains/topics/developer_workstations_and_devcontainers.md",
        "devops_cli/tasks/infrastructure_provisioning.md",
        "devops_cli/tasks/telemetry_and_observability.md",
        "devops_cli/tasks/devcontainer_lifecycle.md",
        "it_domains/tools/opentofu_terraform.md",
        "it_domains/tools/grafana.md",
        "it_domains/tools/prometheus.md",
        "it_domains/tools/opentelemetry_jaeger.md",
        "it_domains/tools/docker.md",
        "devops_cli/tasks/rag_context_indexing.md",
    ],
}

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


def _read_architecture_extra_docs(repo_root: Path) -> list[str]:
    """Read extra architecture reference files if present."""
    extras: list[str] = []
    for extra in ("AGENTS.md", "docs/ARCHITECTURE.md"):
        p_extra = repo_root / extra
        if p_extra.is_file():
            try:
                extras.append(p_extra.read_text(encoding="utf-8"))
            except Exception:
                pass
    return extras


@lru_cache(maxsize=1)
def _get_domain_knowledge_base_index() -> dict[str, tuple[set[str], set[str]]]:
    """Dynamically index domain vocabularies and distinctive terms from the Knowledge Base."""
    kb_dir = get_knowledge_base_dir()
    repo_root = kb_dir.parent.parent.parent.parent
    domain_texts: dict[str, str] = {}
    domain_word_counts: dict[str, Counter[str]] = {}

    for domain, rel_paths in _DOMAIN_KB_TOPIC_MAP.items():
        doc_texts: list[str] = []
        for rel in rel_paths:
            path = kb_dir / rel
            if path.is_file():
                try:
                    doc_texts.append(path.read_text(encoding="utf-8"))
                except Exception:
                    pass

        if domain == "architecture":
            doc_texts.extend(_read_architecture_extra_docs(repo_root))

        full_text = " ".join(doc_texts).lower()
        domain_texts[domain] = full_text
        words = re.findall(r"\b[a-z0-9_-]{2,}\b", full_text)
        filtered_words = [w for w in words if w not in _STOPWORDS]
        domain_word_counts[domain] = Counter(filtered_words)

    num_domains = len(_DOMAIN_KB_TOPIC_MAP)
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

        top_terms = set(sorted(scores, key=lambda w: scores.get(w, 0.0), reverse=True)[:250])
        domain_index[domain] = (phrases, top_terms)

    return domain_index


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
    ) -> list[SectionRetrievalTask]:
        """Sample random sections and synthesize high-signal semantic retrieval queries."""
        if not chunks:
            return []

        # Stratified sampling across detected domain categories for balanced evaluation
        cat_to_indices: dict[str, list[int]] = {}
        for c_i, c in enumerate(chunks):
            cat = self._infer_category(c.heading, c.text)
            cat_to_indices.setdefault(cat, []).append(c_i)

        rng = random.Random(random_seed)
        selected_indices: list[int] = []
        # Sample evenly across all detected categories first
        cats = list(cat_to_indices.keys())
        per_cat = max(1, sample_count // len(cats)) if cats else 1
        for cat, idxs in cat_to_indices.items():
            k = min(per_cat, len(idxs))
            selected_indices.extend(rng.sample(idxs, k))

        # Fill remaining slots up to sample_count
        remaining_slots = sample_count - len(selected_indices)
        all_remaining = [i for i in range(len(chunks)) if i not in selected_indices]
        if remaining_slots > 0 and all_remaining:
            selected_indices.extend(
                rng.sample(all_remaining, min(remaining_slots, len(all_remaining)))
            )

        selected_indices = sorted(set(selected_indices))[:sample_count]

        tasks: list[SectionRetrievalTask] = []
        for task_idx, chunk_idx in enumerate(selected_indices):
            chunk = chunks[chunk_idx]
            query = self._synthesize_section_query(chunk)
            category = self._infer_category(chunk.heading, chunk.text)

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
    def _infer_category(cls, heading: str, text: str = "") -> str:
        """Categorize section heading and text content into standard DevOps domains."""
        norm_heading = heading.lower()
        norm_body = text.lower()
        norm_full = f"{norm_heading} {norm_body}"
        heading_words = set(re.findall(r"\b[a-z0-9_-]{2,}\b", norm_heading)) - _STOPWORDS
        body_words = set(re.findall(r"\b[a-z0-9_-]{2,}\b", norm_body)) - _STOPWORDS

        domain_index = _get_domain_knowledge_base_index()
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
        # Aggregate full documentation suite from knowledge base and repository
        candidate_paths: list[Path] = []

        # 1. Bundled Knowledge Base articles across topics, tools, and tasks
        candidate_paths.extend(list_knowledge_base_articles())

        # 2. Key architectural specifications and documentation
        for top_file in ("AGENTS.md", "README.md", "docs/ARCHITECTURE.md"):
            p = repo_root / top_file
            if p.exists():
                candidate_paths.append(p)

        docs_dir = repo_root / "docs"
        if docs_dir.exists():
            candidate_paths.extend(sorted(docs_dir.glob("*.md")))
            commands_dir = docs_dir / "commands"
            if commands_dir.exists():
                candidate_paths.extend(sorted(commands_dir.glob("*.md")))

        tasks_dir = repo_root / "src" / "devops_cli" / "ai" / "tasks"
        if tasks_dir.exists():
            candidate_paths.extend(sorted(tasks_dir.glob("*.md")))

        kb_dir = repo_root / "src" / "devops_cli" / "ai" / "knowledge_base"
        if kb_dir.exists():
            candidate_paths.extend(sorted(kb_dir.rglob("*.md")))

        seen_paths: set[Path] = set()
        for p in candidate_paths:
            if p in seen_paths or not p.is_file() or p.is_symlink():
                continue
            seen_paths.add(p)
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
                if txt.strip():
                    chunks = tokenizer.tokenize_and_chunk(txt, source_name=p.stem)
                    all_chunks.extend(chunks)
            except Exception:
                continue

    if not all_chunks:
        for p in list_knowledge_base_articles():
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
                if txt.strip():
                    chunks = tokenizer.tokenize_and_chunk(txt, source_name=p.stem)
                    all_chunks.extend(chunks)
            except Exception:
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
        indexed_chunks, sample_count=sample_count, random_seed=random_seed
    )
    corpus = [c.text for c in indexed_chunks]

    return eval_tasks, corpus, indexed_chunks
