# Tasks

## 1. Run the hooks of the repository as a child of the Job

Kind: behavior. Reads: `src/devops_cli/core/process.py`, `.pre-commit-config.yaml`, `tests/support/implement_step.py`. Changes: `src/devops_cli/roadmap/implement_hooks.py` (new), `src/devops_cli/config/commands.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_hooks.py` (new).

- [ ] 1.1 Write failing tests in `tests/roadmap/test_roadmap_implement_hooks.py` for the scenarios of "The hooks of the repository are an exit check" that the hook module decides: the argv of the stage run, `PRE_COMMIT_HOME` under the data directory, no token in the environment, a fixer that is staged and run again, exit 1 as a repairable failure, any other code as a stop, the output cut to a bound, and the argv of the install
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_hooks.py` fails on the base
- [ ] 1.2 Add `implement_hooks.py` with the stage run, the install, the environment, the constants, the program name `pre-commit` and the messages
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_hooks.py` passes

## 2. Give a failed hook and a failed check bounded repair rounds

Kind: behavior. Reads: `src/devops_cli/roadmap/implement_step.py`, `tests/roadmap/test_roadmap_implement_step_repair.py`, `tests/roadmap/test_roadmap_implement_step_ticks.py`. Changes: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_step_hooks.py` (new), `tests/roadmap/test_roadmap_implement_step_repair.py`, `tests/roadmap/test_roadmap_implement_step_ticks.py`, `tests/roadmap/test_roadmap_implement_step.py`.

- [ ] 2.1 Write failing replay tests with a stub model in `tests/roadmap/test_roadmap_implement_step_hooks.py` for the scenarios of "A step asks for a fix of a failed check within the repair rounds" and "The hooks of the repository are an exit check": a hook failure for a `pytest.raises` with no `match` that the model repairs in a round, a hook failure that the model cannot fix, which uses all rounds and stops with the output, a stop at exit code 3, `repair_rounds` 0, the count in the outcome, and a repair that breaks `ruff`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_hooks.py` fails on the base
- [ ] 2.2 Add the setting `roadmap.implement.repair_rounds`, the loop of repair rounds in `_attempt`, the hook check in `_exit_failure`, `StepOutcome.repair_rounds` and its table row, and the message of the hook turn
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_hooks.py`
- [ ] 2.3 Change the existing tests that expect one extra turn: they set `repair_rounds` to 1 where they test the single turn, and gain a case for the default
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py tests/roadmap/test_roadmap_implement_step_repair.py tests/roadmap/test_roadmap_implement_step_ticks.py tests/roadmap/test_roadmap_implement_step_own_text.py tests/roadmap/test_roadmap_implement_step_tests_kept.py tests/roadmap/test_roadmap_implement_strays.py`

## 3. Run the scoped checks before the push

Kind: behavior. Reads: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/commands/ci.py`, `tests/roadmap/test_roadmap_implement_job.py`. Changes: `src/devops_cli/roadmap/implement_scoped_ci.py` (new), `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_scoped_ci.py` (new), `tests/roadmap/test_roadmap_implement_job.py`.

- [ ] 3.1 Write failing tests in `tests/roadmap/test_roadmap_implement_scoped_ci.py` and `tests/roadmap/test_roadmap_implement_job.py` for the scenarios of "The job installs the hook environments before the first step", "The job runs the scoped checks before it pushes" and "The comment on the pull request shows the repair rounds and the scoped checks": the install that fails, the argv of the three checks and the changed paths, a change with no Python file, an ast-grep violation that a fix step repairs before the first push, a check that no fix repairs, which pushes nothing, the documentation generated again after a fix, and the lines of the comment
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_scoped_ci.py tests/roadmap/test_roadmap_implement_job.py` fails on the base
- [ ] 3.2 Add `implement_scoped_ci.py`, the install in `_start`, the scoped checks and their fix rounds in `_push`, and the lines of the comment
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_scoped_ci.py tests/roadmap/test_roadmap_implement_job.py tests/roadmap/test_roadmap_implement_planned.py`

## 4. Scope the workflow checks of the push, and guard the drift

Kind: other. Reads: `.pre-commit-config.yaml`, `tests/invariants/test_workflow_contracts.py`, `Dockerfile`. Changes: `.pre-commit-config.yaml`, `tests/invariants/test_workflow_contracts.py`, `tests/invariants/test_runner_hooks.py` (new), `CONTRIBUTING.md`, `docs/SDLC.md`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/ci_quality_gate.md`.

- [ ] 4.1 Split the `pre-push` hook: `devops-ci-pre-push` runs `lint,format`, and the new `devops-ci-workflows-pre-push` runs `actionlint,zizmor` when the push changes a file of `.github/workflows/` or `.github/actions/`
  - Verification: `uv run pre-commit run --hook-stage pre-push --from-ref origin/main --to-ref HEAD` and `uv run devops ci test tests/invariants/test_workflow_contracts.py`
- [ ] 4.2 Add `tests/invariants/test_runner_hooks.py`: each scoped row is a row of `devops ci`, each local hook runs a tool that the runner holds, and the branch-name hook accepts a branch of every type that the job makes; update the contract test of the `pre-push` hooks
  - Verification: `uv run devops ci test tests/invariants/test_runner_hooks.py tests/invariants/test_workflow_contracts.py`
- [ ] 4.3 Change the three documents that name the hook command
  - Verification: `git grep -n "lint,format,actionlint,zizmor" -- CONTRIBUTING.md docs/SDLC.md src/devops_cli/ai/knowledge_base/devops_cli/tasks/ci_quality_gate.md` prints nothing

## 5. The prompt and the documents

Kind: documents. Reads: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `k8s/README.md`, `docs/ROADMAP_WORKFLOW.md`. Changes: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `tests/roadmap/test_roadmap_implement_prompt.py`, `k8s/README.md`, `docs/ROADMAP_WORKFLOW.md`, `README.md`.

- [ ] 5.1 Tell the agent in the prompt that the hooks of the project run on its changed files, and that a failure gives it a turn
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_prompt.py`
- [ ] 5.2 Describe the hooks, the repair rounds, the setting and the scoped checks in step 16 of `k8s/README.md` and in `docs/ROADMAP_WORKFLOW.md`, with the extra run time of an item
  - Verification: `git grep -n "repair_rounds" -- k8s/README.md docs/ROADMAP_WORKFLOW.md` prints a line for each file
- [ ] 5.3 Regenerate the generated documents
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops ci docs`

## 6. Fail-to-pass and archive

Kind: other.

- [ ] 6.1 Run the fail-to-pass check on the new tests
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [ ] 6.2 Archive the change
  - Verification: `uv run devops openspec archive 3043-runner-hooks-and-scoped-ci` and `uv run devops openspec check`

## Workflow follow-up

- The fix of a failed check after the push stays at one round. Repair rounds after the push are the work of #3053.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
