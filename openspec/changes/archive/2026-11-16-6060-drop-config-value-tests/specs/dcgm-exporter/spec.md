## MODIFIED Requirements

### Requirement: The DCGM exporter collects the counter list of its values and restarts when the list changes
The `dcgm-exporter` Helm values in `k8s/monitoring/dcgm-exporter-values.yaml` SHALL hold the exporter's counter list as `customMetrics` and SHALL pass no `arguments`, so the exporter reads the list that the chart mounts at `/etc/dcgm-exporter/default-counters.csv`. The list SHALL ask for every metric family that a dashboard reads, with the type that the exporter prints. The values SHALL set the pod annotation `checksum/counters` to the SHA-256 of `customMetrics`.

#### Scenario: The values hold the counter list and its checksum
- **WHEN** the `dcgm-exporter` Helm values are loaded
- **THEN** `arguments` is absent or empty
- **AND** `customMetrics` names each family that a dashboard reads, among them `DCGM_FI_DEV_ENFORCED_POWER_LIMIT` and `DCGM_EXP_CLOCK_EVENTS_COUNT`
- **AND** `podAnnotations.checksum/counters` equals the SHA-256 of `customMetrics`

#### Scenario: A counter list that drops a captured family is found
- **WHEN** a counter list omits a family that a dashboard reads
- **THEN** the panel that reads that family shows "No data" on the cluster, so a person sees the gap
