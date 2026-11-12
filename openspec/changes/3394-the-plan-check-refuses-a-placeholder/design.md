# Design

## Decisions

- **Add `pull_request_body` and each `what_changes` line to `_plan_texts`.**: `content_problems` and `check_proposal` already call `_plan_texts`, so one change covers the stage job, the replay and the verification gate.
- **Name the field `what_changes` for every line of that list.**: The problem message names the reply key that holds the text, as it does for `why` and `existing_tool`, and the issue asks for the field name.
- **Keep the rules of `PLAN_FIELD_MIN_CHARS` and `is_placeholder` for the two new fields.**: The issue asks for the same rules, and one rule set keeps the check and the prompt in step.
- **State both fields in the existing Texts rule of the plan stage prompt, and assert the rule in a test.**: The rule already lists the fields that the check refuses, so one list cannot drift from the check, and the prompt test fails when the rule drops a field.
- **Modify the `roadmap-stage/plan-text` requirement `A plan text is no placeholder` and keep all five of its scenarios beside the five new ones.**: A MODIFIED requirement replaces the whole block, so the archive refuses a block that drops a scenario that the living spec holds.

## Rejected alternatives

- **Add Pydantic validators to `StageProposal` for the placeholder rule.**: The rule would leave the stage content check and the replay, and it would reject a model reply before the job can report the problem. `src/devops_cli/roadmap/stage_change.py:398` and `:400` show the fields are plain schema fields, and `content_problems` is the seam that names a problem.
- **Check the two fields only in `check_proposal`.**: `content_problems` calls `_plan_texts`, and `check_proposal` calls `content_problems`, so a separate scan would duplicate the text walk and the replay would miss the rule. `tests/roadmap/test_roadmap_stage_content.py` calls `content_problems` directly.
- **Name each What Changes line `what_changes line N` in the problem message.**: The other checked texts use no position number, and the issue asks for the field name.
- **Add a separate paragraph to the plan stage prompt for the two fields.**: A second list duplicates the Texts rule and can become stale, as the prompt already holds one rule for the checked texts.
- **Replace the living requirement with a block that holds only the two new fields and their scenarios.**: The OpenSpec validation refuses a MODIFIED block that drops a scenario of the current spec, so the five scenarios of `A plan text is no placeholder` stay in the block.
