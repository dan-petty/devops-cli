# Design

## Decisions

- **Add the self-acceptance rule to `content_problems` in `src/devops_cli/roadmap/stage_change.py`.**: `check_proposal` calls `content_problems`, and the stage job and the replay both call `check_proposal`, so one rule set judges both paths with no second seam.
- **Apply the rule only when a behavior group changes `src/devops_cli/roadmap/stage_change.py`.**: A behavior group marks added or changed behavior, so the rule reaches a new plan rule and leaves a refactor or a document alone.
- **Accept a group test text that names `StageProposal`, `content_problems` and no problem, in any group of the plan.**: The check is deterministic and a small rewording of a valid plan still passes; the test that the rule asks for is exactly that one.
- **State the same rule in the staging prompt.**: The model reads the prompt before it writes the plan, so it can write the test at once instead of spending one of the two replies on the problem.
- **Add the tests to the existing modules `tests/roadmap/test_roadmap_stage_content.py` and `tests/roadmap/test_roadmap_stage_prompt_rules.py`.**: Both modules already hold the tests of the text rules and of the prompt rules, so the change adds no new file and no mirror folder.

## Rejected alternatives

- **Build the plan's own `StageProposal` in the stage job and run the new rule on it.**: `src/devops_cli/roadmap/stage_change.py` shows that the rule the plan proposes does not exist at staging time, so the stage job has no rule to run on the plan.
- **State the rule in the staging prompt only, with no gate.**: `content_problems` is the function that `check_proposal` calls, and the prompt gives guidance only, so a plan can still pass every gate and refuse itself.
- **Trigger the rule on any change to `src/devops_cli/roadmap/stage_change.py`, whatever the kind of the group.**: `GroupKind` in `src/devops_cli/roadmap/stage_change.py` tells a behavior group from an other group, and an other group is a refactor or a document that adds no rule, so the rule would demand a test for work that adds no rule.
- **Require the exact sentence that the issue gives as the self-acceptance test.**: `tests/roadmap/test_roadmap_stage_plan.py` shows tests that assert a substring of a message, so an exact sentence match would fail a valid plan after a small rewording.
