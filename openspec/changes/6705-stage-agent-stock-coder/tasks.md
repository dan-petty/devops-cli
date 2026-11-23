# Tasks

## 1. Judge the folders that a branch changes from a base

Kind: behavior. Reads: `src/devops_cli/roadmap/plan_recheck.py`, `src/devops_cli/roadmap/planned.py`, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/stage/stage_removal_references.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`. Changes: `src/devops_cli/roadmap/plan_recheck.py`, `src/devops_cli/roadmap/stage/stage_candidate.py` (new), `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_plan_recheck.py`.

- [x] 1.1 The failing cases are new in `tests/roadmap/test_roadmap_plan_recheck.py`. They cover the folders from a base and no fetch from an `origin` that refuses. They cover no read of a default ref in a repository with no `origin/HEAD`. They also cover the plan-check rules, a test reference of a removal, a closing keyword of the candidate, and the listing reads
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_recheck.py` fails on the base
- [x] 1.2 Give `recheck_plans` in `src/devops_cli/roadmap/plan_recheck.py` a `base`, the default branch and a candidate. With a base it makes no fetch, and takes the folders from `git diff --name-only <base>..<branch>`. Each judge adds `staged_problems` on the title and the body of `stage_candidate.py` (new), and the test references of `scan_removal_references`. Add `BranchRecheck.failed`, the reads protocol, `ListingIssues`, and the lines in `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_recheck.py` passes

## 2. Take a base, a candidate and an issue listing on plan-recheck

Kind: behavior. Reads: `src/devops_cli/commands/roadmap.py`, `tests/commands/test_roadmap_plan_recheck_cmd.py`. Changes: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/help.py`, `tests/commands/test_roadmap_plan_recheck_cmd.py`, `docs/commands/roadmap.md`.

- [x] 2.1 The failing cases are new in `tests/commands/test_roadmap_plan_recheck_cmd.py`: `test_a_base_run_exits_1_for_a_refused_folder_of_the_branch`, `test_a_base_run_puts_the_failed_folders_in_the_json_of_the_branch` and `test_a_run_with_a_listing_opens_no_store`
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_plan_recheck_cmd.py` fails on the base
- [x] 2.2 Add `--base <sha>`, `--candidate <file>` and `--issues <file>` to `plan_recheck_cmd` in `src/devops_cli/commands/roadmap.py`, with their help in `src/devops_cli/lang/en/help.py`. With `--base`, the command exits 1 when `branch.failed` holds a folder. `--json` puts the folders in `branch.failed` with no other line. Run `uv run devops docs generate`
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_plan_recheck_cmd.py` passes

## 3. List the reads of a base and a listing in the dry run

Kind: behavior. Reads: `src/devops_cli/roadmap/request_plan.py`, `tests/commands/test_roadmap_plan_recheck_cmd.py`. Changes: `src/devops_cli/roadmap/request_plan.py`, `tests/commands/test_roadmap_plan_recheck_cmd.py`.

- [x] 3.1 The failing case is the new `test_the_dry_run_of_a_base_and_a_listing_lists_no_issue_read_and_no_fetch` in `tests/commands/test_roadmap_plan_recheck_cmd.py`
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_plan_recheck_cmd.py` fails on the base
- [x] 3.2 Make `plan_recheck_requests` of `src/devops_cli/roadmap/request_plan.py` drop the fetch for a base and the issue reads for a listing
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_plan_recheck_cmd.py` passes

## 4. Prepare the run of the stage agent

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_job.py`, `src/devops_cli/roadmap/implement/implement_phases.py`, `src/devops_cli/roadmap/phases/checkout.py`, `src/devops_cli/openspec/scaffold.py`, `tests/roadmap/stage/test_roadmap_stage.py`. Changes: `src/devops_cli/roadmap/stage/stage_job_phases.py` (new), `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_prepare.py` (new), `tests/support/fakes/roadmap_store.py`.

