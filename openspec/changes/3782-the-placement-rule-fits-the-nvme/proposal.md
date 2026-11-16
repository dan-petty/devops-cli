# Proposal

## Why

Issue #3782: the placement rule of #1634 still gives the full root disk of the control-plane node as its reason, while that node keeps its volumes on a 916 GB NVMe, and the exemption entry for the gateway database names #1635, which is closed and added the database instead of removing the entry.

## What Changes

- Read a CloudNativePG Cluster as a claim owner in `tests/core/test_k8s_local_path_placement.py` when `spec.storage.storageClass` is absent or is `local-path` or `fast-nvme`, and fail the check on a Cluster that names another class.
- Make each entry of `_CONTROL_PLANE_CLAIM_EXEMPTIONS` hold the reason and the item that removes the entry, name #3803 for the Mattermost database, and file and name the follow-up item for the gateway database move.
- State in `k8s/README.md`, section Local-Path Volume Placement, that a volume of the control-plane node lives under that node's NVMe base directory `/mnt/nvme-storage/k8s`, that the ConfigMap `local-path-config` sets each node's base directory, and that the required affinity stays the rule.
- State in `k8s/README.md` why `devops k8s volume move` refuses a target on the control-plane node, and that no metric holds the path of a local-path volume, so the follow-up #3985 adds that check.
- No spec delta: the change edits one test module and one document, so no devops command, manifest or service behavior changes.
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

