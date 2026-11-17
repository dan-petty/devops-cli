# Tasks

## 1. Record the read API decision

Reads: `docs/adr/0003-polling-is-how-the-roadmap-sees-changes.md`, `docs/adr/0008-argo-workflows-run-the-roadmap-jobs-after-a-measured-go.md`, `docs/adr/0009-one-webhook-router-delivers-each-event-to-the-consumers-subscribed-to-it.md`, `docs/adr/0017-each-subscribed-webhook-event-runs-the-update-scoped-to-it.md`, `docs/adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md`, `docs/adr/0022-one-repository-reference-names-the-objects-labels-and-keys-of-each-repository.md`, `docs/adr/README.md`, `src/devops_cli/server/`.

Changes: `docs/adr/0029-the-roadmap-service-serves-a-read-only-api.md` (new), `docs/adr/README.md`.

- [x] 1.1 Write ADR 0029 with the placement, the route list with the data source of each route, the run id, the answer envelope, the `RepoRef` path, the Valkey-only read, the in-cluster exposure, the token rule, the Grafana fact, each write that the API does not have with the open tool that covers it, and the links to ADR 0021 and ADR 0022
  - Verification: `$ uv run devops ci docs`
- [x] 1.2 Set `status: accepted` and the `body-hash`, and regenerate the index of `docs/adr/README.md`
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_records.py`

## Criteria

- Group 1: The record SHALL hold the placement, the route list with the data source of each route, the in-cluster exposure, the token rule, the Grafana exposure fact and each write that the API does not have with the open tool that covers it.
- Group 1: The record SHALL link to ADR 0021 and ADR 0022.
- Group 1: The record SHALL hold no hostname, private address or token value.

## Workflow follow-up

- The items of tracker #4517 build the API. The follow-up work of the record names them.
- Pending a person: review the design record.
