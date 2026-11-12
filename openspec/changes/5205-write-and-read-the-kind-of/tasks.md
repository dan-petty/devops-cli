# Tasks

## 1. Write and read the kind of each task group

Kind: behavior. Reads: `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_plan_read.py`.

- [ ] 1.1 Write `test_each_group_kind_reads_back`, `test_explicit_kind_line_sets_the_kind`, `test_a_word_that_is_no_kind_reads_as_the_old_form`, `test_unchanged_references_read_back`, `test_a_changed_reference_is_no_fact_of_the_files`, `test_the_fields_that_no_file_holds`, `test_each_golden_plan_reads_back`, `test_a_plan_head_reads_with_its_kinds` and the Hypothesis properties `test_no_fact_is_lost` and `test_a_read_plan_is_a_fixed_point` in `tests/roadmap/test_roadmap_plan_read.py`, with the change folders of #4963, #5032 and #5182 at their heads in `tests/fixtures/roadmap/plan_heads/`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_read.py` fails on the base
- [ ] 1.2 Write `Kind: <kind>.` on the files line of `group_text`, read it in `plan_read._kind` with a `manifest` branch in `_group`, infer the kind of a group with no such line or with a word that is no kind from its tasks and `changes_source`, read `## Unchanged references`, drop only the last line that the writer adds to `## What Changes`, and add `FIELDS_NOT_IN_FILES` and `file_facts`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_read.py` passes

## 2. Hold the rendered files line in the tests and the golden set

Kind: other. Reads: `tests/roadmap/stage/__snapshots__/test_roadmap_stage_plan.ambr`, `tests/fixtures/roadmap_eval/stage/3173-a-plan-for-an-alert-rule/plan.json`. Changes: `tests/roadmap/stage/__snapshots__/test_roadmap_stage_plan.ambr`, `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_command.py`, `tests/commands/test_roadmap_eval_screen.py`, `tests/fixtures/roadmap_eval/stage/good-2950-the-alert-case-is-a-manifest-group/case.json` (new), `tests/fixtures/roadmap_eval/stage/good-2950-the-alert-case-is-a-manifest-group/plan.json` (new).

- [ ] 2.1 Update the snapshots and the tests that hold a rendered files line for the `Kind:` line, and add the `manifest` case `good-2950-the-alert-case-is-a-manifest-group` to `tests/fixtures/roadmap_eval/stage/` with the counts of the set
  - Verification: `$ uv run devops ci test tests/roadmap/stage tests/roadmap/implement/test_roadmap_implement_resplit.py` passes

## 3. Document the kinds and the reader

Kind: other. Reads: `docs/TESTING.md`, `docs/roadmap/plan-check.md`, `k8s/README.md`. Changes: `docs/TESTING.md`, `docs/roadmap/plan-check.md`, `k8s/README.md`.

- [ ] 3.1 Name the kind `manifest` and the `Kind:` line in `docs/TESTING.md`, `docs/roadmap/plan-check.md` and item 15 of `k8s/README.md`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: `test_each_group_kind_reads_back` passes for `behavior`, `manifest` and `other`.
- Group 1: `test_no_fact_is_lost` and `test_a_read_plan_is_a_fixed_point` hold for each generated valid proposal.
- Group 1: `test_a_plan_head_reads_with_its_kinds` reads the heads of #4963, #5032 and #5182 with no `PlanReadError`.
- Group 2: `uv run devops ci test tests/roadmap/stage tests/roadmap/implement/test_roadmap_implement_resplit.py` passes.
- Group 3: `uv run devops docs check` passes.
- Pending person: A table in a comment of the pull request gives the read of each plan pull request head of the Service on the base and on the branch, A person reads the table before the merge.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
