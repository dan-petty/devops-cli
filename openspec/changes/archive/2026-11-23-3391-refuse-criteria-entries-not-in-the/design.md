# Design

## Decisions

- **Refuse each `criteria` entry whose `one_line` text is not in `acceptance_criteria(issue_body)`.**: The prompt tells the model to copy person-written items, and `acceptance_criteria` cuts the refine block off, so the person-written list is the only source. Normalizing with `one_line` keeps a copy that differs only in spacing valid.
- **Add the rule to `criterion_problems` and keep `acceptance_criteria` unchanged.**: `criterion_problems` is the one check that the stage job, the implement job, the plan check and the replay's criteria gate call on a `criteria` list, and `acceptance_criteria` already returns the person-written criteria in order.
- **Put the problem text in `MESSAGES.roadmap` as `stage_problem_criterion_unknown`.**: Every problem of the module comes from that table, and the criteria tests assert its exact text.
- **Add one sentence to the `criteria` bullet of the stage prompt and assert it in the prompt rules test.**: The prompt is the model's only copy of the rule, and a sentence that no test holds can drift from the check.

## Rejected alternatives

- **Refuse only an entry whose text appears in the refine block.**: `_without_refine_block` cuts the block off before `acceptance_criteria` reads the body, so a check of the block would read text that the function already discards, and an invented entry would still pass.
- **Accept a substring of a criterion as a match.**: A partial text can match a different criterion and weaken the check. The prompt requires the text copied character for character, and the missing-criterion check compares whole texts.
- **Leave the rule to the prompt and accept an entry that no person wrote.**: The plan for #3320 in #3333 copied five refine-block criteria and every gate accepted it, although the prompt already stated the empty-list rule.
- **Write the problem text inline in `criterion_problems`.**: `src/devops_cli/roadmap/stage/stage_criteria.py` reads every problem text from `MESSAGES.roadmap`, and `tests/roadmap/stage/test_roadmap_stage_criteria.py` asserts the exact text of a problem.
