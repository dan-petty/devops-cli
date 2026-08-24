"""In-memory document tokenization, semantic chunking, and section retrieval benchmarks."""

from __future__ import annotations

import logging
import random
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Built-in comprehensive DevOps specification used when no document path is provided
BUILTIN_TEST_DOCUMENT: str = """# Enterprise DevOps & Agentic Infrastructure Architecture

## 1. Zero-Trust Security, Secret Storage & Network Egress
Modern cloud-native workstations and CI/CD automation systems must operate under zero-trust.
Plaintext API tokens and cloud keys must never be stored in files, env vars, or logs.
The devops_cli.config.keyring subsystem interfaces directly with native OS secret stores:
- Linux: SecretService / D-Bus Secret Service API (freedesktop secret storage)
- macOS: Apple Keychain Services API
- Windows: Windows Credential Manager
All outbound HTTP requests dispatched by AI agents must pass rigorous SSRF validation.
Destination hostnames must resolve to publicly routable IP addresses verified via ipaddress.
Requests reaching RFC 1918 private subnets, link-local, loopback, or metadata endpoints are blocked.

## 2. Kubernetes Cluster Orchestration & Pod Security Standards
Kubernetes deployments in local, homelab, and edge environments enforce Pod Security Standards.
Every container manifest must declare explicit security contexts at Pod and Container scopes:
- runAsNonRoot: true with explicit non-root UID/GID (e.g., 65532:65532)
- readOnlyRootFilesystem: true to prevent runtime binary alteration
- allowPrivilegeEscalation: false
- capabilities.drop: [ALL] to strip unnecessary Linux capabilities
Temporary scratch storage must be mounted via in-memory emptyDir volumes at /tmp and /data.
Ingress routing is managed via Traefik IngressRoute with Let's Encrypt TLS certificates.
NetworkPolicies enforce default-deny ingress and egress isolation across namespaces.

## 3. High-Performance Asynchronous Python Architecture & Type Safety
The DevOps CLI codebase is built upon Python 3.14+ runtime features, adhering to mypy --strict.
Data structures and configuration schemas are declared as immutable Pydantic v2 models.
Field validation uses @field_validator and serialization is via model.model_dump_json().
Static code analysis is performed using Python's native ast module.
The AST CodeScanner parses Python source trees into syntax trees without executing arbitrary code,
extracting FunctionDef, AsyncFunctionDef, and ClassDef nodes to compute McCabe complexity.
For HTTP communication, httpx2 clients enforce strict request timeouts and connection pooling.

## 4. CI/CD Pipeline Optimization, Distroless Containers & Quality Gates
Continuous integration pipelines running on GitHub Actions must maximize speed and determinism.
Dependency resolution is accelerated using uv sync and astral-sh/setup-uv caching.
Multi-stage Docker builds separate build toolchains from runtime containers:
- Stage 1: Build virtual environment and compile native extensions using uv
- Stage 2: Copy virtual environment into distroless with nonroot user privileges
Workflow concurrency groups terminate obsolete runs upon rapid commit pushes.
The devops ci quality gate enforces pre-commit verification including actionlint and ruff.

## 5. Cloud Infrastructure, OpenTofu State Locking & Observability
Infrastructure as Code (IaC) is provisioned using OpenTofu and Terraform configurations:
- S3 backend storage with AES-256 server-side encryption
- DynamoDB state locking tables to prevent conflicting concurrent terraform apply executions
Observability telemetry is collected via OpenTelemetry Collector DaemonSets forwarding OTLP spans.
Prometheus scrapes operational metrics at 15-second intervals for SLA monitoring.
Vector similarity search for code intelligence is indexed into Qdrant vector databases.
"""


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
        """Perform in-memory tokenization and sliding window semantic chunking across text."""
        # Split document by markdown headings (e.g. #, ##, ###)
        raw_sections = re.split(r"\n(?=#{1,4}\s+)", document_text)
        chunks: list[DocumentSectionChunk] = []

        chunk_counter = 0
        for s_idx, raw_sec in enumerate(raw_sections):
            sec_text = raw_sec.strip()
            if not sec_text:
                continue

            lines = sec_text.splitlines()
            heading = lines[0].lstrip("#").strip() if lines else f"Section {s_idx + 1}"

            # Word-level tokenization
            words = sec_text.split()
            if not words:
                continue

            step = max(1, self.chunk_size_words - self.chunk_overlap_words)
            effective_min = min(self.min_chunk_words, max(5, self.chunk_size_words // 4))
            for w_idx in range(0, len(words), step):
                chunk_slice = words[w_idx : w_idx + self.chunk_size_words]
                if len(chunk_slice) < effective_min and w_idx > 0 and chunks:
                    continue
                if not chunk_slice:
                    continue

                chunk_text = " ".join(chunk_slice)
                approx_tokens = len(chunk_slice)
                chunk_id = f"{source_name}-sec{s_idx + 1}-chunk{chunk_counter + 1}"
                chunks.append(
                    DocumentSectionChunk(
                        id=chunk_id,
                        section_index=chunk_counter,
                        heading=heading,
                        text=chunk_text,
                        token_count=approx_tokens,
                        char_count=len(chunk_text),
                    )
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

    def _infer_category(self, heading: str, text: str = "") -> str:
        """Categorize section heading and text content into standard DevOps domains."""
        combined = f"{heading} {text}".lower()
        if any(
            w in combined
            for w in (
                "security",
                "secret",
                "ssrf",
                "keyring",
                "cve",
                "auth",
                "zero-trust",
                "token",
                "egress",
            )
        ):
            return "security"
        if any(
            w in combined
            for w in (
                "kubernetes",
                "k8s",
                "pod",
                "ingress",
                "helm",
                "traefik",
                "minikube",
                "k3s",
                "cluster",
            )
        ):
            return "kubernetes"
        if any(
            w in combined
            for w in (
                "architecture",
                "ast",
                "pydantic",
                "mypy",
                "typing",
                "solid",
                "coupling",
                "cohesion",
                "python 3.14",
            )
        ):
            return "architecture"
        if any(
            w in combined
            for w in (
                "ci",
                "cd",
                "github actions",
                "workflow",
                "actionlint",
                "pre-commit",
                "branch",
                "pr",
                "pull request",
                "git hygiene",
            )
        ):
            return "ci_cd"
        return "infrastructure"


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
    max_bytes = 20 * 1024 * 1024  # 20 MiB per test document

    if document_path and document_path.exists():
        if document_path.is_dir():
            for p in sorted(document_path.rglob("*.md")):
                try:
                    if p.stat().st_size > max_bytes:
                        continue
                    txt = p.read_text(encoding="utf-8", errors="replace")
                    if txt.strip():
                        chunks = tokenizer.tokenize_and_chunk(txt, source_name=p.stem)
                        all_chunks.extend(chunks)
                except Exception:
                    continue
        else:
            try:
                if document_path.stat().st_size <= max_bytes:
                    txt = document_path.read_text(encoding="utf-8", errors="replace")
                    chunks = tokenizer.tokenize_and_chunk(txt, source_name=document_path.stem)
                    all_chunks.extend(chunks)
            except Exception:
                pass
    elif repo_root:
        # Aggregate full documentation suite from repository
        candidate_paths: list[Path] = []
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

        seen_paths: set[Path] = set()
        for p in candidate_paths:
            if p in seen_paths or not p.is_file():
                continue
            seen_paths.add(p)
            try:
                if p.stat().st_size > max_bytes:
                    continue
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
