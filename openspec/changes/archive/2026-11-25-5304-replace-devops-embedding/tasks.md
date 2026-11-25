# Tasks

## 1. Replace dead embedding alias and fix gateway status & benchmark planner

Kind: python. Reads: `src/devops_cli/ai/gateway.py`, `src/devops_cli/commands/ai_gateway.py`, `src/devops_cli/ai/ai_plans.py`, `src/devops_cli/commands/benchmark.py`, `k8s/llm/gateway/config.yaml`. Changes: `src/devops_cli/ai/gateway.py`, `src/devops_cli/commands/ai_gateway.py`, `src/devops_cli/ai/capability.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/ai/ai_plans.py`, `src/devops_cli/ai/benchmark/execution.py`, `src/devops_cli/commands/benchmark.py`, `tests/`.

- [x] 1.1 Write failing tests for live `/model/info` status + failover retention + `not checked` fallback, gateway `/v1/embeddings` dry-run plan, gateway `virtual_model` / `CONST_AI_GATEWAY_VIRTUAL_MODELS` config drift check, and updated `qwen3-embedding:0.6b` expectations
  - Verification: `$ uv run pytest tests/ai/mcp/test_ai_gateway.py tests/commands/test_ai_model_gateway_dry_run.py tests/ai/benchmark/test_k8s_llm_gateway.py`
- [x] 1.2 Replace `devops-embedding` with `qwen3-embedding:0.6b`, fix `src/devops_cli/ai/gateway.py` comment, update `probe_gateway`/`status_cmd` to query `/model/info` with API key and mark fallback routes `not checked`, and plan `/v1/embeddings` for `gateway` embedding benchmarks
  - Verification: `$ git grep -n devops-embedding -- src tests`

## 2. Regenerate docs/snapshots and verify CI gates

Kind: python. Reads: `tests/ai/mcp/test_mcp_tool_listing.py`, `openspec/specs/`. Changes: `docs/commands/ai.md`, `docs/MCP_TOOLS.md`, `tests/ai/mcp/__snapshots__/test_mcp_tool_listing/test_the_tool_listing_matches_the_snapshot.json`, `openspec/specs/`.

- [x] 2.1 Regenerate docs (`devops docs generate`) and MCP tool listing snapshot, verify `devops ci fail-to-pass --base origin/main`, and run full test + CI gate verification after OpenSpec archive
  - Verification: `$ uv run devops ci --check --skip test --force && uv run devops ci fail-to-pass --base origin/main`
