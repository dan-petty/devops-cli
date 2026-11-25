## ADDED Requirements

### Requirement: Documented gateway key of the Service and Jobs
The `The roadmap Service's virtual key` bullet of `k8s/README.md` SHALL state that only the roadmap Service Deployment reads `DEVOPS_CLI_AI_API_KEY` from Secret `roadmap-service-llm-key`, while the stage Job and the runner Jobs read `DEVOPS_CLI_AI_API_KEY` from Secret `devops-cli`, naming the owner decision of 2026-11-20 (`#2695`, comment `7045868447`).

#### Scenario: Stage and runner Job keys in README
- **WHEN** a reader inspects the `The roadmap Service's virtual key` bullet of `k8s/README.md`
- **THEN** the bullet states that both the stage Job and the runner Jobs read `DEVOPS_CLI_AI_API_KEY` from Secret `devops-cli`, Deployment `devops/roadmap-service` reads `DEVOPS_CLI_AI_API_KEY` from Secret `roadmap-service-llm-key`, the 2026-11-20 owner decision (`#2695`, comment `7045868447`) is named, and no claim says the stage Job uses its own virtual key
