# Task 473: Review Performance Baseline Per-Stage Timing, Calls and Tokens on a Fixed Corpus

**Issue**: [#473](https://github.com/dan-petty/devops-cli/issues/473)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

End-to-end review timings were anecdotal. Three identical all-persona runs over the same 15
playbooks took 3 min 36 s to 4 min 31 s and produced 40, 53 and 70 candidate findings. Nothing
split the time between persona review, the verification debate and local work, or counted the LLM
calls and tokens per stage, so the effect of gateway tuning on a review could not be attributed.

### Key Deliverables Completed:

- [x] **Call observers**: the spend ledger is the one place every LLM call passes through with its
  tokens and serving backend. `observe_llm_calls()` shows each recorded call to the observers
  registered in the current context; asyncio tasks and `asyncio.to_thread` copy the context into
  the review's worker threads.
- [x] **Review profile** (`ai/review/profile.py`): every review marks its stages (pre-analysis,
  payloads, persona review, verification, re-ranking, report) and writes `profile.json` next to
  `findings.json`: wall time, LLM calls, prompt and completion tokens and serving backends per
  stage, plus candidate, verified and reported finding counts. Replies served from the response
  cache are counted apart, since no backend worked for them. The review prints a one-line summary
  of where the time went. Stage markers cost nothing outside a profiled review.
- [x] **Benchmark**: `devops review benchmark <targets> -n 3` reviews the same files N times with
  the response cache bypassed, collects each run's profile and saves the medians under
  `.data/reviews/benchmarks/`: per stage (wall time, calls, prompt and completion tokens, backends)
  and overall, with seconds per candidate finding to normalise for runs that verify more findings.
  A digest of the reviewed files, taken before pagination so a page-size change keeps it, marks
  which benchmarks share a corpus.
- [x] **Traces**: the stages already had `review.*` spans; the profile's session ID is an attribute
  of the session's `review.session` span, so a slow stage can be followed into Jaeger.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_review_profile.py`: observers see only calls inside their block; calls from worker
    threads are credited to the running stage; cached replies are counted apart; the orchestrated
    review marks each stage and counts its findings; medians across runs; `profile.json` and the
    saved benchmark round-trip; the benchmark command runs each review uncached and fails when
    nothing was profiled; the corpus digest changes only with the reviewed files.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification on a Live Cluster

`devops review benchmark <homelab>/ansible/playbooks -n 3 --all` through the homelab gateway
(`devops-review` weights 5/3/1/1), corpus digest `ae5bdab904cb9036`:

| Run | Wall time | LLM calls | Candidates | Verified | Reported | s / candidate |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 260 s | 89 | 52 | 2 | 3 | 5.0 |
| 2 | 210 s | 83 | 40 | 6 | 6 | 5.3 |
| 3 | 172 s | 86 | 47 | 3 | 3 | 3.7 |
| **Median** | **210 s** | **86** | **47** | | **3** | **5.0** |

| Stage (median) | Wall time | LLM calls | Prompt tokens | Completion tokens |
| :--- | ---: | ---: | ---: | ---: |
| Pre-analysis | 0.2 s | 0 | 0 | 0 |
| Payloads | 1.3 s | 0 | 0 | 0 |
| Persona review | 161 s | 76 | 314,590 | 39,002 |
| Verification | 48 s | 10 | 39,763 | 7,779 |
| Re-ranking, report | < 0.1 s | 0 | 0 | 0 |

- **Persona review is the review.** It takes 77% of the median time: 15 files × 5 personas, one
  call each. Verification batches the candidates into about ten calls. Local work takes under 2 s.
- **Run-to-run spread sits in persona review** (203 s, 161 s and 124 s), not in verification
  (52 s, 48 s and 47 s).
- **The Ollama nodes are not equal.** Over the three runs, per the spend ledger's serving backend:

  | Backend | Calls | Mean call | Longest call | Tokens/s per call |
  | :--- | ---: | ---: | ---: | ---: |
  | vLLM, 32B (2 GPUs) | 124 | 19.0 s | 56 s | 32 |
  | vLLM, 14B (1 GPU) | 81 | 9.4 s | 35 s | 57 |
  | Ollama `gpt-oss:20b`, Pascal ×2 | 32 | 44.8 s | 101 s | 13 |
  | Ollama `gpt-oss:20b`, Volta ×1 | 21 | 8.2 s | 32 s | 48 |

  Both Ollama deployments carry weight 1, but the Pascal node is about five times slower per call
  and served the longest calls (up to 101 s). The tuner's 3/5/1/2 recommendation (#476) had already
  told the two apart, giving the Volta node twice the Pascal node's weight. Per-backend cost from
  real traffic is #477.

The benchmark accepts any fixed set of paths. This baseline covers the playbooks; this repository's
modules can be added as further targets, and the corpus digest separates the two baselines.
