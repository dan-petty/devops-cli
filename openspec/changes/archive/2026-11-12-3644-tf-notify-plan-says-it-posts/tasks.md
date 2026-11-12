# Tasks

## 1. Behavior: no-request commands do not say that they post

- [x] 1.1 Add the help check and its tests to the dry-run class invariants, and see the repository case fail on `tf notify-plan`
  - Verification: `$ uv run devops ci test tests/invariants/test_dry_run_class_ratchet.py`
- [x] 1.2 Pin what `tf notify-plan` prints, with and without a plan file
  - Verification: `$ uv run devops ci test tests/commands/test_tf_notify_plan.py`
- [x] 1.3 Make the docstring and the help of `--pr` and `--plan-file` say what the command does, delete the unused `HELP.tf.notify_plan`, and regenerate the documents with `uv run devops docs generate --sync-readme`
  - Verification: `$ uv run devops ci test tests/invariants/test_dry_run_class_ratchet.py tests/commands/test_tf_notify_plan.py`

## 2. Documents

- [x] 2.1 Make the `tf notify-plan` row of the knowledge base command reference say that the command prints the comment
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Issue #4929: count the plan from OpenTofu and refuse a missing plan file.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
