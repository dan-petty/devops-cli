# Proposal: #5304

## Why

The gateway configuration `k8s/llm/gateway/config.yaml` serves `qwen3-embedding:0.6b` and defines no `devops-embedding` group, yet `DEFAULT_GATEWAY_ROUTES`, `MODEL_FAILOVER_PAIRS`, `CONST_AI_GATEWAY_VIRTUAL_MODELS`, `src/devops_cli/ai/capability.py`, and `src/devops_cli/commands/benchmark.py` still reference `devops-embedding`. Meanwhile `devops ai gateway status` prints static `DEFAULT_GATEWAY_ROUTES` copied from `/health/readiness` (falsely marking an unserved group healthy and hiding multiple deployments), and `devops ai benchmark --type embedding --dry-run` plans `/api/embeddings` instead of `/v1/embeddings` when `provider` is `gateway`.

## What Changes

- Replace `devops-embedding` with `qwen3-embedding:0.6b` across `CONST_AI_GATEWAY_VIRTUAL_MODELS`, `DEFAULT_GATEWAY_ROUTES`, `MODEL_FAILOVER_PAIRS`, `src/devops_cli/ai/capability.py`, and `src/devops_cli/commands/benchmark.py`, and fix the stale test path comment in `src/devops_cli/ai/gateway.py` (`tests/ai/benchmark/test_k8s_llm_gateway.py`).
- Pass `get_ai_api_key(settings)` to `GatewayRouter` in `status_cmd` (`src/devops_cli/commands/ai_gateway.py`) and have `GatewayRouter.probe_gateway` query `GET /model/info`, rendering live deployments (`checked=True`) while keeping failover records and falling back to `DEFAULT_GATEWAY_ROUTES` marked `not checked` (`checked=False`) when `/model/info` does not answer.
- Update `plan_ai_benchmark` (`src/devops_cli/ai/ai_plans.py`) and `execute_embedding_benchmark` (`src/devops_cli/ai/benchmark/execution.py`) to plan `POST <gateway>/v1/embeddings` with `qwen3-embedding:0.6b` when the provider is `gateway`.
- Extend `tests/ai/benchmark/test_k8s_llm_gateway.py` to assert every route `virtual_model` and `CONST_AI_GATEWAY_VIRTUAL_MODELS` entry exists as a `model_name` in `k8s/llm/gateway/config.yaml`, update affected tests/fixtures/docs, and refresh the MCP tool snapshot.

## Capabilities

- `ai-gateway-routing`: Serve live `/model/info` deployments in `gateway status`, mark fallback defaults `not checked`, and keep `CONST_AI_GATEWAY_VIRTUAL_MODELS` and default routes aligned with `qwen3-embedding:0.6b` in `k8s/llm/gateway/config.yaml`.
- `configured-service-urls`: Plan `/v1/embeddings` with `qwen3-embedding:0.6b` for embedding benchmarks on provider `gateway`.

## Impact

- CLI (`devops ai gateway status`, `devops ai benchmark --type embedding --dry-run`), AI constants/capability mapping, MCP tool listing snapshot, generated docs, and tests.

## Feasibility

Confirmed in `k8s/llm/gateway/config.yaml` (serves `qwen3-embedding:0.6b`, no `devops-embedding`), `src/devops_cli/ai/gateway.py`, `src/devops_cli/commands/ai_gateway.py`, `src/devops_cli/ai/ai_plans.py`, and `tests/ai/benchmark/test_k8s_llm_gateway.py` (`config_reads.toml` cap `29` respected by extending existing route/check functions). Verified new/updated tests failed (`8 failed`) on `origin/main` before fixes.

## Existing Tool Considered

None (`alternatives.verdict: none`). Evaluated BerriAI/litellm (MIT), which supplies `GET /model/info` at runtime but cannot update devops-cli constants, CLI renderers, dry-run planners, or repository config-drift tests; estimated cost ~45k tokens to build.
