# Tasks

## 1. Read CloudNativePG Clusters in the placement test

Reads: `tests/core/test_k8s_local_path_placement.py`, `tests/support/k8s_tree.py`, `k8s/mattermost/database.yaml`, `k8s/llm/gateway-db.yaml`. Changes: `tests/core/test_k8s_local_path_placement.py`.

- [x] 1.1 Add the new case to `tests/core/test_k8s_local_path_placement.py`: a Cluster document with `spec.storage` and an affinity that holds only `podAntiAffinity` makes `keeps_off_the_control_plane` return False, the same document with the control-plane `DoesNotExist` term in every required term returns True, and a document without `spec.storage` is no pod on a claim. Add a helper that takes one manifest document and returns its name and `spec.affinity` when its apiVersion is of the CloudNativePG group and `spec.storage` is set, and call it from `_manifest_pods` so the key joins the file and the Cluster name. Add the Mattermost Cluster to `EXPECTED_MANIFEST_PODS`, and add the Mattermost Cluster and the `llm-gateway-db` Cluster to `_CONTROL_PLANE_CLAIM_EXEMPTIONS`, each with a reason that names #3803 or #3782. Then run `test_every_manifest_pod_on_a_claim_keeps_off_the_control_plane_node` and `test_every_exemption_names_a_pod_on_a_claim_that_stays_on_any_node`
  - Verification: `$ uv run devops ci test tests/core/test_k8s_local_path_placement.py` passes

## 2. State the Cluster rule and the two exemptions in k8s/README.md

Reads: `k8s/README.md`, `tests/core/test_k8s_local_path_placement.py`. Changes: `k8s/README.md`.

- [ ] 2.1 State in the rule paragraph of the section Local-Path Volume Placement that the check reads each CloudNativePG Cluster with `spec.storage` as a pod on a claim and takes its affinity from `spec.affinity`. Replace the paragraph that says the exemption table is empty with the two entries, their reasons and the items that move them (#3803 and #3782). Keep the move procedure unchanged and point at #3803 for the move of the database
  - Verification: `$ uv run devops ci docs` passes
- [ ] 2.2 Edit `k8s/README.md`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Pending person: `kubectl get pv` shows the volume of the database on a worker node, and Mattermost reads its data after the move., The move runs on the live cluster with `kubectl`, which is NOT_IN_RUNNER, and it needs a maintenance window; #3803 delivers it.
- Pending person: `k8s/mattermost/database.yaml` sets the required node affinity with `node-role.kubernetes.io/control-plane` `DoesNotExist` under `spec.affinity.nodeAffinity`., The affinity goes in with the move: with the claim on the control-plane node the pod would stay Pending, so #3803 sets the affinity after the volume moves.
- Group 1: `tests/core/test_k8s_local_path_placement.py` reads the CloudNativePG Cluster manifests, and fails when such an affinity is missing.
- Pending person: The move has a backup of the database first, and a person runs the steps that change the cluster., A backup and the cluster steps need a person and the live cluster; #3803 delivers them in one window.
