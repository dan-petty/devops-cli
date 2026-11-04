# Proposal

## Why

#3478: two jobs take placeholder text from a model as a real result.

- The stage job reads any non-blank `premise_failed` as proof that the premise of the issue is false. It returns the item to New and drops the rest of the reply. 33 of 36 return comments on open items hold filler such as `placeholder`, `x`, `none`, `probe`, `__PROBE__` or "Not yet: I need to inspect the repository first." (#3104). #3193, #3109 and #3255 state that the premise holds, and the job returned them too.
- The refine job stores `x` as the problem statement and as the existing-tool answer. It then asks a person to state a problem that the body already states. 21 New items hold such a stub.

The rule of `is_placeholder` lacks `y` and `probe`, and it cannot catch "Not yet: ...".

## What Changes

- The stage reply has no `premise_failed` key. The stage job has no return path: `PremiseFailed`, the return comment, the `returned` result and its section of the report are gone. The keys of the plan are required keys of the schema, so `{"premise_failed": "x"}` fails the schema.
- `is_placeholder` in `src/devops_cli/roadmap/pull_form.py` also holds `y` and `probe`, and refuses a text that starts with "Not yet:". One new type, `ReplyText`, applies that rule as a pydantic `AfterValidator`. It raises the error type `placeholder_text`.
- The refine reply uses `ReplyText` for each free-text field. The proposal call returns a reply with a placeholder once, through `chat_structured` (`max_retries=1`). A reply that still holds a placeholder is a placeholder failure of the item: refine logs it, records nothing on the item, writes no comment, asks no person and sets no Status. The round does not fail for it, so `FailureLedger` does not count it.
- `StructuredOutputValidationError` names the pydantic error types of the last reply (`error_types`), so a caller can tell a placeholder failure from another schema failure.
- The new command `devops roadmap repair` finds the items that a filler return or a stub refine block stalled. Without `--confirm` it lists them. With `--confirm` it sets a returned item back to Ready, and it strips the stub section and clears the refine block of a stalled item. It leaves an item that a person set. `--dry-run` makes no request.
- The Spec, the stage prompt, `docs/roadmap/refine.md`, `docs/roadmap/stage.md`, `docs/roadmap/repair.md` and `docs/TELEMETRY.md` describe the final behavior.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-repair`: the pass that sets back the items stalled by a placeholder reply of a model.

### Modified Capabilities

- `roadmap-stage`: the return path is removed, and the plan keys are required.
- `roadmap-refine`: the reply text type, the retry and the placeholder failure.

## Impact

- Code: `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_eval_run.py`, `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/repair.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/ai/client/models.py`, `src/devops_cli/ai/client/structured.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `pyproject.toml` and `uv.lock` (`pydantic-core` becomes a direct dependency, because `ReplyText` raises `PydanticCustomError`).
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `docs/roadmap/refine.md`, `docs/roadmap/stage.md`, `docs/roadmap/repair.md`, `docs/TELEMETRY.md`, `docs/ROADMAP_WORKFLOW.md`.
- Tests: `tests/roadmap/`, `tests/ai/`.
- #3483 depends on the repair pass.

## Feasibility

The checks ran against the tree at `origin/main` (commit 336731cd) and against the issues on GitHub.

- `src/devops_cli/roadmap/stage_change.py` types the key as `premise_failed: str | None = None`. Its `_evidence_alone` validator returns `{"premise_failed": ...}` for any text that is not blank. Its validator `_blank_is_none` only strips the text. No rule reads the content.
- `src/devops_cli/roadmap/stage.py` returns `PremiseFailed` from `_gated` and `_verified` for each non-`None` value. `apply_stage` then runs `_return_item`, which posts the comment and sets the Status New.
- `src/devops_cli/ai/tasks/roadmap_stage_change.md` says "When it is a string, no other key is needed", so `{"premise_failed": "x"}` is the smallest valid reply.
- `src/devops_cli/roadmap/refine.py` types `problem_statement: str` and `existing_tool: str`. With empty criteria, `check_ready` is false and `next_step_of` gives `NextStep.PERSON` with `refine_incomplete`.
- The comments of #3193, #3109, #3255 and #3104 on GitHub hold the texts that the tests use. The first three say that the premise holds. The last is "Not yet: I need to inspect the repository first."
- `is_placeholder` holds no `probe` and no `y`. The test for `__PROBE__` passes once the edge characters are stripped: `_PLACEHOLDER_EDGES` holds `_`.
- `FailureLedger.failed` counts a round when the job raises. `raise_for_failed_items` raises for each skipped item, so three rounds with one placeholder item would suspend the refine row.
- The first checks of the implementation run `uv run devops ci test tests/roadmap` and `uv run devops ci test tests/ai`.

## Existing Tool Considered

Pydantic `Annotated` with `AfterValidator` is the open, maintained library for the reply type. The change adds no dependency and no second word list: `ReplyText` calls the extended `is_placeholder`. The stage free-text fields keep the content gate `content_problems`, which already calls `is_placeholder` (see `design.md`). The repair pass uses the roadmap store and `write_each`, as `stop_clear.py` does.

The change deletes `PremiseFailed`, `_return_item`, `_evidence_alone`, `_blank_is_none`, `_plan_unless_premise_failed`, `_PLAN_KEYS`, the `returned` result and the related messages.
