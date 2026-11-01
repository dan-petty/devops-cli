# Tasks

## 1. Add the affinity to the three values files and empty the exemption table

Reads: `tests/core/test_k8s_local_path_placement.py`, `k8s/monitoring/pyroscope-values.yaml`, `k8s/monitoring/grafana-values.yaml`, `k8s/monitoring/prometheus-values.yaml`, `k8s/logging/loki-values.yaml`. Changes: `k8s/monitoring/grafana-values.yaml`, `k8s/monitoring/prometheus-values.yaml`, `k8s/logging/loki-values.yaml`, `tests/core/test_k8s_local_path_placement.py`.

This group changes manifests and removes data from a test. It adds no test: the placement test that exists is the check.

- [ ] 1.1 Verify with `uv run devops ci test tests/core/test_k8s_local_path_placement.py`. On the base it prints `9 passed`. Remove the three entries of `_CONTROL_PLANE_CLAIM_EXEMPTIONS` (loki `singleBinary`, grafana `grafana`, prometheus `server`) and leave `_CONTROL_PLANE_CLAIM_EXEMPTIONS: dict[str, str] = {}` with the comment above it. Run the command again. It must fail and list these three pods, which shows that the check sees the missing affinity
- [ ] 1.2 Add the required node affinity to the three values files, with the comment `# local-path binds the volume on the node where the pod first runs, and the root disk of the control-plane node has the least free space (#1634; k8s/README.md, Local-Path Volume Placement).` above each block. Copy the block of `k8s/monitoring/pyroscope-values.yaml` (lines 25 to 33): `nodeAffinity.requiredDuringSchedulingIgnoredDuringExecution.nodeSelectorTerms` with one `matchExpressions` term, key `node-role.kubernetes.io/control-plane`, operator `DoesNotExist`. Put the block at the top level (`affinity`) in `k8s/monitoring/grafana-values.yaml`, under `server` (`server.affinity`) in `k8s/monitoring/prometheus-values.yaml`, and under `singleBinary` (`singleBinary.affinity`) in `k8s/logging/loki-values.yaml`. Leave the `alertmanager.affinity` block as it is. Verify that `uv run devops ci test tests/core/test_k8s_local_path_placement.py` passes
- [ ] 1.3 Verify that the other tests that read these files pass: `uv run devops ci test tests/invariants/test_k8s_manifests.py tests/invariants/test_k8s_argocd_apps.py tests/k8s tests/commands/k8s tests/prometheus tests/grafana tests/core/test_third_party_telemetry.py tests/core/test_renovate_config.py`

## 2. Correct the README text of the placement test

Reads: `k8s/README.md` (lines 321 to 341 only; the file is 177 KB). Changes: `k8s/README.md`.

This group changes a document only, so it adds no test.

- [ ] 2.1 Verify with `! git grep -n -e 'tests/test_k8s_local_path_placement' -e 'are in it, because their volumes are on the control-plane node' -- k8s/README.md`, a command that exits 0 when it finds nothing. On the base it prints line 337
- [ ] 2.2 In the paragraph of `k8s/README.md` line 337 (section Local-Path Volume Placement), write the test path `tests/core/test_k8s_local_path_placement.py`. Delete the sentence that names Grafana (claim `grafana`), the Prometheus server (`prometheus-server`) and Loki (`storage-loki-0`) as exempt. In its place, write that the table is empty, and that a pod whose volume is still on the control-plane node gets an entry with its reason until the volume moves. Keep the last sentence about the move: move the volume as below, then remove its entry and add the affinity to its values in one pull request. Verify with the command of task 2.1, which now prints nothing
- [ ] 2.3 Regenerate the documentation with `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: before the merge of the pull request, move the three volumes to worker nodes, one at a time, in this order: `devops k8s volume move monitoring/grafana --plan` then without `--plan`, then `monitoring/prometheus-server`, then `logging/storage-loki-0` (`k8s/README.md`, section "Move a volume to another node"). A person does this, or a session that may scale these workloads: the permission system of the session that tried it refused the scale of Grafana to zero (issue #2147). Argo CD tracks `main` with self-heal, so a merge before the move leaves the three pods Pending.
- Pending a person: check each volume after its move. Grafana: the dashboards load. Prometheus: a query returns samples from before the move. Loki: a query returns the logs of the day before.
- Pending a person: after the move, check criterion 1 of the issue with `kubectl get pv -o custom-columns='NAME:.metadata.name,CLAIM:.spec.claimRef.name,POLICY:.spec.persistentVolumeReclaimPolicy,NODE:.spec.nodeAffinity.required.nodeSelectorTerms[0].matchExpressions[0].values[0]'`. The three claims must show reclaim policy `Retain` and a node for which `kubectl get nodes -L node-role.kubernetes.io/control-plane` prints no `true`.
- Pending a person: the old volumes stay `Released` after the move. Delete each one as `k8s/README.md` says, when its data is no longer needed.
