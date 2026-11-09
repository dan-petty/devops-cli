# Tasks

## 1. Record the reference hits in the case and the replay

Reads: `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `src/devops_cli/roadmap/stage/stage_change.py`. Changes: `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `tests/fixtures/roadmap_eval/stage/3412-a-move-plan-leaves-a-test-reference/`, `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_command.py`.

- [x] 1.1 Add failing tests: `test_a_case_reads_its_reference_hits_and_an_old_case_holds_none` in `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, and `test_the_plan_under_test_holds_the_reference_hits_of_its_case` and `test_the_paths_gate_refuses_a_move_plan_that_leaves_a_reference_hit` in `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_cases.py tests/roadmap/stage/test_roadmap_stage_eval_gates.py` fails on the missing `references` field
- [x] 1.2 Add `references: tuple[str, ...] = ()` to `CaseFacts` in `src/devops_cli/roadmap/stage/stage_eval_cases.py`, and state the key in the docstrings of `CaseFacts` and the module.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_cases.py` passes
- [x] 1.3 Add `references: Sequence[str]` with an empty default to `PlanUnderTest` in `src/devops_cli/roadmap/stage/stage_eval_gates.py`, set it from `case.facts.references` in `of_case`, and pass `references=plan.references` in `_path_gate`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py` passes
- [x] 1.4 Add the case `tests/fixtures/roadmap_eval/stage/3412-a-move-plan-leaves-a-test-reference/` with a plan that moves a module, a `facts.json` that records the two test files that hold the old dotted name, and one `missing_path` defect with the gate `paths`.
  - Verification: `$ uv run devops roadmap eval stage --replay` exits 0 and marks the defect caught

## 2. Raise the pinned counts

Reads: `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_command.py`. Changes: `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_command.py`.

- [x] 2.1 Add 3412 to `EVALUATED_PULLS`, raise the case count to 56 and the reviewed count to 51 in `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_cases.py` passes
- [x] 2.2 Raise `JUDGED_BASELINE` to `(81, 317)` and the `missing_path` count to `(37, 0, 0)` in `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py` passes
- [x] 2.3 Raise the replay counts to `56 case(s), 5 good`, `81 of 317 (26%)` and `{"judged": 81, "known": 317}` in `tests/roadmap/stage/test_roadmap_stage_eval_command.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_command.py` passes

## 3. Documents and archive

Reads: `openspec/changes/3412-record-the-reference-hits-of-a/`. Changes: `openspec/changes/archive/`.

- [x] 3.1 Run `uv run devops openspec archive 3412-record-the-reference-hits-of-a` and commit the archive with the change.
  - Verification: `$ uv run devops openspec check` passes
