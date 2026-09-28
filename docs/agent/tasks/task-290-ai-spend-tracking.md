# Task 290: Track Approximate Lifetime Spend for AI/LLM Requests Per Backend Service/Server

**Issue**: [#290](https://github.com/dan-petty/devops-cli/issues/290)
**Status**: Done
**Milestone**: `v0.2.21`
**Priority**: `priority/p1-high`
**Scope**: `scope/ai`, `scope/telemetry`

---

## 1. Description & Objectives

Implementation of lifetime approximate spend and token tracking for all AI/LLM requests across backend services and servers:
- [x] 1. **Open Source Pricing Registry**: Integrated open-source model pricing dataset (LiteLLM registry) with 60+ industry defaults, parameter-bracket heuristics for open weights, and regular remote synchronization via `devops ai cost update-pricing`.
- [x] 2. **SQLite Lifetime Spend Ledger**: Persistent ACID-compliant ledger (`spend.db`) in WAL mode recording request tokens, backend server endpoints, model names, durations, and approximate USD spend without blocking execution.
- [x] 3. **Unified Client & Direct Request Integration**: Automatic spend recording across streaming, non-streaming, and cached requests in `LLMClient` and Pydantic AI direct requests.
- [x] 4. **CLI Command Suite (`devops ai cost` / `devops ai spend`)**: Rich interactive reports by server, model, and provider (`report`), pricing inspection (`list-pricing`), custom price overrides (`set-price`), catalog updates (`update-pricing`), and ledger reset (`reset`).
- [x] 5. **OpenTelemetry, Prometheus & FastMCP Integration**: Metrics emission (`devops_cli_ai_estimated_cost_usd`, `devops_cli_ai_tokens_total`), Prometheus text exposition exporter (`export_ai_spend_prometheus`), `/metrics` scrape endpoint integration, FastMCP tool `ai_spend_report`, and dynamic resource `resource://ai/spend`.
- [x] 6. **Grafana Observability Dashboards**: Dedicated `AI Spend & LLM Usage Telemetry` Grafana dashboard (`k8s/monitoring/dashboards/ai-spend.json`, `uid: "ai-spend-telemetry"`) with spend velocity, backend server breakdown, and token rate panels, plus spend summaries in `devops-cli.json`.
- [x] 7. **Quality & Validation**: Passed all architectural invariants and Gated CI quality checks (`uv run devops ci`).

---

## 2. Verification Results

- **Unit & Integration Test Suites**:
  - `tests/test_ai_spend_pricing.py`: Validated pricing calculation across exact, normalized, parameter-bracket heuristic, and custom override rules.
  - `tests/test_ai_spend_ledger.py`: Validated SQLite WAL mode ledger, thread-safe concurrent insertions, lifetime aggregations, and failure resilience.
  - `tests/test_ai_spend_dispatch.py`: Validated automatic spend recording on streaming, non-streaming, and cached requests in `LLMClient`.
  - `tests/test_ai_spend_cli.py`: Validated `devops ai cost` commands across report formats, pricing updates, and overrides.
  - `tests/test_ai_spend_prometheus.py`: Validated Prometheus exposition formatting, gauge/counter calculations, and `/metrics` endpoint integration.
  - `tests/test_fastmcp_contracts.py`: Validated `ai_spend_report` tool and `resource://ai/spend` resource contracts.
- **Architectural Invariants & Complexity**: Verified all functions $\le 10$ McCabe complexity and $\le 5$ indentation levels with structural tuple assertions.
- **Gated CI Quality Gate**: `uv run devops ci` passed with 100% success across all 10 checks with $\ge 90.0\%$ code coverage.
