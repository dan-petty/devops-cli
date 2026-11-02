# Tasks

## 1. The settings and the manifests

Kind: behavior

- [x] 1.1 Write failing tests in `tests/roadmap/test_roadmap_implement_deadline_settings.py` for the scenarios of "The extension, the stall and the ceiling are settings", and update `tests/k8s/test_k8s_job_admission_policy.py` and `tests/core/test_k8s_runner.py` for the cap of 14400 and the `patch` verb
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_deadline_settings.py tests/k8s/test_k8s_job_admission_policy.py tests/core/test_k8s_runner.py`
- [x] 1.2 Add the three settings with a validator, their defaults and `CONST_ROADMAP_IMPLEMENT_DEADLINE_CAP_SECONDS`, raise the cap in the policy `roadmap-service-jobs`, and add `patch` on `jobs` to the Role
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_deadline_settings.py tests/k8s/test_k8s_job_admission_policy.py tests/core/test_k8s_runner.py tests/security/test_config_declarations.py`

## 2. The deadline in the Job API and in the round

Kind: behavior

- [x] 2.1 Write failing tests in `tests/k8s/test_k8s_cluster_job_api.py` for the start time, the deadline and the annotations of a listed Job, for a Job made with a deadline and annotations, and for `patch_job`; and in `tests/roadmap/test_roadmap_implement_deadline.py` for the scenarios of "The deadline of a runner Job follows its progress", "A run that makes no progress ends at the stall time" and "The trace shows each deadline change", with a replay of three hours
  - Verification: `uv run devops ci test tests/k8s/test_k8s_cluster_job_api.py tests/roadmap/test_roadmap_implement_deadline.py`
- [x] 2.2 Write `src/devops_cli/roadmap/implement_deadline.py`, `ClusterJobs.patch_job`, the `deadline` and `annotations` of `build_job` and `ClusterJobs.create`, the call in `run_implement_round`, the deadline and the annotation of the Job that the round makes, and the stall line of the report
  - Verification: `uv run devops ci test tests/k8s/test_k8s_cluster_job_api.py tests/roadmap/test_roadmap_implement_deadline.py tests/roadmap/test_roadmap_implement_submit.py`

## 3. The documents and the archive

Kind: documents

- [x] 3.1 Update `k8s/README.md` and `docs/ROUTINE_TASKS.md`, and regenerate the generated documents
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`
- [x] 3.2 Archive the change
  - Verification: `uv run devops openspec archive 3063-long-running-tasks-progress-based-deadlines`

## Workflow follow-up

- Resource requests that follow the size of the plan are not part of this change (see the proposal). Follow-up: #3193.
- Pending a person: apply the manifests (`role.yaml`, `admissionpolicy.yaml`) with the image, so the Service may patch a Job; without `patch` a round that finds a Job to move fails.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
