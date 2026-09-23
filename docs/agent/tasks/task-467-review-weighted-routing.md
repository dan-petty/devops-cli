# Task 467: Review Routing Weighted by Backend Throughput

**Issue**: [#467](https://github.com/dan-petty/devops-cli/issues/467)
**PR**: [#468](https://github.com/dan-petty/devops-cli/pull/468)
**Status**: In Review
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/bug`, `scope/k8s`, `scope/ai`, `priority/p2-medium`

---

## 1. Description & Objectives

`devops-review` routed with `least-busy` and capped each deployment with `max_parallel_requests`
(dual-GPU vLLM 8, single-GPU vLLM 2, 1 per Ollama node). In LiteLLM v1.102.1 the router chooses
a deployment first and only then waits on that deployment's semaphore. Least-busy increments its
in-flight count when the backend call starts, after that wait, so requests queued behind a cap
were invisible to routing:

- A capped deployment never looked busier than its cap. The dual-GPU vLLM received a request only
  while it had fewer in flight than the smallest cap, so it ran about 2 requests at a time
  instead of 8.
- Once every deployment was saturated, overflow went to the lowest count, which was a 1-request
  Ollama node, and queued there.

The caps protected nothing: vLLM schedules excess requests itself and Ollama queues them.

Least-busy without caps still clusters bursts. A review sends one call per persona at once, and
those calls are routed before any in-flight count changes, so they land on the first-listed
deployment.

### Key Deliverables Completed:

- [x] **Weighted Shuffle**: `routing_strategy: simple-shuffle`, with `devops-review` weights in
  proportion to measured throughput: dual-GPU vLLM 5, single-GPU vLLM 3, each Ollama node 1.
  Groups without weights (the Ollama-backed aliases) split evenly, and single-deployment groups
  are unaffected. Context-window pre-call checks and fallbacks are unchanged.
- [x] **No Deployment Caps**: `max_parallel_requests` removed from the pool.
- [x] **No Gateway-Based Worker Sizing**: throughput levels off near 2 requests/s from 12 to 48
  concurrent requests. A review already keeps about 24 calls in flight (4 file workers × about 6
  personas), so sizing file workers from gateway capacity would not speed reviews up. The
  roadmap's remaining note for #458 now says so.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_k8s_llm_gateway.py`: the pool has no caps, and the weights order the backends
    (dual-GPU vLLM > single-GPU vLLM > Ollama, with all Ollama nodes equal). The routing strategy
    is pinned.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Measurements on a Live Cluster

The load was 24 concurrent review-style requests (about 1.8K prompt tokens and 200 output tokens
each) against `devops-review`. Before each run, the loaded limits or weights were confirmed
through `/model/info`.

| Routing | Wall time (runs) | Peak running, dual-GPU vLLM |
|---|---|---|
| least-busy + caps (before) | 47 s, 101 s, 104 s | 2–8 |
| least-busy, no caps | 18.7–27.5 s (5 runs) | 6–10 |
| simple-shuffle 5/3/1/1, no caps | 13.1 s, 13.6 s | 8–11 |

Under weighted shuffle, 12 concurrent requests took 5.1 s and 48 took 24.8 s.

A real all-persona `devops ai review path` over 15 Ansible playbooks used the same code, with the
response cache bypassed. Per-backend counts come from vLLM's `request_success_total` and
Ollama's request log.

| Routing | Wall time | Candidate findings | Dual-GPU vLLM | Single-GPU vLLM | Ollama nodes |
|---|---|---|---|---|---|
| least-busy + caps (before) | 4 min 31 s | 40 | 19 (23%) | 22 | 42 (28 + 14, 51%) |
| simple-shuffle 5/3/1/1 | 3 min 36 s | 53 | 40 (45%) | 27 | 21 (12 + 9, 24%) |

Under the caps, half of all calls went to the slowest servers. Weighted routing moved them to the
dual-GPU vLLM and finished 20% sooner, despite 33% more candidate findings to verify.
