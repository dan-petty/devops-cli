# Proposal

## Why

Issue #3028: the stage job has no regression set. On 2026-11-01 a hand run of 37 reviews found 34 flawed plans and 1 plan to reject. Nothing recorded the cases. A change of the stage prompt or of the checks ships with no measure, so nobody knows if it helps.

The plan gates of tracker #3027 (#3005, #3010 and the gates #3011 to #3019 that follow) need a baseline. This change records the cases, runs the real stage code on them, and scores the result.

## What Changes

- A committed golden set under `tests/fixtures/roadmap_eval/stage/`: one folder for each plan. It holds the issue text, the plan as a `StageProposal`, the facts of the tree that the gates need, and the defects that the review found, each with its evidence. It covers the 37 plans of 2026-11-01 and 3 `good` plans (the plans of #2992, #2859 and #2858 with the one wrong path corrected).
- A shared enum of defect types: `missing_path`, `false_premise`, `spec_delta_wrong`, `verify_form`, `task_order`, `criterion_dropped`, `ignores_existing_code`, `contrived_test` and `other`. Each defect names the gate that must refuse it: `paths` (#3010), `kind` (#3005), `pending` or `none`.
- The command `devops roadmap eval stage`, in the new group `devops roadmap eval`. A live run plans each case with the real stage planner and a chosen model, scores the first reply of the model for each type of defect that a gate catches, prints a table, and stores the report as JSON under `.data/`. It is on demand and no part of `devops ci`.
- `--replay` calls no model. It runs the recorded plans through the gates, and fails when a gate stops refusing a known-bad plan or refuses a `good` plan. A defect that waits for a gate that does not exist yet is listed and fails nothing. The test suite runs the replay on the whole set.
- `--dry-run` makes no request and lists the cases and the model calls.
- `plan_item` in `stage.py` is the one public way to plan one item with a given client and checkout. The planner takes a small `StageClient` protocol in place of `LLMClient`, so a client that records replies fits.
- `docs/ROADMAP_WORKFLOW.md` gets a section: how to run the eval, how to read the score, and the rule that a change to the stage prompt or to the checks states its score before and after in its pull request.
- Observable behavior is new (a command and its output), so the change carries a spec delta.
- The change fits one pull request. The fixtures weigh about 1 MB in total.

## Capabilities

### New Capabilities

- `roadmap-stage-eval`: the golden set of the stage job, its replay through the gates, its live score and the command.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/roadmap/stage_eval_cases.py`, `stage_eval_gates.py`, `stage_eval_run.py`, `stage_eval_score.py`, `stage_eval_render.py` (all new), `src/devops_cli/roadmap/stage.py`, `src/devops_cli/commands/roadmap_eval.py` (new), `src/devops_cli/commands/roadmap_eval_stage.py` (new), `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`.
- Data: `tests/fixtures/roadmap_eval/stage/` (new).
- Documents: `docs/ROADMAP_WORKFLOW.md`, `README.md` (generated).
- Tests: `tests/roadmap/test_roadmap_stage_eval_cases.py`, `test_roadmap_stage_eval_gates.py`, `test_roadmap_stage_eval_run.py`, `test_roadmap_stage_eval_command.py` (all new).

## Feasibility

- `devops gh api repos/dan-petty/devops-cli/issues/3028` and `.../3027` give the scope and the order: #3028 and #3030 are the baseline, and both add a subcommand to one `devops roadmap eval` group.
- The evaluation of 2026-11-01 holds 37 reviews (35 merged, 2 open then). `git log origin/main --grep "(#<pr>)$"` finds the merge commit of every one of the 37 pull requests. `git show <merge>:<file>` gives its change folder, and `git ls-tree -r <merge>^` gives the tree it was staged on. Both commits are in the history of this repository.
- The review file is ignored by git on the owner workstation, so the fixtures are derived from it and from `git show`. No fixture is a copy of that file.
- Run on the recorded plans, the path gate (`path_problems`, #3010) refuses 25 of the 37 and the kind rule (`StageGroup`, #3005) refuses 24 of the 37. The two sets agree with the counts in the review and in #3005 (50 groups in 22 plans). The 3 `good` plans pass both.
- A reduced tree gives the same answer as the full tree. For every case the builder checked that `path_problems` returns the same sentences on the tracked files kept in `facts.json` as on the full `git ls-tree` of the commit. So a replay needs no deep clone.
- `_Planner` in `stage.py` takes a client, a checkout, a commit and a budget. `collect_context` reads files with `git show <sha>:<path>`, so a detached worktree of the staging commit is enough. The live run reuses the planner and its checks.

## Existing Tool Considered

`pydantic-evals` (already a dependency, used by `devops roadmap intake-eval`) covers datasets, a run report and evaluators. It does not fit the score here. The score is a count of gate results for each defect type over a fixed table, and the replay needs no model task at all. Using the library needs one evaluator for each type, a report renderer, and a way to feed the first reply of the model to an evaluator, so it removes about 40 lines of counting and adds a layer to keep. The score code in this change is about 120 lines. The cost to build is about 15 000 tokens, to keep about 2 000 tokens a year, and to fix about 5 000 tokens. It takes about 2 hours. `pydantic-ai` `FunctionModel` and the `ModelFake` of the test suite double the model in the tests. The change deletes no code.
