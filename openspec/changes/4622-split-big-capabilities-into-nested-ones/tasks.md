# Tasks

## 1. Split the four big capabilities into nested ones

Kind: other. Reads: `openspec/specs/roadmap-stage/spec.md`, `openspec/specs/roadmap-implement-job/spec.md`, `openspec/specs/roadmap-implement-step/spec.md`, `openspec/specs/roadmap-refine/spec.md`. Changes: the nested capabilities under those four areas, the deltas and the texts of the 13 open change folders that name them, `tests/roadmap/implement/test_roadmap_implement_record_readers.py` and `tests/invariants/test_living_specs.py`.

- [x] 1.1 Add `tests/invariants/test_living_specs.py`, which refuses a capability of more than 80 requirements and an area of nested capabilities that holds a `spec.md` of its own
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Move each requirement of the four capabilities word for word into the nested capability of its gate or module, give each nested capability a Purpose, and delete the four old files
  - Verification: `$ uv run devops ci test tests/invariants/test_living_specs.py`
- [x] 1.3 Move the delta of each open change folder that names a split capability to the nested capability that holds its requirements, name the new ids in its texts, and read the record keys of `test_roadmap_implement_record_readers.py` from the nested specs
  - Verification: `$ uv run devops openspec check`

## 2. Read nested capabilities

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_specs.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/refine/refine.py`. Changes: `src/devops_cli/roadmap/stage/stage_specs.py`, `src/devops_cli/roadmap/stage/stage_tools.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_eval_run.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_validate.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/lang/en/messages.py` and their tests.

- [x] 2.1 Add the failing tests `test_the_base_specs_are_the_capabilities_that_openspec_lists`, `test_with_no_openspec_the_job_knows_no_base_spec`, `test_a_delta_names_a_flat_or_a_nested_capability`, `test_the_validation_sees_the_base_spec_of_a_flat_or_a_nested_capability`, `test_read_spec_reads_a_nested_capability`, `test_a_change_with_a_nested_capability_reads_back`, `test_the_base_specs_at_a_commit_hold_a_nested_capability` and `test_the_context_names_the_requirements_of_a_nested_capability`
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 2.2 Read the base capabilities from `openspec list --specs --json` and delete the flat folder walk, accept a nested capability in a reply and in `read_spec`, copy the base spec of a nested capability for the validation, and read a spec at any depth in `specs_at`, `read_change` and the refine context
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_specs.py tests/roadmap/stage/test_roadmap_stage_tools.py tests/roadmap/stage/test_roadmap_stage_plan.py tests/roadmap/test_roadmap_plan_read.py tests/roadmap/refine/test_roadmap_refine_context.py`

## 3. State the rule and link the nested capabilities

Kind: documents. Reads: `openspec/config.yaml`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`. Changes: `openspec/config.yaml`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `docs/roadmap/stage.md`, `docs/roadmap/implement.md` and `docs/roadmap/refine.md`.

- [x] 3.1 Add the limit of 80 requirements and the nested layout to the spec rules of `openspec/config.yaml`, name the form of a nested capability in the stage prompt, and link the roadmap documents to the nested capabilities
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- #4667: one week after the merge, post on #4622 the number of conflicting base updates that touch `openspec/specs/`, with the census method of 2026-11-11, against 97 in the week before.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
