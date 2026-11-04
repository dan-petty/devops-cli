# Proposal

## Why

The stage proposal check reads paths, spec deltas, criteria and form, but no model field. In #3264 the first reply of the planner read `PullStatus.labels` before `PullStatus` defined `labels`, and the reply left `src/devops_cli/github/client.py` out of its `changes`. The verification pass found the gap. #3399 later added `labels` to `PullStatus`, so the cited class passes today. No deterministic gate checks a model field, so the same gap in another class or field still passes (#3344).

## What Changes

- Add `src/devops_cli/roadmap/stage_models.py` with `referenced_classes`, which collects the dotted references of a plan, and `model_fields`, which reads the named classes at the staged commit with `git grep`, `git show` and `ast`.
- Give `check_proposal` a keyword-only `models` map. It refuses a reference to a field that the named Pydantic model lacks, and it names the reference and the module of the model.
- A plan that reads a missing field passes when a group lists the module of the model in `changes`, and the problem goes back to the model once, as every other problem of `check_proposal` does.
- The stage job reads the map from the checkout at the staged commit and passes it to `check_proposal`. The replay reads no git, so the golden case records the model fields in its facts.
- `tests/roadmap/test_roadmap_stage_models.py` and `tests/roadmap/test_roadmap_stage_plan.py` hold the reader tests, the refused plan, the accepted plan, and the second reply that stops the item.
- The golden set holds a case whose plan reads `PullStatus.labels` and leaves `src/devops_cli/github/client.py` out of `changes`.
- The spec delta of `roadmap-stage` adds the requirements of the attribute check and of the model module in `changes`.
- `docs/ROADMAP_WORKFLOW.md` states the new rule of the `paths` gate.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A read of a model attribute that the model lacks is refused, The module of a model that a plan extends is in changes

## Impact

- Code: `src/devops_cli/roadmap/stage_models.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/test_roadmap_stage_models.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`, `tests/fixtures/roadmap_eval/stage/3344-a-plan-that-reads-an-absent-field/`

## Feasibility

- The probes confirm the cited paths: "The path `src/devops_cli/github/client.py` is a file of the staging commit." and "The path `tests/roadmap/test_roadmap_stage_plan.py` is a file of the staging commit." The probe of the attribute reads: "The path `PullStatus.labels` is no file of the staging commit. No commit in the history deleted or renamed it."
- The source of the staged commit holds the model text, not `StagedTree`. `StagedTree.read` runs `git ls-files` and keeps paths only (`src/devops_cli/roadmap/stage_paths.py:79`). `src/devops_cli/roadmap/implement_hooks.py:110` reads a file of a commit with `git(source, "show", f"{ref}:{name}")`, so the new reader uses the same call.
- `src/devops_cli/roadmap/stage.py:811` calls `check_proposal` with the tree, and `src/devops_cli/roadmap/stage_eval_gates.py:157` calls it with a recorded tree. A new keyword-only `models` argument keeps the replay working when it has no model map.
- `PullStatus` in the staged tree defines `labels` now: commit `499a5462` (#3399) added it. The test and the golden case record a `PullStatus` without `labels`, so the check is tested against the defective text `PullStatus.labels` and the current class passes.
- The replay reads no git (`docs/ROADMAP_WORKFLOW.md:254`). The golden case records the model fields in `facts.json`, and the replay passes them to `check_proposal`.
- The first checks of the implementation against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_models.py`, then `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py`, then `uv run devops roadmap eval stage --replay`.

## Existing Tool Considered

No open, maintained tool covers this check. It reads the Python source of the staged commit, which is specific to this repository's `check_proposal` gate. The standard library `ast` module parses the source, and the existing `git` helper reads it, so the change adds no dependency. Building it in devops-cli costs about 15,000 output tokens for the first version and its tests, about 2,000 tokens for each later fix, and about 3 hours elapsed.
