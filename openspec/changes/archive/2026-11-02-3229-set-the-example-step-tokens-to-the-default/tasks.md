# Tasks

## 1. Set the example and remove the pins

Reads: `k8s/devops/configmap.example.yaml`, `src/devops_cli/config/defaults.py`. Changes: `k8s/devops/configmap.example.yaml`, `tests/k8s/test_k8s_configmap.py`, `tests/config/test_k8s_devops_runtime.py`, `tests/server/routes/test_k8s_roadmap_service.py`.

- [x] 1.1 Set `step_tokens` to 64000 in `k8s/devops/configmap.example.yaml`, remove `test_the_repository_template_sets_the_stage_job_of_the_service` from `tests/k8s/test_k8s_configmap.py`, and cut the pins of the models, the retry count, the window and the telemetry endpoint from `tests/config/test_k8s_devops_runtime.py` and `tests/server/routes/test_k8s_roadmap_service.py`, and verify that `uv run devops ci test tests/k8s/test_k8s_configmap.py tests/config/test_k8s_devops_runtime.py tests/server/routes/test_k8s_roadmap_service.py` passes

## Workflow follow-up

- Pending a person: apply the ConfigMap to the cluster after the merge, because the deployed Service reads the config from the cluster and not from the repository.
