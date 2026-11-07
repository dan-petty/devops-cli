# Tasks

## 1. Read the fields of a named model

Reads: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/implement_hooks.py`, `src/devops_cli/github/client.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_models.py` (new), `tests/roadmap/test_roadmap_stage_models.py` (new).

- [ ] 1.1 Write `tests/roadmap/test_roadmap_stage_models.py` first: `referenced_classes` returns `PullStatus` for texts that hold `PullStatus.labels` and no name for a plain word; `model_fields` on a commit whose `src/devops_cli/github/client.py` defines `PullStatus` with `state` and `head_sha` gives the module and those field names; a class that inherits no `BaseModel` is left out; a module that `ast` cannot parse gives no class and fails no other class
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_models.py` fails on the base
- [ ] 1.2 Add `src/devops_cli/roadmap/stage_models.py`. `referenced_classes(texts)` returns the first part of each dotted reference. `model_fields(source, sha, names)` runs `git grep -n "^class <name>("` at `sha` under `src/`, reads each match with `git show`, parses it with `ast`, keeps each class that subclasses `BaseModel` or a class of the same module, and returns the module path and the annotated field names of each named class. Read a module that raises `SyntaxError` as a module with no model
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_models.py` passes

## 2. Refuse a missing model attribute

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_models.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 2.1 Add to `tests/roadmap/test_roadmap_stage_plan.py` tests of `check_proposal` with a `models` map whose `PullStatus` defines `state` and no `labels`: a group that names `PullStatus.labels` returns one problem that names `PullStatus.labels` and `src/devops_cli/github/client.py`; the same plan with that module in `changes` returns no problem; a group that names `PullStatus.state` returns no problem; a call with no `models` returns no problem. Add a plan run whose first reply keeps the gap and whose second reply is the sample proposal, and a run whose two replies keep the gap and end with `RoadmapStageError` and no ready change
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 2.2 In `check_proposal`, add the keyword-only `models` argument and collect each dotted reference of the group texts, the spec delta texts, the decisions and the rejected alternatives. For a reference whose class is in the map, compare the second part with the field names. Return a problem that names the reference and the module when the field is missing, and ask for the module in a group's `changes` when no group lists it. Keep the existing order of the problems. Add the problem texts to `MESSAGES.roadmap`. In `StageSession._settle`, call `referenced_classes`, read the map once, and pass it
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 3. Replay the missing-field defect

Reads: `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`, `docs/ROADMAP_WORKFLOW.md`. Changes: `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`, `tests/fixtures/roadmap_eval/stage/3344-a-plan-that-reads-an-absent-field/` (new).

- [ ] 3.1 Add `models` to `CaseFacts`, pass it through `PlanUnderTest.of_case` and `_path_gate`, and add the case folder for the #3264 example: its issue text, a plan with a group that reads `PullStatus.labels` and leaves `src/devops_cli/github/client.py` out of `changes`, a `facts.json` that records `PullStatus` with `state` and no `labels`, and a `missing_path` defect with the gate `paths`, the path of the module and the message of the problem. Extend the replay test so the report lists the case and catches its defect
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` fails on the base
- [ ] 3.2 State the new rule at the `paths` gate in `docs/ROADMAP_WORKFLOW.md`: the gate refuses a read of a missing field of a named Pydantic model and names the module. Then run `uv run devops roadmap eval stage --replay` and state the counts of the `paths` gate before and after the change
  - Verification: `$ uv run devops ci docs` passes and `$ uv run devops roadmap eval stage --replay` lists the new case as caught

## Criteria

- Group 2: A test asserts that when a plan relies on reading a new field from a client model, the plan includes updating that model in its task groups.
- Group 2: Plans with complete model updates pass validation.

## Workflow follow-up

- Pending a person: run `uv run devops roadmap eval stage --model <model>` on the base and on the branch, and state both scores and the model.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
