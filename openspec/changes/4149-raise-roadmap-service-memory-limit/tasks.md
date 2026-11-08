# Tasks

## 1. Size the memory of the Service container

Kind: behavior

Reads: `k8s/devops/roadmap-service/deployment.yaml`, `tests/server/routes/test_k8s_roadmap_service.py`, `k8s/monitoring/prometheus-values.yaml`. Changes: `k8s/devops/roadmap-service/deployment.yaml`, `tests/server/routes/test_k8s_roadmap_service.py`.

- [x] 1.1 Add `test_deployment_memory_is_sized_for_the_observed_growth` to `tests/server/routes/test_k8s_roadmap_service.py`. It holds the memory request `768Mi`, the memory limit `3Gi`, the CPU request `100m` and the CPU limit `1`, and it holds that the limit is at least 460 MiB plus 10 hours of growth at 150 MiB each hour, with the source named in a comment. Run it and see it fail on the base
  - Verification: `$ uv run devops ci test tests/server/routes/test_k8s_roadmap_service.py` fails on the base
- [x] 1.2 In `k8s/devops/roadmap-service/deployment.yaml`, set the memory request to `768Mi` and the memory limit to `3Gi`, keep the CPU values, and write a comment above `resources` that says the raise is a stopgap, gives the growth of 100 to 150 MiB each hour from 460 MiB, links #4116 (the analysis of the leak) and #4125 (the open 6-hour flat check), and says that the limit is to be revisited when the leak is fixed. Do not change another manifest
  - Verification: `$ uv run devops ci test tests/server/routes/test_k8s_roadmap_service.py` passes
- [x] 1.3 Prove that the alert rule still reads the limit from the metric and holds no literal limit
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`

## 2. Document the raise

Kind: documents

Reads: `k8s/README.md`. Changes: `k8s/README.md`.

- [x] 2.1 In the Roadmap service section of `k8s/README.md`, add one sentence on the line of the Deployment description: the container `service` requests `768Mi` and limits `3Gi` of memory, the raise is a stopgap for a working set that grows 100 to 150 MiB each hour (#4116 holds the analysis, #4125 the flat check), and `RoadmapServiceMemoryNearLimit` fires before a kill. The alert row keeps its sentence that a rise of the limit only delays the kill
  - Verification: `$ grep -n '3Gi' k8s/README.md | grep -i 'roadmap service'`
- [x] 2.2 Check that no other document names the old memory numbers of the Service
  - Verification: `$ ! git grep -n -E '256Mi.*roadmap-service|roadmap-service.*1Gi' -- k8s docs openspec/specs`
- [x] 2.3 Check the manifests, the documents and the change
  - Verification: `$ uv run devops ci --check --only k8s,docs,openspec`

## Workflow follow-up

- #4116 (closed) holds the analysis of the leak and #4125 holds the 6-hour flat check of the working set. Both stay as they are. The limit is revisited when the working set is flat.
- Pending a person: read `container_memory_working_set_bytes` of container `service` in Grafana after the rollout, and reopen #4116 if the working set still grows.
