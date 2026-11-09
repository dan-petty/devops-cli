# Tasks

## 1. Agent skills and client configurations

- [x] 1.1 Update skill, devcontainer, and workflow tests for `.kilocode/skills/`, `.claude/settings.json`, Antigravity customizations, and Copilot setup steps
  - Verification: `$ uv run devops ci test tests/invariants/test_skills.py tests/invariants/test_devcontainer_config.py tests/commands/test_devcontainer.py tests/invariants/test_workflow_contracts.py`
- [x] 1.2 Synchronize the five project skills across `.agents/skills/`, `.claude/skills/`, and `.kilocode/skills/`, and update `.devcontainer/devcontainer.json`, `.claude/settings.json`, templates, and `.github/workflows/copilot-setup-steps.yml`
  - Verification: `$ uv run devops ci test tests/invariants/test_skills.py tests/invariants/test_devcontainer_config.py tests/commands/test_devcontainer.py tests/invariants/test_workflow_contracts.py`

## 2. TypeSafe Jev 1.14 integration

- [x] 2.1 Add unit and gateway tests for `typesafe/jev-1.14` routing, `SystemOneModel` resolution, `"auto"` tool-call mode, guardrails, eval judges, source verification, and RAG passage classification
  - Verification: `$ uv run devops ci test tests/ai/test_jev.py tests/ai/test_pydantic_ai_profiles_and_providers.py tests/ai/benchmark/test_k8s_llm_gateway.py`
- [x] 2.2 Add `typesafe/jev-1.14` to `k8s/llm/gateway/config.yaml`, `src/devops_cli/config/constants.py`, `src/devops_cli/ai/pydantic_ai_bridge.py`, and `src/devops_cli/ai/jev.py`
  - Verification: `$ uv run devops ci test tests/ai/test_jev.py tests/ai/test_pydantic_ai_profiles_and_providers.py tests/ai/benchmark/test_k8s_llm_gateway.py`

## 3. Kubernetes service environment

- [x] 3.1 Add runtime and stack tests for `k8s/devops/mcp-server/` manifests, implement ladder tiers, and workload telemetry opt-out variables
  - Verification: `$ uv run devops ci test tests/config/test_k8s_devops_runtime.py tests/commands/k8s/test_k8s_devops_stack.py tests/invariants/test_k8s_manifests.py tests/invariants/test_k8s_argocd_apps.py`
- [x] 3.2 Add `k8s/devops/mcp-server/` manifests, update `k8s/devops/configmap.example.yaml`, `k8s/devops/cronjob-runner.yaml`, `k8s/devops/roadmap-service/deployment.yaml`, `k8s/devops/kustomization.yaml`, and `src/devops_cli/commands/k8s/stack_lifecycle.py`
  - Verification: `$ uv run devops ci test tests/config/test_k8s_devops_runtime.py tests/commands/k8s/test_k8s_devops_stack.py tests/invariants/test_k8s_manifests.py tests/invariants/test_k8s_argocd_apps.py`

## 4. Documents

- [x] 4.1 Update `k8s/README.md` with the `k8s/devops/mcp-server/` directory tree
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_manifests.py`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
