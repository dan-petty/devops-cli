# Design

## Decisions

- **Add the rule to `content_problems` in `src/devops_cli/roadmap/stage/stage_change.py`.**: `check_proposal` and the replay both call this function, so one rule judges the stage job and the replay, and one test seam proves both.
- **Recognize a test function in a code span only: the last segment of the span, after the last `::` when there is one, starts with `test_`, with optional parentheses.**: A planner writes the function name or the path with the function name such as `tests/roadmap/stage/test_sample.py::test_conditional_group`, and a bare test file path proves no function, so a conditional group cannot pass with one.
- **Cover only an other group whose every changed path starts with tests.**: The rule targets a group that can only fix a test. One path outside tests gives the group real work, and a behavior group has source work of its own.
- **Read the refusal sentence from the messages table and format it with the title of the group.**: Every other content problem reads its sentence from that table, and the title tells the model which group to fix.
- **State the same rule in the planner prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` and prove it in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.**: The model needs the rule before it writes the plan, so the check is not the first signal, and the prompt test keeps the rule when a later edit changes the prompt.

## Rejected alternatives

- **Refuse the group in the schema of `StageGroup`.**: The schema sees one group and no plan context, and the stage already returns a content fault to the model for one correction, which the schema path does not do.
- **Refuse the group in `form_problems`.**: `form_problems` in `src/devops_cli/roadmap/stage/stage_form.py` judges the shape of the task lines, not the meaning of a test-only group.
- **Accept any code span that names a path under tests.**: A test file path proves no test function, so the group that the plan of #3409 held would pass the rule unchanged.
- **Accept a `test_` word outside a code span.**: The prompt asks for the test function in a code span, so a bare word is no exact reference and the check would accept prose.
- **Cover every other group, whatever its paths.**: A document or manifest group has no test function to name, so the rule would refuse valid work.