- The probes confirm the two cited paths word for word: "The path `tests/core/test_k8s_local_path_placement.py` is a file of the staging commit." and "The path `k8s/README.md` is a file of the staging commit."
- The probes report the two field paths of the issue as no file: "The path `spec.storage.storageClass` is no file of the staging commit. No commit in the history deleted or renamed it." and "The path `spec.affinity` is no file of the staging commit. No commit in the history deleted or renamed it.", so both are fields of a manifest and no rename removed them.
- The probe reached its bound and left these names not checked: `tests/k8s/test_k8s_volume_move.py`, `class.control`, `DoesNotExist`, `Cluster`, `LocalPathNodeDiskHigh`, `HostFilesystemSpaceLow`, `nodeSelectorTerms` and `nodeSelectorTerm`; this run read the names it needs with the tools below: `class.control` is not a name of this repository, and the class `Cluster` that the repository defines is the infra cluster model at `src/devops_cli/infra/nodes.py:264:class Cluster:`, whose definition line is `class Cluster:`, and this change does not touch it.
- The finding of the review is correct and the plan answers it at its place: `src/devops_cli/roadmap/stage/stage_change.py:def class_claim_problems` needs, for a code span that names a class under `src/`, another code span of at least three characters whose text the class source holds at the staged commit; `file_symbols` on `src/devops_cli/infra/nodes.py` listed `264: class Cluster:`, so the feasibility line above gives that class both its citation and its quote.
- The staged constants the plan relies on: `tests/core/test_k8s_local_path_placement.py:32:CNPG_GROUP = "postgresql.cnpg.io"`, `tests/core/test_k8s_local_path_placement.py:29:CONTROL_PLANE_LABEL = "node-role.kubernetes.io/control-plane"` and `tests/core/test_k8s_local_path_placement.py:36:_CONTROL_PLANE_CLAIM_EXEMPTIONS: dict[str, str] = {`; the plan changes the shape of the last one and gives no new name to a bound of the others.
- `read_file` on `tests/core/test_k8s_local_path_placement.py` lines 1-60 showed that the check already reads a CloudNativePG Cluster: `tests/core/test_k8s_local_path_placement.py:14:A CloudNativePG Cluster that sets`, the entry at `tests/core/test_k8s_local_path_placement.py:43:"k8s/llm/gateway-db.yaml:Cluster/llm-gateway-db": (` and its reason at `tests/core/test_k8s_local_path_placement.py:44:"The claim of the gateway database is on the control-plane node, and #3782 moves it."`, so the issue's premise that the test does not read a Cluster is stale and the plan adds no such reading.
- `read_file` on `tests/core/test_k8s_local_path_placement.py:214:if not str(document.get("apiVersion", "")).startswith(f"{CNPG_GROUP}/")` showed that the staged guard reads any Cluster that sets `spec.storage` and filters no storage class, so the change adds the local-path class scope of criterion 1.
- The census of the set that the change guards: `search_code` for `postgresql.cnpg.io/v1` gave 2 hits under `k8s/`, `k8s/llm/gateway-db.yaml:79:apiVersion: postgresql.cnpg.io/v1` and `k8s/mattermost/database.yaml:1:apiVersion: postgresql.cnpg.io/v1`, and `search_code` for `storageClass: local-path` gave `k8s/llm/gateway-db.yaml:101:storageClass: local-path` and `k8s/mattermost/database.yaml:15:storageClass: local-path`; both members are on a local-path class, so both stay in the checked set, none is removed or restricted, and the count is 2.
- The finding is correct, and the plan answers it: `read_issue` for #1635 gave "#1635 issue, closed (completed): feat(k8s): the LiteLLM gateway keeps virtual keys in an in-cluster Postgres" and "No merged pull request closed it", so #1635 added the database and removes no exemption; `read_issue` for #3647 gave "#3647 issue, closed (completed): fix(k8s): move the mattermost database off the control plane", and `read_issue` for its open split #3803 gave "#3803 issue, open: fix(k8s): move the Mattermost database to a worker node", so the Mattermost entry names #3803 and not #3647.
- No open item moves the gateway database volume: `find_issues` with `llm-gateway-db` listed #5081, #3741, #5091, #5267, #4970, #5303, #5535, #3782, #5094 and #3803, and `read_issue` for #3741 gave "feat(k8s): back up the gateway database off its node" and for #5094 gave "build(k8s): plan the PostgreSQL 18 move of the CNPG clusters"; the plan therefore files the follow-up item for the move and the gateway entry names it.
- `read_file` on `k8s/README.md` lines 440-500 showed the stale reason at `k8s/README.md:455:The root disk of the control-plane node is the smallest in the cluster`, the two classes at `k8s/README.md:455:use the local-path provisioner`, the exemption table at `k8s/README.md:473:| Key | Reason | Item |`, the random base-directory sentence at `k8s/README.md:480:puts each new volume under one of the two at random` and the alert paragraph at `k8s/README.md:482:The alert reads only the root filesystem`.
- The provisioner config lives in dan-petty/homelab: `k8s/README.md:35:make storage` shows that its `k8s/manifests/local-path-storage.yaml` holds the provisioner and the two StorageClasses, so the plan records the control-plane node's base directory `/mnt/nvme-storage/k8s` from the issue and names the ConfigMap `local-path-config` as the place that sets it.
- The command already refuses the target: `src/devops_cli/k8s/volume_move.py:646:if node.control_plane:` returns the refusal `volume_move_target_control_plane`, and `k8s/README.md:494:a target on the control-plane node` states the refusal, so the README gains only its reason and no code changes.
- No metric holds the path of a volume: `k8s/monitoring/prometheus-values.yaml:322:alert: LocalPathNodeDiskHigh` reads `mountpoint="/"` at `k8s/monitoring/prometheus-values.yaml:324:(1 - node_filesystem_avail_bytes{mountpoint="/"}` and joins `k8s/monitoring/prometheus-values.yaml:333:kube_persistentvolumeclaim_info{storageclass="local-path"}`, which carries no path; `read_issue` for #3985 gave "feat(k8s): fail a check when a control-plane volume is on the root disk" and "Split from #3782.", so the README names it as the follow-up.
- `read_spec` on `local-path-volume-placement` listed 21 requirements, and its requirement "A pod that mounts a claim does not run on the control-plane node" names no CloudNativePG Cluster and no storage class; the change keeps that rule closed over each Cluster, because a Cluster of another class fails the check, so no living requirement changes and the change carries no spec delta.
- `tests/support/k8s_tree.py:147:def manifests()` and `tests/support/k8s_tree.py:134:def chart_values()` read the manifests and the chart values of a checkout of the repository, so each call of the check needs that checkout, with no client and no network.
- Filing the follow-up item for the gateway database move needs a client of GitHub and a network: the runner image holds `gh`, and the job's installation token names this one repository.
- The runner holds `uv`, `python` and `pytest` from the image and `gh` for the filing, and `kubectl` is `NOT_IN_RUNNER`, so the live read of the PersistentVolumes of criterion 4 stays with #3985; the pod runs with `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault`, and the check writes no file.
- `uv run devops ci test tests/core/test_k8s_local_path_placement.py` and `uv run devops ci docs` introduce no program of their own; their failure classes are `test`, `lint` and `types`, each with the `repair` action.
- The disk figures of the issue, the root disk at 86% used before and at 25% used with 158 GB free now, and the 916 GB NVMe at /mnt/nvme-storage, are live facts of the node: not checked by this run, which reads the repository only, and recorded from the issue and from dan-petty/homelab PR #17.
- The first checks against the real system are `uv run devops ci test tests/core/test_k8s_local_path_placement.py` for the check and `uv run devops ci docs` for the README, then `uv run devops openspec check` for the change folder.

## Existing Tool Considered

`tests/core/test_k8s_local_path_placement.py` is the check, `LocalPathNodeDiskHigh` is the alert and `devops k8s volume move` is the command, and CloudNativePG (cloudnative-pg/cloudnative-pg, Apache-2.0, maintained) applies `spec.affinity` to the database pods, so the change adopts the existing tools and needs no new one; the written cost of extending this code is about 300k tokens and 2 hours.

## Dependencies

- #6046: it is open and changes `k8s/README.md` and `tests/core/test_k8s_local_path_placement.py`, the two files this change edits, so this change takes the chart versions and the claim table of the staged commit.
