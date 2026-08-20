# AI, Multi-Persona Reviews & RAG Cheatsheet

Compare raw LLM API endpoints and manual review scripts with the unified, multi-agent `devops ai` command suite.

---

## 1. Multi-Persona Code Review

| Action / Goal | Original / Manual Workflow | `devops-cli` Command | Key Enhancements in `devops-cli` |
| :--- | :--- | :--- | :--- |
| **Review Target Path / Files** | Manual diff pasting into ChatGPT / Claude | `devops ai review path <path> [--all]` | 6-stage pipeline orchestrator, AST metadata extraction, Trivy/Bandit finding injection, criteria-based LLM verification, and threat reputation lookups. |
| **Review Git Branch Diffs** | `git diff main...feat \| llm -s "review"` | `devops ai review branch <branch>` | Multi-persona analysis across `devsecops`, `architect`, `qa`, `auditor`, and `pm` with boundary tag prompt isolation. |
| **Review GitHub PR** | Manual GitHub web UI inspection | `devops ai review pr <pr_number>` | Automatically downloads PR diffs, paginates large changes, checks CI status, and stages structured review reports in `.data/reviews/`. |
| **Inspect Review Findings** | Manual JSON parsing | `devops ai review findings <session>` | Formatted terminal summary of findings sorted by severity and confidence score, filtering out invalidated false positives. |
| **Export Feedback Dataset** | Manual record curation | `devops ai review export-feedback` | Exports reviewed, verified, and invalidated findings into structured JSONL datasets (`.data/feedback.jsonl`) for prompt alignment. |

---

## 2. Interactive Agent Chat & Context Memory

| Action / Goal | Original Command (`ollama run` / web UI) | `devops-cli` Command | Key Enhancements in `devops-cli` |
| :--- | :--- | :--- | :--- |
| **Interactive Persona Chat** | `ollama run qwen2.5-coder:7b` | `devops ai chat [-p <persona>]` | Real-time token streaming with `<think>` block visualization, DevOps tool execution, semantic RAG retrieval, and automatic size-triggered memory summarization. |
| **Chat with Injected File Context** | Manual file copying into prompt | `devops ai chat -c AGENTS.md` | Sanitizes prompt boundary tags, preserves project conventions, and tracks conversational turns. |

---

## 3. Codebase Analysis & Polyglot RAG Retrieval

| Action / Goal | Original / Manual Workflow | `devops-cli` Command | Key Enhancements in `devops-cli` |
| :--- | :--- | :--- | :--- |
| **Index Workspace in Qdrant** | Custom Python script + embeddings generation | `devops ai rag index` | AST-aware syntax chunker for 8+ programming languages (Python, Go, Rust, TS/JS, Java, C/C++, HCL, YAML) with Qdrant vector storage. |
| **Query Semantic Architecture** | `grep -rn "pattern" .` (lexical only) | `devops ai rag query "auth middleware"` | Hybrid fusion scoring combining dense vector cosine similarity (0.60), lexical token overlap (0.25), exact symbol bonus (+0.15), and security classification (+0.10). |
| **Analyze Target Metadata** | Manual architecture inspection | `devops ai analyze path <path>` | Extracts key symbols, dependencies, complexity scores, and structured pseudocode summaries into `.data/analysis/`. |
| **Validate LLM Connectivity** | `curl http://localhost:11434/api/tags` | `devops ai test` | Probes all configured local and cloud AI backends (Ollama, Claude, Copilot) and reports model latency and health. |
