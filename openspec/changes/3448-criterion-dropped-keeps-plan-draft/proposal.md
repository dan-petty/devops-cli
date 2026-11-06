# Proposal

## Why

The model review of a plan can report that an acceptance criterion of the issue is not delivered, with the finding type `criterion_dropped`. That type is advice: `OPEN_TYPES` in `src/devops_cli/roadmap/stage_verify.py` holds the return types and `spec_delta_wrong`, so the finding does not keep the plan in draft. A later round can then stage the plan as clean, and the criterion stays unmet (#3448).

The first example of the issue does not hold. The merged plan of #3410 is correct: the group that adds the case of a move of the stage modules changes only fixture files and a test file, and it delivers its criterion, because an earlier group adds the field `CaseFacts.search_evidence` that the case needs. A rule that flags every group that changes only test files would refuse that plan. So the rule is narrow. A `criterion_dropped` finding with a quote that is in the input keeps the plan in draft, and the prompt tells the model that a test-only group delivers its criterion when an earlier group changes the code that the criterion needs.

## What Changes

- The change fits one pull request.
- Add `criterion_dropped` to `OPEN_TYPES` in `src/devops_cli/roadmap/stage_verify.py`. The existing rule stays: a finding with no quote that is in the input is advice, and the finding does not return the plan to the planner.
- Keep a `criterion_dropped` finding as advice in the review of refine (`JUDGE_OPEN_TYPES` in `src/devops_cli/roadmap/refine_judge.py`), because a proposal of refine holds no task group. The review of refine keeps its open types.
- Define in `src/devops_cli/ai/tasks/roadmap_stage_verify.md` the criterion whose group changes only test files while no group changes the code that it needs, and say that a test-only group which tests code of an earlier group is no `criterion_dropped`.
- List `criterion_dropped` as an open finding type in `docs/roadmap/stage.md` and in the module text of `src/devops_cli/roadmap/stage.py`.
- Add two cases to the stage eval golden set: the merged plan of #3410, which stays good, and the same plan without the group that adds the field of the case, which stays bad with one `criterion_dropped` defect and the gate `none`.
- Remove the count of the good plans and the count of the cases from `docs/ROADMAP_WORKFLOW.md`, and read the words and not the number in the test of that document, so that a new case changes no sentence.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A dropped criterion finding keeps the plan in draft, The verification prompt separates a dropped criterion from a test-only group that delivers its criterion
- `roadmap-stage-eval`: The golden set holds a test-only group that delivers its criterion and the same plan without the code, The workflow document defines an acceptable stage score and the baseline

## Impact

- Code: `src/devops_cli/roadmap/stage_verify.py`, `src/devops_cli/roadmap/refine_judge.py`, `src/devops_cli/roadmap/stage.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, `docs/roadmap/stage.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/test_roadmap_stage_verify.py`, `tests/roadmap/test_roadmap_refine_trust.py`, `tests/roadmap/test_roadmap_stage_criterion_dropped.py`, `tests/roadmap/test_roadmap_stage_eval_cases.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`, `tests/roadmap/test_roadmap_stage_eval_command.py`, `tests/invariants/test_roadmap_stage_measure_doc.py`, and the cases `tests/fixtures/roadmap_eval/stage/3410-the-eval-field-group-is-dropped/` and `tests/fixtures/roadmap_eval/stage/good-3410-the-stage-gate-proves-a-negative/`

## Feasibility

- Command output: `OPEN_TYPES` in `src/devops_cli/roadmap/stage_verify.py` is `RETURN_TYPES | {DefectType.SPEC_DELTA_WRONG}` before the change, and the test of `OPEN_TYPES` asserted it. So the gap of the issue is real.
- Library source: `CaseFacts.search_evidence` exists in `src/devops_cli/roadmap/stage_eval_cases.py`, and group 3 of the merged plan of #3410 adds it. Group 4 of that plan changes only fixture files and a test file and delivers its criterion. So the example of the issue does not hold, and the change uses a narrow rule and a pair of cases in place of a rule on test-only groups.
- Command output: `uv run devops roadmap eval verify` on the good case and on the dropped case with the model `qwen3.8:27b` of the gateway, on the single-call pass that ran before #3039, once with the prompt before the change and once after it. Both runs gave the same findings: a `missing_path` finding on each case and no `criterion_dropped` finding on the good case. So the narrow rule did not refuse the good plan in that run. The `missing_path` finding on the good case comes from the count of cases in `tests/roadmap/test_roadmap_stage_eval_cases.py`, and the run before the change gave it too.
- Command output: the same command on the agent pass of #3039 gave no findings. Three runs ended with `Tool <text> exceeded max retries count of 2`, two on the good case and one on `good-2739-the-subprocess-environment-guard-accepts-gh`, so the cause is not these cases. #3717 holds the fault. The score of the agent pass before and after the change is not run.

## Existing Tool Considered

No open tool judges whether a task group delivers an acceptance criterion. The criteria gate of #3019 (`src/devops_cli/roadmap/stage_criteria.py`) maps each criterion to a group and does not judge the group, and pydantic-evals, which scores the pass, judges the model and not the plan. The change adds one member to an existing set, one paragraph to an existing prompt and two data cases. It costs about 60,000 tokens to build and test, about 2,000 tokens to keep, and about 3 hours elapsed. It deletes no internal code.

## Dependencies

None.
