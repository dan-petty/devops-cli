# Tasks

## 1. The golden set and its loader

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_paths.py`. Changes: `src/devops_cli/roadmap/stage_eval_cases.py` (new), `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_eval_cases.py` (new).

- [x] 1.1 Write failing tests in `tests/roadmap/test_roadmap_stage_eval_cases.py`: the set loads with at least 40 cases and 3 `good` cases, every one of the 37 pull requests is present, every defect type is in the enum, a case with a bad type fails with the case name, and each `plan.json` holds the fields of a `StageProposal` (the groups raw)
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_cases.py` fails on the base
- [x] 1.2 Add the models and `load_cases` in `src/devops_cli/roadmap/stage_eval_cases.py`, the fixture folders, and the messages
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_cases.py` passes

## 2. The gates and the replay

Reads: `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_paths.py`. Changes: `src/devops_cli/roadmap/stage_eval_gates.py` (new), `tests/roadmap/test_roadmap_stage_eval_gates.py` (new).

- [x] 2.1 Write failing tests in `tests/roadmap/test_roadmap_stage_eval_gates.py`: the replay of the whole set has no failure, a plan whose missing path becomes a tracked file makes the replay miss the defect, a good plan with a missing path is refused, the pending defects are counted and fail nothing, a `pending` defect of a type with a gate is stale, and the names of the gate types match `PENDING_GATES`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` fails on the base
- [x] 2.2 Add the gates, the replay and the report in `src/devops_cli/roadmap/stage_eval_gates.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` passes

## 3. The live run and the score

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `tests/support/roadmap_stage.py`. Changes: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_eval_run.py` (new), `src/devops_cli/roadmap/stage_eval_score.py` (new), `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_eval_run.py` (new).

- [x] 3.1 Write failing tests in `tests/roadmap/test_roadmap_stage_eval_run.py`: a scoring unit test over made-up runs (avoided, caught, no rate for a type without a gate, the total), a run with a faked model whose first reply names a missing path and whose second is right, a run whose first reply passes, a run whose model call fails, and `plan_item` with a recording client
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_run.py` fails on the base
- [x] 3.2 Add `StageClient`, `plan_item` and the shared planner builder in `src/devops_cli/roadmap/stage.py`, then the run and the score
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_run.py tests/roadmap/test_roadmap_stage_plan.py tests/roadmap/test_roadmap_stage_job.py` passes

## 4. The command

Reads: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/stage_eval_run.py`. Changes: `src/devops_cli/commands/roadmap_eval.py` (new), `src/devops_cli/commands/roadmap_eval_stage.py` (new), `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/stage_eval_render.py` (new), `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_eval_command.py` (new).

- [x] 4.1 Write failing tests in `tests/roadmap/test_roadmap_stage_eval_command.py`: `--replay` exits 0 on the set and 1 on a broken set, `--dry-run` makes no model call and names the case, `--case` and `--limit` pick cases, an unknown case exits 1, a live run with a faked model prints the table and stores the report, and the group lists `stage`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_command.py` fails on the base
- [x] 4.2 Add the group, the command, the render functions and the help text, and register the group once in `roadmap.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_command.py tests/invariants/test_dry_run_class_ratchet.py` passes

## 5. The document

Reads: `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `README.md`.

- [x] 5.1 Add one section to `docs/ROADMAP_WORKFLOW.md`: how to run the eval, how to read the score, and the rule that a change to the stage prompt or to the checks states its score before and after in its pull request; then regenerate the documents
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops ci docs` pass, and `uv run devops ci test tests/invariants/test_roadmap_workflow_doc.py` passes

## 6. Fail-to-pass and archive

- [x] 6.1 Run the fail-to-pass check on the new tests
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [x] 6.2 Archive the change
  - Verification: `uv run devops openspec archive 3028-stage-golden-set-eval` and `uv run devops openspec check`

## 7. Fixes of the review

Reads: `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/roadmap/stage_eval_score.py`, `src/devops_cli/roadmap/stage_eval_run.py`. Changes: the same modules, `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_eval_render.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/lang/en/messages.py`, `docs/ROADMAP_WORKFLOW.md`, `tests/fixtures/roadmap_eval/stage/`, and the tests of the golden set.

- [x] 7.1 Write failing tests: a model that breaks the schema twice scores as neither avoided nor caught, the `kind` row has no rate, the replay fails when a spec rule refuses a good plan, the capabilities of the facts decide a modified capability, and a `kind` defect must hold the message of the schema
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_run.py tests/roadmap/test_roadmap_stage_eval_gates.py` fails on the base
- [x] 7.2 Leave the `kind` gate out of the live score, run `check_proposal` as the `paths` gate with the capabilities of the case, add the `message` of a defect, and drop the false `kind` defect of the case 2745
  - Verification: `uv run devops ci test tests/roadmap` passes
- [x] 7.3 Add a test that a plan fails the schema of the reply if and only if a defect names the gate `kind`, and rename the constant of the render module to the one in `stage.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_cases.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
