# Tasks

## 1. Design record

Reads: `docs/adr/0003-polling-is-how-the-roadmap-sees-changes.md`, `docs/adr/0008-argo-workflows-run-the-roadmap-jobs-after-a-measured-go.md`, `docs/adr/0009-one-webhook-router-delivers-each-event-to-the-consumers-subscribed-to-it.md`, `docs/adr/0017-each-subscribed-webhook-event-runs-the-update-scoped-to-it.md`, `src/devops_cli/roadmap/run.py`. Changes: `docs/adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md` (new), `docs/adr/0003-polling-is-how-the-roadmap-sees-changes.md`, `docs/adr/0008-argo-workflows-run-the-roadmap-jobs-after-a-measured-go.md`, `docs/adr/0009-one-webhook-router-delivers-each-event-to-the-consumers-subscribed-to-it.md`, `docs/adr/0017-each-subscribed-webhook-event-runs-the-update-scoped-to-it.md`.

- [x] 1.1 Write ADR 0021 and add the amendment note to ADR 0003, ADR 0008, ADR 0009 and ADR 0017
  - Verification: `$ uv run devops ci docs`

## 2. Glossary

Changes: `CONTEXT.md`.

- [x] 2.1 Define "Unit of work", "Sweep" and "Due mark"
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- The steps of tracker #4517 build the design. #4533 adds the naming record, and the pull request that merges second adds the link between the two records.
- Pending a person: review the design record.
