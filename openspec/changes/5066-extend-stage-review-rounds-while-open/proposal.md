# Proposal: #5066

## Why

The model review of a stage plan returned the plan to the planner at most `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS` (2) times, a hard constant. A plan that still has an open finding after the last round opens as a draft with `plan/needs-fix`, and no job repairs it. In the 24 hours to 2026-11-12, 2 of 7 plan pull requests (#4472 and #4945) used both rounds while the plan still improved, and stopped with open findings that return the plan. Closes #5066.

## What Changes

- The change fits one pull request.
- A setting `roadmap.stage.verify_repair_rounds` (variable `DEVOPS_CLI_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS`) sets the repair rounds of the review, with a default of 2, `ge=0` and `le=CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS_CEILING` (4). The constant `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS` goes away.
- After the last round of the setting, one more round starts only while the last review has fewer open findings than the review before it (`repair_round_due` in `src/devops_cli/roadmap/stage/stage_verify.py`). The check compares counts and makes no model call. No item gets more than 4 repair rounds.
- No repair round starts after the Service stops: `StageJob._verified` calls the drain guard of #4925 (`raise_if_service_stops`) before each round.
- A round past the setting logs `stage review extended: repo=<owner/repo> item=#<n> round=<n> before=<n> open=<n> version=<version>`. The line `stage review round:` keeps one line for each review, and the result line of the item counts each review run in `verify_rounds`, the extended rounds too.
- `docs/roadmap/stage.md`, `docs/ROADMAP_WORKFLOW.md`, `k8s/README.md` and the generated `docs/CONFIGURATION.md` and `docs/ENV_VARS.md` state the setting, the rule and the line.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/verification`: An evidence-backed finding returns the plan for the set repair rounds (renamed from "An evidence-backed finding returns the plan at most twice"); The repair rounds of the review are a setting with a hard ceiling; One more repair round follows while the open findings drop.

## Impact

- Code: `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/round_log.py`.
- Documents: `docs/roadmap/stage.md`, `docs/ROADMAP_WORKFLOW.md`, `k8s/README.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `README.md` (generated).
- Tests: `tests/roadmap/stage/test_roadmap_stage_review_rounds.py` (new), `tests/roadmap/test_roadmap_limit_classes.py`, `tests/security/test_config_declarations.py`.
- Cost: at the defaults nothing changes. An extended item costs one more plan run with its gate returns and one more review run for each extended round. At both ceilings an item makes at most 5R + 6 = 21 plan runs and 5 review runs, against 13 and 3 before.

## Feasibility

- Source on `main` at 21b116eac: `StageJob._verified` in `src/devops_cli/roadmap/stage/stage.py` loops `for round_ in range(1, CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS + 1)` and breaks when the review has no open finding (#5059). No repair round calls `raise_if_service_stops`; only the first plan, the kept plan and each gate return do.
- Command output: Loki, the lines `stage review round:` of the 24 hours to 2026-11-12. #4472 and #4945 reached round 2 with findings that return the plan.
- `roadmap.stage.gate_returns` (#4802, #4900) is a setting with a hard ceiling (`CONST_ROADMAP_STAGE_GATE_RETURNS_CEILING`, `le=` on the field). This change uses the same form.
- `note_attempt` counts the review runs of an item from the traces of the row `review`, so the result line counts an extended round with no change.

## Existing Tool Considered

No open tool decides the repair rounds of a plan. The change follows the form of `roadmap.stage.gate_returns` and reuses the drain guard of #4925 and the log module of #4535. It costs about 300,000 tokens to build and test, about 2,000 tokens to keep, and about 3 hours elapsed. It deletes the constant `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS`.
