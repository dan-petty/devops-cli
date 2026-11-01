## MODIFIED Requirements

### Requirement: A pod that mounts a claim does not run on the control-plane node
Each pod that mounts a claim SHALL have a required node affinity in which every node selector term holds the expression `node-role.kubernetes.io/control-plane` `DoesNotExist`. This applies to a pod in a chart values file that an Argo CD Application installs, and to a pod in a manifest under `k8s/`. A pod in the test's table of exemptions SHALL be the only exception. Each exemption SHALL name a pod that mounts a claim and does not have that affinity.

#### Scenario: A chart pod mounts a claim
- **WHEN** a test reads the values file of each chart that an Application installs, with the claim switches and the affinity paths of that chart
- **THEN** each pod whose claim is on, and that is not exempt, has the expression in every required node selector term

#### Scenario: A manifest pod mounts a claim
- **WHEN** a test reads each workload under `k8s/` that mounts a PersistentVolumeClaim declared under `k8s/` or has a claim template
- **THEN** each such workload that is not exempt has the expression in every required node selector term of its pod spec

#### Scenario: An Application installs a chart that the test does not know
- **WHEN** an Application installs a chart that has no entry in the test's table of chart claims
- **THEN** the test fails and names the chart

#### Scenario: An exemption is stale
- **WHEN** an exemption names a pod that the test does not find, or a pod that has the affinity
- **THEN** the test fails and names the exemption

#### Scenario: Only a required term in every term counts
- **WHEN** the check reads an affinity with no node affinity, with the expression only as a preference, or with a second required term without it
- **THEN** the check reports that the pod can run on the control-plane node

#### Scenario: Grafana, the Prometheus server and Loki keep off the control-plane node
- **WHEN** a test reads `k8s/monitoring/grafana-values.yaml`, `k8s/monitoring/prometheus-values.yaml` and `k8s/logging/loki-values.yaml`, and the table of exemptions names none of their pods
- **THEN** the pods `grafana`, `server` and `singleBinary` each have the expression in every required node selector term
