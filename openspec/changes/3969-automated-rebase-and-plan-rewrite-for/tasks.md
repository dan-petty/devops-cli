# Tasks

## 1. Select the open plan branches and compute the mechanical rewrite

Kind: behavior. Reads: `src/devops_cli/roadmap/plan_recheck.py`, `src/devops_cli/roadmap/plan_rewrite.py`, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/stage/plan_drift.py`, `tests/roadmap/test_roadmap_plan_recheck.py`, `tests/lang/test_language_catalogs.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/roadmap/refine/test_roadmap_refine_tracker.py`, `tests/roadmap/stage/test_roadmap_stage_module_test_order.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`. Changes: `src/devops_cli/roadmap/plan_branches.py` (new), `tests/roadmap/test_roadmap_plan_branches.py` (new), `src/devops_cli/lang/en/messages.py`.
Adds: `BranchResult`, `BranchRewrite`, `open_plan_pulls`, `branch_rewrite`

- [x] 1.1 `tests/roadmap/test_roadmap_plan_branches.py::test_a_plan_that_the_rewrite_does_not_change_is_unchanged` writes the failing case first: `branch_rewrite` returns `BranchResult.UNCHANGED` when the rewrite changes no file and `BranchResult.REWRITTEN` with the new task list when it does; `test_a_delivery_branch_is_no_plan_branch` covers `open_plan_pulls`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_branches.py` fails on the base
- [x] 1.2 Add `src/devops_cli/roadmap/plan_branches.py` with the record `BranchRewrite` and the result `BranchResult` (`rewritten`, `unchanged`, `conflict`, `invalid`). Add `open_plan_pulls(store, reads, repo, default)`, which keeps the open pull requests whose base is the default branch and whose facts pass `is_plan` of `src/devops_cli/roadmap/plan_check.py`, and reads each with `read_pull`. Add `branch_rewrite(source, pull, default, tree)`, which reads the files of the head and calls `rewrite_plan` of `src/devops_cli/roadmap/plan_rewrite.py` against the default-branch tree. Add the messages to `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_branches.py` passes

## 2. Rebase, validate and push a rewritten plan branch

Kind: behavior. Reads: `src/devops_cli/roadmap/plan_branches.py`, `src/devops_cli/roadmap/clone_git.py`, `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/roadmap/plan_rewrite.py`, `tests/support/roadmap_stage.py`, `tests/lang/test_language_catalogs.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/roadmap/refine/test_roadmap_refine_tracker.py`, `tests/roadmap/stage/test_roadmap_stage_module_test_order.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`. Changes: `src/devops_cli/roadmap/plan_branches.py`, `tests/roadmap/test_roadmap_plan_branches.py`, `src/devops_cli/lang/en/messages.py`.
Adds: `push_rewrite`, `rewrite_open_branches`, `render_branch_run`

- [x] 2.1 `tests/roadmap/test_roadmap_plan_branches.py::test_a_rewrite_pushes_exactly_once` writes the failing case first: with a bare `origin`, `push_rewrite` rebases onto the default branch, writes the rewrite, validates it and pushes one commit with a lease. The same module adds `test_a_rewrite_rebases_the_branch`, `test_only_the_base_moved_pushes_nothing`, `test_a_conflicting_branch_pushes_nothing` and `test_a_refused_rewrite_pushes_nothing`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_branches.py` fails on the base
- [x] 2.2 Add `push_rewrite(source, target, rewrite, default)` to `src/devops_cli/roadmap/plan_branches.py`. It opens a detached worktree of the branch head with `checkout_at` of `src/devops_cli/roadmap/clone_git.py`, fetches the default branch and rebases. On a conflict it aborts the rebase and returns `BranchResult.CONFLICT`. It writes the rewrite with `write_rewrite`, validates the result with `read_change`, `check_gates` and `validate_change`, and returns `BranchResult.INVALID` on a refusal. It commits the written files once and pushes with `--force-with-lease=<branch>:<head>`, as `_push` of `src/devops_cli/roadmap/steps/fix_plan.py` does. Add `rewrite_open_branches`, which pushes nothing when the rewrite changes no file, and `render_branch_run`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_branches.py` passes

## 3. Add the branches option to plan-recheck

Kind: behavior. Reads: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/roadmap/plan_branches.py`, `tests/commands/test_roadmap_plan_recheck_cmd.py`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/commands/test_roadmap_plan_check_cmd.py`, `tests/commands/test_roadmap_registries.py`, `tests/github/test_gh_issues_milestones_labels_runs_dry_run.py`, `tests/github/test_github_rate_limiter.py`, `tests/lang/test_language_catalogs.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/roadmap/implement/test_roadmap_implement_outside.py`, `tests/roadmap/refine/test_roadmap_refine_tracker.py`, `tests/roadmap/stage/test_roadmap_stage_module_test_order.py`, `tests/roadmap/stage/test_roadmap_stage_orphan.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/test_roadmap_alternatives_item_writes.py`, `tests/roadmap/test_roadmap_dry_runs.py`, `tests/roadmap/test_roadmap_inbox_requests.py`, `tests/roadmap/test_roadmap_retitle_skip.py`, `tests/roadmap/test_roadmap_run_due_table.py`. Changes: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_roadmap_plan_recheck_cmd.py`.
Adds: `branches_requests`

- [ ] 3.1 `tests/commands/test_roadmap_plan_recheck_cmd.py::test_each_open_plan_branch_is_judged` writes the failing case first: `--branches` prints one result for each open draft plan pull request. `test_a_delivery_branch_is_left_out` covers the filter, and `test_the_branches_dry_run_lists_the_reads` covers the dry run
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_plan_recheck_cmd.py` fails on the base
- [ ] 3.2 Add the option `--branches` to `plan_recheck_cmd` in `src/devops_cli/commands/roadmap.py`. Refuse it together with `--branch`, and keep `--confirm` needing `--source`. Without `--confirm` the run prints the result of each open plan branch and pushes nothing. With `--confirm` it calls `rewrite_open_branches` and prints `render_branch_run`. Add `branches_requests` to `src/devops_cli/roadmap/request_plan.py` for the dry run. Add the help text to `src/devops_cli/lang/en/help.py` and the messages to `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_plan_recheck_cmd.py` passes

## 4. Document the branches pass

Kind: other. Reads: `docs/roadmap/plan-recheck.md`, `docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md`. Changes: `docs/roadmap/plan-recheck.md`, `docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md`.

- [ ] 4.1 Document `--branches` in `docs/roadmap/plan-recheck.md` and in the option table of `docs/commands/roadmap.md`: the rebase only when the rewrite changes a file, the lease push, the conflict and refused results, and the rule that a branch whose plan does not change gets no push. Regenerate `docs/CLI_REFERENCE.md` with the docs generator of the `docs-cli-reference` capability, then run the docs row
  - Verification: `$ uv run devops ci docs` passes
- [ ] 4.2 Edit `docs/roadmap/plan-recheck.md` and `docs/commands/roadmap.md`, and regenerate `docs/CLI_REFERENCE.md`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 3: A command or service row can evaluate and rewrite open plan pull request branches.
- Group 2: The command cleanly rebases branches without conflicts onto the default branch.
- Group 1: The command applies `plan_rewrite` transformations to `tasks.md`.
- Group 2: The updated branch is pushed and CI checks are triggered.
- Group 2: Unit tests verify clean rebasing, mechanical rewriting, and conflict avoidance.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
