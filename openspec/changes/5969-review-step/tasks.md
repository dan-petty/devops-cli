# Tasks

## 1. Settings and the task of the model

Kind: behavior. Reads: `src/devops_cli/config/settings.py`. Changes: `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `tests/config/test_roadmap_job_tasks.py`, `tests/roadmap/steps/test_roadmap_step_review.py`.

- [x] 1.1 Write failing tests: the task `review` has the model DeepSeek and the window 256,000 by default, a model set for it moves it alone, and `roadmap.review` starts in `plan` with 3 rounds and a cap of 16,000,000 tokens
  - Verification: `$ uv run devops ci test tests/config/test_roadmap_job_tasks.py`
- [x] 1.2 Add `AIReviewTaskOverride`, the field `ai.tasks.review`, `RoadmapReviewConfig` and their defaults
  - Verification: `$ uv run devops ci test tests/config/test_roadmap_job_tasks.py`

## 2. The rules, the model and the writes of the step

Kind: behavior. Reads: `src/devops_cli/roadmap/steps/fix_checks.py`, `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/roadmap/pr_verdict.py`. Changes: `src/devops_cli/roadmap/steps/review.py`, `src/devops_cli/roadmap/steps/review_facts.py`, `src/devops_cli/roadmap/steps/review_judge.py`, `src/devops_cli/ai/tasks/roadmap_review_pull.md`, `src/devops_cli/roadmap/pr_verdict.py`, `src/devops_cli/roadmap/job_result.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/exceptions/roadmap.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/steps/test_roadmap_step_review.py`, `tests/roadmap/steps/test_roadmap_step_review_judge.py`, `tests/roadmap/test_job_result.py`, `tests/roadmap/test_job_grade_report.py`.

- [x] 2.1 Write failing tests: each rule; the model verdict and its evidence; the guards, the mode `off` and `plan`, and a run without `--confirm`; mergeable, needs fix, issue changed and both discards with `--confirm`; a head that moves before the write; the cap of verdicts; a failed model call; the cap of new tokens; the grades read the label that the step wrote
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_review.py tests/roadmap/steps/test_roadmap_step_review_judge.py`
- [x] 2.2 Add the facts read, the rules, the model judge and its prompt, the writes and the actions, the record keys, `verdict_label` and the job `review` of the result line
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_review.py tests/roadmap/steps/test_roadmap_step_review_judge.py tests/roadmap/test_job_result.py tests/roadmap/test_job_grade_report.py`

## 3. The command

Kind: behavior. Reads: `src/devops_cli/commands/roadmap_step_fix_checks.py`. Changes: `src/devops_cli/commands/roadmap_step_review.py`, `src/devops_cli/commands/roadmap_step.py`, `src/devops_cli/lang/en/help.py`, `tests/commands/test_roadmap_step_review.py`.

- [x] 3.1 Write a failing test: `devops roadmap step review --dry-run` sends no request, and a run without `--pull` exits 1
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_step_review.py`
- [x] 3.2 Add the command, its help texts and its registration; with `--confirm` in the mode `on` it needs a runner Job and gives the step the delete of a branch with a lease
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_step_review.py`

## 4. The template and the documents

Kind: documents. Changes: `k8s/devops/configmap.example.yaml`, `docs/roadmap/job-success.md`, the generated reference documents.

- [x] 4.1 Add `roadmap.review` in the mode `plan` to the ConfigMap template, with no `ai.tasks.review`, and the job `review` to the job-success table
  - Verification: `$ uv run devops ci test tests/k8s -m 'k8s or not k8s' -k configmap`
- [x] 4.2 Regenerate the reference documents with `devops docs generate`
  - Verification: `$ uv run devops ci docs`

## Criteria

- Group 1: The task `review` starts on DeepSeek, and `roadmap.review` starts in `plan` with 3 rounds and 16,000,000 tokens.
- Group 2: The facts give each verdict that they can, the model decides the rest with evidence in the diff, and only `--confirm` in the mode `on` writes the label, the comment and the action.
- Group 3: The command plans with no write, and acts only in a runner Job.
- Group 4: The template and the documents name the new settings and the job.

## Workflow follow-up

- #6011: the launcher of #5027 starts the step as a runner Job, the watch row makes it due, and ADR 0021 section 8 gets the row `review`.
- Pending a person: set `roadmap.review.mode: on` after a week of plan-mode result lines, and add `ai.tasks.review` to the ConfigMap after the release runs.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
