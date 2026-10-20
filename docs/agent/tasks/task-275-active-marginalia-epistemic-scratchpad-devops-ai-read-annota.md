# Task 275: Active Marginalia & Epistemic Scratchpad (`devops ai research annotate`)

**Issue**: [#275](https://github.com/dan-petty/devops-cli/issues/275)
**Scope**: `type/feature`, `scope/ai`, `priority/p1-high`
**Feasibility**: Verified against `devops_cli.ai.research` crawler, models, and CLI runtime.

---

## 1. Description & Objectives

Emulates human active reading ("reading with a pencil"). Provides a persistent, file-anchored note and hypothesis tier (`.data/marginalia/<file_hash>.jsonl`).

#### Key Deliverables:
- [x] Structured marginalia schema supporting five typed annotations: `ASSUMPTION`, `HYPOTHESIS`, `CONTRADICTION`, `QUESTION`, and `TODO`.
- [x] Persistent JSONL storage keyed by file path hash at `.data/marginalia/<file_hash>.jsonl`.
- [x] Command `devops ai research annotate <path>` with text, JSON, and YAML output formatting and `--list` mode.
- [x] Context injection into `ForageCrawler` and `devops ai research forage` to surface active marginalia without redundant re-reading.
- [x] `devops ai read <path>` and its existing tests remain untouched and passing.
- [x] Unit and integration test coverage with structural tuple equality assertions in `tests/test_ai_research_marginalia.py`.
- [x] Complexity $M \le 10$ and nesting depth $\le 5$ enforced.
- [x] 100% passing across Gated CI validation suite (`uv run devops ci`).
