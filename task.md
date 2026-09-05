# Task Tracking: Elevate Test Coverage to >= 95% Across DevOps CLI

## Task Status Summary

### Completed Tasks
- [x] Baseline coverage extraction and gap analysis (`.data/coverage_baseline.json`: 90.50% overall coverage, 3,058 missed lines across 65 files under 90%).
- [x] Identified minimum delta requirement: +1,449 covered statements needed to hit 95.00%.
- [x] Detailed implementation plan authored in `implementation_plan.md` dividing work into 5 prioritized domain phases.

---

### In-Progress Tasks (WIP)
- [ ] Phase 1: High-Deficit Core CLI & K8s Commands (<80% Coverage)
  - [ ] `src/devops_cli/commands/vault.py` (40.82% -> $\ge 90\%$)
  - [ ] `src/devops_cli/commands/k8s/cluster_runtime.py` (36.59% -> $\ge 90\%$)
  - [ ] `src/devops_cli/commands/k8s/diagnostics.py` (70.49% -> $\ge 90\%$)
  - [ ] `src/devops_cli/commands/k8s/networking.py` (73.87% -> $\ge 90\%$)
  - [ ] `src/devops_cli/commands/pr.py` (75.00% -> $\ge 90\%$)
  - [ ] `src/devops_cli/commands/rag.py` (77.25% -> $\ge 90\%$)
  - [ ] `src/devops_cli/commands/analyze.py` (79.05% -> $\ge 90\%$)

---

### Pending Tasks
- [ ] Phase 2: AI Review System & Pipelines (<85% Coverage & Highest Missed Statements)
  - [ ] `src/devops_cli/ai/review/pipeline.py` (84.10% -> $\ge 90\%$)
  - [ ] `src/devops_cli/ai/review/runner.py` (79.87% -> $\ge 90\%$)
  - [ ] `src/devops_cli/ai/review_schema.py` (83.95% -> $\ge 90\%$)
  - [ ] `src/devops_cli/ai/review/chunker.py` (78.87% -> $\ge 90\%$)
  - [ ] `src/devops_cli/ai/review/auto_fix.py` (76.92% -> $\ge 95\%$)
  - [ ] `src/devops_cli/ai/review/stages/static_scan.py` (84.85% -> $\ge 90\%$)
  - [ ] `src/devops_cli/ai/review/verification.py` (88.39% -> $\ge 92\%$)
- [ ] Phase 3: AI Agents, MCP & Harness Components (<85% Coverage)
  - [ ] `src/devops_cli/ai/agents/agent.py` (79.54% -> $\ge 90\%$)
  - [ ] `src/devops_cli/ai/agents/runner.py` (74.76% -> $\ge 90\%$)
  - [ ] `src/devops_cli/ai/agents/__init__.py` (54.55% -> $\ge 90\%$)
  - [ ] `src/devops_cli/ai/mcp/server.py` (81.49% -> $\ge 90\%$)
  - [ ] `src/devops_cli/ai/context_budget.py` (77.24% -> $\ge 90\%$)
  - [ ] `src/devops_cli/ai/response_repair.py` (76.58% -> $\ge 90\%$)
  - [ ] `src/devops_cli/ai/tools/builtin_tools.py` (82.88% -> $\ge 90\%$)
  - [ ] `src/devops_cli/ai/common_tools.py` (80.83% -> $\ge 90\%$)
  - [ ] `src/devops_cli/ai/thinking_stream.py` (82.73% -> $\ge 90\%$)
- [ ] Phase 4: RAG Vector Engine & Embeddings (<85% Coverage)
  - [ ] `src/devops_cli/ai/rag/qdrant.py` (62.98% -> $\ge 90\%$)
  - [ ] `src/devops_cli/ai/rag/indexer.py` (82.77% -> $\ge 90\%$)
  - [ ] `src/devops_cli/ai/rag/retriever.py` (82.74% -> $\ge 90\%$)
  - [ ] `src/devops_cli/ai/rag/embeddings.py` (86.43% -> $\ge 90\%$)
- [ ] Phase 5: Additional CLI Commands & Remaining Modules (<90% Coverage)
  - [ ] `commands/grafana.py`, `commands/docs.py`, `commands/k8s/stack_lifecycle.py`, `commands/repos.py`
  - [ ] `commands/branches.py`, `commands/benchmark.py`, `commands/k8s/tls_management.py`, `commands/review.py`
  - [ ] `commands/docker.py`, `commands/argo.py`, `commands/release.py`, `commands/ci.py`, `commands/config.py`, `commands/devcontainer.py`
  - [ ] Subsystem utilities (`config/settings.py`, `http/broker.py`, `k8s/credentials.py`, etc.)
- [ ] Phase 6: Full Verification & Routine Tasks
  - [ ] Full pytest coverage run verifying overall coverage $\ge 95.00\%$ and 0 source files $<90\%$.
  - [ ] Full `uv run devops ci` quality gate (10/10 green).
  - [ ] Synchronize documentation: `devops docs generate --sync-readme`.
  - [ ] Update `docs/LOG.md` and generate `walkthrough.md`.
