# Proposal

## Why

Issue #3030: the implement job has no measure. Its first outcomes were two deliveries (#2735 and #2739), two items that needed a person (#2656 and #2747), a stop at group 2 on a scratch file in the checkout root (#2175), and many stops at group 1 on a wrong plan. A change to the implement prompt or to its tool set cannot be compared with an older one. Tracker #3027 puts this baseline first: later changes to the stage job and the implement job must beat a recorded score.

## What Changes

- Fourteen fixtures under `tests/fixtures/roadmap_eval/implement/`, about 275 KB in all. A test holds the set under 300 KB. A fixture holds the issue text, the plan folder (`proposal.md`, `design.md`, `tasks.md`), a base SHA of this repository, the group to run, the paths of its `Changes:` line, the commands that must pass, and the recorded results of earlier runs. A recorded result is a diff with the properties that it is expected to fail. The fixtures come from merged deliveries, from the diffs that stopped runs left in their Job comments, from corrected plans that no run has used yet, and from the merged deliveries of #2735 and #2739 with their corrected plans, which score clean on every property.
- A new module `src/devops_cli/roadmap/implement_eval.py` holds the fixture models and the loader. It refuses a fixture that breaks the schema or contradicts its own plan.
- A new module `src/devops_cli/roadmap/implement_eval_properties.py` evaluates six properties. Four come from a diff alone: `tests_kept`, `diff_scope`, `no_scratch` and `tasks_ticked`. Two run commands in a tree: `tests_pass` and `verify_passes`.
- A new module `src/devops_cli/roadmap/implement_eval_run.py` makes a scratch clone of the base SHA in a temporary folder, puts the plan in it, runs one step through `run_step`, the path that the Job uses, and evaluates the properties. It reads the item from the fixture, so it touches no GitHub state, and it pushes nothing.
- `devops roadmap eval implement` is the command. The group `devops roadmap eval` is a Typer sub-app in its own small module, `src/devops_cli/commands/roadmap_eval.py`, so the command for the stage job (#3028) adds one line. The options are `--fixture` (repeatable), `--model`, `--json`, `--dry-run` and `--check-only`. `--check-only` evaluates the recorded results with no model call and no clone. `--run-commands` adds the two command properties to a check of a recorded result, and then compares all six with the record. A record may name a command property as failed.
- `StepOutcome` gets the field `tool_calls`. `run_step` and `run_fix_step` read the item through the small protocol `ItemReader`, which the roadmap store satisfies.
- `unidiff` becomes a runtime dependency. It reads the files, hunks and lines of a diff.
- A section in `docs/ROADMAP_WORKFLOW.md` states the rule: a change to the implement prompt or tool set states its score before and after.
- The command and its output are observable, so the change carries spec deltas: a new capability `roadmap-eval-implement`, and a changed requirement of `roadmap-implement-step`.
- A run that raises on one fixture still prints and writes the report of the fixtures before it. A report file has a unique name.
- The change fits one pull request.

The command is on demand. It calls the model through the gateway, so it is no row of `devops ci`. Its offline mode runs in the test suite.

## Capabilities

### New Capabilities

- `roadmap-eval-implement`: the fixtures, the six properties, the scratch clone run, and the report of `devops roadmap eval implement`.

### Modified Capabilities

- `roadmap-implement-step`: the requirement "The outcome is a structured report" adds the tool calls.

## Impact

- Code: `src/devops_cli/roadmap/implement_eval.py`, `src/devops_cli/roadmap/implement_eval_properties.py`, `src/devops_cli/roadmap/implement_eval_run.py` (new), `src/devops_cli/commands/roadmap_eval.py` and `src/devops_cli/commands/roadmap_eval_implement.py` (new), `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/exceptions/roadmap.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`.
- Dependency: `unidiff` in `pyproject.toml` and `uv.lock`.
- Data: `tests/fixtures/roadmap_eval/implement/` (new).
- Documents: `docs/ROADMAP_WORKFLOW.md`, and the generated command documents. `openspec/specs/roadmap-implement-step/spec.md` changes by archive.
- Tests: `tests/roadmap/test_roadmap_implement_eval_fixtures.py`, `tests/roadmap/test_roadmap_implement_eval_properties.py`, `tests/roadmap/test_roadmap_implement_eval_run.py`, `tests/commands/test_roadmap_eval_implement.py`, `tests/invariants/test_roadmap_eval_fixtures.py` (new), `tests/roadmap/test_roadmap_implement_step.py`, `tests/support/roadmap_eval.py` (new).

## Feasibility

- `git grep -n "store.item\|store: RoadmapStore" src/devops_cli/roadmap/implement_step.py` shows that `run_step` uses the store for one call, `store.item(item)`. A fixture item can answer it, so the run needs no GitHub read.
- `StepOutcome` holds `requests`, `input_tokens` and `output_tokens`, and the step reads the tool calls of every reply in `_resend_after`. The count of tool calls is one sum over the same replies.
- A stopped run keeps its diff in the Job comment. `devops gh api repos/dan-petty/devops-cli/issues/2175/comments` returns the diff of the stop at group 2 (a scratch file `test_get_ollama_semaphore.py` in the root, all three tasks ticked, no work). The comments of #2735, #2739, #2747, #2531 and #2519 hold the diffs of their stops. Pull request 3000 (closed, not merged) holds the five group commits of the first attempt at #2175, and pull requests 3020 and 3078 hold the group commits of #2519 and #2579.
- `git cat-file -t` prints `commit` for each SHA that a fixture pins: the base of pull request 3000 (`f8b65bd2`), the parents of the squash commits of #2896 (`1545b85a`) and #2901 (`a5082031`), and the plan commits of the corrected plans.
- The plans of #2735 and #2739 name `tests/test_process.py` and `tests/test_process_env.py`. `git ls-tree` shows that neither file exists at the base, and the deliveries put their tests in `tests/core/`. So the property `diff_scope` fails on both deliveries. That is a true result of the old plans, and the fixtures record it.
- `unidiff` 1.0.1 is on PyPI with the license MIT, released 2026-09-15 after 1.0.0 of 2026-07-25, for Python 3.9 and later. `PatchSet` gives each file with `path`, `is_added_file` and `is_removed_file`, and each hunk with its source lines and target lines.
- The review code already parses a diff in `src/devops_cli/review/diff.py`, but it returns the added lines and the hunk ranges. It does not return the removed lines or the added files.
- The CI jobs that run tests check out with `fetch-depth: 0` (`.github/workflows/ci.yml`), but a replay must not need it. So each result is a recorded diff, and the offline properties need no git history.

## Existing Tool Considered

- `unidiff` reads the diffs. `pathspec`, a declared dependency, matches the scratch patterns. `parse_task_groups` and `code_spans` of `step_files.py` read the plan. `run_step` runs the step. `git clone --shared` makes the scratch clone. pydantic validates the fixtures.
- `pydantic-evals` (used by `devops roadmap intake-eval`) was considered for the scoring. Its evaluators return one value for each assertion, and its report averages them. Here a property can be skipped (a stopped step has no tree to run commands in), and the report needs the tokens, the tool calls and the wall time of the step, which no evaluator sees. The six properties are six pure functions over a diff or a tree. The report is a table of them. `pydantic-evals` would add a dataset, an evaluator class for each property and a custom render for the same result.
- The change builds the evaluators and the run. Cost: about 150 000 tokens to write, about 10 000 tokens a year to keep, about 30 000 tokens to fix until it matches the first live runs. It takes about one working day.
- The change deletes no code.
