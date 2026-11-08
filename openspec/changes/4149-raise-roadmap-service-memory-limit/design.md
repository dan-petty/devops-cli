# Design

## Decisions

- **Set the memory request to 768Mi and the limit to 3Gi in `k8s/devops/roadmap-service/deployment.yaml`.**: The working set starts near 460 MiB and grows about 120 MiB each hour, so 3Gi lasts about 21 hours. The alert `RoadmapServiceMemoryNearLimit` fires at 85 percent, about 2.5Gi, before a kill. The request of 768Mi is the normal working set after a few hours.
- **Keep the CPU request (100m) and the CPU limit (1).**: The kills are memory kills (`OOMKilled`), and the issue asks for no CPU change.
- **Change the Deployment in git only.**: Argo CD syncs `main` with self-heal, so a `kubectl patch` would be reverted. A person merges, and the pod restarts once on the rollout.
- **Keep the alert rule.**: The rule divides the working set by `kube_pod_container_resource_limits`, so it follows the new limit.
- **Hold the limit with one test number.**: The test names the start (460 MiB), the growth (150 MiB each hour) and the hours (10) with their source, so a later cut of the limit fails the test and names #4116.
- **Name #4116 as the analysis and #4125 as the open check in the comment and in `k8s/README.md`.**: #4116 is closed, so the text does not call it open.

## Rejected alternatives

- **Use the Vertical Pod Autoscaler.**: It does not stop a leak and needs a new controller in the cluster. The homelab keeps requests in git (see Existing Tool Considered in the proposal).
- **Raise the limit with `kubectl patch`.**: Argo CD self-heal reverts it. The first run of the new test on `origin/main` shows that the manifest is the source: it reads `('256Mi', '1Gi', '100m', '1')`.
- **Raise the limit to more than 3Gi.**: The pod would reach 3Gi after about 21 hours, and the alert fires about 3 hours before that. A larger limit hides the leak for longer and uses more of a node that has 32 GB.
- **Leave the limit at 1Gi until #4140 is rolled out.**: The pod is killed about every 3 hours, a kill loses the memory state, and the alert has no time to warn (the working set read in the proposal reaches 864 MiB in 3 hours).
- **Change the CronJobs.**: `k8s/devops/cronjob-runner.yaml` (4Gi request, 8Gi limit) and `k8s/devops/cronjob.yaml` (256Mi request, 1Gi limit) show no OOM kill.
