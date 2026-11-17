## REMOVED Requirements

### Requirement: A pod that mounts a claim does not run on the control-plane node
**Reason**: Scenarios of this requirement described the test that read the manifests, which #6119 deletes (#6060).
**Migration**: The requirement "A pod on a claim keeps off the control-plane node" holds the rule, with scenarios that name a live check or a validator command.

## ADDED Requirements

### Requirement: A pod on a claim keeps off the control-plane node
Each pod that mounts a claim SHALL have a required node affinity in which every node selector term holds the expression `node-role.kubernetes.io/control-plane` `DoesNotExist`. This applies to a pod in a chart values file that an Argo CD Application installs, and to a pod in a manifest under `k8s/`. A pod in the table of `k8s/README.md` that names the pods that stay on the control-plane node SHALL be the only exception, until its item moves the volume.

#### Scenario: A chart pod mounts a claim
- **WHEN** a person runs `kubectl get pods -A -o wide` and lists the pods that mount a claim
- **THEN** each such pod that is not in the table of `k8s/README.md` runs on a worker node

#### Scenario: A manifest pod mounts a claim
- **WHEN** a reviewer reads the pod spec of a workload under `k8s/` that mounts a PersistentVolumeClaim or has a claim template
- **THEN** each such workload that is not in the table of `k8s/README.md` has the expression in every required node selector term of its pod spec

#### Scenario: Grafana, the Prometheus server and Loki keep off the control-plane node
- **WHEN** a person runs `kubectl -n monitoring get pods -o wide` and `kubectl -n logging get pods -o wide` on the cluster
- **THEN** the pods of `grafana`, of the Prometheus `server` and of Loki run on worker nodes
