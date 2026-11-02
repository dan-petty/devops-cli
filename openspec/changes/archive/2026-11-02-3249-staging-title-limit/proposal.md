# Proposal

## Why

Issue #3249: the stage job builds a title its own form check refuses. The reply field `StageProposal.summary` accepts 60 characters, which is `SUMMARY_MAX_CHARS`. The title is `docs(openspec): plan #<number> <summary>`, and the part after the colon has at most 60 characters, so the lead `plan #<number> ` takes 7 to 13 of them. `staging_title` cut a longer summary at a word and wrote `...`, and `title_problems` refuses a summary that ends with `...`. The planner prompt named a third number, 40, so the three places disagreed and no test held them together. Open plan pull requests carried the defect.

## What Changes

- One number, `STAGE_SUMMARY_MAX_CHARS` in `stage_change.py`, is `SUMMARY_MAX_CHARS` minus the lead for the largest issue number that the job supports (`ISSUE_NUMBER_DIGITS`, 6 digits: 47 characters). The schema (`max_length`), the planner prompt and `staging_title` all agree with it, and tests hold them equal.
- The schema also refuses a summary that is longer once `safe_text` has put a handle or a link in a code span, with a message that goes back to the model. So `staging_title` cuts no summary that the schema accepted.
- The prompt `roadmap_stage_change.md` states 47 characters instead of 40.
- The change alters an observable limit of the stage job, so it carries a spec delta: the requirement "A staged item gets a draft pull request" changes its scenario "A long summary".
- `delivery_title` (the implement job) and `devops pr create` were checked for the same cut. `devops pr create` cuts nothing: it refuses. `delivery_title` still cuts the summary of the issue title with `...`, and so does the "why" in `implement_run.py`. Issue #3215 owns that change, and it removes the `textwrap.shorten` calls for titles and bodies, so this change leaves them.
- The change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-stage`: the summary of the plan is bounded by the room that the title leaves, and the job cuts no accepted summary.

## Impact

- Code: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- Documents: `openspec/specs/roadmap-stage/spec.md` (by archive).
- Tests: `tests/roadmap/test_roadmap_stage_title.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

## Feasibility

- The premise holds. On `origin/main`, `uv run pytest tests/roadmap/test_roadmap_stage_title.py` with the new test `test_a_summary_of_the_most_characters_that_the_schema_accepts_gives_a_title_the_form_accepts` fails for each issue number: a summary of the 60 characters that the schema accepts gives a title that ends with `...`, and `title_problems` refuses it, even for the number `1`.
- The room depends on the digits of the number: `plan #1 ` is 8 characters, `plan #3249 ` is 11, `plan #999999 ` is 13. The schema validates the reply before the job knows the item, and `chat_structured` passes no context to the validator. So the schema limit cannot be a function of the number. It is the room for the largest number that the job supports. A shorter number leaves room over, which is not a defect. A number of 7 digits (a million issues) is out of the support and the constant names it.
- `safe_text` makes a text longer: `@maintainer` becomes `` `@maintainer` ``. A test shows that a summary at the limit with a handle is longer than the room, so a plain `max_length` is not enough, and the validator measures the text as the title shows it.
- The title scope `openspec` has the label `scope/openspec` in `.github/labels.yml`, so the scope is no cause of a refusal.

## Existing Tool Considered

No open tool covers it: the rule joins our own constant `SUMMARY_MAX_CHARS`, our own lead text and a Pydantic schema. Pydantic already gives `max_length` and `field_validator`, and the change uses both. Written cost: about 25 000 tokens and 40 minutes to write and test; about 2 000 tokens a year to keep, as the constants are derived and a test holds them equal; about 5 000 tokens to fix a drift, because the test names the number that differs. The change deletes no code. #3215 will delete the `textwrap.shorten` call of `staging_title`.
