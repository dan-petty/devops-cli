# Tasks

## 1. Design records

Reads: `src/devops_cli/github/repo_ref.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/adr.py`, `k8s/README.md`. Changes: `docs/adr/0020-a-decision-point-is-a-unit-of-a-workflow-with-a-resolver-chain-and-a-rule-goes-before-a-decision-model.md`, `docs/adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md`, `docs/adr/0022-one-repository-reference-names-the-objects-labels-and-keys-of-each-repository.md`.

- [x] 1.1 Add the six rows, section 8, the semaphore `steward` and the corrected Argo Events facts to ADR 0021
  - Verification: `$ uv run devops ci --check --only docs`
- [x] 1.2 Add the six rows and the row name rule to ADR 0022 section 2
  - Verification: `$ uv run devops ci --check --only docs`
- [x] 1.3 Add the point `resolve.question_class` and the count of 92 series to ADR 0020
  - Verification: `$ uv run devops ci --check --only docs`

## 2. Glossary

Changes: `CONTEXT.md`.

- [x] 2.1 Define "Roadmap step" and "Step job"
  - Verification: `$ uv run devops ci --check --only docs`

## Workflow follow-up

- The items of trackers #4780 and #5014 build the rows. Each adds its spec delta and its `ServiceRow` member.
- #5049 records that the ADR budget of the alternatives check has 9 tokens left.
- Pending a person: review the amended records. The merge approves the rows and the semaphore `steward`.
