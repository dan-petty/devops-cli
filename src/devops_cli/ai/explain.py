"""Comprehensive terminology, mathematical formulas, and definitions for AI commands."""

from __future__ import annotations

from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

EXPLANATIONS: dict[str, dict[str, Any]] = {
    "benchmark": {
        "title": "⚡ DevOps AI Benchmark Suite",
        "description": (
            "Mathematical formulations and operational guidelines for vector embedding models, "
            "hardware throughput, and LLM peer-grading benchmarks."
        ),
        "sections": [
            {
                "name": "📊 Embedding Retrieval & Semantic Quality Metrics",
                "items": [
                    (
                        "Recall@1 (%)",
                        (
                            "Percentage of queries where the exact target passage was retrieved "
                            "at rank 1."
                        ),
                        "Formula: (Top-1 Hits / Total Queries) * 100. Target: >= 90%",
                    ),
                    (
                        "Recall@3 / Recall@5 (%)",
                        (
                            "Percentage of queries where the target passage appeared in top 3/5 "
                            "retrieved results."
                        ),
                        "Formula: (Top-K Hits / Total Queries) * 100. Target: >= 98%",
                    ),
                    (
                        "MRR (Mean Reciprocal Rank)",
                        (
                            "Evaluates ranking position of target chunk. Penalizes models ranking "
                            "relevant chunks lower."
                        ),
                        "Formula: (1 / |Q|) * sum(1 / rank_i). Range: [0.0, 1.0]. Target: >= 0.90",
                    ),
                    (
                        "NDCG@5",
                        (
                            "Normalized Discounted Cumulative Gain at rank 5. Measures ranking "
                            "quality with log position discounting."
                        ),
                        (
                            "Formula: DCG@5 / IDCG@5 where DCG = sum(rel_i / log2(i + 1)). "
                            "Target: >= 0.90"
                        ),
                    ),
                    (
                        "Cosine Margin",
                        (
                            "Difference in cosine similarity between true target passage and "
                            "highest scoring distractor."
                        ),
                        (
                            "Formula: sim(query, target) - max(sim(query, distractor)). "
                            "Target: > +0.15"
                        ),
                    ),
                    (
                        "Separation Score",
                        (
                            "Average distance between positive matches and negative distractor "
                            "baseline corpus."
                        ),
                        "Formula: mean(sim_targets) - mean(sim_distractors). Target: > +0.20",
                    ),
                ],
            },
            {
                "name": "⚡ Hardware Performance, Latency & Vector Footprint",
                "items": [
                    (
                        "Latency (p50 / p95 ms)",
                        (
                            "Single-query vector generation time. p50 is median latency; "
                            "p95 represents tail latency."
                        ),
                        "Target: < 10ms for local edge models, < 50ms for remote cloud endpoints",
                    ),
                    (
                        "Throughput (Items/s & Chars/s)",
                        (
                            "Batch indexing speed across the corpus passages. Measures indexing "
                            "throughput."
                        ),
                        "Formula: total_passages / duration_seconds",
                    ),
                    (
                        "Dimension & Memory Footprint",
                        (
                            "Dense vector length (e.g. 384, 768, 1024). Memory required = "
                            "(dim * 4 bytes) for float32."
                        ),
                        (
                            "Formula: (dim * 4) / 1024 KB per vector. 768 dim = 3.0 KB/vec "
                            "(~3.0 GB / 1M vectors)."
                        ),
                    ),
                    (
                        "Asymmetric Task Prefixing",
                        (
                            "Architecture requirement for models like Nomic, Qwen, and BGE using "
                            "task prefixes."
                        ),
                        (
                            "Queries use 'search_query: ' or 'query: '; passages use "
                            "'search_document: ' or 'passage: '"
                        ),
                    ),
                    (
                        "Overall Score (%)",
                        (
                            "Weighted composite score balancing retrieval quality (60%), "
                            "performance (30%), and health (10%)."
                        ),
                        "Formula: (Quality * 0.6) + (Performance * 0.3) + (Health * 0.1)",
                    ),
                ],
            },
            {
                "name": "🤝 Chat LLM Peer-Grading Metrics",
                "items": [
                    (
                        "Peer Grading",
                        (
                            "Blind multi-judge cross-evaluation where candidate LLMs evaluate "
                            "other models' solutions."
                        ),
                        "Eliminates self-evaluation bias by averaging scores from multiple peers",
                    ),
                    (
                        "Evaluation Rubrics",
                        (
                            "4-factor scoring rubric: Accuracy (10 pts), Completeness (10 pts), "
                            "Security (10 pts), Clarity (10 pts)."
                        ),
                        "Total percentage = (sum(scores) / 40) * 100",
                    ),
                    (
                        "Win Rate & Elo/Borda Rank",
                        (
                            "Tournament leaderboard ranking based on pairwise head-to-head "
                            "evaluation wins against other models."
                        ),
                        "Formula: wins / total_comparisons",
                    ),
                ],
            },
        ],
    },
    "review": {
        "title": "🔍 AI Multi-Persona Code Review System",
        "description": (
            "Operational roles, evaluation criteria, severity tiers, and confidence scoring "
            "used by AI review personas."
        ),
        "sections": [
            {
                "name": "👥 Reviewer Personas & Specializations",
                "items": [
                    (
                        "DevSecOps Persona",
                        (
                            "Focuses on zero-trust security, secret leakage, SSRF boundaries, "
                            "OWASP Top 10 vulnerabilities, and CVEs."
                        ),
                        "Focus: OWASP Top 10, CWE-918 (SSRF), secret leaks, egress isolation",
                    ),
                    (
                        "Architect Persona",
                        (
                            "Analyzes system modularity, SOLID design principles, cyclic "
                            "dependencies, and API contracts."
                        ),
                        ("Focus: SOLID, DRY, separation of concerns, high cohesion, low coupling"),
                    ),
                    (
                        "QA Persona",
                        (
                            "Evaluates deterministic test isolation, branch coverage, edge case "
                            "handling, and regressions."
                        ),
                        (
                            "Focus: Test isolation, mocking external I/O, error paths, "
                            "flake prevention"
                        ),
                    ),
                    (
                        "PM Persona",
                        (
                            "Assesses release impact, user experience, documentation accuracy, and "
                            "backward compatibility."
                        ),
                        (
                            "Focus: SemVer compliance, changelog clarity, CLI UX, "
                            "backward compatibility"
                        ),
                    ),
                    (
                        "Auditor Persona",
                        (
                            "Checks regulatory compliance, license hygiene, audit logging, and "
                            "supply-chain SBOM integrity."
                        ),
                        "Focus: Governance, provenance, regulatory standards",
                    ),
                ],
            },
            {
                "name": "🎯 Finding Schema & Severity Levels",
                "items": [
                    (
                        "CRITICAL",
                        (
                            "Immediate remote code execution, unauthenticated data breach, or "
                            "catastrophic service outage risk."
                        ),
                        "Example: Unauthenticated SSRF endpoint with AWS metadata egress",
                    ),
                    (
                        "HIGH",
                        (
                            "Severe security or architectural flaw that must be fixed before "
                            "production deployment."
                        ),
                        "Example: Plaintext secret logged to output or insecure TLS configuration",
                    ),
                    (
                        "MEDIUM",
                        ("Suboptimal design, performance bottleneck, or missing input validation."),
                        "Example: Missing timeout on HTTP subprocess call or unpinned dependency",
                    ),
                    (
                        "LOW / INFO",
                        (
                            "Code style improvement, documentation typo, or minor refactoring "
                            "suggestion."
                        ),
                        "Example: Redundant type annotation or missing docstring",
                    ),
                    (
                        "Confidence Score (0.0 - 1.0)",
                        (
                            "Calibrated probability that finding is genuine. Findings below "
                            "threshold (< 0.70) are filtered out."
                        ),
                        "Formula: Calibrated model certainty based on explicit AST criteria",
                    ),
                ],
            },
        ],
    },
    "analyze": {
        "title": "🔬 Static Code Analysis & AST Scanner Metrics",
        "description": (
            "Definitions of syntactic AST parsing, cyclomatic complexity, maintainability index, "
            "and architectural coupling metrics."
        ),
        "sections": [
            {
                "name": "📐 Code Complexity & Structure Metrics",
                "items": [
                    (
                        "Cyclomatic Complexity (McCabe)",
                        (
                            "Number of linearly independent execution paths through a function "
                            "calculated from branches (if, while, for, except)."
                        ),
                        "Formula: M = E - N + 2P (Edges - Nodes + 2 * Components). Target: <= 10",
                    ),
                    (
                        "Maintainability Index (MI)",
                        (
                            "Composite metric measuring relative maintainability on a 0-100 "
                            "scale from Halstead volume, complexity, and LOC."
                        ),
                        (
                            "Formula: max(0, (171 - 5.2*ln(V) - 0.23*M - 16.2*ln(LOC))*100/171). "
                            "Target: > 70"
                        ),
                    ),
                    (
                        "Fan-In & Fan-Out",
                        (
                            "Fan-In is number of modules importing a module. Fan-Out is number of "
                            "modules imported by a module."
                        ),
                        (
                            "High Fan-In indicates critical shared libraries; "
                            "high Fan-Out is high risk"
                        ),
                    ),
                    (
                        "AST Syntax Scanning",
                        (
                            "Parses Python abstract syntax trees with ast.parse() to extract "
                            "signatures, annotations, and symbols safely."
                        ),
                        "Safe, deterministic, zero-trust static code analysis",
                    ),
                ],
            },
        ],
    },
    "rag": {
        "title": "🧠 Semantic RAG & Vector Retrieval Terminology",
        "description": (
            "Definitions of semantic code chunking, dense vector retrieval, Qdrant indexing, "
            "and contextual retrieval-augmented generation."
        ),
        "sections": [
            {
                "name": "📚 Vector Retrieval & RAG Concepts",
                "items": [
                    (
                        "Polyglot Semantic Chunking",
                        (
                            "Splits code along syntactic AST boundaries (functions, classes) "
                            "preserving semantic coherence."
                        ),
                        (
                            "Preserves symbol context, import dependencies, and docstrings "
                            "in each chunk"
                        ),
                    ),
                    (
                        "Qdrant Vector Database",
                        (
                            "High-performance vector database storing dense embeddings with cosine "
                            "similarity distance and metadata filtering."
                        ),
                        "Collection namespaces: devops_code and devops_docs",
                    ),
                    (
                        "Top-K Context Retrieval",
                        (
                            "Retrieves the K nearest semantic vector neighbors to inject into "
                            "LLM prompts as grounding context."
                        ),
                        "Target: Top-3 to Top-5 highest cosine similarity chunks",
                    ),
                    (
                        "RAG Investigation Step",
                        (
                            "Safe, non-blocking semantic retrieval executed prior to generating "
                            "answers for all AI tasks (chat, review, verify, analyze, agents)."
                        ),
                        (
                            "Grounds model responses in actual codebase architecture and "
                            "specifications"
                        ),
                    ),
                    (
                        "FastMCP Tool Calling",
                        (
                            "Model Context Protocol interface providing structured JSON-RPC 2.0 "
                            "tool execution to AI assistants."
                        ),
                        "Provides strictly typed tools with Pydantic validation and docstrings",
                    ),
                ],
            },
        ],
    },
}


