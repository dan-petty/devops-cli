# Design

## Decisions

- **Keep the required node affinity as the rule that each manifest states, and give the README the NVMe reason for it.**: The check reads files only, so it cannot know the base directory that the provisioner picks for a node; `k8s/README.md:455:The root disk of the control-plane node is the smallest in the cluster` is the stale reason that the change replaces.
- **Read a Cluster as a local-path claim owner when its storage class is absent or is `local-path` or `fast-nvme`, and fail the check on a Cluster that names another class.**: The criterion scopes the rule to a local-path storage class and `k8s/README.md:455:use the local-path provisioner` names the two classes; a Cluster of an unknown class fails, so no Cluster escapes the check, and the two members of `k8s/` both stay in the checked set.
- **Keep both database entries and name the item that removes each: #3803 for the Mattermost database, and the follow-up item filed by this change for the gateway database.**: `read_issue` for #3647 gave "closed (completed)" and #3803 is its open split that moves that volume; `read_issue` for #1635 gave "closed (completed)" and it added the database, and `find_issues` with `llm-gateway-db` lists no open item that moves the gateway volume, so this change files the follow-up item and the entry names it.
- **State the reason of the volume-move refusal in `k8s/README.md` and change no code of the command.**: `src/devops_cli/k8s/volume_move.py:646:if node.control_plane:` refuses the target today, and the provisioner chooses the base directory from the node's own config, so the command cannot prove that a new volume is on the NVMe.
- **Add no live check and no new metric.**: `k8s/monitoring/prometheus-values.yaml:333:kube_persistentvolumeclaim_info{storageclass="local-path"}` carries no path and the rule reads `mountpoint="/"`, so no series holds the path of a volume; #3985 adds the check that reads the PersistentVolumes.
- **Carry no spec delta.**: The change edits one test module and one document, and `read_spec` on `local-path-volume-placement` shows no requirement that names a CloudNativePG Cluster or a storage class, so no living requirement changes.
- **Leave the recorded-plan fixtures that name `_CONTROL_PLANE_CLAIM_EXEMPTIONS` alone.**: They are the recorded case, issue, plan and result of items #2147 and #2519, and this change re-records none of them.

## Rejected alternatives

- **Name #1635 as the item that removes the gateway database exemption.**: `read_issue` for #1635 gave "#1635 issue, closed (completed): feat(k8s): the LiteLLM gateway keeps virtual keys in an in-cluster Postgres" and "No merged pull request closed it", so #1635 added the database and moves no volume.
- **Name #3647 as the item that removes the Mattermost exemption.**: `read_issue` for #3647 gave "#3647 issue, closed (completed): fix(k8s): move the mattermost database off the control plane", and its open split #3803 gave "#3803 issue, open: fix(k8s): move the Mattermost database to a worker node".
- **Read the provisioner config in the check instead of the affinity.**: The config lives in dan-petty/homelab and is not in this repository, so the check would depend on a repository that it does not read.
- **Drop the affinity rule and rely on the `LocalPathNodeDiskHigh` alert.**: `k8s/README.md:482:The alert reads only the root filesystem`, so it reports the root filesystem and never the path of a volume.
- **Add the required affinity to the two Cluster manifests now.**: `k8s/llm/gateway-db.yaml:101:storageClass: local-path` and `k8s/mattermost/database.yaml:15:storageClass: local-path` show both volumes bind on the control-plane node, so a pod with the affinity stays Pending and the database goes down.
- **Accept the control-plane node as a target of `devops k8s volume move`.**: `src/devops_cli/k8s/volume_move.py:646:if node.control_plane:` keeps the refusal, and the provisioner picks the base directory from the node's own config, so the command cannot prove that the new volume is on the NVMe.

## Unchanged references

- `tests/fixtures/roadmap_eval/stage/2147-the-volumes-of-grafana-the-prometheus/plan.json` (recorded plan): It holds the recorded plan of item #2147, and this change re-records no plan.
- `tests/fixtures/roadmap_eval/stage/2147-the-volumes-of-grafana-the-prometheus/case.json` (recorded case): It holds the recorded case of item #2147, and this change re-records no case.
- `tests/fixtures/roadmap_eval/stage/2147-the-volumes-of-grafana-the-prometheus/issue.txt` (recorded issue text): It holds the recorded issue text of item #2147, and this change re-records no issue text.
- `tests/fixtures/roadmap_eval/completeness/plan-2147-dropped/case.json` (recorded case): It holds the recorded case of item #2147, and this change re-records no case.
- `tests/fixtures/roadmap_eval/completeness/plan-2147-dropped/draft.diff` (recorded diff): It holds the recorded diff of item #2147, and this change re-records no diff.
- `tests/fixtures/roadmap_eval/implement/2519-claim-table-versions/results/committed.diff` (recorded result): It holds the recorded result of item #2519, and this change re-records no result.

## Security

The change edits one test module and the document `k8s/README.md` under `k8s/`; it adds no manifest, no cluster rule, no credential and no pod setting, so no trust boundary moves. A person must confirm that each exemption entry names the item that removes it and that the follow-up item for the gateway database move is filed, because an entry with no such item would let a database volume stay on the root disk of the node that also runs the API server. `uv run devops ci test tests/core/test_k8s_local_path_placement.py` fails when a CloudNativePG Cluster on a local-path class has no control-plane affinity, when an exemption goes stale, or when an entry names no removing item.
