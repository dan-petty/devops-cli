# Tasks

## 1. Run the hooks of the repository as a child of the Job

Kind: behavior. Reads: `src/devops_cli/core/process.py`, `.pre-commit-config.yaml`, `tests/support/implement_step.py`. Changes: `src/devops_cli/roadmap/implement_hooks.py` (new), `src/devops_cli/config/commands.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_hooks.py` (new).

- [x] 1.1 Write failing tests in `tests/roadmap/test_roadmap_implement_hooks.py` for the scenarios of "The hooks of the repository are an exit check" that the hook module decides: the argv of the stage run, `PRE_COMMIT_HOME` under the data directory, no token in the environment, a fixer that is staged and run again, exit 1 as a repairable failure, any other code as a stop, the output cut to a bound, and the argv of the install
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_hooks.py` fails on the base
- [x] 1.2 Add `implement_hooks.py` with the stage run, the install, the environment, the constants, the program name `pre-commit` and the messages
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_hooks.py` passes

## 2. Give a failed hook and a failed check bounded repair rounds

Kind: behavior. Reads: `src/devops_cli/roadmap/implement_step.py`, `tests/roadmap/test_roadmap_implement_step_repair.py`, `tests/roadmap/test_roadmap_implement_step_ticks.py`. Changes: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_step_hooks.py` (new), `tests/roadmap/test_roadmap_implement_step_repair.py`, `tests/roadmap/test_roadmap_implement_step_ticks.py`, `tests/roadmap/test_roadmap_implement_step.py`.

- [x] 2.1 Write failing replay tests with a stub model in `tests/roadmap/test_roadmap_implement_step_hooks.py` for the scenarios of "A step asks for a fix of a failed check within the repair rounds" and "The hooks of the repository are an exit check": a hook failure for a `pytest.raises` with no `match` that the model repairs in a round, a hook failure that the model cannot fix, which uses all rounds and stops with the output, a stop at exit code 3, `repair_rounds` 0, the count in the outcome, and a repair that breaks `ruff`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_hooks.py` fails on the base
- [x] 2.2 Add the setting `roadmap.implement.repair_rounds`, the loop of repair rounds in `_attempt`, the hook check in `_exit_failure`, `StepOutcome.repair_rounds` and its table row, and the message of the hook turn
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_hooks.py`
- [x] 2.3 Change the existing tests that expect one extra turn: they set `repair_rounds` to 1 where they test the single turn, and gain a case for the default
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py tests/roadmap/test_roadmap_implement_step_repair.py tests/roadmap/test_roadmap_implement_step_ticks.py tests/roadmap/test_roadmap_implement_step_own_text.py tests/roadmap/test_roadmap_implement_step_tests_kept.py tests/roadmap/test_roadmap_implement_strays.py`

## 3. Run the scoped checks before the push

Kind: behavior. Reads: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/commands/ci.py`, `tests/roadmap/test_roadmap_implement_job.py`. Changes: `src/devops_cli/roadmap/implement_scoped_ci.py` (new), `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_scoped_ci.py` (new), `tests/roadmap/test_roadmap_implement_job.py`.

- [x] 3.1 Write failing tests in `tests/roadmap/test_roadmap_implement_scoped_ci.py` and `tests/roadmap/test_roadmap_implement_job.py` for the scenarios of "The job installs the hook environments before the first step", "The job runs the scoped checks before it pushes" and "The comment on the pull request shows the repair rounds and the scoped checks": the install that fails, the argv of the three checks and the changed paths, a change with no Python file, an ast-grep violation that a fix step repairs before the first push, a check that no fix repairs, which pushes nothing, the documentation generated again after a fix, and the lines of the comment
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_scoped_ci.py tests/roadmap/test_roadmap_implement_job.py` fails on the base
- [x] 3.2 Add `implement_scoped_ci.py`, the install in `_start`, the scoped checks and their fix rounds in `_push`, and the lines of the comment
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_scoped_ci.py tests/roadmap/test_roadmap_implement_job.py tests/roadmap/test_roadmap_implement_planned.py`

## 4. Scope the workflow checks of the push, and guard the drift

Kind: other. Reads: `.pre-commit-config.yaml`, `tests/invariants/test_workflow_contracts.py`, `Dockerfile`. Changes: `.pre-commit-config.yaml`, `tests/invariants/test_workflow_contracts.py`, `tests/invariants/test_runner_hooks.py` (new), `CONTRIBUTING.md`, `docs/SDLC.md`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/ci_quality_gate.md`.

