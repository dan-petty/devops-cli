# Design

## Decisions

1. **Fold the texts in the schema, and add no gate on the rendered text.** The writer emits a `Verification:` line only from `verify` and from the documents task. With every text on one line, no other line can come out, so a second check of the rendered text would test what the schema already makes impossible. The round trip test with a line break in each field pins this.
2. **Fold, and do not refuse.** `Process` folds already. A model that puts a line break in a sentence meant the same sentence; a refusal costs the one retry of the job for no gain.
3. **Refuse a backtick in `verify` at the gate.** A backtick changes the command (the code span ends), so folding would not keep its meaning. The gate sentence goes back to the model in the one retry, as the other `verify` problems do.
4. **The `reason` of a criterion is folded when written.** The criterion is folded there already. The schema of `StageCriterion` lives in `stage_criteria.py`, and the text is only a risk where it enters `tasks.md`.
5. **The clause of finding 5 is in a scenario.** A requirement over 500 characters makes `openspec validate --strict` warn, and the check fails.

## Rejected alternatives

- **A gate that renders the group and checks each `Verification:` line.** Rejected: see decision 1. It adds a second path that must agree with the writer.
- **Refuse a line break in the texts.** Rejected: see decision 2.
- **Write the span with a fence longer than any backtick run in `verify`.** Rejected: the parser reads the span, but a command with a backtick is a shell substitution, and the step runs no shell. No plan needs one.
