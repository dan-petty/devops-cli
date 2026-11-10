# Design

## Decisions

- **Read `spec.affinity` of a CloudNativePG Cluster that sets `spec.storage` in `_manifest_pods`.**: The operator applies `spec.affinity` to the database pods, the test already reads an affinity object through `keeps_off_the_control_plane`, and the tree readers render no chart.
- **Keep the guard in `tests/core/test_k8s_local_path_placement.py` and add no new test module.**: `keeps_off_the_control_plane`, `_CONTROL_PLANE_CLAIM_EXEMPTIONS` and `_manifest_pods` live there, and a second module would need a second exemption table with the same rule.
- **Allowlist both Clusters that the new guard finds: `mattermost-db` with a reason that names #3803, and `llm-gateway-db` with a reason that names #3782.**: Both set `spec.storage` with the `local-path` class and neither sets `spec.affinity`, so the new guard fails on both; the exemption test fails when an entry goes stale, so each entry goes when its Cluster gains the affinity.
- **Do not set the affinity in `k8s/mattermost/database.yaml` in this change.**: The claim is on the control-plane node, so the pod would stay Pending and Mattermost would stop; #3803 sets the affinity with the move of the volume.
- **Add the Mattermost Cluster to `EXPECTED_MANIFEST_PODS` and leave the gateway Cluster to the exemption test.**: The issue requires the expected entry for the Mattermost Cluster, and the exemption test already fails when an exempt key names no pod that the checks find.
- **Correct the paragraph of `k8s/README.md` that says the exemption table is empty.**: The change makes the table non-empty, and that paragraph is the rule a person reads before a volume move.

## Rejected alternatives

- **Extend `devops k8s volume move` to move the claim of a CloudNativePG Cluster.**: The issue records that the command refuses with `Pod mattermost-db-1 belongs to Cluster mattermost-db.`, and the operator owns the pods and the claim.
- **Set the control-plane affinity in `k8s/mattermost/database.yaml` now.**: The volume is on the control-plane node, so the pod cannot mount the claim there and stays Pending; #3803 moves the volume first.
- **Render the CloudNativePG chart and read the pods it produces.**: `tests/support/k8s_tree.py` states that the readers read files only and render no chart, and the Cluster is a manifest, not a chart.
- **Leave CloudNativePG Clusters out of the placement test.**: #3782 records that the gap let the Mattermost and gateway databases land on the control-plane root disk with no check.
- **Add a new test module for CloudNativePG Clusters.**: The exemption table and `keeps_off_the_control_plane` are in `tests/core/test_k8s_local_path_placement.py`, and a second module would duplicate the exemption rule.

## Security

Nothing new crosses a trust boundary: the change edits one test file and one README section, and the test reads YAML files of the repository with no cluster, no network and no credential. A person must confirm that each entry of `_CONTROL_PLANE_CLAIM_EXEMPTIONS` names a claim owner that is still on the control-plane node, and that the Mattermost entry goes when the volume moves in #3803. If the Cluster gains the control-plane affinity while its exemption stays, `test_every_exemption_names_a_pod_on_a_claim_that_stays_on_any_node` fails.
