# Task 474: LLM Gateway Calls Record Their Serving Backend in the Spend Ledger

**Issue**: [#474](https://github.com/dan-petty/devops-cli/issues/474)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/ai`, `priority/p1-high`

---

## 1. Description & Objectives

The gateway picks a deployment for every call, but devops-cli recorded only the gateway itself:
`server` is the gateway host, and `backend_info` reads `gateway (<host>)`. So cost, latency and
review quality could not be attributed to the backend that did the work. The gateway names that
backend in every response header (`x-litellm-model-api-base`). Per-backend cost for
`devops ai gateway tune` (#477) and the per-backend quality baseline (#475) both need it.

### Key Deliverables Completed:

- [x] **Capture**: the OpenAI-compatible client reads `x-litellm-model-api-base`
  (`CONST_AI_GATEWAY_SERVED_BY_HEADER`) into `LLMResponse.served_by`. Streamed responses pass it
  through the `stream_served_by` context variable, because a stream's spend is recorded after its
  last chunk. Providers without a gateway record `None` rather than a guess.
- [x] **Ledger**: a `served_by` column (indexed) on `ai_spend_records`. Existing ledgers gain it in
  place on open (`ALTER TABLE ... ADD COLUMN`), keeping their rows.
- [x] **Report**: `LifetimeSpendReport.backends` breaks gateway calls down by serving backend:
  models, requests, tokens, completion tokens per request, and mean duration.
  `devops ai cost report --by backend` (and `--by all`) renders it, and `--json` includes it.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_ai_served_by.py`: grouping by backend with tokens per request; migrating a ledger
    created before the column existed; header capture for plain and streamed responses; no
    serving backend without the header; the `--by backend` report.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification on a Live Cluster

Eight `devops-review` calls through the homelab gateway recorded their backends. Four went to the
dual-GPU vLLM, two to the single-GPU vLLM and two to an Ollama node, matching the 5/3/1/1
weights. `devops ai cost report --by backend --days 1` listed the three backends: the Ollama node
averaged 17.5 completion tokens and 5.3 s per call, and the vLLM backends 4 tokens in 0.1–0.6 s.
