# Design

## Context

See proposal.md (#3596). A `Verification:` line holds one or more code spans. The step ran all of them, so a prose span stopped the group.

## Decisions

### 1. The mark is `$ ` at the start of the code span

- **Decision**: A code span that starts with `$ ` is a command. The parser removes the two characters. Any other code span is prose.
- **Rejected**: A label such as `cmd: ` in the span. No document or tool uses it, so it adds a private rule.
- **Rejected**: The first code span of the line. A line with two commands would run only the first, and a prose span in first position would still be refused.
- **Rejected**: A span whose first word is an allowed program. The step would never refuse a command, so a marked command that the step refuses could not stop it.

### 2. No mark gives no command

- **Decision**: A line with no marked span gives the group no command. The project keeps no old form (`AGENTS.md`), and the mechanical rewrite of `plan-recheck` adds a marked line to a group with none.
- **Rejected**: Read the first span as a command when no span is marked. It keeps two rules, and a new plan can still have its prose refused.
- **Rejected**: Stop the step on an unmarked line. A merged plan would stop its group until a person edits it.

### 3. The templates write the mark

- **Decision**: `stage_task_test`, `stage_task_pass` and `stage_task_documents` write `$ ` before the command, and so does the task that `implement_amend` adds. `FAILS_ON_BASE` reads the text after the last backtick, so the mark does not change it.
- **Rejected**: Leave the templates. A staged plan would give no command to its step.
