# Tasks

## 1. Add the manifest kind to the schema and its render

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_kind.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_kind.py`, `tests/roadmap/stage/test_roadmap_stage_manifest.py` (new).

- [x] 1.1 Write `test_a_manifest_group_renders_its_case_first_and_then_its_work` in `tests/roadmap/stage/test_roadmap_stage_manifest.py`, which fails on the base because `GroupKind` holds no `manifest`, and `test_the_plan_check_accepts_the_plan_of_this_change`, which builds the plan's own `StageProposal` and asserts that `content_problems` returns no problem for it
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_manifest.py` fails on the base
- [x] 1.2 Add `MANIFEST = "manifest"` to `GroupKind` in `src/devops_cli/roadmap/stage/stage_change.py`, and add `_manifest_problems` with its line in `_kind_rules`. Render a manifest group with `stage_task_test` first in `_task_texts`, and add `manifest` to the kind test of `_task_work_texts`. Add the message texts to `MESSAGES.roadmap` in `src/devops_cli/lang/en/messages.py`. Change the pinned schema message in `tests/roadmap/stage/test_roadmap_stage_kind.py` to the three kinds, and add the schema, render and self-acceptance tests to `tests/roadmap/stage/test_roadmap_stage_manifest.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_manifest.py` passes

## 2. Refuse an other group that changes a case path

Reads: `src/devops_cli/roadmap/stage/stage_form.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_form.py`. Changes: `src/devops_cli/roadmap/stage/stage_form.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_form.py`.

- [x] 2.1 Add `test_an_other_group_that_changes_a_case_path_is_refused_with_the_manifest_kind` to `tests/roadmap/stage/test_roadmap_stage_form.py`, which fails on the base because `form_problems` returns no problem for a group that changes `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_form.py` fails on the base
- [x] 2.2 Add `_CASE_SUFFIXES` and `_is_case_path` to `src/devops_cli/roadmap/stage/stage_form.py`. Add to `form_problems` one problem for each `other` group whose `changes` or `creates` hold a case path, which names the path, `other` and `manifest`, with its text in `MESSAGES.roadmap`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_form.py` passes

## 3. Refuse a manifest verify that runs no case

Reads: `src/devops_cli/roadmap/stage/stage_form.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_form.py`. Changes: `src/devops_cli/roadmap/stage/stage_form.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_form.py`.

- [x] 3.1 Add `test_a_manifest_verify_that_is_not_a_case_of_the_group_is_refused` and `test_a_manifest_verify_that_runs_a_path_of_the_group_is_accepted` to `tests/roadmap/stage/test_roadmap_stage_form.py`, which fail on the base because the check holds no manifest rule
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_form.py` fails on the base
- [x] 3.2 Add `_manifest_verify_problems` to `src/devops_cli/roadmap/stage/stage_form.py` and its line in `form_problems`: a manifest `verify` is `uv run devops ci test` followed by one path of the group or its folder. The problem names the command and the form to use, with its text in `MESSAGES.roadmap`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_form.py` passes

## 4. Name the manifest kind in the planner prompts

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [x] 4.1 Name the kind `manifest`, its case-first rule and its verify rule in `src/devops_cli/ai/tasks/roadmap_stage_change.md` and in `src/devops_cli/ai/tasks/roadmap_stage_split.md`. Read the kind names as a list in the kind test of `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, and add the assertion of the manifest rules
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes
- [x] 4.2 Edit `src/devops_cli/ai/tasks/roadmap_stage_change.md` and `src/devops_cli/ai/tasks/roadmap_stage_split.md` to name the kind `manifest` and its two rules
  - Verification: `$ uv run devops ci docs` passes

## 5. Replay the hand-written plan of #3173

Reads: `tests/fixtures/roadmap_eval/stage/3331-a-plan-that-changes-a-check/case.json`, `openspec/changes/archive/2026-11-06-2950-alternatives-coverage-gauge-searches-per-check/tasks.md`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`. Changes: `tests/fixtures/roadmap_eval/stage/3173-a-plan-for-an-alert-rule/case.json` (new), `tests/fixtures/roadmap_eval/stage/3173-a-plan-for-an-alert-rule/plan.json` (new), `tests/fixtures/roadmap_eval/stage/3173-a-plan-for-an-alert-rule/issue.txt` (new), `tests/fixtures/roadmap_eval/stage/3173-a-plan-for-an-alert-rule/facts.json` (new), `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`.

- [x] 5.1 Add the four files of the case `3173-a-plan-for-an-alert-rule` from the plan of #3173, which is the change folder `openspec/changes/archive/2026-11-06-2950-alternatives-coverage-gauge-searches-per-check/`: its group 5 changes `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml` with the kind `other`, and the defect has the type `task_order`, the gate `paths`, that path in `paths` and the message that names `manifest`. Give the plan the `creates_lines` of each created path, so the schema accepts it. Update the pinned counts of `tests/roadmap/stage/test_roadmap_stage_eval_gates.py` for the new caught defect, and run `uv run devops roadmap eval stage --replay` with the score before and after the change in this task
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py` passes

## Criteria

- Group 3: A test shows that a manifest group with the case first and a failing verify passes `form_problems`.
- Group 1: A test shows that a manifest group with the implementation first is refused.
- Group 4: The planner prompt names the kind, and the #3210 prompt-vs-rules test passes.
- Group 5: The golden set has one replay case from #3173 or #3171.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
