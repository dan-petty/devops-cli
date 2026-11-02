# Tasks

## 1. The counts by type and the reason of a defect

- [x] 1.1 Write failing tests in `tests/roadmap/test_roadmap_stage_eval_gates.py`, `tests/roadmap/test_roadmap_stage_eval_command.py` and `tests/roadmap/test_roadmap_stage_eval_run.py` for the scenarios of "The replay counts the defects by type", "A defect that no gate can judge says why", "A rule of the spec delta stops refusing" and "No type waits"
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py tests/roadmap/test_roadmap_stage_eval_command.py` (fails on the base)
- [x] 1.2 Add the field `reason` to `Defect`, `TypeTotals`, `ReplayReport.by_type` and `ReplayReport.judged` to `stage_eval_gates.py`, print the table by type and the share in `stage_eval_render.py` and in the JSON report, and add the messages
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py tests/roadmap/test_roadmap_stage_eval_command.py tests/roadmap/test_roadmap_stage_eval_run.py`

## 2. The labels of the golden set

- [x] 2.1 Run the replay for each defect of the four types, set the gate `paths` and the `message` for the 4 defects that the check catches, and set the gate `none` and a `reason` for the other 63, with a script that runs once and changes no `plan.json`; empty `PENDING_GATES`
  - Verification: `uv run devops roadmap eval stage --replay` exits 0 and prints `Defects that a gate judges: 64 of 299 (21%).`; `! git grep -n '"gate": "pending"' tests/fixtures/roadmap_eval/stage`
- [x] 2.2 Run the whole replay test suite on the labels
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py tests/roadmap/test_roadmap_stage_eval_command.py tests/roadmap/test_roadmap_stage_eval_run.py`

## 3. The documents and the archive

- [x] 3.1 State the gates, the reason and the report in `docs/ROADMAP_WORKFLOW.md`
  - Verification: `uv run devops docs check`
- [x] 3.2 Archive the change
  - Verification: `uv run devops openspec archive 3208-replay-the-defects-whose-gates-exist`

## Workflow follow-up

- Work the item will not do: a rule for a delta on `pyproject.toml` or on documents at the root, in #3212. The `reason` of the defects names the gaps.
- Work the item will not do: a check on the reply for code that exists. #3012 gives that code to the model as input and builds no check, and no issue plans one.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
