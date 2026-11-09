# Tasks

## 1. A schema failure names its violations

Kind: behavior. Reads: `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/roadmap/stage/stage.py`. Changes: `src/devops_cli/ai/schema_reflection.py`, `src/devops_cli/ai/client/models.py`, `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_toolbox.py`, `tests/roadmap/stage/test_roadmap_stage_refused_reply.py`.

- [x] 1.1 Add the tests: the trace keeps 3 texts of 5 violations and the count 5, cuts a message of 300 characters at 200, and masks a secret; the toolbox raises the error with the texts and the stop reason `validation` or `no tool call`; the failure text names the location, the type, the stop reason and the count
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_toolbox.py tests/roadmap/stage/test_roadmap_stage_refused_reply.py` fails on the base
- [x] 1.2 Add `ViolationText`, the trace field, the error fields, the failure text and the constants
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_toolbox.py tests/roadmap/stage/test_roadmap_stage_plan.py` passes

## 2. A schema failure is kept in the refused file

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_plan_record.py`. Changes: `src/devops_cli/roadmap/stage/stage_plan_record.py`, `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_refused_reply.py`.

- [x] 2.1 Add the tests: a schema failure writes `<n>.refused.json` with the stop reason, the count and the texts, logs one line, masks a secret, and keeps the replies refused before it; the staging of the item deletes the file
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_refused_reply.py` fails on the base
- [x] 2.2 Add `schema_failure` to the record and keep it from `_gated`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_refused_reply.py` passes

## 3. Documents

Kind: documents. Changes: the documents that the change makes wrong, if any.

- [x] 3.1 Search the documents for the old text of the failure line ("schema violation(s)") and for the refused file, and fix each one that the change makes wrong
  - Verification: `$ uv run devops ci docs` passes
- [x] 3.2 Validate the change folder
  - Verification: `$ uv run devops openspec check` passes
