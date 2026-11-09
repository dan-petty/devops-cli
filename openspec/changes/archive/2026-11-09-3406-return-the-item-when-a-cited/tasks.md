# Tasks

## 1. Probe a cited class field

Reads: `src/devops_cli/roadmap/stage/stage_probe.py`,
`src/devops_cli/roadmap/stage/stage_models.py`, `tests/roadmap/stage/test_roadmap_stage_probe.py`.
Changes: `src/devops_cli/roadmap/stage/stage_models.py`,
`src/devops_cli/roadmap/stage/stage_probe.py`, `src/devops_cli/lang/en/messages.py`,
`tests/roadmap/stage/test_roadmap_stage_probe.py`.

- [x] 1.1 Write the failing tests of `tests/roadmap/stage/test_roadmap_stage_probe.py` first: a
      class that defines the cited field gives a line with its file and line and no missing entry;
      a class without the field gives the absence line and the reference is in `missing`; a cited
      `Class.field` writes no path line; a body that says the field is absent gives the probe line
      in `false_premises`; the field probe counts each command and leaves `git status --porcelain`
      empty
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_probe.py`
- [x] 1.2 Add `parse_class_fields` to `src/devops_cli/roadmap/stage/stage_models.py` and the field
      reference, absence phrase and field probe to
      `src/devops_cli/roadmap/stage/stage_probe.py`. Add the probe texts to `MESSAGES.roadmap`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_probe.py`

## 2. Return the item on a false absence

Reads: `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_job.py`.
Changes: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/lang/en/messages.py`,
`tests/roadmap/stage/test_roadmap_stage_job.py`.

- [x] 2.1 Write the failing test of `tests/roadmap/stage/test_roadmap_stage_job.py` first: an item
      whose body says that a class defines no field which the staging commit defines goes back to
      New with no model call, `refine.next_step` `edit`, and a comment that quotes the probe line
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_job.py`
- [x] 2.2 Add the `FalsePremise` outcome, the probe check in `_Planner`, the write of
      `_return_premise`, and the render line of the returned item. Add the texts to
      `MESSAGES.roadmap`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_job.py`

## 3. Documents

Reads: `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [x] 3.1 State in `docs/ROADMAP_WORKFLOW.md` that the probe reads a cited class field, and that a
      body that says a field is absent while the commit defines it returns the item to New with
      `refine.next_step` set to `edit`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
