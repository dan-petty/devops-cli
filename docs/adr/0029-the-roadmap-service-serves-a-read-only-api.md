---
status: accepted
date: 2026-11-17
decision-makers: [owner]
issue: 4581
tracker: 4517
body-hash: "b314754029a5a6f0514dd0b158114bddb183314bf888645d4536bf65ac30ebf6"
---

# The roadmap Service serves a read-only API

## Context and Problem Statement

The roadmap Service has no API. Its HTTP surface is two webhook routes, two probes and `/metrics`, and it turns OpenAPI off (`src/devops_cli/server/`). The owner asked on 2026-11-11 for read endpoints of the Service state: health, budgets, items, claims and runs. The pipeline dashboard (#3655), the cluster start page and the CLI need that read. ADR 0021 moves the state into Valkey and the work into pods, so no process memory holds the state any more, and the API must read Valkey.

## Considered Options

- **A read-only API in the webhook router** (ADR 0021): the one long-running process that the move keeps, 2 replicas at the end. It already serves HTTP and holds the Service settings: chosen.
- **A separate read Deployment**: it adds a second process, a second image and a second settings source: rejected, because the router is the one process that the move keeps.
- **A public route through an Ingress and a Cloudflare Access application**: it widens the exposure that ADR 0003 keeps private: rejected.
- **A read of the process memory**: ADR 0021 moves the state into Valkey, so no process holds it: rejected.
- **Write routes in v1**: a pause that lives only in Valkey would break the rule that Valkey never holds the only copy of a decision: rejected.

## Decision Outcome

Chosen option: "A read-only API at `/api/v1/roadmap/` in the webhook router, in the cluster only, with one read-only token for each reader", because the router is the one long-running process that the move keeps, the state lives in Valkey, and the readers are in the cluster.

### 1. Route table and data source

One route list, and each route reads `valkey-roadmap` only:

| Route | Answer |
| :--- | :--- |
| `GET /api/v1/roadmap/health` | The liveness of the router and its Valkey connection |
| `GET /api/v1/roadmap/repos` | The managed repositories |
| `GET /api/v1/roadmap/repos/{owner}/{name}/items` | The items of one repository |
| `GET /api/v1/roadmap/repos/{owner}/{name}/items/{number}` | One item |
| `GET /api/v1/roadmap/claims` | The claims |
| `GET /api/v1/roadmap/runs` | The runs |
| `GET /api/v1/roadmap/runs/{run_id}` | One run |
| `GET /api/v1/roadmap/budgets` | The budgets |
| `GET /api/v1/roadmap/openapi.json` | The OpenAPI document |

### 2. Run id

`run_id` is the uid of the Job or the Workflow that runs the row. One id names one run.

### 3. Answer envelope

Each answer holds `as_of`, the time of the read, `links`, and one list or one object field. No route returns a bare list.

### 4. Repository in the route path

A repository is two path segments, `{owner}/{name}`, parsed with `RepoRef` (ADR 0022).

### 5. Reads and no writes

A read never sends a GitHub request or a model request. v1 has no write route. The open tool of each write: a label or a comment triggers the rows (ADR 0009, ADR 0017); the argo CLI submits, retries and suspends Workflows (ADR 0008); a limit and a suspension are GitOps changes; the halt clear is a command in the router pod.

### 6. Exposure

The API is in the cluster only. It has no Ingress and no Cloudflare Access application, and ADR 0003 keeps every other route of the Service private. The readers are Grafana through its Infinity data source, the start page widget, and the CLI through its own `kubectl port-forward`.

### 7. Auth

One named read-only bearer token for each reader (`grafana`, `startpage`, `cli`), compared in constant time. Grafana gives anonymous viewers what its token reads, from the home address with no login.

### Confirmation

`tests/invariants/test_adr_records.py` checks the form and the index of this record, and `uv run devops ci docs` regenerates the index of `docs/adr/README.md`.

## Limits

- This record holds no hostname, no private address and no token value.
- A read comes from Valkey only, so it costs no GitHub request and no model request.
- v1 holds no write route.

## Follow-up work

Each item names this record, `docs/adr/0029-the-roadmap-service-serves-a-read-only-api.md`:

1. Add the read-only API, the route list and the answer envelope.
2. Add the named read-only tokens and the constant-time compare.
3. Point Grafana, the start page and the CLI at the API.

## More Information

- The item: #4581. The records: `docs/adr/README.md`.
- The naming record: `docs/adr/0022-one-repository-reference-names-the-objects-labels-and-keys-of-each-repository.md`. The move record: `docs/adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md`.

## Status History

2026-11-17: Accepted by the owner, item #4581.
