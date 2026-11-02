# Proposal

## Why

Issue #3249 made the summary limit of a plan one number (`STAGE_SUMMARY_MAX_CHARS`, 47) that the schema, the prompt and `staging_title` agree on. The review of that change found eight minor gaps. This follow-up closes the ones that are defects and names the owner of the others.

- The spec said the job never cuts an accepted summary, with no condition. A number of 7 digits or more still gave a title that ends with `...` and that `title_problems` refuses, and no check saw it.
- The scenario "A long summary" lost its old assertion about the cut at a word, while the cut was still code.
- The schema counted two different things. `max_length` counted the raw reply, and the validator counted the text as the title shows it. A reply `"a" * 47 + "\n"` was refused with a message that gave no count, although its title fits, and a reply with a run of spaces that the title collapses was refused too. Each refusal costs a retry.
- The retry message of the plain case named the limit but not the count, no test held the text, and the prompt did not say that a handle or a link costs characters.

## What Changes

- `staging_title` no longer cuts. A summary that does not fit the title raises `RoadmapStageError` for the item, so `_plan_each` records a failure for that item and the run goes on. This removes the `textwrap.shorten` call of `staging_title`, which issue #3215 also plans to remove.
- The schema counts one thing: the one-line text of the title (`safe_text`). The field gives `maxLength` in its JSON schema, which the model reads, and the validator is the only check. Every refusal names the count and the limit.
- The prompt says that the limit counts the summary as the title shows it, so the model writes no handle or link in it.
- The requirement "A staged item gets a draft pull request" states the condition (a number of up to 6 digits) and the error for a longer number. Its scenarios replace the cut at a word, which the code no longer does, with the refusal.
- The change alters what a consumer sees (the spec and a message), so it carries a spec delta. It fits one pull request.

Findings of the review that this change does not fix:

- A summary that ends with `...` or `…` passes the schema and gives a refused title. The open plan for #3200 owns the refusal of cut text in a plan.
- The check `Semantic PR title` counts UTF-16 units, and Python counts code points. That is an existing difference of the checks, not of this change, and #3215 (build titles with `pull_form`) is where it belongs.
- The first-reply refusal rate with a live model is not measured here. Run `devops roadmap eval stage` with the live model.

## Capabilities

### Modified Capabilities

- `roadmap-stage`: the title of a plan is never cut, and the limit of the summary counts the text as the title shows it.

## Impact

- Code: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- Documents: `openspec/specs/roadmap-stage/spec.md` (by archive).
- Tests: `tests/roadmap/test_roadmap_stage_title.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`, `tests/support/builders.py`.

## Feasibility

- Each finding was reproduced on `origin/main` before the fix. `staging_title(1000000, "a" * 47)` returns a title that ends with `...`. `make_stage_proposal(summary="a" * 47 + " ")` raises "String should have at most 47 characters" although `len(safe_text(...))` is 47. A reply with a summary of 48 characters gets a message that names the limit and no count.
- Pydantic keeps `maxLength` in `model_json_schema()` when `json_schema_extra={"maxLength": n}` replaces `max_length`, so a provider that reads the JSON schema still sees the limit. A test reads the limit from that schema.
- `_plan_each` catches `RoadmapStageError`, records a `StageFailure` and goes on with the next item. A test shows the same for a summary refused twice: one item fails, and the next item is staged.

## Existing Tool Considered

Pydantic already gives `max_length` and `field_validator`. `max_length` counts the raw string and cannot count the text after `safe_text`, so the change keeps the validator and gives the limit to the JSON schema by `json_schema_extra`. No other library measures a title. Written cost: about 30 000 tokens and 45 minutes to write and test; about 2 000 tokens a year to keep; about 5 000 tokens to fix a drift, because the tests name the number that differs. The change deletes the `textwrap.shorten` call and the cut of `staging_title`.
