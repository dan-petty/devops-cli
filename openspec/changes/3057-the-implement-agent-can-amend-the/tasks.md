# Tasks

## 1. Classify a plan defect

Reads: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/stage.py`. Changes: `src/devops_cli/roadmap/implement_amend.py` (new), `tests/roadmap/test_roadmap_implement_amend.py` (new).

- [ ] 1.1 tests/roadmap/test_roadmap_implement_amend.py, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_amend.py` fails on the base
- [ ] 1.2 Add `Amendment` with the defect, the evidence and the corrected text, and `classify_defect` that returns a bounded amendment, a premise failure or a scope change. Add `apply_amendment` that rewrites the group text of `tasks.md` and appends an entry to its `## Amendments` section. Write the failing test first, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_amend.py` passes

## 2. Raise the amendment from a step

Reads: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_amend.py`, `src/devops_cli/roadmap/implement_submit.py`. Changes: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_submit.py`, `tests/roadmap/test_roadmap_implement_step.py`.

- [ ] 2.1 tests/roadmap/test_roadmap_implement_step.py, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py` fails on the base
- [ ] 2.2 Let a step raise an amendment from its turn, apply it to the change folder before the exit checks, and record it in `StepOutcome`. Post the amendment and its evidence as one comment on the pull request from the job's submit path, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py` passes

## 3. Return the item on a false premise

Reads: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/return_item.py`, `src/devops_cli/roadmap/implement_amend.py`. Changes: `src/devops_cli/roadmap/implement_step.py`, `tests/roadmap/test_roadmap_implement_step.py`.

- [ ] 3.1 tests/roadmap/test_roadmap_implement_step.py, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py` fails on the base
- [ ] 3.2 Return the item to New with the evidence through `return_item` when the classification is a premise failure, and post a question on the issue and apply nothing when it is a scope change. Commit no code in either case, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py` passes

## 4. Re-split a group over its budget

Reads: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_validate.py`. Changes: `src/devops_cli/roadmap/implement_step.py`, `tests/roadmap/test_roadmap_implement_step.py`.

- [ ] 4.1 tests/roadmap/test_roadmap_implement_step.py, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py` fails on the base
- [ ] 4.2 Send a group whose inputs exceed the budget through `_Planner._fit` of `stage.py` instead of refusing the step, write the new groups into `tasks.md`, and let the job run them. Record the re-split as an amendment, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py` passes

## 5. Record the amendment behavior in the spec

Reads: `openspec/specs/roadmap-implement-step/spec.md`. Changes: `openspec/changes/3057-plan-amendment/specs/roadmap-implement-step/spec.md` (new), `openspec/changes/3057-plan-amendment/tasks.md` (new).

- [ ] 5.1 Write the spec delta of the bounded amendment, the tasks.md record, the pull request comment, the premise return, the scope boundary and the re-split into the change folder, and tick the tasks of the earlier groups, and verify that `openspec validate --strict` passes
- [ ] 5.2 openspec/changes/3057-plan-amendment/specs/roadmap-implement-step/spec.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
