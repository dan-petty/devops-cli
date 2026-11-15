# Design

## Decisions

- **Use the existing `DefectType.VERIFY_FORM` with the gate `paths`, and add no enum value.**: One gate catches one type, and `test_the_gates_and_the_pending_gates_cover_each_type_once_but_those_no_gate_judges` requires every member to be caught, pending or unjudged, so a new member would need gate code that this issue forbids.
- **Label the recorded case `2576-a-token-that-argo-cd-refuses` and record no new case.**: Group 1 of its plan is a behavior group whose verify runs a test module that the group names in none of its lists, and the case already holds the plan, the facts and the issue text.
- **Change the case and the pinned counts of both replay modules in one manifest group.**: `tests/roadmap/stage/test_roadmap_stage_eval_gates.py` and `tests/roadmap/stage/test_roadmap_stage_eval_command.py` both pin the totals, so the case change alone leaves both modules red, and a second group that only repairs a broken test is refused; one step keeps the folder green.
- **Give the defect the message `which runs no test module of the group`.**: `_explains` matches the message as a substring of a problem of the gate, and those words sit in the template of the rule, so the defect is caught without copying the whole command.
- **Leave the defect's `paths` empty.**: The rule prints the module in backticks only when the group names a candidate test module, and group 1 names none, so a path in the defect would never appear and the defect would be missed; an empty tuple judges the message alone.
- **Keep the recorded plan and facts of the case unchanged.**: The replay reads the case files and no git, and the rule refuses the plan as it stands, so the change adds one defect record and moves the counts.

## Rejected alternatives

- **Add `VERIFY_TEST = "verify_test"` to `DefectType` and label the case with it, as the issue proposes.**: `tests/roadmap/stage/test_roadmap_stage_eval_gates.py:def test_the_gates_and_the_pending_gates_cover_each_type_once_but_those_no_gate_judges` requires every member to be caught, pending or unjudged; a new member would need a gate that catches it, which the issue forbids, or the `none` gate, which fails no replay.
- **Record a new reject case for the unnamed verify test.**: `tests/fixtures/roadmap_eval/stage/2576-a-token-that-argo-cd-refuses/plan.json:141:"verify": "uv run devops ci test tests/test_argo_credentials.py",` already holds the plan that the rule refuses, so a new case copies a plan, its facts and its issue text.
- **Wait for #3463 before labeling the case.**: `read_issue` of #3463 gives closed (completed) and Released in v0.138.0, and `git_log` of `src/devops_cli/roadmap/stage/stage_form.py` gives `65268d6f 2026-11-14 fix(roadmap): refuse a behavior verify that runs no test (#5684)`, so the rule is at the staged commit.
- **Record the test module in the defect's `paths` so the gate must name it.**: `src/devops_cli/roadmap/stage/stage_eval_gates.py:420:return holds_message and _names_every_path(problems, defect.paths)` requires each path in backticks in a problem, and the rule prints `a test module of the group` for group 1, so such a defect would be MISSED.
