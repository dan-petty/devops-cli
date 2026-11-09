# Proposal: #4274

## Why

Coding agents (Antigravity, Claude Code, GitHub Copilot, and Kilo Code) and the in-cluster service environment lacked synchronized project skills, consistent devcontainer and permission templates, an in-cluster role-scoped MCP server manifest set, and TypeSafe Jev (`typesafe/jev-1.14`) System One decision support (#4274).

## What Changes

- Synchronize `devops-openspec-new` and `new-scaffold` across `.agents/skills/`, `.claude/skills/`, and `.kilocode/skills/`, and add `devops-pr-ci`, `devops-review`, and `devops-roadmap` to all three skill roots.
- Align `customizations.antigravity` with `customizations.vscode` in `.devcontainer/devcontainer.json` and `src/devops_cli/templates/devcontainer.json.j2`, scaffold `.claude/settings.json` in `devops devcontainer init`, and install pinned security and OpenSpec tools in `.github/workflows/copilot-setup-steps.yml`.
- Add `typesafe/jev-1.14` (`openrouter/typesafe/jev-1.14`) to `k8s/llm/gateway/config.yaml` and `CONST_AI_GATEWAY_HOSTED_MODELS`, resolve `typesafe/jev-1.14` and `"auto"` in `resolve_pydantic_ai_model`, and provide Jev System One helpers in `src/devops_cli/ai/jev.py` for probability routing, auto tool calling, tool guardrails, eval judges (`LLMJudge` and `GEval`), source verification, and RAG passage classification.
- Add `k8s/devops/mcp-server/` manifests, configure two-tier implement ladders in `k8s/devops/configmap.example.yaml`, and set telemetry and banner opt-out variables on cluster workloads.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `devcontainer-agent-config`: add requirements for scaffolding `.claude/settings.json` and synchronizing skills across `.agents/skills/`, `.claude/skills/`, and `.kilocode/skills/`.
- `roadmap-service-deployment`: add requirements for `typesafe/jev-1.14` in the gateway config, the `k8s/devops/mcp-server/` manifests, and telemetry opt-out variables on `devops` workloads.

## Impact

- Code: `src/devops_cli/ai/jev.py`, `src/devops_cli/ai/providers/__init__.py`, `src/devops_cli/ai/pydantic_ai_bridge.py`, `src/devops_cli/commands/devcontainer.py`, `src/devops_cli/commands/k8s/stack_lifecycle.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/templates/claude_settings.json.j2`, `src/devops_cli/templates/devcontainer.json.j2`
- Manifests & Configurations: `.claude/settings.json`, `.devcontainer/devcontainer.json`, `.github/workflows/copilot-setup-steps.yml`, `k8s/devops/configmap.example.yaml`, `k8s/devops/cronjob-runner.yaml`, `k8s/devops/kustomization.yaml`, `k8s/devops/mcp-server/`, `k8s/devops/roadmap-service/deployment.yaml`, `k8s/llm/gateway/config.yaml`
- Skills & Documents: `.agents/skills/`, `.claude/skills/`, `.kilocode/skills/`, `k8s/README.md`
- Tests: `tests/ai/test_jev.py`, `tests/ai/benchmark/test_k8s_llm_gateway.py`, `tests/commands/k8s/test_k8s_devops_stack.py`, `tests/commands/test_devcontainer.py`, `tests/config/test_k8s_devops_runtime.py`, `tests/invariants/test_devcontainer_config.py`, `tests/invariants/test_skills.py`, `tests/invariants/test_workflow_contracts.py`

## Feasibility

- Confirmed against `pydantic_ai` 1.84.0 (`pydantic_ai.models.system_one.SystemOneModel`, `pydantic_ai.models.decision.DecisionModel`, `pydantic_ai.models.fallback.FallbackModel`, `pydantic_ai.profiles.typesafe.typesafe_model_profile`) and `pydantic_evals.evaluators.llm_as_a_judge` (`LLMJudge`, `GEval`).
- Confirmed against TypeSafe Jev 1.14 documentation (`https://docs.typesafe.ai/cookbooks`): Jev 1.14 supports 255 choice options, 10 score levels, and a 262,144-token input context window at $0.042/M input tokens and $0/M output tokens via OpenRouter (`openrouter/typesafe/jev-1.14`).
- Confirmed `Dockerfile` target `mcp-server` builds `ghcr.io/dan-petty/devops-cli/mcp-server` with `devops mcp serve --transport streamable-http`.

## Existing Tool Considered

Uses upstream `pydantic_ai` (`SystemOneModel`, `DecisionModel`, `FallbackModel`, `typesafe_model_profile`) and `pydantic_evals` (`LLMJudge`, `GEval`) directly. No custom HTTP client or decision parser is built. The change deletes no internal code.
