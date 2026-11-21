# Tasks

## 1. Record the path of service Secrets

Reads: `docs/adr/README.md`, `docs/adr/0032-infrastructure-templates-live-in-four-homes.md`, `src/devops_cli/k8s/cluster_secrets.py`, `docs/SERVICE_PATTERNS.md`, `SECURITY.md`.

Changes: `docs/adr/0033-service-secrets-come-from-external-secrets-operator.md` (new), `docs/adr/README.md`.

- [ ] 1.1 Write ADR 0033 with the two paths for cluster Secrets, the store namespace of each service, the remote key rule, the generated, typed and unchangeable values, and the sync-wave order
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_records.py`
- [ ] 1.2 Write the owner decision of 2026-11-21 as decision text
  - Verification: `$ grep -c "2026-11-21" docs/adr/0033-service-secrets-come-from-external-secrets-operator.md`
- [ ] 1.3 Set `status: accepted` and `body-hash` on ADR 0033, and regenerate the index of `docs/adr/README.md`
  - Verification: `$ uv run devops ci --check --only docs,domain`

## 2. Accept ADR 0032

Changes: `docs/adr/0032-infrastructure-templates-live-in-four-homes.md`, `docs/adr/README.md`.

- [ ] 2.1 Set `status: accepted` and `body-hash` on ADR 0032, add a dated `Status History` line that says the merge of #6683 accepted it, and regenerate the index
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_records.py`

## 3. Documents

Changes: `docs/SERVICE_PATTERNS.md`, `SECURITY.md`, `docs/guidelines/production-readiness.md`.

- [ ] 3.1 Name the `ExternalSecret` path of a service Secret in CF4, CF5, principle 1 and ACC-1
  - Verification: `$ grep -n ExternalSecret docs/SERVICE_PATTERNS.md SECURITY.md docs/guidelines/production-readiness.md`

## Criteria

- Group 1: `ls docs/adr/0033-*.md` SHALL find one file, and `grep -c 0033 docs/adr/README.md` SHALL print 1 or more.
- Group 1: The record SHALL hold no real domain, host or node name, private address, device path or secret value.
- Group 2: The body of ADR 0032 SHALL keep the text of its merge: its `body-hash` SHALL be the hash of the body at 37b498a08.
- Group 3: `grep -n ExternalSecret docs/SERVICE_PATTERNS.md SECURITY.md` SHALL find CF4, CF5 and principle 1.

## Workflow follow-up

- The items of the plan build the decision: dan-petty/infra#12, dan-petty/homelab#82, dan-petty/homelab#96 and #6685.
