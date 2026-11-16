# Design

## Decisions

- **One project document in `docs/`.** The patterns cite issues, dates and the workloads of this cluster. A guideline of `docs/guidelines/` names no issue, date or path of one environment (`docs/guidelines/index.md`), so the patterns are a project profile. The document links each guideline rule and does not copy it.
- **Three parts for each pattern.** The rule, the reason and the check, in one table for each group. A pattern with no check says "No check yet" and names the issue that adds the check, when one exists.
- **Checks follow the owner rules of 2026-11-16.** A check is a test of the source code, a schema or policy tool, an integration or end-to-end test, or a live check. No check is a test that holds a value of a manifest or a configuration file.
- **The audit is a comment, not a table in the document.** The production readiness guideline says that no document holds the state of each row, and that an agent posts the table as a comment until the readiness report exists (#5537). `k8s/README.md` (Service levels) sends each gap to tracker #5541. So the audit of 2026-11-16 is a comment on #5541, and the document gives the steps.
- **No new ADR.** Each pattern comes from an accepted ADR, a guideline, an owner decision on an issue or an upstream document. The rollout with no gap is in ADR 0021 section 1 for the Service, and in the SRE guideline (Change safety) for each service. The choice between a Kubernetes Lease and a Valkey lock for the rows of the Service belongs to #6058.

## Rejected alternatives

- **Put the patterns in `docs/guidelines/`.** Rejected: `tests/invariants/test_guidelines.py` holds a guideline to no issue, date or environment path, and the patterns need them.
- **Put the audit table in the document.** Rejected: the state of each cell changes with each release, and the production readiness guideline keeps state out of documents.
- **Write a proposed ADR for "each workload that serves traffic rolls with no gap".** Rejected: the SRE guideline already holds the rule, with the exception path, and ADR 0021 section 1 holds it for the Service.
- **Name the value tests of the manifests as checks.** Rejected: the owner rule of 2026-11-16 forbids such tests, and #6060 deletes them.
