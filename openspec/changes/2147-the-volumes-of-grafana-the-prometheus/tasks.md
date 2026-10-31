# Tasks

## 1. Add control-plane affinity to the three values files

Reads: none. Changes: `monitoring/grafana-values.yaml`, `monitoring/prometheus-values.yaml`, `logging/loki-values.yaml`.

- [ ] 1.1 Add an assertion to tests/test_k8s_local_path_placement.py that reads each of the three values files and asserts the control-plane DoesNotExist node affinity is present at the correct key path. Run the test; it fails because the affinity is not yet in the files, and verify that `uv run devops ci test tests/test_k8s_local_path_placement.py` fails on the base
- [ ] 1.2 Add the requiredDuringSchedulingIgnoredDuringExecution nodeAffinity block with node-role.kubernetes.io/control-plane DoesNotExist to monitoring/grafana-values.yaml at key affinity, to monitoring/prometheus-values.yaml at key server.affinity, and to logging/loki-values.yaml at key singleBinary.affinity, and verify that `uv run devops ci test tests/test_k8s_local_path_placement.py` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Remove the three exemptions from constants and test

Reads: none. Changes: `src/devops_cli/config/constants.py`, `tests/test_k8s_local_path_placement.py`.

- [ ] 2.1 Remove the three entries (grafana, prometheus-server, storage-loki-0) from _CONTROL_PLANE_CLAIM_EXEMPTIONS in tests/test_k8s_local_path_placement.py. Run the test; it now checks the affinity for these three workloads and passes because the previous group added it, and verify that `uv run devops ci test tests/test_k8s_local_path_placement.py` fails on the base
- [ ] 2.2 Remove the three entries from CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS in src/devops_cli/config/constants.py. If the list is empty after removal, set the constant to an empty list or remove it, and verify that `uv run devops ci test tests/test_k8s_local_path_placement.py` passes
- [ ] 2.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
