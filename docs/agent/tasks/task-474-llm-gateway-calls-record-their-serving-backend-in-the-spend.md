# Task 474: LLM Gateway Calls Record Their Serving Backend in the Spend Ledger

**Issue**: [#474](https://github.com/dan-petty/devops-cli/issues/474)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/ai`, `priority/p1-high`

---

## 1. Description & Objectives

The gateway picks a deployment for every call, but devops-cli records only the gateway as the server. Cost, latency and review quality therefore cannot be attributed to the backend that did the work. The gateway already names the deployment in every response (`x-litellm-model-id`, `x-litellm-model-api-base`), and the spend ledger's `backend_info` column is unused for gateway calls.

#### Key Deliverables:
- Context & Rationale*: The gateway picks a deployment for every call, but devops-cli records only the gateway as the server. Cost, latency and review quality therefore cannot be attributed to the backend that did the work. The gateway already names the deployment in every response (`x-litellm-model-id`, `x-litellm-model-api-base`), and the spend ledger's `backend_info` column is unused for gateway calls.
- Deliverable*: Capture those headers in the OpenAI-compatible client (streaming included) and record them per call. Add `devops ai cost --by backend`. This is the input for cost from real traffic in `devops ai gateway tune` and for the per-backend quality baseline.
- Constraint*: Providers other than the gateway leave the field empty rather than guessing.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