def render_explanation(topic: str, console_instance: Console | None = None) -> None:
    """Render a comprehensive Rich explanation panel for the requested topic."""
    c = console_instance or console
    data = EXPLANATIONS.get(topic.lower())
    if not data:
        data = EXPLANATIONS["benchmark"]

    panel_title = f"[bold white]{data['title']}[/bold white]"
    c.print()
    c.print(
        Panel(
            f"[dim]{data['description']}[/dim]",
            title=panel_title,
            title_align="left",
            border_style="cyan",
            expand=True,
        )
    )
    c.print()

    for sec in data["sections"]:
        table = Table(
            title=sec["name"],
            box=box.ROUNDED,
            expand=True,
            header_style="bold cyan",
            border_style="dim",
        )
        table.add_column("Term / Metric", style="bold white", width=28)
        table.add_column("Definition & Operational Purpose", style="dim white", width=50)
        table.add_column("Formula / Guideline", style="yellow")

        for term, definition, formula in sec["items"]:
            table.add_row(term, definition, formula)

        c.print(table)
        c.print()


def get_explanation_markdown(topic: str) -> str:
    """Generate Markdown representation of explanation glossary."""
    data = EXPLANATIONS.get(topic.lower())
    if not data:
        data = EXPLANATIONS["benchmark"]

    lines = [f"# {data['title']}", "", data["description"], ""]
    for sec in data["sections"]:
        lines.append(f"## {sec['name']}")
        lines.append("")
        lines.append("| Term / Metric | Definition & Purpose | Formula / Guideline |")
        lines.append("| :--- | :--- | :--- |")
        for term, definition, formula in sec["items"]:
            lines.append(f"| **{term}** | {definition} | `{formula}` |")
        lines.append("")

    return "\n".join(lines)
