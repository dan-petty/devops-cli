# Tasks

## 1. Fail a branch run of plan-recheck on a folder that the branch changes

Kind: behavior. Reads: `src/devops_cli/roadmap/plan_recheck.py`, `src/devops_cli/commands/roadmap.py`, `tests/commands/test_roadmap_plan_recheck_cmd.py`, `tests/roadmap/test_roadmap_plan_recheck.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `docs/roadmap/plan-check.md`. Changes: `src/devops_cli/roadmap/plan_recheck.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_plan_recheck.py`, `tests/commands/test_roadmap_plan_recheck_cmd.py`.

- [ ] 1.1 The failing cases are the new `test_a_branch_run_exits_1_for_a_refused_folder_that_the_branch_adds` and `test_a_branch_run_of_a_new_gate_exits_0_with_refusals_of_merged_plans` in `tests/commands/test_roadmap_plan_recheck_cmd.py`, and the new `test_the_failed_folders_of_a_branch_are_the_folders_it_adds_or_changes_that_are_not_ok` in `tests/roadmap/test_roadmap_plan_recheck.py`. The first fails until `--branch` exits 1 for a branch whose own folder has the result `new-plan` or `rewrite`
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_plan_recheck_cmd.py` fails on the base
- [ ] 1.2 Add the property `failed` to `BranchRecheck` in `src/devops_cli/roadmap/plan_recheck.py`: the records of the folders that the branch adds or changes, against the files of the default branch, whose result is not `ok`. In `plan_recheck_cmd` of `src/devops_cli/commands/roadmap.py`, print one line for each such folder after the report and exit 1 when one is there. Add the line to `src/devops_cli/lang/en/messages.py`. Change `test_the_json_output_of_a_branch_run_holds_the_comparison` to give the branch no folder of its own, so its exit 0 stays
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_plan_recheck_cmd.py` passes

## 2. Read the issues of plan-recheck from a listing file

Kind: behavior. Reads: `src/devops_cli/roadmap/plan_recheck.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/listing_snapshot.py`, `src/devops_cli/commands/roadmap.py`. Changes: `src/devops_cli/roadmap/plan_recheck.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/help.py`, `tests/commands/test_roadmap_plan_recheck_cmd.py`, `docs/commands/roadmap.md`.

- [ ] 2.1 The failing case is the new `test_a_run_with_an_issue_listing_sends_no_github_request` in `tests/commands/test_roadmap_plan_recheck_cmd.py`: an installed store factory that raises on any call, an `--issues` file with one open issue and one closed issue in the form of `IssueRecord`, and the same results as the run with the store
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_plan_recheck_cmd.py` fails on the base
- [ ] 2.2 Give `recheck_plans` in `src/devops_cli/roadmap/plan_recheck.py` a protocol of the two reads that it makes, `open_items` and `item`, and add `ListingIssues`, which answers both from a list of `IssueRecord` through `item_of`. Add `--issues <file>` to `plan_recheck_cmd` in `src/devops_cli/commands/roadmap.py`, with its help in `src/devops_cli/lang/en/help.py`: with the option, the command opens no store. Run `uv run devops docs generate`
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_plan_recheck_cmd.py` passes

## 3. Prepare the run of the stage agent

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_job.py`, `src/devops_cli/roadmap/implement/implement_phases.py`, `src/devops_cli/roadmap/phases/files.py`, `src/devops_cli/roadmap/phases/checkout.py`, `src/devops_cli/openspec/scaffold.py`, `tests/roadmap/stage/test_roadmap_stage.py`. Changes: `src/devops_cli/roadmap/stage/stage_job_phases.py` (new), `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_prepare.py` (new), `tests/support/fakes/roadmap_store.py`.

- [ ] 3.1 The failing cases are in the new `tests/roadmap/stage/test_roadmap_stage_prepare.py`: `test_prepare_writes_the_state_the_inputs_and_the_scaffold_of_the_change`, `test_a_failed_read_of_the_comments_fails_the_item_with_ci_infra`, `test_a_false_job_time_premise_returns_the_item_in_prepare`, `test_a_false_premise_of_the_body_returns_the_item_in_prepare`, `test_a_blocker_of_an_open_plan_returns_the_item_in_prepare` and `test_a_left_out_item_ends_the_run_in_prepare`. Add `comments_on` to the reads that `fail_read` of `tests/support/fakes/roadmap_store.py` can fail
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prepare.py` fails on the base
- [ ] 3.2 Create `src/devops_cli/roadmap/stage/stage_job_phases.py` with the models `StageState` and `StageAgentInput` and `prepare_stage_job`. It reads the round of the item, runs `StageWriter.begin`, decides the job-time premise, the false premise of `probe_premise` and the blocker of `open_plan_creates`, and returns the item or checks in when one of them ends the run. Else it clones with `clone_branch`, switches the branch to the base, writes the scaffold of the change folder with its date, and writes the state file `state.json` with the issue listing `issues.json` in the state folder, and `input.json` with a copy of the listing in the work folder. In `src/devops_cli/roadmap/stage/stage.py`, add `StageWriter.resume`, so a later process gets the writes of `begin`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prepare.py` passes

