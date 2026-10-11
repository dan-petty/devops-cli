# Task: Agentic Information Foraging & Scent Trails (#274)

**Issue**: [#274](https://github.com/dan-petty/devops-cli/issues/274)
**Status**: Done
**Milestone**: v0.2.34
**Priority**: priority/p0-critical
**Scope**: scope/ai
**Feasibility**: Feasible - Confirmed offline through repository analysis that relational edge extraction across Python imports, markdown links, and git history combined with local BM25 scoring enables a fast (<1s tests), deterministic crawler with zero LLM and zero network dependencies.

## Description
Implements Pirolli & Card's Information Foraging Theory as a deterministic, local-only crawler following relational "information scent" across codebases. Rather than executing disjointed keyword grep searches, the agent follows outbound relational cues from a starting anchor (file path or keyword), scores edges via semantic relevance (BM25), maintains an explicit cycle-detection ledger, and systematically backtracks when an information trail grows cold.

Per the owner's design refinement for v1:
- **Local-only & deterministic**: Completely offline execution with zero LLM calls, zero network egress, and zero file mutations.
- **Relational edge extractors**:
  - **Python imports (`ast`)**: Resolves both absolute and relative module imports to concrete repository source files.
  - **Markdown links (`markdown-it-py`)**: Parses internal relative markdown cross-references while cleanly filtering external URLs and fragment anchors.
  - **Git co-changes (`GitPython`)**: Inspects commit history to uncover files frequently committed together with the current node.
- **BM25 semantic scent scoring**: Evaluates candidate file content against the user's inquiry query using `devops_cli.ai.lexical.bm25_scores` with term matching bonuses.
- **Best-first priority search & backtracking**:
  - Uses `heapq` priority queue to greedily explore highest-scent nodes first.
  - Tracks visited nodes in a ledger to avoid circular paths.
  - Detects when immediate neighbor nodes score below `--min-score`, systematically backtracking to the next highest-scoring frontier node and recording a `BacktrackEvent`.
- **CLI interface**:
  - Registered `devops ai research forage <anchor> --query TEXT [--max-nodes N] [--min-score S] [--repo PATH] [--json] [--dry-run]` under `research_app` in `src/devops_cli/commands/ai_research.py`.
  - Supports interactive Rich summary panels and trail tables, as well as machine-readable `--json` output conforming to `ForageTrail`.

## Acceptance Criteria
- [x] Registered `devops ai research forage` CLI command with anchor, `--query`, `--max-nodes`, `--min-score`, `--repo`, `--json`, and `--dry-run`.
- [x] Implemented multi-edge extraction across Python imports (`ast`), markdown links (`markdown-it-py`), and git co-changes (`GitPython`).
- [x] Computed numeric BM25 semantic scent scores for all visited nodes, prioritizing relevant files over unrelated ones.
- [x] Ledger tracks visited nodes and edges, detecting cycles and preventing duplicate node visits.
- [x] Crawler systematically backtracks to the best frontier node when branch scent drops below `--min-score`, logging `BacktrackEvent`.
- [x] Emits structured JSON adhering to the `ForageTrail` schema when `--json` is specified.
- [x] Unit test suite in `tests/test_ai_research_forage.py` runs completely offline on an isolated git fixture with total call duration < 1.0 s.
- [x] Documentation regenerated and verified clean via `uv run devops docs check`.
- Pending a person: `uv run devops ci` on this branch; it is this PR's own check, which readiness reads.

## Measurements
The regression test suites, run offline with `uv run pytest`:

| Test Suite | Call Duration | Tests Passed |
| :--- | ---: | ---: |
| `tests/test_ai_research_forage.py` | 0.81 s | 10 |
| `tests/test_architectural_invariants.py` | 14.43 s | 70 |
| `tests/test_agent_task_files.py` | 11.20 s | 509 |
