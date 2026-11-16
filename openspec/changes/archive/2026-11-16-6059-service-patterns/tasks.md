# Tasks

## 1. Write the service design patterns

Reads: `docs/adr/`, `docs/CLUSTER.md`, `k8s/README.md`, `ARCHITECTURE.md`, `SECURITY.md`, `docs/DESIGN.md`, `docs/TESTING.md`, `docs/guidelines/`.

Changes: `docs/SERVICE_PATTERNS.md`, `AGENTS.md`, `ARCHITECTURE.md`, `docs/CLUSTER.md`, `docs/index.md`, `.nav.yml`.

- [x] 1.1 Write `docs/SERVICE_PATTERNS.md` with the rule, the reason and the check of each pattern.
  - Verification: `$ uv run devops ci docs`
- [x] 1.2 Add the row of `AGENTS.md`, and link the document from `docs/CLUSTER.md`, `ARCHITECTURE.md`, `docs/index.md` and `.nav.yml`.
  - Verification: `$ uv run devops ci test tests/invariants/test_agents_md.py`

## 2. Audit the live workloads

- [x] 2.1 Check each workload of `k8s/devops/` and the gateway stack of `k8s/llm/` against each pattern, and post the table as a comment on tracker #5541. Link an open issue for each gap, and file an issue only when none exists.
  - Verification: `$ uv run devops openspec check`

## Workflow follow-up

- #6064, #6065, #6066, #6067, #6068 and #6071 hold the gaps that the audit found and that no open issue held. The audit table is a comment on tracker #5541.
