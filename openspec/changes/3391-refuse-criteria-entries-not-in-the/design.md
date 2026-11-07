# Design

## Decisions

- **Refuse each `criteria` entry whose `_one_line` text is not in `acceptance_criteria(issue_body)`.**: The prompt tells the model to copy person-written items, and `acceptance_criteria` cuts the refine block off, so the person-written list is the only source. Normalizing with `_one_line` keeps a copy that differs only in spacing valid.
- **Add the rule to `criterion_problems` and keep `acceptance_criteria` unchanged.**: `criterion_problems` is the one check that the stage job, the implement job and the plan check call on a `criteria` list, and `acceptance_criteria` already returns the person-written criteria in order.
- **Put the problem text in `MESSAGES.roadmap` as `stage_problem_criterion_unknown`.**: Every problem of the module comes from that table, and the criteria tests assert its exact text.
- **Give the replay's `paths` gate the issue body of a plan that has a `criteria` list, and no body for a plan that has none.**: `_path_gate` runs `check_proposal`, which holds the criteria rule, and the job gives that rule the body. With no body the new rule would refuse an entry that a person wrote; with a body for a recorded plan that has no list it would refuse a plan that was never asked for one.
- **Run the gate change in group 1 and the refusal in group 2.**: The replay test at `tests/roadmap/stage/test_roadmap_stage_eval_gates.py:311` calls the `paths` gate on a mapped plan with a body, so the body must reach `check_proposal` before the new rule refuses entries. Each step then keeps one module and one test module.
- **Add one sentence to the `criteria` bullet of the stage prompt and assert it in the prompt rules test.**: The prompt is the model's only copy of the rule, and a sentence that no test holds can drift from the check.

## Rejected alternatives

- **Refuse only an entry whose text appears in the refine block.**: `_without_refine_block` cuts the block off before `acceptance_criteria` reads the body, so a check of the block would read text that the function already discards, and an invented entry would still pass.
- **Accept a substring of a criterion as a match.**: A partial text can match a different criterion and weaken the check. The prompt requires the text copied character for character, and the missing-criterion check compares whole texts.
- **Leave the rule to the prompt and accept an entry that no person wrote.**: The plan for #3320 in #3333 copied five refine-block criteria and every gate accepted it, although the prompt already stated the empty-list rule.
- **Write the problem text inline in `criterion_problems`.**: `src/devops_cli/roadmap/stage/stage_criteria.py` reads every problem text from `MESSAGES.roadmap`, and `tests/roadmap/stage/test_roadmap_stage_criteria.py` asserts the exact text of a problem.
- **Let the replay's `paths` gate judge the criteria rule with no issue body.**: `src/devops_cli/roadmap/stage/stage_eval_gates.py:def _path_gate` passes no `issue_body`, so the new rule would refuse the entry of `tests/fixtures/roadmap_eval/stage/3411-a-what-changes-item-that-names/plan.json`, which copies the criterion of `tests/fixtures/roadmap_eval/stage/3411-a-what-changes-item-that-names/issue.txt:13: The stage check refuses a What Changes item that names a repository path`.
- **Merge the gate change and the refusal into one group.**: One group would hold three source files and two test modules, and a step reads them with the issue, the change and the prompt, which is more than the small step that `budget` sizes. The order of group 1 and group 2 gives the same result with two small steps.
