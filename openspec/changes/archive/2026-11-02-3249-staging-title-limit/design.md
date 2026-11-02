# Design

## One number, the room for the largest number

The title is `docs(openspec): plan #<number> <summary>` and the form allows `SUMMARY_MAX_CHARS` (60) characters after the colon. The lead `plan #<number> ` is `stage_title_lead`, so the room for the model's summary is 60 minus the lead, and the lead grows with the digits of the number.

`STAGE_SUMMARY_MAX_CHARS` is computed once from the lead and the largest number of `ISSUE_NUMBER_DIGITS` (6) digits, 47 characters. The schema, the prompt and the tests read it. This is the simplest rule that cannot cut: the schema is the only gate before the title is built, it cannot see the number, and one fixed limit for the longest lead fits every shorter lead.

Rejected: a limit that is a function of the number. It needs the number inside the validator of the reply. `chat_structured` validates a reply in a retry loop and passes no context, so the job would have to build a schema class for each item, or check the length after parsing and send the reply back by hand. That is more code for 1 to 6 characters of room, and the prompt would still have to name one number.

Rejected: leave the limit at 60 and let `staging_title` shorten a text without `...`. The title would be a cut sentence, and the model would not know the room.

## The text as the title shows it

`staging_title` writes `safe_text(summary)`, which puts a handle or a link in a code span and adds characters. A `field_validator` on `summary` measures `safe_text(summary)` against the same limit and refuses a longer one with the message `stage_summary_long`, which the model reads as a refusal of its reply. `max_length` stays on the field, so the plain length is refused with Pydantic's own message.

## What `staging_title` does for a number of 7 digits or more

It still cuts at a word with `...`, and `title_problems` refuses the title. The constant `ISSUE_NUMBER_DIGITS` names the support. The cut is removed by #3215, with the other `textwrap.shorten` calls for titles.

## The prompt

The prompt is a Markdown file and holds the number as text, like the 800 of `pull_request_body`. A test reads the number from the prompt and holds it equal to `STAGE_SUMMARY_MAX_CHARS`, as the 800 is held equal to `BODY_MAX_CHARS`.
