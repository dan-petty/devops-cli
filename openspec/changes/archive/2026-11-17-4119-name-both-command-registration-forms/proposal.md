# Proposal

## Why

The stage prompt does not state how a CLI command registers its name. In pull request #4112 for issue #3296, the planner wrote a check for a new command that searched only for a double-quoted string, such as `f'"{word}"'`, in the command file. Many commands under `src/devops_cli/commands/` register by a function name and not by a string literal: `src/devops_cli/commands/workspace.py` puts `@app.command()` above `def add(`, and `src/devops_cli/commands/branches.py` puts `@app.command("sync")` and `@app.command()` above `def update(`. A check that searches only for a quoted literal misses the function form, so it treats an edit to an existing command as a new command and fails the plan and the implementation checks (#4119).

## What Changes

- The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` states that a command registers its name in one of two forms: `@app.command("name")` registers the string literal, and `@app.command()` or `@<group>.command()` registers the function name below the decorator.
- The prompt states that a check for a command name is a negative search for the bare name, such as `! git grep -n <name> src/ tests/`, because that search finds both `@app.command("<name>")` and `def <name>(`. A search for the quoted literal only misses the function form, and the negative-search grammar already refuses a quoted literal.
- The `roadmap-stage/plan-text` capability gains the requirement that names both forms and the bare-name search. The prompt is the product text that the planner reads, so it carries a delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/plan-text`: The stage prompt names both command registration forms

## Impact

- Prompts: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

## Feasibility

- The premise holds in the code at the staging commit. `src/devops_cli/commands/workspace.py` puts `@app.command()` above `def add(` and passes no literal to the decorator, and `src/devops_cli/commands/branches.py` puts `@app.command("sync")` and `@app.command()` above `def update(`. A search for a quoted literal only therefore misses the function form.
- The stage form already refuses a quoted literal: `form_problems` in `src/devops_cli/roadmap/stage/stage_form.py` reads the `! git grep` literal as letters, digits, spaces and the signs `_ . : / = @ + , # % ~ -`, so a `"` is refused, and the prompt states that grammar.
- The stage check already refuses a negative search with a surviving hit, so a bare-name search over a path that holds `def <name>(` is refused without new code. The refine job recorded that the AST detector that the issue proposes adds no refusal, and no test can trigger it.
- The test that proves the rule reads the prompt text, in the same way as the other prompt rules of `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.
- The check is `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, which runs the new case beside the existing prompt rules.
- The second check is `uv run devops openspec check`, which validates the added requirement and its scenarios.

## Existing Tool Considered

`griffe` (`https://pypi.org/project/griffe`, ISC, maintained) parses decorators and function names, and the refine job considered it. It holds no roadmap-stage rule for which decorators count as command registrations, no stage-verification refusal and no prompt text. The refine job recorded that the AST detector adds no refusal: a negative search for the bare name finds `def add(`, so the existing no-hit rule already refuses the plan, and a quoted literal is already refused by the negative-search grammar. This change adopts no parser and builds no code. It deletes no code. The written cost to build an AST detector, keep it and fix it until it matches the grammar rule is about 12,000 tokens and about 3 hours, with no new refusal and no test that can trigger it, so the change updates the prompt only.

## Dependencies

None.
