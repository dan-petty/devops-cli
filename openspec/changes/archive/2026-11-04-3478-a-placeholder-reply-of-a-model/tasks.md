# Tasks

## 1. One placeholder rule and the ReplyText type

Reads: `src/devops_cli/roadmap/pull_form.py`, `tests/roadmap/test_roadmap_pull_form.py`. Changes: `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/lang/en/messages.py`, `pyproject.toml`, `uv.lock`, `tests/roadmap/test_roadmap_pull_form.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_pull_form.py`, add cases that `is_placeholder` is true for `y`, `probe`, `__PROBE__` and "Not yet: I need to inspect the repository first.", false for "The probe shows the path", and that `ReplyText` refuses each with the error type `placeholder_text` and accepts a real sentence
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_pull_form.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/pull_form.py`, add `y` and `probe` to the placeholder set, refuse the lead "Not yet:" in `is_placeholder`, and add `ReplyText` (`Annotated[str, AfterValidator(...)]` that raises `PydanticCustomError("placeholder_text", ...)`) with its message in `MESSAGES.roadmap`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_pull_form.py` passes

## 2. Remove the return path of the stage job

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_eval_run.py`, `src/devops_cli/commands/roadmap.py`, `tests/support/builders.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_eval_run.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_apply.py`, `tests/roadmap/test_roadmap_stage_job.py`, `tests/roadmap/test_roadmap_stage_verification.py`, `tests/roadmap/test_roadmap_stage_eval_run.py`, `tests/roadmap/test_roadmap_stage_kind.py`, `tests/roadmap/test_roadmap_stage_text_lines.py`.

- [x] 2.1 In `tests/roadmap/test_roadmap_stage_plan.py`, replace the premise tests with cases that the schema refuses `{"premise_failed": value}` for `placeholder`, `x`, `none`, `probe`, `__PROBE__`, the text of #3104 and the texts of #3193, #3109 and #3255 (also next to a valid plan), that it refuses `{}` and names each missing key, and that the job returns no item and writes no comment when the model answers with `premise_failed` twice
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [x] 2.2 In `src/devops_cli/roadmap/stage_change.py`, delete `premise_failed`, `_evidence_alone`, `_blank_is_none`, `_plan_unless_premise_failed` and `_PLAN_KEYS`, and make the keys of the plan required
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes
- [x] 2.3 In `src/devops_cli/roadmap/stage.py`, `stage_eval_run.py` and `commands/roadmap.py`, delete `PremiseFailed`, `_premise_failed`, `_return_item`, `StagePlan.returned`, `StageApplied.returned`, `StageResult.RETURNED`, `Outcome.RETURNED` and the report section, and delete their messages. Update the tests of the apply, the job, the verification, the eval run and the text lines to the new shape
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_apply.py tests/roadmap/test_roadmap_stage_job.py tests/roadmap/test_roadmap_stage_verification.py tests/roadmap/test_roadmap_stage_eval_run.py tests/roadmap/test_roadmap_stage_text_lines.py` passes
- [x] 2.4 In `src/devops_cli/ai/tasks/roadmap_stage_change.md`, delete the rule and the key `premise_failed`, and tell the model to state in `feasibility` that the issue cannot be built as written. Update `tests/roadmap/test_roadmap_stage_kind.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_kind.py` passes
- [x] 2.5 Check that no source file names the deleted key
  - Verification: `! git grep -nw premise_failed src/devops_cli`

## 3. Refine: one reply text type and a failure that moves no item

Reads: `src/devops_cli/roadmap/refine.py`, `src/devops_cli/ai/client/models.py`, `src/devops_cli/ai/client/structured.py`, `src/devops_cli/roadmap/run.py`, `tests/roadmap/test_roadmap_refine.py`. Changes: `src/devops_cli/roadmap/refine.py`, `src/devops_cli/ai/client/models.py`, `src/devops_cli/ai/client/structured.py`, `tests/roadmap/test_roadmap_refine_placeholder.py`, `tests/roadmap/test_roadmap_refine.py`, `tests/ai/client/test_ai_client_structured.py`.

