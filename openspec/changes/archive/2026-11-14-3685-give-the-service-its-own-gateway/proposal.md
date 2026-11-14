# Proposal: #3685

## Why

The roadmap Service calls the LLM gateway with the master key, the same key as every other caller. The gateway cannot set a budget or a requests-per-minute limit for the Service, so a fault in it can spend without limit. The Service and the cluster Jobs read `DEVOPS_CLI_AI_API_KEY` from Secret `devops-cli` with `envFrom`, so the Service holds the master key. #1635 delivered the gateway database that LiteLLM virtual keys need, so the change can start. Closes #3685.

## What Changes

- The roadmap Service Deployment reads `DEVOPS_CLI_AI_API_KEY` from key `api-key` of Secret `roadmap-service-llm-key`, and it takes no `envFrom` entry from Secret `devops-cli`.
- Each other variable of that Secret has an explicit `secretKeyRef`: the two required keys, and the four optional keys with `optional: true`.
- `k8s/README.md` says which key the Service uses, how a person mints it and stores it, and how to rotate it. No key value enters the repository, and the other cluster Jobs keep the master key.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-service-deployment`: The Service reads its own gateway key.

## Impact

- Manifests: `k8s/devops/roadmap-service/deployment.yaml`
- Documents: `k8s/README.md`
- Tests: `tests/k8s/test_roadmap_service_key.py` (new)

## Feasibility

Read on 2026-11-14 against `origin/main` at `04107728d`.

- The Service loads the shared Secret: `k8s/devops/roadmap-service/deployment.yaml:75:envFrom` with `name: devops-cli`.
- The gateway keeps virtual keys in Postgres: `k8s/README.md:116`, "Gateway database and virtual keys", and the database `llm-gateway-db` exists (`k8s/llm/gateway-db.yaml`).
- The stage Job rule admits the master key only to a stage Job: `k8s/devops/roadmap-service/admissionpolicy.yaml:91`, guarded by `variables.stage`, so it does not constrain the Service Deployment.
- `kustomize build k8s/devops/roadmap-service/` on the branch renders one `DEVOPS_CLI_AI_API_KEY` entry with `secretKeyRef` `roadmap-service-llm-key`/`api-key`, and the pod template holds no `envFrom`.
- The new tests pass on the branch: `uv run devops ci test tests/k8s/test_roadmap_service_key.py`.

## Existing Tool Considered

LiteLLM's virtual keys on the deployed gateway cover the need: `/key/generate` sets a budget, a requests-per-minute limit and a model list, and the gateway keeps them in Postgres. A person mints and stores the key, because only a person changes secrets (`AGENTS.md`). The change builds no code and adds no dependency.
