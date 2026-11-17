# Design

## Decisions

- **State both registration forms in the stage prompt.**: The prompt is the only document that the planner reads, so the rule belongs there. The rule names `@app.command("name")`, `@app.command()`, `@<group>.command()` and `def <name>(`.
- **Tell the planner to check a command name with a negative search for the bare name.**: The bare name matches the quoted literal `@app.command("<name>")` and the function form `def <name>(`. The stage check already refuses a search with a surviving hit, so no new code is needed.
- **Add the rule to the `roadmap-stage/plan-text` capability.**: That capability already holds the other prompt rules, such as "The stage prompt names the security rule" and "The stage prompt asks for a count of a claimed set".

## Rejected alternatives

- **Add an AST detector to the stage verification.**: The refine job recorded that it adds no refusal. A negative search for the bare name finds `def add(` in `src/devops_cli/commands/workspace.py`, so the existing no-hit rule already refuses the plan, and no test can trigger the detector.
- **Change the negative-search grammar to accept a quoted literal.**: The grammar refuses a `"` on purpose, and the bare name already matches both forms, so the change adds nothing.
- **Search the quoted literal only.**: It misses the function form, and the negative-search grammar refuses a quoted literal.