- [x] 4.1 The failing cases are in the new `tests/roadmap/stage/test_roadmap_stage_prepare.py`: `test_prepare_commits_the_scaffold_with_its_date_and_writes_the_state_and_the_inputs`, `test_the_listing_of_a_store_over_1_mib_holds_the_item_body_and_the_states_only`, `test_a_failed_read_of_the_comments_fails_the_item_with_ci_infra`, `test_a_false_job_time_premise_returns_the_item_in_prepare`, `test_a_false_premise_of_the_body_returns_the_item_in_prepare` and `test_a_blocker_of_an_open_plan_returns_the_item_in_prepare`. Add `comments_on` to the reads that `fail_read` of `tests/support/fakes/roadmap_store.py` can fail
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prepare.py` fails on the base
- [x] 4.2 Create `src/devops_cli/roadmap/stage/stage_job_phases.py` with `StageState`, `StageAgentInput` and `prepare_stage_job`. It reads the round, runs `StageWriter.begin`, and decides the job-time premise, the false premise and the blocker. A decision that ends the run checks in. Else it clones, switches to the base, commits the scaffold, and writes the state file, the listing and the inputs. Add `StageWriter.resume` to `src/devops_cli/roadmap/stage/stage.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prepare.py` passes

## 5. Build the stage agent on stock Coder

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/roadmap/stage/stage_agent.py` (new), `src/devops_cli/ai/tasks/roadmap_stage_coder.md` (new), `tests/roadmap/stage/test_roadmap_stage_agent.py` (new).

- [x] 5.1 The failing cases are in the new `tests/roadmap/stage/test_roadmap_stage_agent.py`. `test_the_stage_agent_is_coder_on_the_clone_with_the_three_checks_and_no_stage_tool` finds `LocalWorkspace` with its `env`, `Coder` with `repo_context=False`, and `exempt_paths == ()`. `test_each_check_counts_and_a_probe_or_a_recheck_with_no_base_does_not` covers the patterns
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_agent.py tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` fails on the base
- [x] 5.2 Create `src/devops_cli/roadmap/stage/stage_agent.py` with `build_stage_agent`. It holds `LocalWorkspace` with a scratch `HOME` and `DEVOPS_CLI_CONFIG`, and `Coder(repo_context=False, sub_agents=False)`. It also holds `RequireVerification` with the three patterns, and `Hooks`. Write `src/devops_cli/ai/tasks/roadmap_stage_coder.md`, and keep each shared rule in the phrase that the prompt-rule test holds
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_agent.py tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes

## 6. Run the agent phase with no GitHub credential

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/phases/files.py`, `src/devops_cli/roadmap/attempt_kill.py`, `tests/core/test_process.py`, `tests/roadmap/phases/test_roadmap_phase_patch.py`. Changes: `src/devops_cli/roadmap/stage/stage_job_phases.py`, `src/devops_cli/core/process.py`, `src/devops_cli/roadmap/phases/patch.py`, `tests/roadmap/stage/test_roadmap_stage_agent_phase.py` (new).

- [x] 6.1 The failing cases are in the new `tests/roadmap/stage/test_roadmap_stage_agent_phase.py`. They cover the refusal of a credential and of an output folder that is there. They cover the outputs, and the ends `unverified`, `ended` and `timeout`. One case writes a file with a script, and one sends a SIGTERM that writes no check-in
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_agent_phase.py` fails on the base
- [x] 6.2 Add `StageOutcome` and `run_stage_agent` to `src/devops_cli/roadmap/stage/stage_job_phases.py`. The phase refuses the variables of `CONST_GITHUB_AGENT_REFUSED_ENV` and a gh login (`finds_github_login`, new in `src/devops_cli/core/process.py`). It runs the agent with `UsageLimits(request_limit=None)` and writes `plan.patch`, `candidate.md` and `outcome.json` in the output folder. Give `write_patch` of `src/devops_cli/roadmap/phases/patch.py` an optional path
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_agent_phase.py` passes

## 7. Check the plan files in the one push of publish

Kind: behavior. Reads: `src/devops_cli/roadmap/phases/publish.py`, `src/devops_cli/openspec/gate.py`, `src/devops_cli/roadmap/failure.py`, `tests/roadmap/stage/test_roadmap_stage.py`. Changes: `src/devops_cli/roadmap/stage/stage_job_phases.py`, `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_publish_checks.py` (new).

- [ ] 7.1 The failing cases are in the new `tests/roadmap/stage/test_roadmap_stage_publish_checks.py`, one for each rule. The `plan_defect` path cases are a name outside the plan, a link, a mode other than `100644` and a file that is not UTF-8. The `plan_defect` content cases are a secret, another date, a scaffold marker, a refusal of `openspec validate` and an overlap of two changes. More `plan_defect` cases are a refused folder, an outcome outside its model and an `unverified` outcome with a refused folder. So are a patch over 16 MiB and a state of another item. The `ci_infra` cases are an `openspec` off its pin and a missing tool. A group over the budget stops with `_stop_on_budget`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_publish_checks.py` fails on the base
- [ ] 7.2 In `src/devops_cli/roadmap/stage/stage.py`, make the push of `_stage_one` an argument with the default `push_plan`. In `src/devops_cli/roadmap/stage/stage_job_phases.py`, add the push of `publish`: one `publish_patch` call. Its `before_push` allows only the files of a plan, scans for secrets and checks the date. It then runs the three checks on the new tree, with the base, the default branch and the listing of the state. It classes each finding, and catches `PublishRefusedError` as `plan_defect`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_publish_checks.py` passes

