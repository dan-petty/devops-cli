# Design

## Decisions

- **Extract the requirement lines with markdown-it-py in `stage_criteria.py`, with the IDs `REQ-001`, `REQ-002` in source order.**: The module already cuts the refine block and parses the lists of the issue body, and a deterministic scan gives a test one stable key to assert offline.
- **List the requirements in the stage request as `requirements`, extracted from the whole `item.body`.**: The plan check reads the whole body, so the model and the check judge the same lines.
- **Map each ID in a `coverage` list of the reply, with a group number or `pending-person` and a reason.**: The validator can name a missing requirement only when the reply holds a stable key for it.
- **Render the coverage lines in the existing `## Criteria` section and read them back in `plan_read._criteria`.**: One section keeps the acceptance criteria and the requirement lines together, and plan-check reads the same section back.
- **Judge the coverage in the replay through a `coverage` gate that skips a recorded plan with no `coverage` key, as the `criteria` gate does.**: A recorded plan holds no coverage list, so the replay cannot judge it, and a `good` case still passes every gate.
- **Refuse a `when` clause that holds a person-intent phrase and no backticked literal, and accept every other clause.**: It refuses the `when its author says so` case and refuses no clause that names a value, a path or a literal.

## Rejected alternatives

- **Parse the issue body again in the validator instead of a list in the context.**: Two parses can differ, and the model would read no list to map. `src/devops_cli/roadmap/stage/stage_criteria.py:def acceptance_criteria` already reads the body once for the model and the check.
- **Add a new `## Coverage` section to `tasks.md`.**: `src/devops_cli/roadmap/plan_read.py:def _criteria` reads one section, and a second section adds a second parser path to keep in step.
- **Judge every recorded plan of the golden set with the new gate.**: `src/devops_cli/roadmap/stage/stage_eval_gates.py:def _criteria_gate` skips a recorded plan with no list, and the recorded plans hold no `coverage` key, so the gate would refuse every `good` case.
- **Refuse every `when` clause with no backticked literal.**: `src/devops_cli/roadmap/stage/stage_change.py:class StageScenario` holds plain text, and a valid clause such as `a plan maps every extracted ID` names a state and no literal.
- **Judge the coverage with a model call.**: The plan check runs with no model, and the replay of the golden set calls no model.
