# Task 494: Review Replies Are Capped

**Issue**: [#494](https://github.com/dan-petty/devops-cli/issues/494)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

Review verification sent requests with no reply limit. On a vLLM backend a reply could then run
until the model's context window was full. During the #486 validation, verifying one playbook on
the 32B model took 10 min 18 s, while every other file verified in 10–48 s. That one call more
than doubled the review's wall time (756 s against 241–284 s). Persona review calls had the same
gap.

### Key Deliverables Completed:

- [x] **Per-call reply cap**: `limit_completion_tokens(n)` in `devops_cli.ai.client.network` sets
  a context-carried cap, the same way request priority travels. Each provider takes the smaller
  of it and the configured `max_tokens` (`_completion_limit`): the OpenAI-compatible and gateway
  path as `max_tokens` (or `max_completion_tokens` for reasoning models), streamed replies
  included; Ollama as `num_predict`; Claude as `max_tokens`.
- [x] **Verification cap**: 2048 tokens plus 384 per finding checked, at most 8192, reasoning
  included. A reply cut short fails to parse and leaves its findings unverified, with the
  existing "verification did not complete" note, rather than invalidating them.
- [x] **Persona review cap**: 8192 tokens per reply, in both the pipeline and the per-segment
  runner.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_review_reply_caps.py`: the cap sets `max_tokens`, the smaller limit wins, and
    nothing leaks past the block; verification is capped by finding count; persona review runs
    under its cap.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification on a Live Cluster

An all-persona review of the homelab playbooks on the default 5/3/1/1 weights, with the caps in
place, finished in 200 s (the median without caps was 229 s). It reported 13 findings from 50
candidates, all verified. Every file verified in 11–37 s, and no verification was cut short.
