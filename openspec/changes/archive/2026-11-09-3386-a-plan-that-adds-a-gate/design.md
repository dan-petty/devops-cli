# Design

## Decisions

- **Apply the gate defect rule when a group changes `src/devops_cli/roadmap/stage/stage_eval_gates.py` or `src/devops_cli/roadmap/stage/stage_change.py`**: Both gate files hold the gate definitions and the plan content checks.
- **Run the rule in `content_problems`**: `check_proposal` and `_content_gate` both call this function, ensuring the stage job and the replay share the same check.
- **Match defective text via code spans in `feasibility`**: A code span is the standard plan representation for quoted code or identifiers, and tests can verify it offline.
- **Require the matching gate group `test` to contain the code span and the phrase `fails on the base`**: This asserts that the test specifically verifies the defect against the base commit.
- **Require a stated non-goal when gate test text holds `skip` or `skips`**: If the test notes a skipped case, the plan must document it as a non-goal in decisions, rejected alternatives, or spec deltas.
- **Define messages in `RoadmapMessages` in `src/devops_cli/lang/en/messages.py`**: All roadmap error messages reside in this catalog.

## Rejected alternatives

- **Only check `stage_eval_gates.py`**: A gate check can also change in `stage_change.py`, as the content rule itself does.
- **Require free text match instead of code spans**: Free text is brittle against formatting and wording differences.
- **Always require a non-goal**: Gate plans that do not skip cases would suffer false refusals.
