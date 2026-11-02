# Design

## The title is built whole or not at all

`staging_title` writes `safe_text(summary)` after the lead, or raises `RoadmapStageError` with the number of the item in `failed_items`. A cut text ends with `...`, and `title_problems` refuses it, so the cut only moved the failure to a later step. The error stops one item: `_plan_each` catches `RoadmapStageError`, adds a `StageFailure`, and plans the next item. For a number of 6 digits or fewer the schema has already refused every summary that does not fit, so the error is reached only by a number of 7 digits or more (one million issues), which the constant `ISSUE_NUMBER_DIGITS` names as out of support.

Rejected: raise `ValueError` and catch it in `_settle`. `staging_title` knows the number, and `RoadmapStageError` already carries `failed_items`, so the catch and its test are not needed.

Rejected: run `title_problems` in `_settle` and send the problem back to the model. That is the change of #3215. For a number of 7 digits the model cannot help, because the limit that it knows is the room for 6 digits.

## One measure for the limit

`max_length` counts the raw string, and `safe_text` changes its length: it collapses whitespace (shorter) and puts a handle or a link in a code span (longer). With both checks the schema refused a reply whose title fits, and the message of `max_length` gave no count. The field now gives `maxLength` to the JSON schema with `json_schema_extra`, which is what a provider reads, and the validator counts `len(safe_text(summary))` and names the count and the limit. The tests read the limit from `model_json_schema()`.

## The cut at a word

The old scenario "A long summary" described the cut at a word. The code no longer cuts, so the scenario is replaced, not kept: a summary that is too long is refused by the schema, and a number that is too large stops the item. `delivery_title` still cuts the title of an issue at a word. It belongs to the implement job and to #3215.
