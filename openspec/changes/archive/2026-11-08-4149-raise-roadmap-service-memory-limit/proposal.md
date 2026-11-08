# Proposal

## Why

#4149: the kernel killed the container `service` of `deployment/roadmap-service` with `OOMKilled` two times on 2026-11-08, after 2 h 39 min and after 3 h 40 min. The memory request is 256Mi and the limit is 1Gi. The working set grows 100 to 150 MiB each hour, from 370-460 MiB to more than 860 MiB. The fix of #4116 (bounded session answers, a capped export queue and the alert `RoadmapServiceMemoryNearLimit`) is merged, but it is not proven to stop the growth, and its image is not rolled out yet. A kill loses the memory state of the Service, and the alert (85 percent of the limit) has no time to warn, because the pod dies in about 3 hours. The owner asked on 2026-11-08 to raise the limits a reasonable amount. A limit of 3Gi lets the pod run for about 21 hours at 120 MiB each hour from 460 MiB, so the alert fires before a kill. The raise is a stopgap and not the fix: #4116 holds the analysis of the leak, and #4125 (the 6-hour flat check of the working set) stays open.

## What Changes

- `k8s/devops/roadmap-service/deployment.yaml`: the memory request of container `service` goes from 256Mi to 768Mi, and the memory limit from 1Gi to 3Gi. The CPU request (100m) and the CPU limit (1) stay. A comment above `resources` says that the raise is a stopgap, gives the observed growth, and links #4116 and #4125.
- `k8s/README.md`, section Roadmap service: one sentence names the request, the limit and the reason, and links #4116 and #4125.
- `tests/server/routes/test_k8s_roadmap_service.py`: the test `test_deployment_memory_is_sized_for_the_observed_growth` holds the four values and holds that the limit is at least 10 hours of growth at 150 MiB each hour above 460 MiB. A later cut of the limit fails the test and names #4116.
- The change carries a spec delta, because a manifest is observable: `roadmap-service-deployment` gains the requirement "The Service container has memory for the observed growth".
- The alert rule `RoadmapServiceMemoryNearLimit` needs no change: it divides the working set by `kube_pod_container_resource_limits`, and it holds no literal limit. The CronJobs (`cronjob-runner.yaml`, `cronjob.yaml`), the Job admission policy and the PVC stay.
- The change fits one pull request.
- Rollout: the change sets the Deployment only. No ConfigMap key changes, so no ConfigMap must be applied before the rollout. Argo CD syncs the Deployment from `main`, and the pod restarts once, which is expected. Nobody changes the cluster by hand.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-service-deployment`: The Service container has memory for the observed growth

## Impact

- Manifests: `k8s/devops/roadmap-service/deployment.yaml`
- Documents: `k8s/README.md`
- Tests: `tests/server/routes/test_k8s_roadmap_service.py`

## Feasibility

- The manifest holds the old values: `k8s/devops/roadmap-service/deployment.yaml` sets `requests` to `cpu: 100m`, `memory: 256Mi` and `limits` to `cpu: "1"`, `memory: 1Gi` for the container `service`. Argo CD syncs `main` with self-heal, so a change in git is the only change that stays. A `kubectl patch` would be reverted.
- The metrics confirm the premise. They were read from Prometheus through the Grafana datasource, with no write to the cluster. `kube_pod_container_resource_limits` for container `service` is 1024 MiB. `container_memory_working_set_bytes` over 6 hours, at 30-minute steps, reads 508, 576, 651, 683, 763, 788, 856 and 864 MiB, then 613 MiB after a restart, then 660, 682, 700 and 763 MiB. So the growth is 100 to 150 MiB each hour, and the 1Gi limit is reached in about 3 hours.
- The first run of the new test fails for the right reason: on `origin/main` it reports `('256Mi', '1Gi', '100m', '1') != ('768Mi', '3Gi', '100m', '1')`.
- The alert reads the limit from the metric: `k8s/monitoring/prometheus-values.yaml` divides the working set by `kube_pod_container_resource_limits{resource="memory"}`, and the fixture `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml` sets its own limit series. The alert therefore follows the new limit with no rule change (about 2.5Gi at 85 percent of 3Gi).
- No merged or open pull request does this. #4140 (merged) is the mitigation of the leak. #4125 is open. No newer issue or ADR supersedes the item.
- The issue says that #4116 stays open. #4116 is closed (the pull request #4140 closed it, and its change is archived as `openspec/changes/archive/2026-11-08-4116-roadmap-service-is-oomkilled-after`). So the comment in the Deployment and the sentence in `k8s/README.md` link #4116 as the issue that holds the analysis of the leak, and #4125 as the open check. They do not say that #4116 is open. The pull request comment says that the leak is not proven fixed, and that a person may reopen #4116 if the working set still grows after the rollout.
- The smallest node has 32 GB of memory and at most 44 percent is used, so a request of 768Mi and a limit of 3Gi fit.
- Documents that name the old numbers: `git grep -n -E '1Gi|256Mi'` finds `openspec/specs/gitea-forge/spec.md` (Gitea), `tests/server/routes/test_k8s_roadmap_service.py` (the storage of the PVC), `k8s/devops/roadmap-service/pvc.yaml` (storage) and `k8s/devops/cronjob.yaml` (a CronJob). None names the memory of the Service Deployment, so none changes.

## Existing Tool Considered

The Vertical Pod Autoscaler (the upstream Kubernetes autoscaler) can set requests from observed use. It does not stop a leak, it needs a new controller in the cluster, and the homelab keeps the request in git (Argo CD with prune and self-heal), so it is not used for one Deployment. A `LimitRange` or a `ResourceQuota` sets a default and not the size of one Deployment. The alert `RoadmapServiceMemoryNearLimit` (kubelet and kube-state-metrics series) is the tool that shows the leak, and it stays. A heap measure of the live pod (`memray` or the standard `tracemalloc`) finds the cause, and that is the work of #4116. The change adds no code and deletes no internal code. Written cost: about 25,000 tokens to build and test it, one number to revisit when the leak is fixed, and about 20 minutes of elapsed time including the CI run.

## Dependencies

None.
