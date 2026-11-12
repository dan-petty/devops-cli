# Proposal

## Why

Every retry of a step uses the same model tier. A model defect fails the same call on every repeat and a harder step gets no stronger model (#3060).

## What Changes

- Add a config setting `roadmap.implement.ladder` that maps each step class (`plan`, `edit`, `repair`, `review`) to an ordered tier list.
- Default the ladder to local model tiers only, following `SECURITY.md` item 12.
- Validate that the ladder setting rejects hosted model names unless explicitly configured.
- Print the ladder setting in `devops config show`.
- Define an attempt as one run of a step with a specific tier from the ladder.
- Rebuild the step agent for each attempt with the model and context window of that tier.
- Advance to the next tier of the ladder when failure classification selects `FailureAction.CHANGE_TIER` (such as `FailureClass.PARSER`).
- Do not increment the repair round counter when the step changes tiers.
- Update `failure.py` so stop comments record a tier change as an action taken.
- Read gateway tier health before a tier choice and skip a tier that the gateway reports unhealthy.
- Record the tier and token counts of each completed step in `StepOutcome` and persist per-tier spend under `implement.spend` in the run record.
- Add spec deltas to `roadmap-implement-step/model-calls`, `roadmap-implement-job/record`, and `roadmap-failure-taxonomy`.
- Record the order against #3207 for maintainer priority decision.
- The change fits one pull request.

## Order and Dependencies

Issue #3207 asks to park cost work (#3066, #3060) until the cloud baseline evaluation passes. A person sets priorities. This plan lets a maintainer decide whether to implement #3060 before or after the #3207 cloud baseline passes.
PR #3223 closed #3206 by making model request timeouts configurable via `roadmap.implement.request_timeout_seconds`. Each tier attempt in the ladder respects this configured timeout.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step/model-calls`: The step chooses a tier per attempt from the ladder and advances on FailureAction.CHANGE_TIER
- `roadmap-implement-job/record`: The spend itemizes token cost per tier
- `roadmap-failure-taxonomy`: The action left is wait after a tier change is taken

## Impact

- Code: `src/devops_cli/config/settings.py`, `src/devops_cli/commands/config.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/ai/client/factory.py`, `src/devops_cli/ai/gateway.py`, `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_run.py`
- Documents: `docs/CONFIGURATION.md`, `docs/commands/config.md`, `docs/roadmap/implement.md`
- Tests: `tests/config/test_settings.py`, `tests/commands/test_config_cmd.py`, `tests/ai/test_ai_gateway_probes.py`, `tests/roadmap/test_roadmap_failure.py`, `tests/roadmap/test_roadmap_implement_step.py`, `tests/roadmap/test_roadmap_implement_records.py`

## Feasibility

- Gateway configuration in `k8s/llm/gateway/config.yaml:295, 310-311` shows LiteLLM router retries (`num_retries: 5`) and fallback routing (`devops-coder: [devops-reasoning, devops-chat]`).
- Gateway model definitions in `k8s/llm/gateway/config.yaml:24-35` show `devops-coder` and `devops-reasoning` both map to `qwen3-coder:30b` on `ollama-48gib-fast`. Only `devops-chat` (`qwen3.8:27b`) provides an alternative model family on the cluster.
- Gateway probing in `src/devops_cli/ai/gateway.py:460-476` (`_probe_gateway_http`) checks `/health/readiness` and `/health` for overall router availability. It provides no per-tier health status.
- LiteLLM router fallbacks handle network and transport errors when an endpoint is down. LiteLLM cannot handle semantic failures where the model returns HTTP 200 with unparseable tool call syntax (`FailureClass.PARSER`, #2953).
- The client ladder carries out `FailureAction.CHANGE_TIER` after parser classification failure. It rebuilds the agent with the appropriate model and context window.
- The implementation checks run offline with `uv run devops ci test tests/config/test_settings.py`, `tests/commands/test_config_cmd.py`, `tests/ai/test_ai_gateway_probes.py`, `tests/roadmap/test_roadmap_failure.py`, `tests/roadmap/test_roadmap_implement_step.py`, and `tests/roadmap/test_roadmap_implement_records.py`.

## Existing Tool Considered

LiteLLM (`k8s/llm/gateway/config.yaml`) covers backend network retries and fallbacks between deployment targets.
LiteLLM does not cover client-side recovery from semantic parser failures (`FailureClass.PARSER`). It does not provide per-step-class ladder configuration (`plan`, `edit`, `repair`, `review`). It does not adjust agent context windows across attempts, and does not record per-tier token spend in roadmap run records.
The change builds the ladder mechanism on top of the existing gateway client. The cost to build, keep, and fix this feature is 24,000 tokens and 3 hours. The change deletes no internal code.
