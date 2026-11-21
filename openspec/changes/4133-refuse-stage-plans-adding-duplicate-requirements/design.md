# Design

## Decisions

- **Give the planner the scenario names of each requirement and the requirements that the active changes add or modify, in the `read_spec` answer for a capability.**: The comment of 2026-11-13 by dan-petty names this: with the scenarios of the active changes in that context, the planner sees the requirement to modify before it writes a new one, and the plan review keeps the semantic check.
- **Read the delta file of each active change with a plain file read, and not `openspec show` for each change.**: One `openspec show` run per change would start 46 subprocesses inside one tool answer, and the delta file holds the same requirement and scenario headings.
- **Read the active changes of the capability that the tool is asked about, and not of every capability.**: A tool answer stays inside its cap, and the planner reads the capability that it plans to change.
- **Keep the semantic check of a paraphrase in the plan review of the stage job, and add no gate that compares the text of a requirement.**: The measurement of 2026-11-13 shows that each text signal either misses the two copies of the incident or refuses merged plans that hold no duplicate, and ADR 0005 keeps a finding from a model out of a gate.
- **Leave the entry of a capability in the model input to #3246, and add the scenarios and the active changes to the tool answer only.**: #3246 moves the purpose and the requirement names out of the request and into the `read_spec` answer, so a second edit of that entry would contradict it (ADR 0010).
- **Add no problem text to `MESSAGES.roadmap`.**: No gate reports a duplicate, so the change reports no message and no test asserts one.
- **Leave out a requirement under the removed section of a delta.**: A change that removes a requirement holds no requirement to modify, and the planner would name the wrong change.

## Rejected alternatives

- **Refuse an added requirement whose scenario name, WHEN text and THEN text equal those of a base requirement or of a requirement of another active change, in the spec delta gate.**: The measurement of 2026-11-13 reports "| Equal normalized WHEN and THEN text of one scenario (the design) | No | 0 |": the THEN text of each copy of the incident differs from its original, so the rule refuses no copy.
- **Refuse an added requirement whose normalized scenario name and WHEN text equal those of a base requirement or of a requirement of another active change.**: The same measurement reports "| Equal scenario name and equal WHEN text on one scenario | Yes, 2 of 2 | 4, in 2 plans |": it refuses two merged plans that hold no duplicate.
- **Refuse an added requirement whose normalized title equals the title of another requirement of the same capability.**: The same measurement reports "| Equal normalized title (the design) | No | 0 |": a synonym title passes, so the defect stays.
- **Report the duplicate from `devops openspec check` through a new check of the OpenSpec gate.**: Such a check would compare the same text as the gate, so it refuses the same merged plans and misses the same copies; `src/devops_cli/openspec/overlap.py:40:return ("show", change, "--json", "--deltas-only")` shows that the existing overlap check reads the deltas of a change and judges only the MODIFIED, REMOVED and RENAMED operations.
- **Call a model or an embedding similarity inside the gate.**: ADR 0005 keeps findings from tools: a finding exists only when a pinned tool, an advisory database, a confirmed version fact or a tested rule produces it, and the replay calls no model.
- **Add a golden-set case of a plan that copies a scenario.**: No plan of the incident holds a copy under equal text, so the case would be written to match the rule; the measurement shows that the two copies differ from their originals in the THEN text.
- **Read each active change with `openspec show <change> --json --deltas-only` inside the tool answer.**: `src/devops_cli/openspec/overlap.py:40:return ("show", change, "--json", "--deltas-only")` starts one subprocess per change, and the staged commit holds 46 active change folders, so one answer would start 46 subprocesses.
