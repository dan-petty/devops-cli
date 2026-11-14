# Tasks

## 1. Give the Service its own key

Kind: behavior. Reads: `k8s/devops/roadmap-service/deployment.yaml`, `k8s/README.md`. Changes: the same paths, `tests/k8s/test_roadmap_service_key.py`.

- [x] 1.1 Read `DEVOPS_CLI_AI_API_KEY` from Secret `roadmap-service-llm-key`, remove `envFrom`, and name each other variable with a `secretKeyRef`
  - Verification: `$ uv run devops ci test tests/k8s/test_roadmap_service_key.py` passes
  - Verification: `$ kustomize build k8s/devops/roadmap-service/` renders the new reference
- [x] 1.2 Write the mint, store and rotate steps in `k8s/README.md`
  - Verification: `$ uv run devops ci docs` passes

## 2. Run the gates

Kind: other. Reads: `tests/k8s/`. Changes: none.

- [x] 2.1 Run the gate of the branch
  - Verification: `$ uv run devops ci test tests/k8s` passes
  - Verification: `$ uv run devops ci --check --only lint,format,typecheck` passes
