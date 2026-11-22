# Design

## Decisions

- **Measure only the text above the trailer line, with its trailing blank lines removed.**: `CONTRIBUTING.md:181:in at most 1,000 characters before the trailers` and the message field `form_body_long` give that meaning, and the acceptance criteria ask for it.
- **Measure the text above `Plans` for a plan body with the same limit.**: A plan body has no `Closes` line, and one measure for both forms keeps the plan check and the plan form check from disagreeing about one body.
- **Name the measured line through a `{line}` placeholder in `form_body_long`.**: One message serves a delivery body and a plan body, and a fixed word would name a line that the check did not measure.
- **Give the room of a plan text and the room of the implement why the whole limit.**: `plan_body_room` and `_why` subtract the trailer lines from the same bound, so keeping the subtraction leaves two meanings of one limit.
- **Keep the phrase `in at most 1,000 characters before the trailers` in `CONTRIBUTING.md` and add the measured part after it.**: `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` reads the number from that phrase, and the added clause states the measured part with no second place for the bound.
- **Change the plan check to measure the text above `Plans`.**: The plan check reads the same body that the plan form check builds, so a whole-body measure there refuses a plan body that the form check accepts.

## Rejected alternatives

- **Include the `Closes` and `Change:` lines in the limit.**: `CONTRIBUTING.md:181:in at most 1,000 characters before the trailers` and `src/devops_cli/lang/en/messages.py:1700:The body has {length} characters before its trailers.` say that the limit covers the text before the trailers, so the whole-body measure refuses a body that both of them allow.
- **Keep the whole-body measure and name the difference in the text.**: It leaves two meanings of one limit, and the plan check would still refuse a plan body that the plan form check accepts.
- **Add a warning threshold above the limit instead of changing the measure.**: A second threshold keeps the measure that refuses a body the document allows, so the disagreement that stopped the merges stays.
