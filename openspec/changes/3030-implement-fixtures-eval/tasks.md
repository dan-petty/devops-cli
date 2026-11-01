# Tasks

## 1. Count the tool calls, and read the item through a protocol

Reads: `src/devops_cli/roadmap/implement_step.py`. Changes: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_step.py`.

- [x] 1.1 Write a failing test in `tests/roadmap/test_roadmap_implement_step.py` that a step whose scripted model makes three tool calls in two replies reports `tool_calls` 3 in the outcome, in its JSON and in its table
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py` fails on the base
- [x] 1.2 Add `tool_calls` to the turn and to `StepOutcome`, add the row to the table, add the protocol `ItemReader` for the `store` parameter of `build_step_inputs`, `run_step` and `run_fix_step`, and make `commands_failure` public
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py tests/roadmap/test_roadmap_implement_job.py`

## 2. Load and validate the fixtures

Reads: `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/exceptions/roadmap.py`. Changes: `src/devops_cli/roadmap/implement_eval.py` (new), `src/devops_cli/exceptions/roadmap.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_eval_fixtures.py` (new), `tests/support/roadmap_eval.py` (new).

- [x] 2.1 Write failing tests in `tests/roadmap/test_roadmap_implement_eval_fixtures.py` for the scenarios of "A fixture holds an item, its plan, a pinned commit and its properties": a valid folder, an unknown field, a bad SHA, a missing group, a `changes` path the group does not name, a missing diff file, and a result that expects a command property to fail
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_eval_fixtures.py` fails on the base
- [x] 2.2 Add the models, the loader and `ImplementEvalError` in `src/devops_cli/roadmap/implement_eval.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_eval_fixtures.py` passes

## 3. Evaluate the six properties

Reads: `src/devops_cli/roadmap/implement_test_names.py`, `src/devops_cli/roadmap/implement_step.py`. Changes: `pyproject.toml`, `uv.lock`, `src/devops_cli/roadmap/implement_eval_properties.py` (new), `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_eval_properties.py` (new).

- [x] 3.1 Write failing tests in `tests/roadmap/test_roadmap_implement_eval_properties.py` for the scenarios of "Four properties come from a diff and the plan" and "Two properties run commands in the tree of the result"
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_eval_properties.py` fails on the base
- [x] 3.2 Add the dependency `unidiff` and the module `implement_eval_properties.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_eval_properties.py` passes

## 4. Run a fixture in a scratch clone, and report

Reads: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/clone_git.py`, `tests/support/implement_step.py`. Changes: `src/devops_cli/roadmap/implement_eval_run.py` (new), `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_eval_run.py` (new), `tests/support/roadmap_eval.py`.

- [x] 4.1 Write failing tests in `tests/roadmap/test_roadmap_implement_eval_run.py` that run a fixture through the real step with a scripted model in a temporary repository: a step that does the group, a step that leaves a scratch file and stops, a check of recorded results, the cleanup, and the JSON report
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_eval_run.py` fails on the base
- [x] 4.2 Add the scratch clone, the run of one fixture, the check of a recorded result, the model choice, the report and its render in `implement_eval_run.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_eval_run.py` passes

## 5. The command `devops roadmap eval implement`

Reads: `src/devops_cli/commands/roadmap.py`. Changes: `src/devops_cli/commands/roadmap_eval.py` (new), `src/devops_cli/commands/roadmap_eval_implement.py` (new), `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_roadmap_eval_implement.py` (new).

- [ ] 5.1 Write failing CLI tests in `tests/commands/test_roadmap_eval_implement.py` for `--dry-run`, `--fixture` with an unknown name, `--check-only` with a matching and a mismatching result, `--json`, and a live run with the model fake
  - Verification: `uv run devops ci test tests/commands/test_roadmap_eval_implement.py` fails on the base
- [ ] 5.2 Add the group `eval`, the command and its help
  - Verification: `uv run devops ci test tests/commands/test_roadmap_eval_implement.py tests/invariants/test_dry_run_class_ratchet.py` passes

## 6. The fixtures

Reads: `tests/fixtures/dry_run_gaps.json`. Changes: `tests/fixtures/roadmap_eval/implement/` (new), `tests/invariants/test_roadmap_eval_fixtures.py` (new).

- [ ] 6.1 Build the 12 fixtures from the merge history of `main`, the group commits of closed pull request 3000 and of pull requests 3020 and 3078, and the diffs in the Job comments of #2175, #2519, #2531, #2735, #2739 and #2747
  - Verification: `uv run devops roadmap eval implement --check-only` exits 0 and prints every recorded result as behaving as recorded
- [ ] 6.2 Add an invariant test that loads the committed set, counts at least 10 fixtures with #2175 and #2735 among them, requires a recorded result that fails nothing and one that fails something, and holds the set under 300 KB
  - Verification: `uv run devops ci test tests/invariants/test_roadmap_eval_fixtures.py`

## 7. Documents, evidence and archive

Reads: `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [ ] 7.1 Add the section "Measure the implement job" to `docs/ROADMAP_WORKFLOW.md`: the command, the six properties, and the rule that a change to the implement prompt or tool set states its score before and after
  - Verification: `uv run devops ci docs`
- [ ] 7.2 Regenerate the command documents
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops ci docs`
- [ ] 7.3 Run the fail-to-pass check on the new tests
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [ ] 7.4 Archive the change
  - Verification: `uv run devops openspec archive 3030-implement-fixtures-eval` and `uv run devops openspec check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
