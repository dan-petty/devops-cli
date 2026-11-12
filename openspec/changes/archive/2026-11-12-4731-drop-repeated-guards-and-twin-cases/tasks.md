# Tasks

## 1. Test the root flag on a table of argv shapes
kind: other

- [x] 1.1 Give the stub module a command that declares `--dry-run` and a nested group, and add the table of argv shapes to `tests/commands/test_global_dry_run.py`
  - Verification: `$ uv run devops ci test tests/commands/test_global_dry_run.py`
- [x] 1.2 Delete the per-command root twins of the AI, argo, Cloudflare, Valkey and Vault, pr, scan and gh dry-run tests
  - Verification: `$ ! git grep -n test_request_plan_flag_order_global_dry_run tests/`

## 2. Delete the repeated gaps checks
kind: other

- [x] 2.1 Delete the 14 gaps tests whose list is within their class table, and keep the prefix rule of the review commands
  - Verification: `$ uv run devops ci test tests/invariants/test_dry_run_class_ratchet.py tests/commands/test_review_dry_run.py`

## 3. One network block for dry runs
kind: other

- [x] 3.1 Add `refuse_requests` and `misclassified` to `tests/support`, and delete the subprocess, DNS and per-file network blocks of the dry-run files
  - Verification: `$ ! git grep -n -e guard_external_calls -e GAP_COMMAND_NAMES -- tests/`
- [x] 3.2 Run the dry-run files that use the two helpers
  - Verification: `$ uv run devops ci test tests/commands/test_argo_dry_run.py tests/commands/test_k8s_dry_run.py tests/commands/test_scan_dry_run.py tests/commands/test_tf_dry_run.py tests/github/test_gh_issues_milestones_labels_runs_dry_run.py`

## 4. Documents
kind: documents

- [x] 4.1 Say in `docs/TESTING.md` how a dry-run test uses the floor, the two helpers, the ratchet and the root-flag table
  - Verification: `$ uv run devops ci docs`
