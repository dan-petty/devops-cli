# Design

## Decisions

- **Put the refusal in `content_problems` instead of a new gate.**: The rule judges the text of the plan, which is what `content_problems` collects, and the self-acceptance test of a plan-check rule asserts that `content_problems` returns no problem.
- **Match each trigger as a case-insensitive text in the plan's Changes, group paths and task texts.**: A task can name a credential or an egress rule with no path, and a code span of `what_changes` can name `SECURITY.md` without a group path.
- **Fire on the first trigger in list order and name it in the refusal.**: The issue requires the message to name the matched path or word, and one problem is enough for the author to add the section.
- **Give the `security` field the empty string as its default.**: A plan with no trigger writes no section, so `_design_file` keeps its current output and no existing plan changes.
- **Hold the trigger paths in a tuple subclass whose docstring states the reason of each entry.**: Criterion 3 asks for a named constant with a docstring, and `SECURITY_TRIGGER_PATHS.__doc__` then holds that text for the test to read.
- **Add a golden case of the security refusal to the replay.**: `stage_change.py` and the prompt are trigger paths of the stage measure, so the replay must show that the new rule stops a known-bad plan and that no accepted case regressed.

## Rejected alternatives

- **Let the model edit `design.md` directly.**: `src/devops_cli/roadmap/stage/stage_change.py:def render_change` writes `design.md` from the proposal after the check, so no model edit of that file exists.
- **Require three fixed labels in the security section.**: The issue names no labels, and a fixed label set refuses valid prose that answers the three questions in its own words.
- **Add the rule as a new `ProposalGate` member.**: The self-acceptance rule of the plan check names `content_problems`, so a separate gate would leave the plan's own acceptance test judging no rule.
- **Scan the whole proposal for trigger words.**: `why` and `feasibility` quote the issue, and the issue itself names `credential` and `SECURITY.md`, so a plan that changes neither would be refused.
- **Use glob patterns for the trigger paths.**: A glob can match no file and hide a missing path, and criterion 3 asks for a test that fails when a path does not exist.
