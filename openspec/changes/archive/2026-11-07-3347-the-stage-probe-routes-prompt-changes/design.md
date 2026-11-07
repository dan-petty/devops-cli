# Design

## Decisions

- **Add the rule to `content_problems` in `src/devops_cli/roadmap/stage/stage_change.py`**: The function already collects every content problem of a reply, and both the stage job and the replay run it through `check_proposal`, so the planner gets the problem in its one retry.
- **Name the prompt by its prefix `src/devops_cli/ai/tasks/roadmap_stage_` and its suffix `.md`**: The repository holds two prompts of that family, and a prefix names both without a list that a third prompt would miss.
- **Give one problem for a group whose `verify` names no prompt-rule test, and no second problem when the same group gives `process` instead**: A group with `process` has no `verify` at all, so one sentence names the prompt path and the test path and the model fixes both in one edit.
- **Test the rule in `tests/roadmap/stage/test_roadmap_stage_content.py`**: That module already holds the tests of `content_problems`, including the self-acceptance rule, and the prompt-rules module tests the agreement of the prompt with the rules.
- **State the rule in both planner prompts and pin the sentence in the prompt-rules test**: The model follows the rule before a retry, and the pin fails when the prompt and the rule drift apart.

## Rejected alternatives

- **A separate linter command that reads a plan and reports the prompt-rule problem**: `src/devops_cli/roadmap/stage/stage_change.py:def check_proposal` already returns every problem of a reply to the model, so a second path adds a command whose result the planner never reads.
- **Refuse a prompt change only in the planner prompt, with no check**: `src/devops_cli/ai/tasks/roadmap_stage_change.md` shows that the prompt cannot refuse a reply, and the plan of #3265 in the merged pull request #3306 shows that a prompt change cited no prompt-rule test.
- **Require the prompt-rule test in `reads` of any group of the proposal, not in the group that changes the prompt**: `tests/roadmap/stage/test_roadmap_stage_content.py` shows that a plan can hold several groups, so a separate group could satisfy the rule while the prompt edit itself reads and verifies no prompt-rule test.
- **Keep the issue's path `tests/roadmap/test_roadmap_stage_prompt_rules.py` in the check**: The probe reads "The path `tests/roadmap/test_roadmap_stage_prompt_rules.py` is no file at the root of the staging commit", so a check on that path would refuse every compliant plan and accept no plan that names the real module.
