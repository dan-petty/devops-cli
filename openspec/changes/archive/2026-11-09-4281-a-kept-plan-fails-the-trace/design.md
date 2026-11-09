# Design

## Decisions

- **Facts in the record.** `PlanFacts` holds `tools` and `paths` as sorted lists of text. `TraceFacts` holds frozen sets, which JSON cannot write. `PlanFacts.of(facts, proposal)` keeps all tool names and only the paths that appear in a line of `proposal.feasibility`, because `_uncalled_path` compares a code span of the Feasibility text with the paths. So the file is bounded by the toolset and by the text of the plan, and no new constant is needed.
- **Absent facts are a miss.** `facts` defaults to `None` so an old record loads. `_Planner._kept` treats a record with `facts = None` as a miss and deletes the file. A pass for such a record would keep the unchecked claims.
- **Facts of a plain client.** A planner with no toolbox client has no trace and its gate is off. It writes empty facts. A hit uses the kept facts only when the client is a toolbox client, so the gate is on or off as it was on the miss.
- **Join.** `_trace_facts` returns the union of the kept facts and the facts of the plan runs of the item. It returns `None` only when both are absent, as before.
- **Model change.** No rule is added. The key holds the model name.

## Rejected alternatives

- **Skip the trace gate on a hit.** The first reply would stay unchecked, and a revision after a hit would pass any claim.
- **Store the whole `RunTrace`.** It holds tool answers of large size. The gate reads only names and paths.
- **A constant for the number of paths.** A cut list refuses a true claim for a reason that the plan text does not show. The text of the plan bounds the list.
