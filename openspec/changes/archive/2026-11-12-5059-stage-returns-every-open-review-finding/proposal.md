# Proposal: #5059

## Why

The model review of a stage plan keeps the plan pull request in draft with the label `plan/needs-fix` when its last review has an open finding (#3264). But the repair loop sent only some open findings back to the planner. `OPEN_TYPES` in `src/devops_cli/roadmap/stage/stage_verify.py` was `RETURN_TYPES | {SPEC_DELTA_WRONG, CRITERION_DROPPED}`, and `StageJob._verified` in `src/devops_cli/roadmap/stage/stage.py` started a repair round only when `returning` gave a finding of `RETURN_TYPES`. So a plan whose open findings were all `spec_delta_wrong`, `criterion_dropped` or a placeholder got no repair round. It opened as a draft with `plan/needs-fix`, and no job revisits such a pull request. In the 24 hours to 2026-11-12, 5 of 7 plan pull requests ended this way. Closes #5059.

## What Changes

- The change fits one pull request.
- Each open finding returns the plan to the planner while a repair round remains. `OPEN_TYPES` lists the seven types, and `RETURN_TYPES` and `returning` go away. `StageJob._review` gives the findings and the open findings, and `StageJob._verified` starts a repair round when the review has an open finding. The repair request lists each open finding of the review in `problem`, as before.
- The planner prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` says that `problem` can list the open findings of a model review, and tells the planner how to fix a `criterion_dropped` finding and a `spec_delta_wrong` finding.
- `devops roadmap eval verify` counts the open findings on the good plans as the findings that return a plan.
- The line `stage review round:` keeps its fields. `returned` and `open` are now equal.
- The review of refine keeps its open types: `JUDGE_OPEN_TYPES` is `OPEN_TYPES` less `task_order`, `verify_form` and `criterion_dropped`, and `OPEN_TYPES` holds the same seven types.
- `docs/roadmap/stage.md` and the module texts of `stage.py` and `stage_verify.py` state the rule.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/verification`: Every open finding returns the plan to the planner.
- `roadmap-stage/ready`: An open finding keeps the plan in draft (the scenario of a test-only group).

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_verify_eval.py`, `src/devops_cli/roadmap/round_log.py`.
- Prompt: `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- Documents: `docs/roadmap/stage.md`.
- Tests: `tests/roadmap/stage/test_roadmap_stage_verification.py`, `tests/roadmap/stage/test_roadmap_stage_verify.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.
- Cost: a plan with an open finding of the two types, or a placeholder finding, now uses up to `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS` (2) more planner runs and reviews, as a plan with a `missing_path` finding does.

## Feasibility

- Source on `main` at a172563f7: `returning` in `src/devops_cli/roadmap/stage/stage_verify.py` keeps only `RETURN_TYPES`, and the loop in `StageJob._verified` breaks when `returned` is empty, while `open_findings` takes `OPEN_TYPES` and the placeholder rule. So the gap of the issue is real.
- Command output: Loki, the lines `stage review round:` of the 24 hours to 2026-11-12. Of 7 plan pull requests, 5 ended with `returned=0` and `open>=1`: #1910 (round 0, open 2), #2530 (round 0, open 1), #4757 (round 1, open 1), #2968 (round 1, open 2) and #4697 (round 1, open 1).
- Command output: the three new tests of `tests/roadmap/stage/test_roadmap_stage_verification.py` fail on `main` (`ValueError: not enough values to unpack (expected 2, got 1)`: the planner gets no second request) and pass with the change.
- Archive `2026-11-06-3448-criterion-dropped-keeps-plan-draft` chose not to return `criterion_dropped`, so that a false finding costs one label and no second planner call. The Loki data shows the cost of that choice: no job repairs the label, so the plan stays a draft. The decision is reversed in `design.md`.
- `uv run devops roadmap eval stage --replay` runs the recorded plans through the gates and calls no model, so it gives the same report before and after the change. `uv run devops roadmap eval verify` calls the model of the task `verification` through the gateway, so it does not run offline.

## Existing Tool Considered

No open tool repairs an OpenSpec plan from review findings. The change merges two sets of an existing module into one and deletes a function, `returning`, and a set, `RETURN_TYPES`. It costs about 150,000 tokens to build and test, about 1,000 tokens to keep, and about 2 hours elapsed.
