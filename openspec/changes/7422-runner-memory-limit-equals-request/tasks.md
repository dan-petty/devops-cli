# Tasks

## 1. The memory limit of each row equals its request

Kind: behavior.

Reads: `src/devops_cli/roadmap/implement/implement_size.py`, `src/devops_cli/roadmap/job_launcher.py`, `src/devops_cli/config/settings.py`.

Changes: `src/devops_cli/roadmap/implement/implement_size.py`, `src/devops_cli/roadmap/job_launcher.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `tests/roadmap/implement/test_roadmap_implement_size.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/security/test_config_declarations.py`.

- [x] 1.1 Write the tests and watch them fail: each row gives equal requests and limits (1 CPU with 5Gi, 4 CPU with 11Gi), each peak is at most 80 % of the memory of its row, and the Job that a round creates has the memory limit of its row. Delete the tests of the setting `roadmap.implement.max_memory_limit`.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_size.py tests/roadmap/implement/test_roadmap_implement_submit.py`
- [x] 1.2 Set the rows from the peaks of 14 days, make `RunnerSize.resources()` give each limit equal to its request, and remove the memory limit argument of `job_launcher.runner_job` and `job_launcher.launch`.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_size.py tests/roadmap/implement/test_roadmap_implement_submit.py`
- [x] 1.3 Remove the setting `roadmap.implement.max_memory_limit`, its default, its validator, `MIN_MEMORY_LIMIT_GI` and its variable from the list of declared variables.
  - Verification: `$ uv run devops ci test tests/security/test_config_declarations.py`

## 2. The admission policy pins the memory limit

Kind: manifests.

Changes: `k8s/devops/roadmap-service/admissionpolicy.yaml`, `tests/gate/k8s_checks/job_admission_policy.py`.

- [x] 2.1 Admit the rows 1 CPU with 5Gi and 4 CPU with 11Gi only, and refuse a memory limit that differs from the memory request. The gate check builds the Job of each row with no memory limit argument, tries the grid with each limit equal to its request, and refuses a limit of 16Gi and of 4Gi.
  - Verification: `$ uv run devops ci --check --only k8s`

## 3. The example ConfigMap

Kind: manifests.

Changes: `k8s/devops/configmap.example.yaml`.

- [x] 3.1 Remove `max_memory_limit` and its comment from `roadmap.implement`.
  - Verification: `$ ! git grep -n max_memory_limit -- src tests k8s`

## 4. Documents

Kind: documents.

Changes: `docs/CLUSTER.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`.

- [x] 4.1 Give the rows and the rule in the Admission policy, Size and Deadline lines of `docs/CLUSTER.md`, and generate the settings documents again.
  - Verification: `$ uv run devops ci --check --only docs`

## Workflow follow-up

- After the deploy, the live checks of #7422: a runner Job of the Service has a memory request equal to its memory limit and the policy admits it, no runner pod goes to a node whose free allocatable memory is below its limit, and no runner Job of the next 7 days ends with `OOMKilled`.
- The live ConfigMap `devops/devops-cli-config` holds `max_memory_limit: 16Gi`. The Service ignores the key, so its source in dan-petty/homelab can drop it at any time.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
