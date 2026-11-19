# Tasks

## 1. Move the prune test worktrees under the managed folder

Kind: other. Reads: `tests/git/test_repos_worktrees.py`, `tests/git/conftest.py`, `src/devops_cli/git/worktree_inventory.py`. Changes: `tests/git/test_repos_worktrees.py`.

- [ ] 1.1 In `tests/git/test_repos_worktrees.py`, take the `managed` fixture of `tests/git/conftest.py` and build the worktree under it in place of `tmp_path` in `test_prune_removes_worktree_whose_tip_heads_a_merged_pull_request`, `test_prune_keeps_new_worktree_at_the_tip_of_main`, `test_prune_keeps_pushed_branch_with_an_open_pull_request`, `test_prune_keeps_worktree_with_a_commit_after_the_merge`, `test_prune_keeps_commit_that_github_does_not_know`, `test_prune_reads_no_pull_request_for_locked_dirty_or_unreadable_worktrees`, `test_prune_removes_the_record_of_a_worktree_whose_directory_is_gone`, `test_prune_removes_nothing_when_a_pull_request_read_fails`, `test_prune_without_confirm_reads_github_and_removes_nothing`, `test_prune_dry_run_makes_no_request_and_lists_the_requests`, `test_prune_dry_run_prints_the_request_plan`, `test_prune_refuses_dry_run_with_confirm`, `test_forced_prune_of_a_locked_worktree_reports_the_failure_and_keeps_the_directory`, `test_forced_prune_removes_an_unmerged_worktree_without_reading_github` and `test_prune_report_in_table_names_removed_and_refused_worktrees`, so `tests/git/test_repos_worktrees.py:404:` `merged = tmp_path / "wt_merged"` becomes `merged = managed / "wt_merged"`. Keep the repository, the bare origin and every expectation as they are: prune removes a clean worktree at a merged head wherever it sits today, so the module stays green on the base
  - Verification: `$ uv run devops ci test tests/git/test_repos_worktrees.py` passes

## 2. Add one scope refusal and use it in the reclaim

Kind: behavior. Reads: `src/devops_cli/git/worktree_inventory.py`, `src/devops_cli/git/worktree_add.py`, `src/devops_cli/lang/en/messages.py`, `tests/git/test_repos_worktrees_reclaim_scope.py`, `tests/core/test_repos_worktrees_add.py`, `tests/git/test_repos_worktrees.py`, `tests/git/test_repos_worktrees_reclaim.py`, `tests/lang/test_language_catalogs.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/roadmap/implement/test_roadmap_implement_git_isolation.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/refine/test_roadmap_refine_tracker.py`, `tests/roadmap/stage/test_roadmap_stage_module_test_order.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`, `tests/roadmap/steps/test_roadmap_step_scaffold.py`, `tests/roadmap/test_roadmap_explain.py`, `tests/roadmap/test_roadmap_faults.py`. Changes: `src/devops_cli/git/worktree_inventory.py`, `src/devops_cli/git/worktree_add.py`, `src/devops_cli/lang/en/messages.py`, `tests/git/test_repos_worktrees_reclaim_scope.py`.
Adds: `scope_refusal`

- [ ] 2.1 Write `test_scope_refusal_names_the_folder_and_the_ignored_count` in `tests/git/test_repos_worktrees_reclaim_scope.py` first, and change `test_json_report_lists_each_kept_worktree_with_its_reason` to assert that the outside reason names the managed folder; each fails until the shared function gives that reason
  - Verification: `$ uv run devops ci test tests/git/test_repos_worktrees_reclaim_scope.py` fails on the base
- [ ] 2.2 Add `scope_refusal(entry, *, managed_root: Path) -> str | None` to `src/devops_cli/git/worktree_inventory.py`: it returns the outside reason for a path that is not under `managed_root`, then the unknown reason when `count_ignored_paths` returns None, then the count reason, and None in scope. Replace the two inline checks of `_split_by_scope` in `src/devops_cli/git/worktree_add.py` with one call, keeping the main worktree out of the kept list. Rename the three reason attributes in `src/devops_cli/lang/en/messages.py` to `worktrees_kept_outside`, `worktrees_kept_ignored` and `worktrees_kept_ignored_unknown`, with the texts `outside the managed folder {folder}`, `holds {count} ignored path{plural}` and `ignored paths are unknown (git status failed)`; keep `worktrees_add_kept_line`. Change the `OUTSIDE` constant and the equality assertion of `tests/git/test_repos_worktrees_reclaim_scope.py` to the new outside reason that names the folder
  - Verification: `$ uv run devops ci test tests/git/test_repos_worktrees_reclaim_scope.py` passes

## 3. Make prune ask the scope rule

