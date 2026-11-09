# Design

## Decisions

- **Refuse the placeholder summary in `StageProposal._summary_fits_the_title`, beside the blank, cut and length checks.** The field validator returns the reply to the model before `check_proposal`, as the other schema replies do, so the model writes a summary that names the work in the same round.
- **Reuse `stage_problem_text_placeholder` with the field `summary`.** The message already names the field and the placeholder text, so the change adds no message key and no second wording for the same rule.
- **Judge the shown title text, after `safe_title`, with `is_placeholder`.** The validator already measures the text as the title shows it, and a summary of `x` shows as `x`, so the placeholder rule reads the same text as the length rule.
- **Hold the title and the body on `PullStatus`.** `read_draft` and the `stage_ready` row already carry the `PullStatus` of the pull request, so the decision reads both fields with no new request and stays a pure function.
- **Refuse a `STAGE_PLAN` draft when either the title summary or the body is a placeholder.** Either field alone leaves the plan with no usable summary or body. A title-only placeholder still names no work.
- **Find the summary after the `stage_title_lead` of the item number.** The lead `plan #<number> ` hides the placeholder from `title_problems`, so the decision removes the one definition of the lead and judges the remaining text.
- **Keep the staging title lead `docs(openspec): plan #<number> `.** The summary alone is the model's text, and the existing title checks depend on the lead.
- **Report the summary problem through `summary_problem` in the replay.** `PlanUnderTest.of_case` builds the plan with `model_construct`, so it collects no top-level field problem. The replay therefore names the placeholder summary through the same function as the schema, and the golden case `3167` records a `kind` gate defect for it.

## Rejected alternatives

- **Add `summary` to `_plan_texts`.** `_text_problems` applies `PLAN_FIELD_MIN_CHARS`, and a scan of the `tasks.md` files found 183 of 1776 group titles under 10 characters. The content gate runs later than the field validator, and its minimum length would refuse real summaries.
- **Check the whole text after the colon.** The lead `plan #3321 ` is no placeholder, so a title-only placeholder would pass, as `title_problems` shows today.
- **Add a regex for the full staging title.** It copies the title format into a second place, and a change to the lead would leave the copy behind.
- **Refuse only when the title summary and the body are both placeholders.** A title-only placeholder still names no work and would pass.
- **Call GitHub inside `_judge_completeness`.** The decision is a pure function, and a request would break its tests and its callers.
- **Add title and body to `Draft` instead of `PullStatus`.** It duplicates the pull request record and makes every caller fill two more fields.
- **Leave the golden case `3167` without a `kind` gate defect.** The check `test_a_plan_fails_the_schema_of_the_reply_only_when_a_defect_names_the_kind_gate` would then refuse a case that no defect names, and the replay would disagree with the schema about the same plan.