Creates: `tests/roadmap/test_roadmap_refine_placeholder.py`.

- [x] 3.1 In `tests/ai/client/test_ai_client_structured.py`, add a case that a call whose last reply broke the schema raises `StructuredOutputValidationError` with `error_types` set to the pydantic error types, and a case with a reply that held no JSON (empty `error_types`). In `tests/roadmap/test_roadmap_refine_placeholder.py`, add cases for the refine reply: `x` in both required keys with empty criteria fails the schema, a placeholder in a criterion, an answer and a deferred part fails, `suspected_block` `none` passes; a first placeholder reply and a valid second reply give the second reply with two model calls; two placeholder replies write no comment, no body, no mark and no Status; a placeholder with another violation is a normal failure; `raise_for_failed_items` does not raise for a placeholder failure; and a ledger that runs the refine row three times with a placeholder failure does not suspend it
  - Verification: `uv run devops ci test tests/ai/client/test_ai_client_structured.py tests/roadmap/test_roadmap_refine_placeholder.py` fails on the base
- [x] 3.2 In `src/devops_cli/ai/client/models.py` and `structured.py`, add `error_types` to `StructuredOutputValidationError` and set it from the last reply
  - Verification: `uv run devops ci test tests/ai/client/test_ai_client_structured.py` passes
- [x] 3.3 In `src/devops_cli/roadmap/refine.py`, use `ReplyText` for the free-text fields of the reply except `suspected_block`, ask `chat_structured` for one retry, set `RefineFailure.placeholder` and `item_caused` from `error_types`, and skip a placeholder failure in `raise_for_failed_items`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine_placeholder.py tests/roadmap/test_roadmap_refine.py` passes

## 4. The repair pass

Reads: `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/request_plan.py`, `tests/roadmap/test_roadmap_stop_clear.py`, `tests/roadmap/test_roadmap_inbox_command.py`. Changes: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`.

Creates: `src/devops_cli/roadmap/repair.py`, `tests/roadmap/test_roadmap_repair.py`, `tests/roadmap/test_roadmap_repair_command.py`.

- [x] 4.1 In `tests/roadmap/test_roadmap_repair.py`, add cases with an in-memory store for the listing of a filler return (the texts of #3104 and `placeholder`), the listing of a stub refine block, the items that the pass leaves (a return with real evidence, a Status that a person set, a reply after the return, an owner label, a closed item, an edited section, a held item) and the writes of `--confirm` (Ready for a return, no section and no refine marks for a stub block, a second run lists nothing, an item that changed since the read). In `tests/roadmap/test_roadmap_repair_command.py`, add cases for the command: the list without `--confirm` writes nothing, `--confirm` writes, `--dry-run` opens no store and lists the requests
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_repair.py tests/roadmap/test_roadmap_repair_command.py` fails on the base
- [x] 4.2 In `src/devops_cli/roadmap/repair.py`, add `plan_repair` and `apply_repair`, and in `request_plan.py` add `repair_requests`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_repair.py` passes
- [x] 4.3 In `src/devops_cli/commands/roadmap.py`, add the command `devops roadmap repair` with `--repo`, `--dry-run` and `--confirm`, with its help text and its messages
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_repair_command.py` passes

## 5. Documents

Reads: `docs/roadmap/refine.md`, `docs/roadmap/stage.md`, `docs/TELEMETRY.md`, `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/roadmap/refine.md`, `docs/roadmap/stage.md`, `docs/TELEMETRY.md`, `docs/ROADMAP_WORKFLOW.md`.

Creates: `docs/roadmap/repair.md`.

- [x] 5.1 Write `docs/roadmap/repair.md` and link it from `docs/ROADMAP_WORKFLOW.md`. Describe the placeholder failure in `docs/roadmap/refine.md`, delete the return path from `docs/roadmap/stage.md` and the `returned` result from `docs/TELEMETRY.md`, and regenerate the command reference with `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