## 8. Write the plan and end the run in publish

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_job.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/pull_form.py`, `tests/roadmap/stage/test_roadmap_stage_apply.py`, `tests/roadmap/stage/test_roadmap_stage_job.py`, `tests/security/test_config_declarations.py`. Changes: `src/devops_cli/roadmap/stage/stage_job_phases.py`, `src/devops_cli/roadmap/stage/stage_job.py`, `src/devops_cli/config/settings.py`, `tests/roadmap/stage/test_roadmap_stage_publish.py` (new), `docs/ENV_VARS.md`.

- [ ] 8.1 The failing cases are in the new `tests/roadmap/stage/test_roadmap_stage_publish.py`. With a fixed commit time, the first gives the same tree, `stage.sha`, title, body, labels, record and comments in both forms. Others cover no git command under `work/`, the fallbacks, one `safe_text` on each text, the control characters and the fitted comment. Others cover the requests of `prepare` and each end of the outcome table, with the count of an agent `ci_infra`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_publish.py` fails on the base
- [ ] 8.2 In `src/devops_cli/roadmap/stage/stage_job_phases.py`, clone the repository at the base into the home of `publish`. Build the texts with `stage_candidate.py`, clean them and fit the plan-state comment. Settle the change with the resumed writer on that clone and the push of task 7.2, then check in. Count an agent `ci_infra` with `plan_defects` in the marks of `check_in`. Update the text of the count in `src/devops_cli/roadmap/stage/stage_job.py` and `src/devops_cli/config/settings.py`, and run `uv run devops docs generate`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_publish.py tests/roadmap/stage/test_roadmap_stage_apply.py` passes

## 9. Take a phase and a run folder on the stage command

Kind: behavior. Reads: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/phases/names.py`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`. Changes: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_job_entry.py`, `docs/commands/roadmap.md`.

- [ ] 9.1 The failing cases are new in `tests/roadmap/stage/test_roadmap_stage_job_entry.py`. A phase needs its job item, `--confirm` and a run folder, and `--source` goes only with `prepare` and `all`. The three phases run in turn on one run folder. No phase runs `run_stage_job` with no run file
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_job_entry.py` fails on the base
- [ ] 9.2 Add `--phase` (`RunPhase`, default `all`) and `--work` to `stage_cmd` in `src/devops_cli/commands/roadmap.py`, with their help in `src/devops_cli/lang/en/help.py` and the refusals in `src/devops_cli/lang/en/messages.py`. A phase other than `all` hardens the process, then calls its phase. Run `uv run devops docs generate`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_job_entry.py` passes

## 10. Document the phases and the measured checks

Kind: other. Reads: `docs/roadmap/stage.md`, `docs/roadmap/plan-recheck.md`, `docs/adr/0030-roadmap-steps-run-their-agent-apart-from-the-app-key.md`, `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md`. Changes: `docs/roadmap/stage.md`, `docs/roadmap/plan-recheck.md`, `docs/adr/0030-roadmap-steps-run-their-agent-apart-from-the-app-key.md`, `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md`.

- [ ] 10.1 On a clone of `main` with one plan commit, time `devops openspec check`, `openspec validate <change> --strict` and the recheck of the agent. Write the times in the new section "The phases of the stage Job" of `docs/roadmap/stage.md`. A check over 270 s stops the task, and the owner decides the tool
  - Verification: `$ uv run devops ci docs` passes
- [ ] 10.2 In `docs/roadmap/stage.md`, add the count of an agent `ci_infra` to the paragraph on the classes. Add `--base`, `--candidate` and `--issues` to `docs/roadmap/plan-recheck.md`. Add the addendum "The stage Job on the phases (#6705)" to ADR 0030, and `RequireVerification` to `pydantic_ai_harness.md`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 5: A test of the stage agent finds `Coder` with the stock capabilities, `RequireVerification` with the three checks, and no custom tool.
- Pending person: The custom engine code and its tests are gone., #6846 delivers this criterion after #6814 is live, because `--phase all` runs that engine until then.

## Workflow follow-up

- #6846 deletes the old stage engine, moves or deletes fix-plan and the golden-set runs, and refuses `--phase all` with `--job-item`.
- #6831 has `prepare` write the other GitHub reads of the agent, and builds on the issue listing of this change.
- #6814 runs the three phases as containers of CronJob `roadmap-stage`.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
