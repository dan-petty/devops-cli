# Tasks

## 1. Read each Cluster on a local-path class and name the item that removes each exemption

Kind: other. Reads: `k8s/llm/gateway-db.yaml`, `k8s/mattermost/database.yaml`, `tests/support/k8s_tree.py`, `tests/core/test_k8s_local_path_placement.py`. Changes: `tests/core/test_k8s_local_path_placement.py`.

- [x] 1.1 In `tests/core/test_k8s_local_path_placement.py`, read a CloudNativePG Cluster as a claim owner when `spec.storage.storageClass` is absent or is `local-path` or `fast-nvme`, and fail the check with the key of a Cluster that names any other class, so no Cluster escapes. Add the gateway Cluster to `EXPECTED_MANIFEST_PODS`. Change `_CONTROL_PLANE_CLAIM_EXEMPTIONS` into a table whose entries hold the reason and the item that removes the entry, keep the Mattermost entry with #3803, and file the follow-up item `fix(k8s): move the gateway database off the control-plane node` with `gh issue create` for the gateway entry, because #1635 is closed and no open item moves that volume. Extend `test_every_exemption_names_a_pod_on_a_claim_that_stays_on_any_node` and add `test_every_exemption_names_the_item_that_removes_it`, which fails and names the claim of an entry with no removing item. Update the module docstring with the new rule, the class scope and the two entries
  - Verification: `$ uv run devops ci test tests/core/test_k8s_local_path_placement.py` passes

## 2. State the NVMe rule, the provisioner config and the missing metric in k8s/README.md

Kind: other. Reads: `tests/core/test_k8s_local_path_placement.py`, `k8s/monitoring/prometheus-values.yaml`, `src/devops_cli/k8s/volume_move.py`. Changes: `k8s/README.md`.

- [ ] 2.1 In the section Local-Path Volume Placement of `k8s/README.md`, replace the reason that the root disk is the smallest in the cluster with the NVMe: the root disk of the control-plane node is at 25% used with 158 GB free, a 916 GB NVMe is mounted at /mnt/nvme-storage, and a volume of that node lives under its NVMe base directory /mnt/nvme-storage/k8s, so a pod may run on that node when its volume path is under that directory. Name the ConfigMap `local-path-config` in namespace `local-path-storage` as the place that sets the base directory of each node, and state that the base directory of the control-plane node is the NVMe one. State that the check reads a Cluster whose storage class is `local-path` or `fast-nvme` and fails on a Cluster of another class. Extend the exemption table so each row names the claim, the reason and the item that removes the entry, with #3803 for the Mattermost database and the follow-up item of this change for the gateway database, and state that an entry with no removing item fails the check. Add the reason why `devops k8s volume move` refuses a target on the control-plane node: the provisioner chooses the base directory from the node's own config, so the command cannot prove that a new volume is on the NVMe. State in the paragraph on `LocalPathNodeDiskHigh` that the rule reads only the root filesystem, that `HostFilesystemSpaceLow` reads a filesystem by its mountpoint, that no metric or series holds the path of a local-path volume, and that #3985 adds the check that reads the PersistentVolumes
  - Verification: `$ uv run devops ci docs` passes
- [ ] 2.2 Edit `k8s/README.md`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: The test reads each `postgresql.cnpg.io/v1` `Cluster` in `k8s/` with a local-path storage class, and applies the same rule as it does to a StatefulSet.
- Group 2: The rule text in `k8s/README.md` (Local-Path Volume Placement) states the new reason and the new rule: a pod may run on the control-plane node when its volume path is under the NVMe base directory of that node, and the README names the provisioner config as the place where the path is set.
- Group 1: The test keeps its table of exemptions. An entry names the claim, the reason, and the issue that removes it. The gateway database and the Mattermost database (#3647) are entries until their volumes are on the NVMe.
- Group 2: A check reads the live volumes and fails when a local-path volume of the control-plane node is under the root-disk base directory (`/var/lib/rancher/k3s/storage`). Use the existing alert and metric path (`LocalPathNodeDiskHigh`, `HostFilesystemSpaceLow`) if it can express this. If no metric holds the path of a volume, say so and file the follow-up.
- Group 2: `devops k8s volume move` accepts the control-plane node as a target when the target path is on the NVMe, or the README says why it does not.