## 4. Build the stage agent on stock Coder

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `openspec/config.yaml`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/roadmap/stage/stage_agent.py` (new), `src/devops_cli/ai/tasks/roadmap_stage_coder.md` (new), `tests/roadmap/stage/test_roadmap_stage_agent.py` (new).

- [ ] 4.1 The failing cases are in the new `tests/roadmap/stage/test_roadmap_stage_agent.py`: `test_the_stage_agent_is_coder_on_the_clone_with_the_three_checks_and_no_stage_tool`, which builds the agent with a stub model and finds `LocalWorkspace` at the clone, `Coder` with its stock leaves, `RequireVerification` with the three patterns in order and `exempt_paths == ()`, and no tool of `stage_tools` or `stage_toolbox`, and `test_each_check_command_counts_and_a_probe_or_a_branch_less_recheck_does_not`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_agent.py tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` fails on the base
- [ ] 4.2 Create `src/devops_cli/roadmap/stage/stage_agent.py` with `build_stage_agent`: `LocalWorkspace(<clone>)`, `Coder(sub_agents=False)` with the prompt `roadmap_stage_coder.md`, its `Shell` leaf on `run_command` with the time left of the budget and a scratch home, its context controls on the window of the task `stage`, `RequireVerification` with the three patterns, `exempt_paths=()` and instructions that name the three commands, and `Hooks` for `CompletionUnverifiedEvent` and the time budget. Write `src/devops_cli/ai/tasks/roadmap_stage_coder.md`, and keep each rule that it shares with `roadmap_stage_change.md` in the phrase that `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` holds
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_agent.py tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes

## 5. Run the agent phase with no GitHub credential

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/phases/patch.py`, `src/devops_cli/roadmap/attempt_kill.py`, `tests/core/test_process.py`, `tests/roadmap/phases/test_roadmap_phase_patch.py`. Changes: `src/devops_cli/roadmap/stage/stage_job_phases.py`, `src/devops_cli/core/process.py`, `src/devops_cli/roadmap/phases/patch.py`, `tests/roadmap/stage/test_roadmap_stage_agent_phase.py` (new).

- [ ] 5.1 The failing cases are in the new `tests/roadmap/stage/test_roadmap_stage_agent_phase.py`: `test_the_agent_phase_refuses_the_app_key_a_token_and_a_gh_login`, `test_the_agent_phase_writes_the_patch_of_the_change_folder_the_candidate_and_the_outcome`, `test_a_run_that_ends_unverified_has_the_end_unverified_and_the_names_of_its_failed_checks`, `test_the_outcome_holds_no_text_of_the_model` and `test_an_agent_phase_past_its_time_budget_writes_the_end_timeout`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_agent_phase.py` fails on the base
- [ ] 5.2 Add `run_stage_agent` to `src/devops_cli/roadmap/stage/stage_job_phases.py`: it refuses each variable of `CONST_GITHUB_AGENT_REFUSED_ENV` and a gh login (`finds_github_login`, new in `src/devops_cli/core/process.py`), runs the agent of `build_stage_agent` with `UsageLimits(request_limit=None)`, and writes `plan.patch`, `candidate.md` and `outcome.json` with `StageOutcome` in the output folder. Give `write_patch` of `src/devops_cli/roadmap/phases/patch.py` an optional path, so the patch holds the change folder only
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_agent_phase.py` passes

## 6. Check the plan files again in publish before any push

Kind: behavior. Reads: `src/devops_cli/roadmap/phases/publish.py`, `src/devops_cli/roadmap/phases/files.py`, `src/devops_cli/openspec/gate.py`, `src/devops_cli/roadmap/stage/stage_validate.py`, `tests/roadmap/test_roadmap_plan_recheck.py`. Changes: `src/devops_cli/roadmap/stage/stage_job_phases.py`, `src/devops_cli/roadmap/plan_recheck.py`, `tests/roadmap/stage/test_roadmap_stage_publish_checks.py` (new).

- [ ] 6.1 The failing cases are in the new `tests/roadmap/stage/test_roadmap_stage_publish_checks.py`, one for each rule, each with an output that breaks it and each ending with `plan_defect`, exit 1 and no push: a path outside the change folder, a link, a secret, another date in `.openspec.yaml`, a scaffold marker that `devops openspec check` refuses, a file that `openspec validate` refuses, a folder that `plan-recheck` refuses, an outcome with a key or a class outside its model, a verified outcome whose files fail a check, a patch over its limit of 16 MiB, and a state file of another item
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_publish_checks.py` fails on the base
- [ ] 6.2 Add the checks of `publish_stage_job` to `src/devops_cli/roadmap/stage/stage_job_phases.py`: read `state/` and `out/` with `read_run_file`, end an unverified run, apply the patch with `publish_patch`, and in `before_push` refuse a path outside the change folder, a secret and another date, then run `check_openspec`, `openspec validate --strict` and `recheck_plans` with the listing of `state/` on the new tree. Raise `RoadmapStageError` for each refusal. Give `recheck_plans` in `src/devops_cli/roadmap/plan_recheck.py` the default branch and its tip as arguments, for a repository with no `origin` refs
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_publish_checks.py` passes

## 7. Write the plan in publish with the writer of phase all

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_phases.py`, `src/devops_cli/roadmap/stage/stage_job.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/pull_form.py`, `tests/roadmap/stage/test_roadmap_stage.py`. Changes: `src/devops_cli/roadmap/stage/stage_job_phases.py`, `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_publish.py` (new).

