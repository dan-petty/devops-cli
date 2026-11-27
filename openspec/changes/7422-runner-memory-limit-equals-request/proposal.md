# Proposal: #7422

## Why

A runner Job requests the memory of its size row (`2Gi` or `6Gi`, `src/devops_cli/roadmap/implement/implement_size.py`), and its limit is the setting `roadmap.implement.max_memory_limit` (`16Gi` on this cluster). The scheduler places a pod by its request only. So a Job can go to a node that cannot hold its limit, and a Job that grows past its request takes memory from the other pods of the node and from the k3s server (#7422). The owner decided on 2026-11-27 to use the standard Kubernetes form with no custom node label: memory is not compressible, so the memory limit equals the memory request.

## What Changes

- Each row of `RUNNER_SIZES` gives the memory request and the memory limit of the container `agent` as one value. The small row is 1 CPU with 5Gi and the large row is 4 CPU with 11Gi, from the peaks of the last 14 days with the room of T1 in `docs/guidelines/kubernetes.md` (the peak is at most 80 % of the limit).
- Remove the setting `roadmap.implement.max_memory_limit`, its variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_MAX_MEMORY_LIMIT`, its default and its validator. Nothing else reads it. `job_launcher.runner_job` and `RunnerSize.resources` take no memory limit.
- The admission policy `roadmap-service-jobs` admits the two new rows only, and refuses a Job of the Service whose memory limit differs from its memory request.
- The example ConfigMap holds no `max_memory_limit`.
- `docs/CLUSTER.md` gives the new rows and the rule. `docs/CONFIGURATION.md` and `docs/ENV_VARS.md` lose the setting.

The change alters a manifest and the Jobs of the Service, so it carries spec deltas.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job/runner-job`: the rows give the memory limit; the setting and its requirements go.
- `roadmap-implement-runner`: the policy pins the memory limit to the memory request.
- `roadmap-fix-checks`: the fix-checks Job has the large row of 4 CPU with 11Gi.
- `roadmap-service-deployment`: the example ConfigMap holds no runner memory limit.

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_size.py`, `src/devops_cli/roadmap/job_launcher.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`
- Manifests: `k8s/devops/roadmap-service/admissionpolicy.yaml`, `k8s/devops/configmap.example.yaml`
- Tests: `tests/roadmap/implement/test_roadmap_implement_size.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/security/test_config_declarations.py`, `tests/gate/k8s_checks/job_admission_policy.py`
- Documents: `docs/CLUSTER.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`
- The cluster: a large Job reserves 11Gi in place of 6Gi, and a small Job 5Gi in place of 2Gi. A node with less free allocatable memory gets no runner Job.
- The live ConfigMap `devops/devops-cli-config` holds `max_memory_limit: 16Gi`. The section `roadmap.implement` ignores a key that it does not declare (`extra="ignore"`), so the Service loads it with the new image. A settings load with that key in the file and the old variable set gave no error on 2026-11-27. The key can go from the ConfigMap source at any time.

The change fits one pull request.

## Feasibility

- Read on `origin/main`, 2026-11-27: `job_launcher.launch` is the only reader of `roadmap.implement.max_memory_limit` (`git grep -n max_memory_limit -- src`). `settings.RoadmapImplementConfig` has `extra="ignore"`.
- Prometheus, 2026-11-27, 14 days, namespace `devops`, containers `agent` and `runner`, joined per pod with `kube_pod_container_resource_requests` and `kube_pod_init_container_resource_requests` (the container `agent` is an init container): every Job had a limit of 16Gi. Small row (1 CPU, request 2Gi): 42 Jobs, highest working set 3.80 GiB (4.08 GB). Large row (4 CPU, request 6Gi): 117 Jobs, highest working set 8.05 GiB (8.65 GB), p95 4.76 GiB. Five Jobs of each row went above the request of the row.
- The container `agent` exists only since the three-container Job of #3700 (first pod 2026-11-22). Its peaks are 2.10 GiB (16 Jobs, small row) and 4.54 GiB (26 Jobs, large row). The other Jobs of the window ran every phase in one container `runner`. The `prepare` and `publish` containers peak at 0.56 GiB and 0.25 GiB, so they do not explain the higher peaks of the one container. The issue gave 4.54 GiB as the highest peak of 14 days. That number holds only the container `agent`, so the rows use the peaks of both containers.
- No container of the window ended with the reason `OOMKilled` (`kube_pod_container_status_terminated_reason` and `kube_pod_init_container_status_terminated_reason`).
- Kubernetes takes the largest request and the largest limit of the init containers, and the sum of the app containers, as those of the pod. `agent` (5Gi or 11Gi) is above the 2Gi limits of `prepare` and `publish`, so the pod request equals the pod limit.

## Existing Tool Considered

The Kubernetes scheduler and the request of a pod cover the need: no new tool and no custom node label (#5485 and dan-petty/homelab#302 are closed as not planned). The change deletes the setting `roadmap.implement.max_memory_limit`, `DEFAULT_ROADMAP_IMPLEMENT_MAX_MEMORY_LIMIT`, `MIN_MEMORY_LIMIT_GI` and the validator `_check_max_memory_limit`.
