# Proposal: #6549

## Why
The bullet `The roadmap Service's virtual key` in `k8s/README.md` wrongly states that both the roadmap Service and its stage Job call the gateway with their own virtual key. In the manifests, only `k8s/devops/roadmap-service/deployment.yaml` reads `DEVOPS_CLI_AI_API_KEY` from Secret `roadmap-service-llm-key`, while `k8s/devops/cronjob-stage.yaml` and `k8s/devops/cronjob-runner.yaml` both read `DEVOPS_CLI_AI_API_KEY` from Secret `devops-cli`.

## What Changes
- Update `The roadmap Service's virtual key` in `k8s/README.md` so it states that only the roadmap Service Deployment calls the gateway with its virtual key (`Secret roadmap-service-llm-key`), while both the stage Job and the runner Jobs read `DEVOPS_CLI_AI_API_KEY` from Secret `devops-cli`, citing the owner decision of 2026-11-20 (`#2695`, comment `7045868447`).
- Add a requirement to `openspec/specs/roadmap-service-deployment/spec.md` documenting this distinction.

## Capabilities
- Modified: `roadmap-service-deployment`

## Impact
- `k8s/README.md`
- `openspec/specs/roadmap-service-deployment/spec.md`

Fits in one pull request.

## Feasibility
Confirmed on `origin/main`:
- `k8s/README.md:125` claims the stage Job uses its own virtual key.
- `k8s/devops/cronjob-stage.yaml:110-114` and `k8s/devops/cronjob-runner.yaml:167-171` read `DEVOPS_CLI_AI_API_KEY` from Secret `devops-cli`.
- `k8s/devops/roadmap-service/deployment.yaml:92-96` reads `DEVOPS_CLI_AI_API_KEY` from key `api-key` of Secret `roadmap-service-llm-key`.

## Existing Tool Considered
No external tool applies; this is a documentation correction (`alternatives.verdict: not-applicable`), costing minimal prose edit and review time.
