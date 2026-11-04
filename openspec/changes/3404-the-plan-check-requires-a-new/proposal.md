# Proposal

## Why

A plan that adds a rule over plan text can write text that its own rule refuses. The plan of PR #3349 held a sentence naming a finding with a `kind` outside `DefectType`, so a later staging would return a problem for the rule it adds. The stage checks read the plan and the rule in one place, and they never run the proposed rule on the plan. #3386 makes the conflict certain: a plan that adds a gate must quote the defect that the gate refuses, so the plan holds the text that a prose rule refuses.

## What Changes

- `content_problems` refuses a plan that changes `src/devops_cli/roadmap/stage_change.py` in a behavior group and gives no group test that names `StageProposal`, `content_problems` and no problem.
- The new problem message lives beside the other text problems of the roadmap stage messages.
- A test of the stage content covers a plan without the self-acceptance test and a plan with it.
- The staging prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` states the self-acceptance test rule beside the other checks of a plan.
- A test loads the prompt and asserts that it names the rule and both symbols.
- The change carries a spec delta on `roadmap-stage`, because the stage gate and its prompt are behavior that a consumer observes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A plan that adds a text rule carries its self-acceptance test, A plan that changes no plan check needs no self-acceptance test, The staging prompt states the self-acceptance test rule

## Impact

- Code: `src/devops_cli/roadmap/stage_change.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/test_roadmap_stage_content.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`, `tests/roadmap/test_roadmap_stage_plan.py`

## Feasibility

- The probe shows: The path `src/devops_cli/roadmap/stage_change.py` is a file of the staging commit.
- The probe shows: The path `tests/roadmap/test_roadmap_stage_plan.py` is a file of the staging commit.
- The probe shows: The path `src/devops_cli/ai/tasks/roadmap_stage_change.md` is a file of the staging commit.
- The source of `src/devops_cli/roadmap/stage_change.py` shows `content_problems` and `check_proposal`, which `stage.py` and `stage_eval_gates.py` already call, so one added rule reaches the job and the replay.
- The source of `tests/roadmap/test_roadmap_stage_content.py` shows tests that build a proposal with `make_stage_proposal` and call `content_problems` with no network, no cluster and no scanner.
- The first check is the failing test: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py`.
- The second check is the whole roadmap suite: `uv run devops ci test tests/roadmap`.
- The third check is the staged change itself: `uv run devops openspec check`.

## Existing Tool Considered

No open, maintained tool checks a plan against the rule that the plan adds; the stage check is the only place that reads both the rule and the plan text. The project builds the check itself: about 6,000 tokens to build, about 1,500 tokens to keep and fix, and about 4 hours elapsed.
