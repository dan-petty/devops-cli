# Task 669: Gateway Tune Large Prompts, Weight Overrides and Concurrency Settings

**Issue**: [#669](https://github.com/dan-petty/devops-cli/issues/669)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/bug`, `scope/ai`, `priority/p2-medium`

---

## 1. Description & Objectives

Remediate `devops ai gateway tune` benchmark execution, parameter handling, and container reuse:
1. Prevent Linux `MAX_ARG_STRLEN` (128KB) overflow when passing prompts larger than 32K tokens to `kubectl debug` by piping benchmark scripts via `stdin` rather than passing them on the command-line invocation vector.
2. Reuse ephemeral debug containers across benchmark iterations to avoid pod spec clutter and resource leaks.
3. Match weight overrides consistently by either deployment ID or backend label across both live sweep and fallback paths.
4. Calculate and surface recommended concurrency settings, applying configured concurrency overrides across benchmark runs.

### Key Deliverables Completed:
- [x] **Stdin Script Pipelining**:
  - Piped benchmark payload via `stdin` to prevent argv overflow on prompts exceeding 128KB in `src/devops_cli/ai/gateway_tune.py`.
- [x] **Ephemeral Container Reuse**:
  - Reused ephemeral debug container across benchmark iterations, eliminating container sprawl on gateway pods.
- [x] **Weight and Concurrency Overrides**:
  - Supported backend label-keyed weight matching across sweep paths and computed/displayed recommended concurrency.
- [x] **Automated Tests & Quality Gates**:
  - Added unit and integration tests verifying large prompt handling, label matching, and concurrency overrides in `tests/test_ai_gateway_tune.py`.
  - 100% passing status across Gated CI quality gates (`uv run devops ci`).