- [x] 4.1 Split the `pre-push` hook: `devops-ci-pre-push` runs `lint,format`, and the new `devops-ci-workflows-pre-push` runs `actionlint,zizmor` when the push changes a file of `.github/workflows/` or `.github/actions/`
  - Verification: `uv run pre-commit run --hook-stage pre-push --from-ref origin/main --to-ref HEAD` and `uv run devops ci test tests/invariants/test_workflow_contracts.py`
- [x] 4.2 Add `tests/invariants/test_runner_hooks.py`: each scoped row is a row of `devops ci`, each local hook runs a tool that the runner holds, and the branch-name hook accepts a branch of every type that the job makes; update the contract test of the `pre-push` hooks
  - Verification: `uv run devops ci test tests/invariants/test_runner_hooks.py tests/invariants/test_workflow_contracts.py`
- [x] 4.3 Change the three documents that name the hook command
  - Verification: `git grep -n "lint,format,actionlint,zizmor" -- CONTRIBUTING.md docs/SDLC.md src/devops_cli/ai/knowledge_base/devops_cli/tasks/ci_quality_gate.md` prints nothing

## 5. The prompt and the documents

Kind: documents. Reads: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `k8s/README.md`, `docs/ROADMAP_WORKFLOW.md`. Changes: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `tests/roadmap/test_roadmap_implement_prompt.py`, `k8s/README.md`, `docs/ROADMAP_WORKFLOW.md`, `README.md`.

- [x] 5.1 Tell the agent in the prompt that the hooks of the project run on its changed files, and that a failure gives it a turn
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_prompt.py`
- [x] 5.2 Describe the hooks, the repair rounds, the setting and the scoped checks in step 16 of `k8s/README.md` and in `docs/ROADMAP_WORKFLOW.md`, with the extra run time of an item
  - Verification: `git grep -n "repair_rounds" -- k8s/README.md docs/ROADMAP_WORKFLOW.md` prints a line for each file
- [x] 5.3 Regenerate the generated documents
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops ci docs`

## 6. Keep the scoped checks bounded, the hooks trusted and every stop safe

Kind: behavior. Reads: `src/devops_cli/core/test_selection.py`, `src/devops_cli/roadmap/implement_run.py`, `tests/core/test_roadmap_implement_checks.py`. Changes: `src/devops_cli/roadmap/implement_scoped_ci.py`, `src/devops_cli/roadmap/implement_hooks.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `docs/adr/0014-required-checks-gate-the-merge-and-the-pre-push-hook-runs-the-fast-static-checks.md`, `tests/roadmap/test_roadmap_implement_scoped_ci.py`, `tests/roadmap/test_roadmap_implement_hooks.py`, `tests/roadmap/test_roadmap_implement_step_hooks.py`, `tests/roadmap/test_roadmap_implement_job_scoped.py`, `tests/core/test_roadmap_implement_checks.py`.

- [x] 6.1 Write failing tests for the scenarios of the review: a shared module keeps only the changed test modules, a change that no test covers runs no test command, a configuration that the agent edits changes no hook run, a hook stage that runs out of time stops the step and a fix step with no push, an error in the scoped checks pushes nothing, and a failed check after the push gets bounded rounds with a comment for each
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_scoped_ci.py tests/roadmap/test_roadmap_implement_hooks.py tests/roadmap/test_roadmap_implement_step_hooks.py tests/roadmap/test_roadmap_implement_job_scoped.py tests/core/test_roadmap_implement_checks.py` fails on the code before this group
- [x] 6.2 Add `plan_tests` and the limit `CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES`, the notes of the comment, and the trusted configuration (`trusted_config`, `--config` on every run, `hooks` on the step); make a hook run that runs out of time a failure that no repair fixes; stop with no push on any error of the scoped phase; loop the post-push rounds with a comment for each
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_scoped_ci.py tests/roadmap/test_roadmap_implement_hooks.py tests/roadmap/test_roadmap_implement_step_hooks.py tests/roadmap/test_roadmap_implement_job_scoped.py tests/core/test_roadmap_implement_checks.py`
- [x] 6.3 Record the measured time of the bounded tests check in the proposal, `docs/ROADMAP_WORKFLOW.md` and `k8s/README.md`, and fix the sentence of ADR 0014 on the pre-push hook
  - Verification: `! git grep -n -e "2 to 3 minutes" -e "10 s to 90 s" -e "no-fallback" -- docs/ROADMAP_WORKFLOW.md k8s/README.md` prints nothing
- [x] 6.4 Regenerate the generated documents
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops ci docs`

## 7. Fail-to-pass and archive

Kind: other.

- [x] 7.1 Run the fail-to-pass check on the new tests
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [ ] 7.2 Archive the change
  - Verification: `uv run devops openspec archive 3043-runner-hooks-and-scoped-ci` and `uv run devops openspec check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
