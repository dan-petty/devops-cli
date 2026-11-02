# Proposal

## Why

Issue #3063. The runner Job of the implement job has a fixed `activeDeadlineSeconds` of 7200. A large item, such as a refactor of 40 files, a migration or a slow test run, either fits in two hours or the Job ends at the deadline with its work discarded. No rule lets a run that makes progress go on, and no rule ends a run that makes none before the deadline.

## What Changes

- Three settings in `roadmap.implement`: `deadline_stall_seconds` (default 2400), `deadline_extension_seconds` (default 3600) and `deadline_ceiling_seconds` (default 14400). A validator refuses a stall above the extension and an extension above the ceiling. The ceiling has a hard maximum of 14400, the cap in the admission policy.
- The Service creates the runner Job with `activeDeadlineSeconds` set to the extension step and the annotation `roadmap.devops-cli/progress-at`. The Job spec shows the deadline in force at all times.
- New module `src/devops_cli/roadmap/implement_deadline.py`. In each round of the `implement` row, for each Job of the repository that has not ended and carries the annotation, the Service reads the last `CONST_ROADMAP_IMPLEMENT_DEADLINE_LOG_LINES` lines of the Job log and compares their digest with the digest in the annotation `roadmap.devops-cli/progress`.
  - A changed digest is a progress event. The Service patches the Job: `activeDeadlineSeconds` becomes the smaller of the ceiling and the greater of the deadline in force and the seconds since the Job started plus the extension step. It stores the digest and the time in the annotations.
  - An unchanged digest for `deadline_stall_seconds` is a stall. The Service patches `activeDeadlineSeconds` to the seconds since the Job started, so the Job controller ends the Job at once with the reason `DeadlineExceeded`, and sets the annotation `roadmap.devops-cli/stalled`.
  - Each extension and each stall is a span `implement.deadline` under the span of the round, with the Job, the old and the new deadline and the reason, and one log line.
- The report comment of a Job that ended names the stall when the annotation `roadmap.devops-cli/stalled` is set, and the failure class of that stop is `timeout` (#3065): the Job went over its deadline.
- `ClusterJobs` gets `patch_job`, and `ClusterJob` carries the start time, the deadline and the annotations. `build_job` takes a `deadline` and `annotations`.
- Manifests: the Role `roadmap-service-jobs` adds `patch` on `jobs`; the policy `roadmap-service-jobs` allows at most 14400 seconds. The CronJob template keeps 7200 for `devops k8s run-job`.
- Docs: `k8s/README.md`, `docs/ROUTINE_TASKS.md`, `docs/ENV_VARS.md` and `docs/CONFIGURATION.md` (generated).
- Observable behavior changes (settings, Job spec, manifests, report), so the change carries a spec delta.
- The change fits one pull request.

### Out of scope

- Resource requests that follow the size of the plan (second bullet of the issue). The three tiers in the proposed design (2, 4 and 8 Gi) would lower the memory of small items and conflict with the acceptance criterion that the 8 Gi limit stays as it is. The sizes of the plan are no measured input, and the CPU tier must equal `PYTEST_XDIST_AUTO_NUM_WORKERS` (a test holds it). This is the separate issue #3193. The memory limit does not change here.
- A setting `memory_limit_gib`. It has no use without the tiers.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-runner`: MODIFIED the Role and the policy that bounds the run of a Job of the Service.
- `roadmap-implement-job`: ADDED requirements for the deadline, the stall and the settings.

## Impact

- Code: `src/devops_cli/roadmap/implement_deadline.py` (new), `src/devops_cli/roadmap/implement_submit.py`, `src/devops_cli/k8s/cluster_job.py`, `src/devops_cli/k8s/cluster_job_api.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`.
- Manifests: `k8s/devops/roadmap-service/role.yaml`, `k8s/devops/roadmap-service/admissionpolicy.yaml`.
- Documents: `k8s/README.md`, `docs/ROUTINE_TASKS.md`, `docs/ENV_VARS.md`, `docs/CONFIGURATION.md`.
- Tests: `tests/roadmap/test_roadmap_implement_deadline.py` (new), `tests/config/test_roadmap_implement_deadline_settings.py` (new), `tests/k8s/test_k8s_cluster_job_api.py`, `tests/k8s/test_k8s_job_admission_policy.py`, `tests/core/test_k8s_runner.py`, `tests/security/test_config_declarations.py`.

## Feasibility

Checked on 2026-11-02 against the repository and the Kubernetes source:

- The deadline of a running Job can change. In Kubernetes v1.33.0, `ValidateJobSpecUpdate` (`pkg/apis/batch/validation/validation.go`) makes `completions`, `selector`, the pod template, `completionMode`, `podFailurePolicy`, `backoffLimitPerIndex`, `managedBy` and `successPolicy` immutable. It does not list `activeDeadlineSeconds`. The Job controller handles the change: `updateJob` (`pkg/controller/job/job_controller.go`) queues a new sync after `activeDeadlineSeconds` minus the time passed when the field changes. A deadline in the past ends the Job at the next sync (`pastActiveDeadline`). So a patch can extend a deadline and can end a Job at once.
- The issue names `.github/roadmap.toml`. That file does not exist. Settings of `roadmap.implement` are fields of `RoadmapImplementConfig` in `src/devops_cli/config/settings.py`, each with an environment variable, as `repair_rounds` is. The change uses them.
- The Service cannot patch a Job today. Role `roadmap-service-jobs` allows `create`, `get` and `list` on `jobs`, and a test holds the four rules. The admission policy refuses a Job of the Service with a deadline above 7200 on CREATE and UPDATE. The change adds `patch` and moves the cap to 14400, and tests hold both.
- No heartbeat exists in the runner. The issue says "the heartbeat"; the code has none. The runner does write one line to the Job log for each tool call (`ToolCallLog._note`, `implement_tool_log.py`), and the Service already reads the Job log through `ClusterJobs.log_tail`. So the progress signal is a change of the tail of that log. The runner needs no code change.
- The default stall of the issue is 300 seconds. That is wrong for this code. A run is silent in the Job log for up to `CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS` (900) in a verification command, `CONST_ROADMAP_IMPLEMENT_REQUEST_TIMEOUT_SECONDS` (600) in a model call, and `CONST_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS` (1800) while it watches the checks of the pull request. A stall of 300 seconds would end a healthy run. The default is 2400 seconds, the longest silent wait plus 600 seconds. The row `implement` runs every 7 minutes (`DEFAULT_ROADMAP_IMPLEMENT_INTERVAL_MINUTES`) and a tick of the Service is 151 seconds, so a stall is seen up to 571 seconds late. The default extension is 3600 seconds, above the stall plus that delay, so the Service sees a stall before the deadline of a Job passes. A test holds both relations.
- Command output on the base: `uv run pytest tests/roadmap/test_roadmap_implement_submit.py tests/k8s/test_k8s_cluster_job_api.py tests/k8s/test_k8s_job_admission_policy.py tests/core/test_k8s_runner.py` passes.
- The premise holds with these corrections. The change writes no code that works around a missing tool.

## Existing Tool Considered

Kubernetes sets one fixed `activeDeadlineSeconds` and has no extend-on-progress feature. No open, maintained operator extends the deadline of a plain Job on a progress signal, and a new controller would be one more deployment for one Job type. The change uses the API call that Kubernetes already offers (a patch of the field) from the Service, which already lists the Jobs and reads their logs. Written cost: about 60 000 tokens and 4 hours to build; about 10 000 tokens to keep and to fix the defaults when a measured silent wait changes. It deletes no code.
