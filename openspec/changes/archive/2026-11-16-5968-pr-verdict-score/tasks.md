# Tasks

## 1. Declare the verdict labels and score the first verdict of each bot pull request

Kind: behavior. Reads: `src/devops_cli/roadmap/workflow_labels.py`, `src/devops_cli/roadmap/job_grade_report.py`, `src/devops_cli/github/client.py`, `src/devops_cli/roadmap/plan_check.py`. Changes: `src/devops_cli/roadmap/workflow_labels.py`, `src/devops_cli/roadmap/pr_verdict.py`, `src/devops_cli/roadmap/job_grade.py`, `src/devops_cli/roadmap/job_grade_report.py`, `src/devops_cli/commands/roadmap_eval_grades.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `tests/roadmap/test_pr_verdict.py`, `tests/commands/test_roadmap_eval_grades.py`, `tests/roadmap/test_job_grade_report.py`, `tests/roadmap/__snapshots__/test_job_grade_report.ambr`, `tests/support/roadmap_job_grades.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/security/test_config_declarations.py`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `docs/commands/roadmap.md`.

- [x] 1.1 Add the tests: the verdict labels of each kind, the first verdict from the label events, a first label of the other kind that leaves the pull request unscored with a logged reason, the verdict score with the partial setting, the GraphQL search of the window and the repository, the verdict rows of the report and its text, the dry run, and the note with no slug
  - Verification: `$ uv run devops ci test tests/roadmap/test_pr_verdict.py tests/commands/test_roadmap_eval_grades.py` fails on the base
- [x] 1.2 Declare the labels, add `roadmap.verdict_partial_score`, read the verdicts in `roadmap/pr_verdict.py`, and give them in the report of `devops roadmap eval grades`
  - Verification: `$ uv run devops ci test tests/roadmap/test_pr_verdict.py tests/commands/test_roadmap_eval_grades.py tests/roadmap/test_job_grade_report.py tests/roadmap/test_roadmap_labels_file.py tests/roadmap/test_roadmap_limit_classes.py tests/security/test_config_declarations.py`
- [x] 1.3 Regenerate the reference documents
  - Verification: `$ uv run devops docs generate`

## 2. Replace `plan/needs-fix` with `verdict/fix-plan`

Kind: behavior. Reads: `git grep -n 'plan/needs-fix' -- src tests docs openspec/specs k8s`. Changes: each reader and writer of the label under `src/devops_cli/roadmap/`, `src/devops_cli/lang/en/`, `src/devops_cli/config/settings.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/commands/roadmap_step_fix_plan.py`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/github_project_management.md`, their tests, `k8s/devops/configmap.example.yaml`, the documents that name the label, and `openspec/specs/roadmap-plan-drift/spec.md` (Purpose).

- [x] 2.1 Change the tests of the readers and writers, and the test of the labels file, to `verdict/fix-plan` and `FIX_PLAN_LABEL`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_labels_file.py tests/roadmap/stage tests/roadmap/steps tests/roadmap/implement tests/roadmap/stores/test_roadmap_store_labelled_pulls.py tests/roadmap/test_roadmap_run_row_cadence.py tests/commands/test_roadmap_step_fix_plan.py` fails on the base
- [x] 2.2 Rename the label and the constant in the code, the settings text, the messages, the documents and the ConfigMap template; find the open findings section of a plan comment by the first sentence of its heading, which names no label; keep the archived changes, the decision records and the recorded fixtures
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_labels_file.py tests/roadmap/stage tests/roadmap/steps tests/roadmap/implement tests/roadmap/stores/test_roadmap_store_labelled_pulls.py tests/roadmap/test_roadmap_run_row_cadence.py tests/commands/test_roadmap_step_fix_plan.py`
- [x] 2.3 Leave no live name of the old label
  - Verification: `$ ! git grep -n plan/needs-fix -- src k8s`

## 3. Documents

Kind: other. Reads: `docs/roadmap/job-success.md`. Changes: `docs/roadmap/job-success.md`.

- [x] 3.1 State the verdicts, their labels and the verdict score in `docs/roadmap/job-success.md`
  - Verification: `$ uv run devops ci docs`

## Criteria

- Group 1: a plan whose label events are `verdict/fix-plan`, then `verdict/mergeable` counts as needs fix; with 2 mergeable, 1 needs fix and 1 discard plan of stage and the default setting, the stage score is 0.625.
- Group 1: a delivery whose first verdict label is `verdict/fix-plan` is unscored, and the read logs the pull request and the label.
- Group 1: the report of the 7-day window sends one GraphQL request for each 100 bot pull requests.
- Group 2: no file under `src`, `k8s` or `docs` names `plan/needs-fix`, the decision records aside.
- Group 2: the recorded stage comments, which name `plan/needs-fix`, still give their open findings to the step fix-plan.

## Workflow follow-up

- #5014: an automatic review job that writes the verdict belongs with the Service step jobs. Until then a person or an agent vet sets the label.
- Old merged pull requests with no verdict label stay open in the report. This change maps none of them.
- Rollout of #5968: after the release with this change runs, an agent renames the GitHub label `plan/needs-fix` to `verdict/fix-plan` with one `PATCH`, runs the label sync, and checks one hour later that no stage Job of the old image added the old label again.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
