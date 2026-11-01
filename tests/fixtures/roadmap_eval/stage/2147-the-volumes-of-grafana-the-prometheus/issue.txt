### What happened

#1634 moves every local-path volume off the control-plane node, whose 236 GB root disk is about 79% used. On 2026-10-24 an agent moved Pyroscope, Qdrant and Open WebUI with the copy procedure of `k8s/README.md` (Local-Path Volume Placement), and checked each copy. It could not move Grafana (`monitoring/grafana`), the Prometheus server (`monitoring/prometheus-server`) and Loki (`logging/storage-loki-0`): the permission system of that session refused the scale to zero of Grafana. Their old volumes are set to Retain, and `CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS` in `src/devops_cli/config/constants.py` exempts them from the placement test, so the merge of #1634 does not leave their pods Pending.

### What should happen

A person (or a session where scaling these workloads is allowed) moves the three volumes to worker nodes with the README procedure, one at a time (Grafana, then Prometheus, then Loki), and checks each one: Grafana dashboards load, Prometheus has samples from before the move, Loki answers a query for the day before. Then the values get the control-plane `DoesNotExist` affinity (`affinity` for Grafana, `server.affinity` for Prometheus, `singleBinary.affinity` for Loki), and the three entries leave the exemption list.

### Acceptance criteria

- [ ] `kubectl get pv` shows the volumes of the three claims on worker nodes, with reclaim policy Retain.
- [ ] `CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS` is empty or gone, and `tests/test_k8s_local_path_placement.py` passes with no exemption.


Source: https://github.com/dan-petty/devops-cli/issues/1634

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=48c78ca94dcb5ef557482da4f7711266d31a7673 -->
## Proposed design

### Problem statement
Grafana, Prometheus server and Loki volumes are on the control-plane node. This uses 79% of the 236 GB root disk. Moving these volumes off the control-plane node improves system stability.

### Acceptance criteria
- Criterion 1: kubectl get pv shows the volumes of the three claims on worker nodes, with reclaim policy Retain.
  Verification: Run 'kubectl get pv' and verify that grafana, prometheus-server and storage-loki-0 volumes are on worker nodes and have reclaim policy Retain.
- Criterion 2: CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS is empty or gone, and tests/test_k8s_local_path_placement.py passes with no exemption.
  Verification: Check that CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS in src/devops_cli/config/constants.py is empty or removed. Run tests/test_k8s_local_path_placement.py to verify it passes without exemptions.

### Key questions
- **Which three volumes are currently on the control-plane node?**: The volumes are grafana in monitoring namespace, prometheus-server in monitoring namespace, and storage-loki-0 in logging namespace. [sources: k8s/README.md]
- **What is the procedure to move a volume to another node?**: Use 'devops k8s volume move /' command with the README procedure. The command copies data from old volume to new volume on worker node, scales workloads to zero during copy, and checks each copy. [sources: k8s/README.md]
- **What changes are needed after moving the volumes?**: The affinity rules need to be added to Grafana, Prometheus server and Loki configurations. The entries must also be removed from CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS in src/devops_cli/config/constants.py. (proposed) [sources: k8s/README.md]

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Medium", "Owner": null, "Priority": "P1-High", "Status": "Planned", "Value": "High", "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "8873a3f0c283e1b03224eb3ed169e664eebf9ee884b4bf18db04cd4a7dddd92d", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "ac5f5ab39b24fe42005ca136646536987a286f04561563198bc6d4342d3b0106", "stage.branch": "fix/2147-the-volumes-of-grafana-the-prometheus", "stage.file_cap": null, "stage.groups": "[[\"Add control-plane affinity to the three values files\", 2680], [\"Remove the three exemptions from constants and test\", 2672]]", "stage.needs_split": null, "stage.pr": "2857", "stage.ready": "2857", "stage.sha": "ff7d18baad9a68626c3dab9c70fa54cb63bab427"} -->
