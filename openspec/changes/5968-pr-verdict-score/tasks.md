# Tasks

## 1. Declare the verdict labels and score the first verdict of each bot pull request

Kind: behavior. Reads: `src/devops_cli/roadmap/workflow_labels.py`, `src/devops_cli/roadmap/job_grade_report.py`, `src/devops_cli/github/client.py`, `src/devops_cli/roadmap/plan_check.py`. Changes: `src/devops_cli/roadmap/workflow_labels.py`, `src/devops_cli/roadmap/pr_verdict.py`, `src/devops_cli/roadmap/job_grade.py`, `src/devops_cli/roadmap/job_grade_report.py`, `src/devops_cli/commands/roadmap_eval_grades.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `tests/roadmap/test_pr_verdict.py`, `tests/commands/test_roadmap_eval_grades.py`, `tests/roadmap/test_job_grade_report.py`, `tests/roadmap/__snapshots__/test_job_grade_report.ambr`, `tests/support/roadmap_job_grades.py`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `docs/commands/roadmap.md`.

- [x] 1.1 Add the tests: the verdict labels of each kind, the first verdict from the label events, the verdict score with the partial setting, the GraphQL search of the window and the repository, the verdict rows of the report and its text, the dry run, and the note with no slug
  - Verification: `$ uv run devops ci test tests/roadmap/test_pr_verdict.py tests/commands/test_roadmap_eval_grades.py` fails on the base
- [x] 1.2 Declare the labels, add `roadmap.verdict_partial_score`, read the verdicts in `roadmap/pr_verdict.py`, and give them in the report of `devops roadmap eval grades`
  - Verification: `$ uv run devops ci test tests/roadmap/test_pr_verdict.py tests/commands/test_roadmap_eval_grades.py tests/roadmap/test_job_grade_report.py tests/roadmap/test_roadmap_labels_file.py`
- [x] 1.3 Regenerate the reference documents
  - Verification: `$ uv run devops docs generate`

## 2. Documents

Kind: other. Reads: `docs/roadmap/job-success.md`. Changes: `docs/roadmap/job-success.md`.

- [x] 2.1 State the verdicts, their labels and the verdict score in `docs/roadmap/job-success.md`
  - Verification: `$ uv run devops ci docs`

## Criteria

- Group 1: a plan whose label events are `plan/needs-fix`, then `verdict/mergeable` counts as needs fix; with 2 mergeable, 1 needs fix and 1 discard plan of stage and the default setting, the stage score is 0.625.
- Group 1: the report of the 7-day window sends one GraphQL request for each 100 bot pull requests.

## Workflow follow-up

- #5014: an automatic review job that writes the verdict belongs with the Service step jobs. Until then a person or an agent vet sets the label.
- Old merged pull requests with no verdict label stay open in the report. This change maps none of them.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
