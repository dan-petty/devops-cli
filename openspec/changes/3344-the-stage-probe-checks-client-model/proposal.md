# Proposal

## Why

The stage job plans a change without checking that a client model it reads already has the field the plan reads. In #3264 the plan read `PullStatus.labels`, and `PullStatus` in `src/devops_cli/github/client.py` defines `state`, `draft`, `merged`, `head_sha` and `head_ref` only. The plan also left that module out of its groups, so the implementation step would have read a field that does not exist (#3344).

## What Changes

- `check_proposal` reads every Pydantic model class under `src/` of the staged commit with `ast`, and records the annotated field names of each class.
- `check_proposal` collects the dotted references in the text of the groups, the spec deltas and the design, such as `PullStatus.labels`.
- A reference whose class is a Pydantic model of the staged tree and whose attribute is no field of that class becomes a problem that names the reference and the module of the model.
- A plan that reads a missing attribute passes when a group lists the module of the model in `changes`, and the problem goes back to the model once, as every other problem of `check_proposal` does.
- `tests/roadmap/test_roadmap_stage_plan.py` holds the refused plan, the accepted plan, and the second reply that stops the item.
- The spec delta of `roadmap-stage` adds the requirements of the attribute check and of the model module in `changes`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A read of a model attribute that the model lacks is refused, The module of a model that a plan extends is in changes

## Impact

- Code: `src/devops_cli/roadmap/stage_models.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`
- Documents: `openspec/changes/3344-stage-model-attribute-check/specs/roadmap-stage/spec.md`, `openspec/changes/3344-stage-model-attribute-check/tasks.md`
- Tests: `tests/roadmap/test_roadmap_stage_models.py`, `tests/roadmap/test_roadmap_stage_plan.py`

## Feasibility

- The probes confirm the cited paths: "The path `src/devops_cli/github/client.py` is a file of the staging commit." and "The path `tests/roadmap/test_roadmap_stage_plan.py` is a file of the staging commit." The probe of the attribute reads: "The path `PullStatus.labels` is no file of the staging commit. No commit in the history deleted or renamed it."
- The context shows `class PullStatus(BaseModel)` in `src/devops_cli/github/client.py` with `state`, `draft`, `merged`, `head_sha` and `head_ref`, and no `labels`. The field that #3264 read is still absent, so the gap is real.
- The context shows `src/devops_cli/roadmap/stage_change.py` importing `StagedTree` and `path_problems` from `devops_cli.roadmap.stage_paths`, and the tests call `check_proposal(make_stage_proposal(), [], SAMPLE_TREE, requirements=base)`: the check takes the tree of the staged commit and returns a list of problem texts.
- The context shows that `check_proposal` judges paths, spec deltas, the criteria and the form, and reads no model definition, so no gate catches a missing attribute today.
- The first checks of the implementation against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py`, then `uv run devops openspec check` on the change folder, then `uv run devops roadmap stage --dry-run` on an item whose plan reads a missing attribute.

## Existing Tool Considered

No open, maintained tool covers this check. It reads the Python source of the staged commit, which is specific to this repository's `check_proposal` gate and its `StagedTree`. The standard library `ast` module parses the source, and it is no separate dependency. Building it in devops-cli costs about 15,000 output tokens for the first version and its tests, about 2,000 tokens for each later fix, and about 3 hours elapsed.