- [ ] 7.1 The failing cases are in the new `tests/roadmap/stage/test_roadmap_stage_publish.py`: `test_the_same_plan_gives_the_same_tree_title_body_labels_record_and_comments_in_both_forms`, `test_a_candidate_with_a_closing_keyword_ends_as_plan_defect`, `test_a_summary_that_does_not_fit_gives_the_summary_of_the_issue_title`, `test_a_body_text_that_the_form_refuses_gives_the_why_of_the_proposal`, `test_safe_text_runs_once_on_each_text`, `test_a_text_for_github_loses_its_control_characters_and_a_comment_fits_github`, `test_an_unverified_run_checks_in_with_plan_defect_and_pushes_nothing` and `test_a_prepare_that_ends_the_run_gives_publish_its_end`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_publish.py` fails on the base
- [ ] 7.2 In `src/devops_cli/roadmap/stage/stage.py`, give `_stage_one` the push as an argument, `push_plan` for `--phase all`. In `src/devops_cli/roadmap/stage/stage_job_phases.py`, build the title with `staging_title`, the body with `pull_request_body` and the fallbacks, the commit message, the measure and the `StagedChange`, settle it with the resumed writer, and check in as `_finish_stage_job` does. In `src/devops_cli/roadmap/stage/stage.py`, remove the control characters other than the line feed from the body and from each comment that the stage writer posts, and cut each comment to 65536 characters
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_publish.py` passes

## 8. Take a phase and a run folder on the stage command

Kind: behavior. Reads: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/phases/names.py`, `tests/roadmap/stage/test_roadmap_stage_job_entry.py`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`. Changes: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_job_entry.py`, `docs/commands/roadmap.md`.

- [ ] 8.1 The failing cases are the new `test_a_phase_of_the_stage_job_needs_its_job_item_confirm_and_a_run_folder`, `test_source_goes_only_with_prepare_and_all`, `test_each_phase_of_the_cli_runs_in_turn_on_one_run_folder` and `test_no_phase_runs_the_stage_job_in_one_process_with_no_run_file` in `tests/roadmap/stage/test_roadmap_stage_job_entry.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_job_entry.py` fails on the base
- [ ] 8.2 Add `--phase` (`RunPhase`, default `all`) and `--work` to `stage_cmd` in `src/devops_cli/commands/roadmap.py`, with their help in `src/devops_cli/lang/en/help.py` and the refusals in `src/devops_cli/lang/en/messages.py`. A phase other than `all` hardens the process first, then calls `prepare_stage_job`, `run_stage_agent` or `publish_stage_job`. Run `uv run devops docs generate`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_job_entry.py` passes

## 9. Document the phases of the stage Job

Kind: other. Reads: `docs/roadmap/stage.md`, `docs/roadmap/plan-recheck.md`, `docs/adr/0030-roadmap-steps-run-their-agent-apart-from-the-app-key.md`, `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md`. Changes: `docs/roadmap/stage.md`, `docs/roadmap/plan-recheck.md`, `docs/adr/0030-roadmap-steps-run-their-agent-apart-from-the-app-key.md`, `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md`.

- [ ] 9.1 Add the section "The phases of the stage Job" to `docs/roadmap/stage.md`, the fail rule of a branch and `--issues` to `docs/roadmap/plan-recheck.md`, the addendum "The stage Job on the phases (#6705)" to ADR 0030, and `RequireVerification` with its stage use to `pydantic_ai_harness.md`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 4: A test of the stage agent finds `Coder` with the stock capabilities, `RequireVerification` with the three checks, and no custom tool.
- Pending person: The custom engine code and its tests are gone., `--phase all` runs that engine until #6814 is live, so the follow-up item that deletes it after a live Job of #6814 delivers this criterion.

## Workflow follow-up

- A new item deletes the old stage engine after a live Job of #6814 passes: `stage_tools.py`, `stage_toolbox.py`, the gate returns, the gate extension, the schema retry and their settings, and it decides the fix-plan row, the golden-set runs and `--phase all`.
- #6831 has `prepare` write the other GitHub reads of the agent, and reuses the issue listing of this change.
- #6814 runs the three phases as containers of CronJob `roadmap-stage`, with egress to github.com and no credential for the agent container.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
