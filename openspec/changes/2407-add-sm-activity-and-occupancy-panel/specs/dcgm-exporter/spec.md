## MODIFIED Requirements

### Requirement: The DCGM exporter collects the counter list of its values and restarts when the list changes
The `dcgm-exporter` Helm values in `k8s/monitoring/dcgm-exporter-values.yaml` SHALL hold the exporter's counter list as `customMetrics`, SHALL pass no `arguments`, and SHALL set the pod annotation `checksum/counters` to the SHA-256 of `customMetrics`. The list SHALL ask for every metric family that a dashboard reads, with the type that the exporter prints, and SHALL ask for `DCGM_FI_PROF_SM_ACTIVE` and `DCGM_FI_PROF_SM_OCCUPANCY` as gauges.

#### Scenario: The values hold the counter list and its checksum
- **WHEN** the `dcgm-exporter` Helm values are loaded
- **THEN** `arguments` is absent or empty, `customMetrics` names each family that a dashboard reads, among them `DCGM_FI_DEV_ENFORCED_POWER_LIMIT`, `DCGM_EXP_CLOCK_EVENTS_COUNT`, `DCGM_FI_PROF_SM_ACTIVE` and `DCGM_FI_PROF_SM_OCCUPANCY`, and `podAnnotations.checksum/counters` equals the SHA-256 of `customMetrics`

#### Scenario: A counter list that drops a captured family is found
- **WHEN** a counter list omits a family that a dashboard reads
- **THEN** the panel that reads that family shows "No data" on the cluster, so a person sees the gap
