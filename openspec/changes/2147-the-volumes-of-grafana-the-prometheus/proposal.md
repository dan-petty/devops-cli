# Proposal

## Why

Issue #2147 (follow-up of #1634): the volumes of Grafana (`monitoring/grafana`), the Prometheus server (`monitoring/prometheus-server`) and Loki (`logging/storage-loki-0`) are still on the control-plane node, whose root disk has the least free space. The test of the placement rule exempts the three pods for this reason. When the volumes sit on worker nodes, the three pods get the control-plane `DoesNotExist` node affinity, and the exemptions go.

A person moves the volumes with `devops k8s volume move`. This change delivers the part that the repository holds: the affinity in the three values files, the empty exemption table, and the README text.

## What Changes

- Add the required node affinity with `node-role.kubernetes.io/control-plane` `DoesNotExist` to `k8s/monitoring/grafana-values.yaml` (key `affinity`), to `k8s/monitoring/prometheus-values.yaml` (key `server.affinity`) and to `k8s/logging/loki-values.yaml` (key `singleBinary.affinity`).
- Remove the three entries of `_CONTROL_PLANE_CLAIM_EXEMPTIONS` in `tests/core/test_k8s_local_path_placement.py`. The table stays and is empty, with its comment, so a later pod that must stay on the node has a place for its reason.
- Change the text of the section Local-Path Volume Placement in `k8s/README.md`: the test path is `tests/core/test_k8s_local_path_placement.py`, and the text no longer names the three pods as exempt.
- The issue names a constant `CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS` in `src/devops_cli/config/constants.py`. This constant does not exist (see Feasibility). The only exemption table is `_CONTROL_PLANE_CLAIM_EXEMPTIONS` in the test. The change touches no file under `src/`.
- The spec delta is a MODIFIED requirement of `local-path-volume-placement`. The values files are manifests, and a consumer sees their affinity. The delta adds one scenario to the requirement and keeps the rest of it.
- The change fits one pull request. It must not merge before the volumes are moved (see Workflow follow-up in `tasks.md`).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-path-volume-placement`: the requirement "A pod that mounts a claim does not run on the control-plane node" gets a scenario for Grafana, the Prometheus server and Loki.

## Acceptance

- Criterion 1, `kubectl get pv` shows the volumes of the three claims on worker nodes with reclaim policy Retain: pending a person. The move scales Grafana, Prometheus and Loki to zero and changes the cluster, which an implementation Job does not do. The check is in Workflow follow-up.
- Criterion 2, the exemption list is empty or gone and the placement test passes with no exemption: group 1 (the table is empty and the test passes). Group 2 corrects the README text of the same table.
- The affinity in the three values files, and the move of each volume with its check (dashboards load, Prometheus has samples from before the move, Loki answers a query for the day before): the affinity is group 1. The move and its checks are pending a person.

## Impact

- Manifests: `k8s/monitoring/grafana-values.yaml`, `k8s/monitoring/prometheus-values.yaml`, `k8s/logging/loki-values.yaml`.
- Test: `tests/core/test_k8s_local_path_placement.py`. The change reuses its `CHART_CLAIMS` entries for `grafana`, `prometheus` and `loki`, its `EXPECTED_CHART_PODS`, and `keeps_off_the_control_plane`. It adds no test.
- Document: `k8s/README.md`, section Local-Path Volume Placement (lines 321 to 341).
- Spec: `openspec/specs/local-path-volume-placement/spec.md` (via the delta in this folder).
- Tests that read the three values files and must stay green: `tests/invariants/test_k8s_manifests.py`, `tests/invariants/test_k8s_argocd_apps.py`, `tests/commands/k8s`, `tests/prometheus`, `tests/grafana`.
- The open plan #2519 changes the keys of `CHART_CLAIMS` in the same test file. It does not touch `_CONTROL_PLANE_CLAIM_EXEMPTIONS`, so the two changes edit different lines and need no order.

## Feasibility

All checks ran on 2026-11-01 on `origin/main` (commit 9f3b7010).

- The constant of the issue does not exist. `git grep -n CLAIM_EXEMPTIONS -- src tests k8s` prints only `tests/core/test_k8s_local_path_placement.py` (lines 14, 32, 274, 288 and 303, all `_CONTROL_PLANE_CLAIM_EXEMPTIONS`) and `k8s/README.md:337`. `git grep -n CONTROL_PLANE src/devops_cli/config/constants.py` prints only line 3465, `CONST_K8S_CONTROL_PLANE_LABEL`. So the plan changes no constant.
- The paths of the issue are wrong. `git ls-files` lists `k8s/monitoring/grafana-values.yaml`, `k8s/monitoring/prometheus-values.yaml`, `k8s/logging/loki-values.yaml` and `tests/core/test_k8s_local_path_placement.py`. There is no `tests/test_k8s_local_path_placement.py`, and `k8s/README.md:337` names that wrong path.
- The affinity is absent. `git grep -n -i affinity -- k8s/monitoring/grafana-values.yaml k8s/logging/loki-values.yaml` prints nothing. In `k8s/monitoring/prometheus-values.yaml` the only `affinity:` (line 57) is under `alertmanager:` (line 49), not under `server:`.
- The test passes on the base: `uv run devops ci test tests/core/test_k8s_local_path_placement.py` prints `9 passed`. It has three exemptions: `k8s/logging/loki-values.yaml:singleBinary`, `k8s/monitoring/grafana-values.yaml:grafana` and `k8s/monitoring/prometheus-values.yaml:server`.
- The order matters. In a trial copy, the removal of the three entries alone made the test fail: `test_every_chart_pod_on_a_claim_keeps_off_the_control_plane_node` listed exactly these three pods. The affinity alone fails `test_every_exemption_names_a_pod_on_a_claim_that_stays_on_any_node`, because that test requires an exempt pod to lack the affinity (lines 292 to 304 of the test). So the affinity and the removal go in one group.
- With the affinity added and the table empty, the trial copy passed: `9 passed` for the placement test, `725 passed` for `tests/invariants/test_k8s_manifests.py tests/invariants/test_k8s_argocd_apps.py tests/k8s`, and `666 passed` for `tests/commands/k8s tests/prometheus tests/grafana tests/core/test_third_party_telemetry.py tests/core/test_renovate_config.py tests/core/test_k8s_local_path_placement.py`. The trial copy was reverted.
- The charts take the keys. `helm template` with the trial values rendered the block in the pod spec of the Deployment `grafana` (chart `grafana` 14.0.1, `grafana-community` repository), of the Deployment of the Prometheus server (chart `prometheus` 29.35.0) and of the Loki StatefulSet (chart `loki` 20.0.2, template `monolithic/workload.yaml`). The versions are the `targetRevision` of `k8s/argocd/apps/grafana.yaml`, `prometheus.yaml` and `loki.yaml`.
- The volumes are not moved yet. `kubectl get pv` (columns name, claim, reclaim policy, status, node of the volume's node affinity) shows `monitoring/grafana`, `monitoring/prometheus-server` and `logging/storage-loki-0` as `Retain` and `Bound`, and `kubectl get nodes -L node-role.kubernetes.io/control-plane` shows that their node is the one control-plane node. So the premise holds, and the move is still to do.
- Nothing newer did or removed the work. `git log --since=2026-10-24 --format='%h %s' -- k8s/monitoring k8s/logging` has no commit that moves these volumes or changes their affinity. The issue #1634 is closed; its pull request (#2150) added the test and the exemptions.
- The merge order is a risk. `k8s/README.md:337` says a pod with the affinity cannot start while its volume is on the control-plane node, and Argo CD tracks `main` with prune and self-heal. A merge before the move leaves the three pods Pending. The plan states this gate in Workflow follow-up.
- Out of scope, seen in the same `kubectl get pv`: the volume `mattermost/mattermost-db-1` is also on the control-plane node. It is no claim of this issue, and the placement test does not read the CloudNativePG cluster.

## Existing Tool Considered

No external tool covers this. `devops k8s volume move` (`src/devops_cli/k8s/volume_move.py`, `k8s/README.md` section "Move a volume to another node") already moves a volume, and the placement test already checks the affinity. The change edits three values files, one dict in the test and one README paragraph. It deletes the three exemption entries and builds no new code.
