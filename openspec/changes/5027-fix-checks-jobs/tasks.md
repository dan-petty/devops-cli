# Tasks

## 1. Behavior: the step and its command

- [x] 1.1 Write failing tests: the claim `owner/service` does not stop `fix-checks` or `fix-conflict`, `--check` names the check of the round, a lease refusal after a move of the head is `skipped` with no mark, and SIGTERM exits 75
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_checks.py tests/roadmap/steps/test_roadmap_step_fix_conflict.py tests/commands/test_roadmap_step_fix_checks.py`
- [x] 1.2 Add `claim_labels`, the option `--check`, the re-read of the head after a refused push, and `sigterm_raises` with exit 75
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_checks.py tests/roadmap/steps/test_roadmap_step_fix_conflict.py tests/commands/test_roadmap_step_fix_checks.py`

## 2. Behavior: the separate counts of the implement repair loop

- [x] 2.1 Write a failing test: a repair round of the implement Job leaves no `fix_checks.*` mark
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_phase_marks.py`
- [x] 2.2 Remove the `fix_checks.*` writes of the implement repair loop
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_phase_marks.py`

## 3. Behavior: the due predicate and the live unit of the watch row

- [x] 3.1 Write failing tests: `due_steps` gives `fix_checks` for a failed test or lint check of a bot pull request with the shard first and no cancelled check, and the watch row starts one Job for a bot delivery pull request whose implement Job ended, with no GitHub write
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_due_steps.py tests/roadmap/test_roadmap_watch_row.py`
- [x] 3.2 Add `DueStep.FIX_CHECKS` and `fix_checks_check`, read the live unit with `job_holds`, and call the fix round after the ledger write
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_due_steps.py tests/roadmap/test_roadmap_watch_row.py tests/roadmap/test_roadmap_status_round.py`

## 4. Behavior: the launcher seam, the fix round and the shared limit

- [x] 4.1 Write failing tests: one Job for a due unit in each mode, 409 for a second create, a suspended fix Job that holds the place of a new implement or stage Job, the resume, the report of an ended Job, the next attempt with its wait and cap, the nested deadline, and the admission of the manifest
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_fix_checks_row.py tests/roadmap/implement/test_roadmap_implement_submit.py tests/roadmap/stage/test_roadmap_stage_submit.py tests/roadmap/test_job_result.py`
- [x] 4.2 Add `job_launcher.py` and `fix_checks_row.py`, route `implement_submit._create` through the seam, bound the implement and stage rows by `model_slots`, add `roadmap.fix_checks.mode` and `roadmap.model_jobs`, the job `fix_checks` of the result line, and the suspension of `build_job` and `patch_job`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_fix_checks_row.py tests/roadmap/implement/test_roadmap_implement_submit.py tests/roadmap/stage/test_roadmap_stage_submit.py tests/k8s/test_k8s_cluster_job.py tests/roadmap/test_job_result.py`

## 5. Behavior: the counter and the alert

- [x] 5.1 Write failing tests: the counter `devops_cli_service_fix_checks_jobs_total` is a served series of the Service, and `RoadmapFixChecksJobWithoutResult` fires for the result `none`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py tests/telemetry/test_telemetry_instruments.py`
- [x] 5.2 Prime the counter at zero and add the rule
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py tests/telemetry/test_telemetry_instruments.py tests/server`

## 6. Manifests

- [x] 6.1 Set `roadmap.fix_checks.mode` to `on` in `k8s/devops/configmap.example.yaml`, by the owner direction of 2026-11-16
  - Verification: `$ uv run devops ci test tests/config`
- [x] 6.2 The admission gate check builds the fix Job of the seam in both modes, suspended and as attempt 2
  - Verification: `$ uv run python -c "import sys; from tests.gate.k8s import main; sys.exit(main())"`

## 7. Documents

- [x] 7.1 Regenerate the command and setting documents, and update `docs/CLUSTER.md` (Runner Jobs and the alert table), `docs/TELEMETRY.md`, `docs/roadmap/job-success.md` and the Status History of ADR 0021
  - Verification: `$ uv run devops docs check`

## Workflow follow-up

- The plan-draft repair of ADR 0021 section 8 is #5997.
- The entry `ai.tasks.fix_checks` of the ConfigMap template waits for the release image that declares the key, as #5990 changes the model lines of the template.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
