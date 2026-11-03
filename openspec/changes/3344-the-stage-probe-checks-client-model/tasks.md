# Tasks

## 1. Read the models of the staged tree

Reads: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/github/client.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_models.py` (new), `tests/roadmap/test_roadmap_stage_models.py` (new).

- [ ] 1.1 Write `tests/roadmap/test_roadmap_stage_models.py` first: a tree that holds a class of `pydantic.BaseModel` with the fields `state` and `head_sha` gives a map from the class name to its module and its field names; a class that inherits no `BaseModel` is left out; a file that `ast` cannot parse gives no class and fails no other file
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_models.py` fails on the base
- [ ] 1.2 Add `src/devops_cli/roadmap/stage_models.py` with `model_fields(tree)`, which parses each `.py` file of the `StagedTree` with `ast`, keeps each class that subclasses `BaseModel` or another class of the same tree, and returns its module path and its annotated field names. Read a file that raises `SyntaxError` as a file with no model, so a tree with one broken file still gives the other models
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_models.py` passes

## 2. Refuse a missing model attribute

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_models.py`, `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 2.1 Add to `tests/roadmap/test_roadmap_stage_plan.py` three tests of `check_proposal` against a tree whose `src/devops_cli/github/client.py` defines `state` and no `labels`: a group that names `PullStatus.labels` returns one problem that names `PullStatus.labels` and `src/devops_cli/github/client.py`; the same plan with that module in `changes` returns no problem; a group that names `PullStatus.state` returns no problem. Add a plan run whose first reply keeps the gap and whose second reply is the sample proposal, and a run whose two replies keep the gap and end with `RoadmapStageError` and no ready change
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 2.2 In `check_proposal`, build the model map from the `StagedTree` and collect each dotted reference of the group texts, the spec delta texts and the design texts. For a reference whose first part is a model class of the tree, compare the second part with the field names. Return a problem that names the reference and the module when the field is missing, and add the module to a group's `changes` when no group lists it. Keep the existing order of the problems. In `stage.py`, pass the problem to the one retry as every other problem of `check_proposal` goes
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 3. Add the spec delta of the attribute check

Reads: `openspec/specs/roadmap-stage/spec.md`. Changes: `openspec/changes/3344-stage-model-attribute-check/specs/roadmap-stage/spec.md` (new), `openspec/changes/3344-stage-model-attribute-check/tasks.md` (new).

- [ ] 3.1 Write the two added requirements of the plan into the spec delta of `roadmap-stage`, with their scenarios, and list the groups of this change in `tasks.md`
  - Verification: `uv run devops openspec check` passes
- [ ] 3.2 openspec/changes/3344-stage-model-attribute-check/tasks.md, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## Criteria

- Group 2: A test asserts that when a plan relies on reading a new field from a client model, the plan includes updating that model in its task groups.
- Group 2: Plans with complete model updates pass validation.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
