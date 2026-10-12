# Task 277: Cross-Domain Analogical Pattern Retriever (`devops ai research analogies`)

**Issue**: [#277](https://github.com/dan-petty/devops-cli/issues/277)
**Status**: Done
**Milestone**: `v0.2.35`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/ai`, `priority/p1-high`
**Feasibility**: Verified against Qdrant vector index schema in ai/rag/indexer.py, knowledge base articles in ai/knowledge_base, and Typer CLI subcommands in commands/ai_research.py.

---

## 1. Description & Objectives

Detects structural pattern isomorphisms across disparate software modules and IT domains in the DevOps CLI Knowledge Base. Implements `devops ai research analogies` utilizing multi-vector topological clustering over the existing RAG vector index and knowledge base documents to surface cross-domain analogies (such as comparing network backoff to retry loops in Kubernetes reconcilers, or database write-ahead logs to event-sourcing pipelines).

#### Key Deliverables:
- Subcommand `devops ai research analogies` registered under the `devops ai research` command group.
- Pydantic models for `CrossDomainAnalogy` and `AnalogyReport` with fields for `source`, `target`, `pattern`, and `score`.
- Multi-vector topological clustering engine `AnalogicalPatternRetriever` in `src/devops_cli/ai/research/analogies.py` operating over the existing Knowledge Base RAG collection without introducing separate indexes or pipelines.
- Canonical structural patterns catalog `CONST_STRUCTURAL_PATTERNS` in `src/devops_cli/config/constants.py`.
- Formatted output support (`table`, `json`, `yaml`, `markdown`) and dry run preview.
- Unit and integration tests in `tests/test_ai_research_analogies.py` verifying CLI options, clustering on fixture knowledge bases, and structured JSON output.
- Cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ enforced.
- 100% passing across Gated CI validation suite (`uv run devops ci`).

## 2. Acceptance Criteria
- [x] Criterion 1: A `devops ai research analogies` subcommand is registered under the `devops ai research` command group and is invocable from the CLI. Verified via `devops ai research analogies --help` exiting 0 with option descriptions.
- [x] Criterion 2: The command performs multi-vector topological clustering over the knowledge base's indexed content to identify structural pattern isomorphisms, verified with a fixture knowledge base containing structurally similar but domain-different modules.
- [x] Criterion 3: The command surfaces cross-domain analogies as structured output naming the source module, the target module, the shared structural pattern, and a confidence or similarity score. Verified with `--format json`.
- [x] Criterion 4: The command operates on the DevOps CLI Knowledge Base's existing RAG/vector index rather than requiring a separate index, importing and calling existing RAG collection lookup and Qdrant query seams.
- [x] Changelog fragment authored at `changelog.d/277.md`; `uv run devops ci` passes 100%.