Kind: behavior. Reads: `src/devops_cli/git/worktree_inventory.py`, `src/devops_cli/git/worktree_add.py`, `src/devops_cli/commands/repos.py`, `tests/git/test_repos_worktrees_reclaim_scope.py`, `tests/git/test_repos_worktrees_reclaim.py`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/commands/test_repos.py`, `tests/core/test_repos_worktrees_add.py`, `tests/git/test_repos_worktrees.py`, `tests/roadmap/implement/test_roadmap_implement_git_isolation.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`, `tests/roadmap/steps/test_roadmap_step_scaffold.py`, `tests/roadmap/test_roadmap_explain.py`, `tests/roadmap/test_roadmap_faults.py`. Changes: `src/devops_cli/git/worktree_inventory.py`, `src/devops_cli/git/worktree_add.py`, `src/devops_cli/commands/repos.py`, `tests/git/test_repos_worktrees_reclaim_scope.py`, `tests/git/test_repos_worktrees_reclaim.py`.

- [ ] 3.1 Write `test_prune_refuses_a_merged_worktree_that_holds_one_ignored_file` in `tests/git/test_repos_worktrees_reclaim_scope.py` first, then `test_prune_refuses_a_merged_worktree_outside_the_managed_folder`, `test_prune_and_the_reclaim_refuse_with_the_same_reason` and `test_prune_under_force_removes_a_refused_worktree`, and rewrite `test_prune_keeps_its_scope_and_removes_a_merged_worktree_outside_the_folder` as `test_prune_keeps_a_merged_worktree_outside_the_folder`; each fails until prune asks the shared function
  - Verification: `$ uv run devops ci test tests/git/test_repos_worktrees.py tests/git/test_repos_worktrees_reclaim.py tests/git/test_repos_worktrees_reclaim_scope.py` fails on the base
- [ ] 3.2 Give `_decide`, `plan_prune` and `prune_worktrees` in `src/devops_cli/git/worktree_inventory.py` a `managed_root: Path` keyword and call `scope_refusal` after `_decided_by_local_state` and before `merged_pull`, so a refused worktree costs no GitHub read and the preview lists no request for it. Pass `managed_folder(root)` from `worktrees_prune` in `src/devops_cli/commands/repos.py` and from `reclaim_merged_worktrees` in `src/devops_cli/git/worktree_add.py`, whose call `src/devops_cli/git/worktree_add.py:301:` `return ReclaimResult(kept=kept, requests=plan_prune(entries, repo=repo).requests)` takes the new keyword. Pass the managed folder in the direct `prune_worktrees` call of `tests/git/test_repos_worktrees_reclaim.py:277:` `report = prune_worktrees(repo, entries, repo="example-org/app", confirm=True)`
  - Verification: `$ uv run devops ci test tests/git/test_repos_worktrees.py tests/git/test_repos_worktrees_reclaim.py tests/git/test_repos_worktrees_reclaim_scope.py` passes

## 4. State the prune scope in its help text

Kind: behavior. Reads: `src/devops_cli/commands/repos.py`, `src/devops_cli/lang/en/help.py`, `tests/commands/test_repos.py`, `docs/commands/repos.md`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/lang/test_language_catalogs.py`. Changes: `src/devops_cli/commands/repos.py`, `src/devops_cli/lang/en/help.py`, `tests/commands/test_repos.py`.

- [ ] 4.1 Write `test_prune_help_names_the_managed_folder_the_ignored_refusal_and_force` in `tests/commands/test_repos.py` first; it fails until the docstring of `worktrees_prune` and the help strings state the scope
  - Verification: `$ uv run devops ci test tests/commands/test_repos.py` fails on the base
- [ ] 4.2 Change the docstring of `worktrees_prune` in `src/devops_cli/commands/repos.py` to say that the command removes only the worktrees under the managed folder that hold no ignored path, that it refuses a worktree outside that folder and a worktree that holds ignored paths, and that `--force` removes every worktree but the main one. Change `worktrees_prune` and `worktrees_force` in `src/devops_cli/lang/en/help.py` to the same statement, and assert the output of `prune --help` in the new test
  - Verification: `$ uv run devops ci test tests/commands/test_repos.py` passes

## 5. Regenerate the command page and document the scope

Kind: other. Reads: `docs/commands/repos.md`, `CONTRIBUTING.md`, `src/devops_cli/commands/repos.py`. Changes: `docs/commands/repos.md`, `CONTRIBUTING.md`.

- [ ] 5.1 Run `uv run devops docs generate` so that `docs/commands/repos.md` holds the new help sentence of `prune`, and add one paragraph to section 4 of `CONTRIBUTING.md` that says prune removes only a clean worktree under `.data/agent/worktrees` at the head of a merged pull request, keeps a worktree that holds ignored paths and a worktree outside that folder, and removes every worktree but the main one only under `--force`
  - Verification: `$ uv run devops ci docs` passes
- [ ] 5.2 Edit `CONTRIBUTING.md` section 4 and regenerate `docs/commands/repos.md`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 3: A test makes a clean worktree at a merged head that holds one ignored file. Prune refuses it and names the ignored count.
- Group 3: A test makes a clean worktree at a merged head outside the managed folder. Prune refuses it and names the folder.
- Group 3: Prune and the reclaim decide scope with one shared function, so the two rules cannot drift.
- Group 5: The help text of `prune` and `CONTRIBUTING.md` say which worktrees prune removes.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
