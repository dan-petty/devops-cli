# Tasks

## 1. Design record

Reads: `docs/adr/0019-a-decision-step-asks-jev-short-closed-questions-about-evidence-that-tools-extract.md`, `src/devops_cli/roadmap/adr.py`, `src/devops_cli/github/repo_ref.py`, `k8s/llm/valkey-devops.yaml`. Changes: `docs/adr/0023-the-project-brain-is-a-derived-index-in-two-cache-tiers-and-two-scheduled-runs-keep-it.md` (new), `docs/adr/0020-a-decision-point-is-a-unit-of-a-workflow-with-a-resolver-chain-and-a-rule-goes-before-a-decision-model.md`, `docs/adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md`, `docs/adr/0022-one-repository-reference-names-the-objects-labels-and-keys-of-each-repository.md`.

- [x] 1.1 Write ADR 0023, add the two brain rows to the unit table of ADR 0021 and the row `brain` to ADR 0022 section 2, and add the amendment note to ADR 0020, ADR 0021 and ADR 0022
  - Verification: `$ uv run devops ci docs`

## 2. Glossary

Changes: `CONTEXT.md`.

- [x] 2.1 Define "Project brain"
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- The items of tracker #4624 build the design. Each adds its spec delta under `openspec/specs/project-brain/<area>/spec.md`.
- Pending a person: review the design record.
