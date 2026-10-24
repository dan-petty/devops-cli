# Task: Grafana Provisioning Deletes the Read-Only Jaeger Datasource (#2036)

**Issue**: [#2036](https://github.com/dan-petty/devops-cli/issues/2036)
**Scope**: scope/telemetry
**Feasibility**: After #1624, Grafana 13.2.4 still listed the Jaeger datasource. `DELETE /api/datasources/uid/jaeger` returned `{"message":"Cannot delete read-only data source"}` on 2026-10-24, because Grafana marks a provisioned datasource read-only. `prune: true` deletes only rows that Grafana marked prunable, and this row is older than that setting. Grafana's provisioning documents `deleteDatasources`, which deletes each listed datasource at start and ignores a name that does not exist.

## Description
The provisioning file in `k8s/monitoring/grafana-values.yaml` lists Jaeger under `deleteDatasources`. The text check in `tests/test_k8s_tempo.py` still bans every Jaeger mention in `k8s/`, a comment included, except the names in that list. The chart puts a checksum of the datasource config on the pod, so the change restarts Grafana once, and Grafana deletes the datasource at that start.

## Acceptance Criteria
- [x] `test_grafana_provisioning_deletes_a_datasource_that_leaves_the_file` requires `deleteDatasources: [{name: Jaeger, orgId: 1}]`. It fails on the base and passes now.
- [x] The text check of `test_tempo_stack_contract_and_datasource_links` leaves out only the names in `deleteDatasources`.
- Pending a person: after Argo CD syncs, `GET /api/datasources` lists five datasources and no Jaeger.
