# Tasks

## 1. Documents

- [x] 1.1 Update the `The roadmap Service's virtual key` bullet in `k8s/README.md` to name Secret `devops-cli` for `DEVOPS_CLI_AI_API_KEY` in stage and runner Jobs, Secret `roadmap-service-llm-key` for Deployment `devops/roadmap-service`, and the 2026-11-20 owner decision
  - Verification: `$ rg -n 'stage Job.*DEVOPS_CLI_AI_API_KEY.*devops-cli' k8s/README.md && rg -n 'runner Jobs.*DEVOPS_CLI_AI_API_KEY.*devops-cli' k8s/README.md && rg -n 'Deployment.*DEVOPS_CLI_AI_API_KEY.*roadmap-service-llm-key' k8s/README.md && rg -n '2026-11-20.*#2695.*7045868447' k8s/README.md && ! rg -n 'Service and its stage Job call the gateway with their own virtual key' k8s/README.md`
- [x] 1.2 Archive `6549-k8s-readme-stage-key` into `openspec/specs/roadmap-service-deployment/spec.md` and pass OpenSpec and docs checks
  - Verification: `$ uv run devops ci --check --no-cache --only docs,openspec`
