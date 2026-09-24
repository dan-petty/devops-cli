# Task 545: Review Load Spreads Across the Whole LLM Pool

**Issue**: [#545](https://github.com/dan-petty/devops-cli/issues/545)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/ai`, `priority/p1-high`

---

## 1. Description & Objectives

During a live review the 32B vLLM was busy in 12 of 13 samples, the 14B vLLM in none and the Ollama nodes in 0 and 1; at a stage's end all four calls sat on one server. Three causes combine. `simple-shuffle` routes by weight (5:3:1:1), not load. Pre-call checks drop the 14B server from prompts over its 12,288-token limit, which numbered pages and whole-file verification reach, sending about 71% to the 32B server. And a review keeps few calls in flight: 4 files at once, a file's pages in sequence, one call at each stage's tail.

#### Key Deliverables:
- Context & Rationale*: During a live review the 32B vLLM was busy in 12 of 13 samples, the 14B vLLM in none and the Ollama nodes in 0 and 1; at a stage's end all four calls sat on one server. Three causes combine. `simple-shuffle` routes by weight (5:3:1:1), not load. Pre-call checks drop the 14B server from prompts over its 12,288-token limit, which numbered pages and whole-file verification reach, sending about 71% to the 32B server. And a review keeps few calls in flight: 4 files at once, a file's pages in sequence, one call at each stage's tail.
- Deliverable*: Route by load (LiteLLM load-aware strategies weighed against the burst problem in the gateway config, or client-side dispatch). Keep prompts within the smallest window or send that backend only what fits. Review a file's pages in parallel and size concurrency from the pool's capacity. Measure each backend's busy share and review wall time before and after, with #546's metrics.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
