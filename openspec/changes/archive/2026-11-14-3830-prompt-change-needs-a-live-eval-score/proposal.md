# Proposal: #3830

## Why

A plan task can ask for evidence that its own command cannot give. The plan of #3309 held a task that ran `uv run devops roadmap eval stage --replay` as the score of a prompt change. The replay calls no model: it runs recorded plans through the gates, so a stage prompt change cannot move its score. The implement job ticked the task and recorded no score. The stage job must name the live run, and bound its cost, when a plan changes the stage prompt.

## What Changes

- `src/devops_cli/roadmap/stage/stage_change.py` splits the eval trigger paths: the stage prompt needs `uv run devops roadmap eval stage --limit <n>` or `--case <n>` with the words `score`, `before` and `after`; a gate module keeps the replay command with those words; a plan that changes both needs both commands.
- `src/devops_cli/lang/en/messages.py` adds `stage_problem_eval_live` and `stage_problem_eval_live_score`.
- `src/devops_cli/ai/tasks/roadmap_stage_change.md` states the two commands.
- `docs/ROADMAP_WORKFLOW.md` and `docs/TESTING.md` state the rule and the command forms.
- Tests cover a prompt change with the replay, with a bounded live run, with the live run but no score, and with both paths.
- The implement-job evidence rule stays with #4005, which `refine.deferred` names.

## Capabilities

- `roadmap-stage/self-rules`
- `roadmap-stage-eval`

## Impact

A plan that changes the stage prompt states a live score with a case limit. A plan that changes a gate keeps the replay. The command `--limit` exists already; no new option and no model call is added by this change.

## Feasibility

Checked on `origin/main` 5fbcd0519, 2026-11-14. `eval_replay_problems` runs under `ProposalGate.EVAL_REPLAY`. `devops roadmap eval stage` already takes `--limit` and `--case`, and `select_cases(cases, (), 2)` is covered in `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`. `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_gates.py tests/roadmap/stage/test_roadmap_stage_prompt_rules.py tests/invariants/test_roadmap_workflow_doc.py` passes.

## Existing Tool Considered

No open tool covers a rule of this project's plan check. The change extends `eval_replay_problems` and the stage prompt; it builds about 80 lines of code with its tests.
