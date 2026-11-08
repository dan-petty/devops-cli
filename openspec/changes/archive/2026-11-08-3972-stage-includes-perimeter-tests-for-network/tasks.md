# Tasks

## 1. Record the tests that a changed manifest reaches

Reads: `src/devops_cli/roadmap/stage/stage_paths.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/support/roadmap_stage.py`. Changes: `src/devops_cli/roadmap/stage/stage_paths.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_paths.py`, write `test_the_record_names_the_test_that_builds_the_path_from_its_parts` first, with a temporary checkout that holds `k8s/logging/networkpolicy.yaml`, a test file named `test_logging_policy.py` whose text holds `logging` and `networkpolicy.yaml` in separate strings, and a test file named `test_logging_only.py` whose text holds `logging` alone; it asserts that `record_test_references` names the first test and not the second, that `missing_reference_problems` names the first test when the plan lists only the manifest, and that it gives no problem when the plan lists both
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_paths.py` fails on the base
- [x] 1.2 Add `record_test_references(groups, search)` to `src/devops_cli/roadmap/stage/stage_paths.py`: for each path in the `changes` of a group that ends in `.yaml` and starts with `k8s/`, it calls `search` once with the file name of the manifest, keeps the paths under `tests/` that hold that name, and keeps the ones that also hold the name of the manifest's folder, keyed by the manifest path. Add `missing_reference_problems(groups, references)`, which names each changed manifest and each test path of its record that no group lists in `changes`. Give `path_problems` the record as an optional argument and report those problems with it. Add the message `stage_problem_missing_perimeter_test` to `MESSAGES.roadmap` in `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_paths.py` passes

## 2. Refuse a manifest plan that omits its reference

Reads: `src/devops_cli/roadmap/stage/stage_paths.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/plan_recheck.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/support/builders.py`, `tests/roadmap/test_roadmap_plan_recheck.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/plan_recheck.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/test_roadmap_plan_recheck.py`.

- [x] 2.1 In `tests/roadmap/stage/test_roadmap_stage_paths.py`, write `test_a_manifest_plan_that_omits_its_test_is_refused` first: `check_gates` gives one `paths` problem for a group that changes `k8s/logging/networkpolicy.yaml` when the record names `tests/commands/k8s/test_k8s_logging_stack.py` and the plan lists only the manifest, and gives none once the group lists the test too
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_paths.py` fails on the base
- [x] 2.2 Add the keyword `manifest_references` to `check_gates` and `check_proposal` in `src/devops_cli/roadmap/stage/stage_change.py`, and pass it to the `paths` gate as the argument of `missing_reference_problems`. Pass the record in `_record` of `src/devops_cli/roadmap/plan_recheck.py`, recorded with `record_test_references` and a search that runs `git grep -l -F` over `tests` at `shared.rev` in `shared.source`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_paths.py` passes
- [x] 2.3 In `tests/roadmap/test_roadmap_plan_recheck.py`, cover `_test_search` caching and `recheck_plans` with a manifest plan: `test_test_search_finds_tests_and_caches_result` and `test_manifest_plan_omitting_perimeter_test_is_refused_by_paths_gate`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_recheck.py` passes

## 3. Record the references in the job and the replay

Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_request.py`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_request.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_request.py`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_request.py`, `tests/roadmap/stage/test_roadmap_stage_self_acceptance.py` (new).

- [x] 3.1 In `tests/roadmap/stage/test_roadmap_stage_self_acceptance.py`, write `test_this_plan_passes_the_content_gate` first: it builds the `StageProposal` of this plan with its four groups, calls `content_problems` and asserts that it gives no problem
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py` fails on the base
- [x] 3.2 Add the keyword `manifest_references` to `gate_arguments` in `src/devops_cli/roadmap/stage/stage_request.py`. Record the references in `_Planner._problems` of `src/devops_cli/roadmap/stage/stage.py` with `record_test_references` and the search that the job already runs, and pass the record to `gate_arguments`. Add the field `manifest_references` to `CaseFacts` in `src/devops_cli/roadmap/stage/stage_eval_cases.py`, empty by default, and read it in `of_case` of `src/devops_cli/roadmap/stage/stage_eval_gates.py`. Run `uv run devops roadmap eval stage --replay` on the base commit and on the change with the same model, and state the score before and after the change in the pull request comment
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py` passes

## 4. State the rule of a manifest plan

Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/plan-check.md`, `src/devops_cli/roadmap/stage/stage_paths.py`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/plan-check.md`.

- [x] 4.1 State the rule at the plan check of `docs/ROADMAP_WORKFLOW.md` and on the plan-check page of `docs/roadmap/plan-check.md`: a plan that changes a YAML manifest under `k8s/` lists every test file that references the manifest, and the `paths` gate refuses the plan that leaves one out
  - Verification: `$ uv run devops ci docs` passes
- [x] 4.2 Edit `docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/plan-check.md` with the rule of a manifest plan and the name of the `paths` gate that refuses it
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
