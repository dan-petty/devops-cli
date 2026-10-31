## ADDED Requirements

### Requirement: grafana-prometheus-loki-control-plane-affinity
The values files for Grafana, the Prometheus server, and Loki SHALL include the control-plane DoesNotExist node affinity, and the three claims SHALL NOT appear in the control-plane claim exemption list.

#### Scenario: placement test passes with no exemptions
- **WHEN** tests/test_k8s_local_path_placement.py runs with grafana, prometheus-server, and storage-loki-0 removed from the exemption list
- **THEN** the test passes, confirming the affinity is present in all three values files

#### Scenario: exemption list is empty
- **WHEN** CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS is read from src/devops_cli/config/constants.py
- **THEN** the list is empty or the constant is absent
