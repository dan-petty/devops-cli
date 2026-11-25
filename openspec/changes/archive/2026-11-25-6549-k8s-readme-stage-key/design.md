# Design

## Decisions
- Rewrite only the stale sentence and add the owner decision citation in the `The roadmap Service's virtual key` bullet of `k8s/README.md` so all bootstrap and key-rotation instructions stay unchanged.
- Record both Secret bindings (`roadmap-service-llm-key` for Deployment `devops/roadmap-service`; `devops-cli` for the stage Job and runner Jobs) and cite `2026-11-20 (#2695, comment 7045868447)`.

## Rejected alternatives
- Leave the virtual-key wording unchanged or rewrite surrounding bullets: rejected because the stage Job text directly contradicts `k8s/devops/cronjob-stage.yaml` while the surrounding bootstrap notes remain accurate.
