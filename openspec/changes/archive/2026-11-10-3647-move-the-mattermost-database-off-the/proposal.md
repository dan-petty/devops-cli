# Proposal

## Why

The claim of the Mattermost database in namespace `mattermost` sits on the control-plane node, and the placement test cannot see it: `_manifest_pods` in `tests/core/test_k8s_local_path_placement.py` reads workload kinds, and a CloudNativePG Cluster is no workload kind. #3647 makes the check see the Cluster and records why its volume stays, and the follow-up item moves it.

## What Changes

- Read each CloudNativePG Cluster that sets `spec.storage` as a pod on a claim, with its affinity from `spec.affinity`, in `_manifest_pods` of `tests/core/test_k8s_local_path_placement.py`.
- Add the Mattermost Cluster to `EXPECTED_MANIFEST_PODS` at `tests/core/test_k8s_local_path_placement.py:152:EXPECTED_MANIFEST_PODS = frozenset(` so a wrong path cannot pass by finding nothing.
- Add an entry to `_CONTROL_PLANE_CLAIM_EXEMPTIONS` at `tests/core/test_k8s_local_path_placement.py:33:_CONTROL_PLANE_CLAIM_EXEMPTIONS: dict[str, str] = {}` for the Mattermost Cluster, with a reason that names #3803, and one for the `llm-gateway-db` Cluster, with a reason that names #3782.
- Correct the paragraph at `k8s/README.md:383:of the test is empty, because each pod that mounts a claim has the affinity.` so it states the two exemptions, and state in the rule paragraph that the check reads CloudNativePG Clusters.
- No spec delta: the change edits a test and a document, and no `devops` command, service or manifest behavior changes; no cluster is touched.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `k8s/README.md`
- Tests: `tests/core/test_k8s_local_path_placement.py`

## Feasibility

- The probe confirms the two cited paths word for word: "The path `k8s/mattermost/database.yaml` is a file of the staging commit." and "The path `tests/core/test_k8s_local_path_placement.py` is a file of the staging commit."
- The probe says of the API group: "The path `postgresql.cnpg.io` is no file of the staging commit. No commit in the history deleted or renamed it.", so no rename applies and the issue asks for a new reading of a document kind that exists.
- The probe reached its bound: "Not probed, the bound of 10 commands is reached: `spec.storage`, `spec.affinity.nodeAffinity.requiredDuringSchedulingIgnoredDuringExecution.nodeSelectorTerms`, `spec.storage.storageClass`, `spec.storage.size`, `spec.instances`, `tests/support/k8s_tree.py`, `k8s/README.md`, `that.DoesNotExist`, `It.command`, `Retain`, `backup`, `affinity`, `CHART_CLAIMS`, `DoesNotExist`, `nodeSelectorTerms`, `EXPECTED_MANIFEST_PODS`, `test_every_manifest_pod_on_a_claim_keeps_off_the_control_plane_node`, `_CONTROL_PLANE_CLAIM_EXEMPTIONS`, `test_every_exemption_names_a_pod_on_a_claim_that_stays_on_any_node`, `mattermost`, `keeps_off_the_control_plane`". Each item of that list is `not checked` by the probe; the files below were read with the tools of this run.
- `read_file` on `k8s/mattermost/database.yaml` showed a CloudNativePG Cluster `mattermost-db` with `k8s/mattermost/database.yaml:15:storageClass: local-path` and no `spec.affinity` key, which confirms the premise of the issue.
- `read_file` on `k8s/llm/gateway-db.yaml` lines 55-100 showed a second CloudNativePG Cluster `llm-gateway-db` with `k8s/llm/gateway-db.yaml:85:storageClass: local-path` and no `spec.affinity`, so the new guard covers two members and each member needs a decision.
- `search_code` for `postgresql.cnpg.io` gave 7 hits: the two Cluster manifests under `k8s/`, a reader in `tests/invariants/test_k8s_manifests.py` and four test lines; the set under `k8s/` has 2 members, both allowlisted with a reason, and none is removed or restricted.
- `read_file` on `k8s/README.md` lines 365-392 showed the sentence the change corrects, `k8s/README.md:383:of the test is empty, because each pod that mounts a claim has the affinity.`, and the rule paragraph at line 381.
- `read_spec` on `local-path-volume-placement` listed 13 requirements and none names a CloudNativePG Cluster; the change edits a test and a document, so it carries no spec delta.
- `read_issue` for #1634 and #2147 showed both closed; #3803 is open and is the follow-up split from #3647 that moves the database, sets the affinity and removes the exemption; #3782 is open and reads CloudNativePG Clusters in the same test and the same README section. `find_issues` with `mattermost-db control plane` listed #3647, #3803 and #3782.
- The issue cannot be built in full in a pull request: `kubectl` is `NOT_IN_RUNNER`, the volume is on the control-plane node, and the affinity makes the pod Pending before the move; the refine block defers the move and the affinity to #3803, and this plan plans no code that compensates.
- First checks against the real system: `uv run devops ci test tests/core/test_k8s_local_path_placement.py` for the test change, then `uv run devops ci docs` for the README change.
- `uv run devops ci test tests/core/test_k8s_local_path_placement.py` and `uv run devops ci docs` need a checkout of the repository and no client and no network; the test reads files of that checkout and renders no chart.
- Runner: `uv`, `python` and `pytest` come from the runner image, and `kubectl` is `NOT_IN_RUNNER`; the pod runs with `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault`, and the test writes no file.
- Failure classes of the two commands: `test` for a failing case, `lint` and `types` for the static checks of the changed file; each takes the `repair` action.

## Existing Tool Considered

CloudNativePG (cloudnative-pg/cloudnative-pg, Apache-2.0, maintained, last activity 2026-11-07) applies `spec.affinity` to the database pods and can make an instance on a worker node from a replica or a restore, so the change adopts it and builds no tool of its own.

## Dependencies

- Overlap with #3782: it changes `tests/core/test_k8s_local_path_placement.py` and the Local-Path Volume Placement section of `k8s/README.md`, so one plan lands first and the other rebases on it.
- Follow-up #3803: it changes `tests/core/test_k8s_local_path_placement.py` and `k8s/mattermost/database.yaml`, and it removes the exemption that this plan adds, so it lands after this plan.
