# Task: Update Agent Instructions with Roadmap-Service Details, Concurrency Guardrails, and Liveness Diagnostics (#1236)

**Issue**: [#1236](https://github.com/dan-petty/devops-cli/issues/1236)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p2-medium
**Scope**: scope/ai, type/docs

## Description

Updated canonical AI agent instructions in `AGENTS.md` and generator templates in `src/devops_cli/ai/instruction_generator.py`:
- Documented in-cluster `roadmap-service` architecture, continuous daemon execution (`devops serve --service`), webhook integration (`POST /webhooks/github`), and autonomous background batch jobs (`intake`, `close`, `reprioritize`, `refine`, `metrics`).
- Established strict concurrency guardrails: AI agents and workflows must avoid running overlapping manual roadmap mutations (`devops roadmap close --confirm`, `devops roadmap intake --confirm`, manual PR cuts) while `roadmap-service` is active to eliminate GitHub rate limit starvation and git worktree/clone contention.
- Provided comprehensive service liveness and health inspection procedures (`kubectl` deployment/pod status, HTTP probes `GET /readyz` and `/healthz` on port 8000, service logs, and Prometheus metrics), along with recovery runbooks (`devops k8s push-secrets --rotate`, pod restart) and safe manual fallback protocols when the service is confirmed offline.

## Acceptance Criteria

- [x] `AGENTS.md` documents in-cluster `roadmap-service` architecture, execution mode, webhooks, and autonomous operations.
- [x] `AGENTS.md` mandates concurrency avoidance against running overlapping roadmap mutations or duplicate state changes while `roadmap-service` is active.
- [x] `AGENTS.md` details how to verify if `roadmap-service` is running via Kubernetes CLI, HTTP probes (`/readyz`, `/healthz`), logs, and Prometheus metrics.
- [x] `AGENTS.md` documents troubleshooting, credential rotation recovery, and safe manual fallback when offline.
- [x] `src/devops_cli/ai/instruction_generator.py` scaffolds `AGENTS.md` containing `roadmap-service` and concurrency guidance when `is_devops_cli=True`.
- [x] All claim and generator verification tests pass (`tests/test_agents_md_claims.py`, `tests/test_instruction_generator.py`, `tests/test_docs_review_loop.py`).
- [x] Fast in-gate checks pass and `changelog.d/1236.md` is provided.
- Pending a person: `uv run devops ci` passes on this branch.

## Deliverables

- [x] `AGENTS.md`: Added `roadmap-service` architecture, concurrency guardrails, liveness verification, and offline fallback procedures.
- [x] `src/devops_cli/ai/instruction_generator.py`: Updated `devops_roadmap_governance_block` template.
- [x] `changelog.d/1236.md`: Added release changelog fragment.
- [x] `docs/agent/tasks/task-1236-update-agent-instructions-roadmap-service.md`: Task tracking file.
