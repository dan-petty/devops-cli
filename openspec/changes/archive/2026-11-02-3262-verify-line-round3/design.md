# Design

## Decisions

1. **Two ends for the criterion.** The parser takes only a top-level heading, because a heading in a list item is never a group of the file. The writer starts each criteria line with a fixed word, because a text at the start of a line is the one place where markdown reads block syntax. Each end holds if the other fails.
2. **Fold in the schema, refuse a mark only at the start of a line.** A folded text on one line is safe after a fixed prefix (`- `, `### Requirement: `, `- **WHEN** `). The few texts at the start of a line (`why`, `existing_tool`, `purpose`, the requirement `text`) need the second rule. A refusal goes back to the model in its one retry.
3. **No check of the rendered headings.** The structure of the reply is the only source of a section. A check of the rendered text would be a second path that must agree with the writer.
4. **`verify` joins lines and keeps spaces.** A command may hold two spaces inside a quoted word. `str.splitlines` ends a line at every character that markdown or Python ends one at.
5. **`validate_assignment` and a note on `group_text`.** An assignment is validated like a reply. `model_construct` skips validation by design in pydantic; the one caller that uses it (`stage_eval_gates`) renders nothing.
6. **Both problems of a command in one run.** The job asks the model once, so a second fault found after the retry stops the item.

## Rejected alternatives

- **Only the parser fix.** Rejected: the text still reads as a block in a viewer of the file, and other parsers (`openspec`) read headings at any place the writer leaves open.
- **Only the writer fix.** Rejected: the parser takes text from every `tasks.md`, including a file that a person wrote with a nested heading.
- **Escape the mark with a backslash.** Rejected: the raw file would show the backslash, and the fixed word is simpler.
- **Refuse a line break in a text.** Rejected: a model that writes a line break means the same sentence, and a refusal costs the one retry.
- **A gate that reads the rendered `spec.md` for a `REMOVED` heading.** Rejected: see decision 3.
