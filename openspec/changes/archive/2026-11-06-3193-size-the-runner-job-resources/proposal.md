# Proposal

## Why

Issue #3193. The runner Job has one resource class for every item: 2 CPU and 4 Gi of memory requested, 8 Gi at most. A small item holds the same request as a refactor of 40 files, so the scheduler reserves memory and CPU that the Job never uses. The change that gave the Job a progress-based deadline (#3063) left the sizing out.

## What Changes

- New module `src/devops_cli/roadmap/implement_size.py` with the size table `RUNNER_SIZES` and `runner_size`. The table has two rows, chosen by the number of files that the tasks of the plan name:
  - Small, at most 10 files: CPU request and limit 1, memory request 2Gi.
  - Large, more than 10 files: CPU request and limit 4, memory request 6Gi.
  - Each row names the measured Job sample and its peak memory. The memory request of a row is above that peak.
  - `plan_file_count` counts the distinct file paths in the code spans of `tasks.md`.
- The Service sizes the Job in `run_implement_round`. It reads `tasks.md` of the item at the revision that holds the plan (`origin/<default branch>` for a Planned item, `origin/<branch>` for a Staged item), counts the files, and passes the resources and the value of `PYTEST_XDIST_AUTO_NUM_WORKERS` to the Job. Both values come from the CPU of the row, so they cannot differ.
- `build_job` and `ClusterJobs.create` take `resources`, which replaces the named request and limit values of the container of the template. The other values of the template, such as `ephemeral-storage`, stay.
- New setting `roadmap.implement.max_memory_limit` (default `8Gi`, variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_MAX_MEMORY_LIMIT`). It sets the memory limit of every runner Job that the Service creates. It is a whole number of Gi, and the configuration refuses a value below the largest memory request of the table.
- The admission policy `roadmap-service-jobs` gets one rule: the CPU request equals the CPU limit and is 1 with 2Gi, or 4 with 6Gi, and the environment value `PYTEST_XDIST_AUTO_NUM_WORKERS` equals the CPU limit. The memory limit is not pinned, so the setting can raise it.
- The template `k8s/devops/cronjob-runner.yaml` keeps 2 CPU and 4Gi, the default of a manual run (`devops k8s run-job`, `devops roadmap implement --item`). The policy does not select those Jobs. A gate check keeps its `PYTEST_XDIST_AUTO_NUM_WORKERS` equal to its CPU limit.
- Documents: `k8s/README.md` (Runner Jobs), and the generated `docs/ENV_VARS.md` and `docs/CONFIGURATION.md`.
- Observable behavior changes (a setting, the Job spec, a manifest), so the change carries a spec delta.
- The change fits one pull request.

### Out of scope

- A third row or a formula. The repository holds two measured peaks only (see Feasibility), so a middle row would be a guess.
- Any change in the cluster. A person lets Argo CD sync the policy with the Service image.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: MODIFIED the memory limit requirement. ADDED the size table, the worker count, the table provenance and the setting.
- `roadmap-implement-runner`: ADDED the rule of the policy for the resources of a Job of the Service.

## Impact

- Code: `src/devops_cli/roadmap/implement_size.py` (new), `src/devops_cli/roadmap/implement_submit.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/k8s/cluster_job.py`, `src/devops_cli/k8s/cluster_job_api.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`.
- Manifests: `k8s/devops/roadmap-service/admissionpolicy.yaml`.
- Documents: `k8s/README.md`, `docs/ENV_VARS.md`, `docs/CONFIGURATION.md` (generated).
- Tests: `tests/roadmap/test_roadmap_implement_size.py` (new), `tests/roadmap/test_roadmap_implement_submit.py`, `tests/k8s/test_k8s_cluster_job_api.py`, `tests/gate/k8s_checks/job_admission_policy.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/security/test_config_declarations.py`.

## Feasibility

Checked on 2026-11-06 against the repository on `origin/main`:

- The issue says that the staging commit lacks a Job spec builder, the setting and the policy. The builder exists now: `build_job` in `src/devops_cli/k8s/cluster_job.py`, which the Service calls through `ClusterJobs.create` in `run_implement_round`. The policy exists too: `k8s/devops/roadmap-service/admissionpolicy.yaml` (#2696). Only the setting `roadmap.implement.max_memory_limit` is missing, and the change adds it.
- The template sets 2 CPU request and limit, 4Gi memory request, 8Gi memory limit and `PYTEST_XDIST_AUTO_NUM_WORKERS=2`, and the gate check `check_the_runner_bounds_the_workers_of_the_test_runner_to_its_cpu_limit` holds the last equal to the CPU limit (`k8s/devops/cronjob-runner.yaml`, `tests/gate/k8s_checks/runner.py`).
- The measured peaks are in the archived change `2806-runner-memory-and-command-log` and in the comment of the template: 1.24 GB at most over the 10 Jobs that did not run out of memory, and 4.13 GB for the Job that the kernel killed at its 4 Gi cap. 2Gi covers the first, and 6Gi covers the second. The memory limit stays 8Gi, which fits the smallest node (15.5 Gi allocatable, measured then with `kubectl get nodes`).
- The Service has the plan at the moment it creates the Job. `tasks.md` is on `origin/<default branch>` for a Planned item and on `origin/<branch>` for a Staged item, and the judge of the round has read the plan already. The count needs no model call.
- The policy runs standard CEL. `check_the_expressions_use_only_standard_cel` compiles each expression with `cel_expr_python`, so the new rule is tested with the same engine as the other rules. The API server stores `1`, `4`, `2Gi` and `6Gi` unchanged, because they are in canonical form.
- Command output on the base: `uv run devops ci test tests/roadmap/test_roadmap_implement_submit.py tests/k8s/test_k8s_cluster_job_api.py` passes.
- The premise holds. The issue asks for a measured table, and the repository holds two measured points, so the table has two rows.

## Existing Tool Considered

The alternatives check of 2026-11-05 found no tool. VPA and KRR set requests from observed usage after pods ran. They cannot size a Job from its plan before the first run, set `PYTEST_XDIST_AUTO_NUM_WORKERS`, or write the admission policy. The change builds a two-row table and passes it to the existing Job builder. Written cost: about 60 000 tokens and 3 hours to build; about 4 000 tokens each month to keep it and to move the table when a new peak is measured. It deletes no code.
