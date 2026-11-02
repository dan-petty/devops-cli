# Design

## Decisions

1. **The writer renders a `Verification:` line, and the parser stays as it is.** The parser, `openspec/config.yaml`, the spec `roadmap-implement-step` and the committed plans of the people use this one form. The change makes the writer agree with it.
2. **The words "fails on the base" and "passes" go on the `Verification:` line.** The line is then the claim that the step checks: the command, and what it must do. A reader of `tasks.md` sees the same words as before.
3. **The messages hold the line break.** A task is the work, a line break and the line. `group_text` already writes `- [ ] n.m ` and a line end around each task, so it does not change, and the messages stay the one place that holds the text.
4. **The task of a manual check has no line.** `stage_task_process` has no command to run, and the step runs only a code span of a `Verification:` line.
5. **The check of the documents task is a line too.** `uv run devops ci docs` was a code span in the sentence of that task, and the step did not run it either.
6. **The existing folders stay as they are.** They are committed text. Rewriting them is a second change, with its own review.

## Rejected alternatives

- **Teach the parser to read the code span after "verify that".** Rejected: the parser would read two forms, and the phrase is free text that a person or a model edits. The issue prefers the first way, and `step_files.py` documents the line.
- **Write the line in the same paragraph as the task.** Rejected: `_task_of` reads the first inline token of the item as the task and the later ones as lines. Text in the same paragraph is one token, so the parser would read no command (Feasibility 5).
- **Rewrite the folders that the job wrote before.** Rejected: acceptance criterion 4 of the issue says this change does not.
