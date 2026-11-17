# Tasks

## 1. The wrapper asks draft readiness

Kind: behavior. Changes: `src/devops_cli/roadmap/steps/ready.py`, `src/devops_cli/lang/en/messages.py`.

- [x] 1.1 Test that `mark_ready` refuses an implement draft with an unticked task group, reads the draft when its caller gives none, and sends `gh pr ready` for the `--force` of a person
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_ready.py`
- [x] 1.2 Make `mark_ready` ask `draft_readiness` first, and add `read_ready_draft`
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_ready.py`

## 2. Every caller gives its draft

Kind: behavior. Changes: `src/devops_cli/roadmap/watch_row.py`, `src/devops_cli/roadmap/steps/fix_checks.py`, `src/devops_cli/roadmap/steps/review.py`, `src/devops_cli/roadmap/implement/implement_pull.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/stage/stage_ready.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/commands/roadmap_step_ready.py`.

- [x] 2.1 Test that the watch row leaves a green draft that its item records as `stage.pr` and as `implement.pr`, with task group 5 not ticked, a draft in two rounds
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_watch_row.py`
- [x] 2.2 Judge the plan draft in the watch row before the Jev check and the mark, and pass the judged draft from each other caller
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_watch_row.py tests/roadmap/steps/test_roadmap_step_fix_checks.py tests/roadmap/steps/test_roadmap_step_review.py tests/roadmap/stage/test_roadmap_stage_ready.py tests/roadmap/test_roadmap_status_round.py tests/commands/test_roadmap_step_ready.py tests/commands/test_pr.py`

## 3. Documents

Kind: documents. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [x] 3.1 Say that the row `watch` asks `draft_readiness`, and run `devops docs generate` for the new message
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
