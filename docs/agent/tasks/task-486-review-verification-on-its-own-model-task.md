# Task 486: Review Verification on Its Own Model Task

**Issue**: [#486](https://github.com/dan-petty/devops-cli/issues/486)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/ai`, `priority/p1-high`

---

## 1. Description & Objectives

One LLM client, built from the analysis task, served persona review and finding verification. In
#476, weighting `devops-review` toward the single-GPU 14B backend cut the median review time by
19%, but top-severity false positives passed verification. The hypothesis was that generation
could use the fastest pool if a stronger model verified.

### Key Deliverables Completed:

- [x] **`ai.tasks.verification`**: an `AITaskOverride` layered on the analysis task
  (`analysis_config.for_task("verification")`), so it only has to name what differs, such as a
  model on the same gateway. Unset, reviews verify with the analysis client, so existing setups
  are unchanged.
- [x] **Wiring**: `ReviewClients.verification` (defaults to `analysis`) feeds both verification
  call sites: the pipeline's stage 4 (`ReviewPipelineOrchestrator(verification_client=...)`) and
  per-segment verification in the runner. The debate stage makes no model calls. Stage 4 now
  names the verification model in its progress line.
- [x] **Cleanup**: removed `_resolve_review_clients`. It had no callers, and it built every task's
  client from the global configuration, ignoring the task.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_review_verification_task.py`: the default falls back to analysis; the override is
    layered on analysis (provider, gateway, window); both call sites use the verification client;
    stage 4 reports the verification model.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification on a Live Cluster

The #476 comparison was repeated with the tuned weights (3/5/1/2) and
`ai.tasks.verification.model: devops-reasoning` (the 32B model): three all-persona reviews of the
homelab playbooks.

| Config | Wall time (3 runs) | Median | Reported findings |
|---|---|---|---|
| A: 5/3/1/1 | 305, 229, 223 s | 229 s | 3, 7, 1 |
| B: 3/5/1/2 | 170, 185, 202 s | 185 s | 11, 6, 12 |
| C: 3/5/1/2, verified by 32B | 284, 756, 241 s | 284 s | 0, 0, 2 |

The split did not work out:

- It was slower, because every verification queued on the one 32B server. One run stalled for
  10 min 18 s on a single verification reply, which has no length cap (#494).
- The 32B verifier rejected nearly every candidate (`0/N valid` for every file in one run).
- It still passed "Unencrypted Communication Scheme" at top severity for plain HTTP to the
  in-cluster registry mirror.

So the false positive does not come from the verifier's size. It comes from what the verifier is
told, which is the subject of the prompt benchmarking and review quality baseline work (#413,
#475). The setting ships unset, and 5/3/1/1 stays.
