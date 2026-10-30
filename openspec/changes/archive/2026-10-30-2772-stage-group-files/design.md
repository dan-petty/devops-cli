# Design

## Decisions

- **Constraints on the model, not a check after it.** `StageGroup` carries the rules as pydantic constraints. A reply that breaks them never reaches `check_proposal`, and `chat_structured` already sends the violation back. This is the only retry. The change adds no loop. The planner asks for one correction (`max_retries=1`), as the issue says.
- **Two types for a text.** `Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]` types `title` and `verify`. `Sentence` types `test`, `implementation` and `documentation`: it strips the whitespace and the full stops at the end, and refuses a text with nothing left. The rule sits in the type, so the check and the rendering cannot differ, and a text of only full stops goes back to the model. `group_text` calls neither `.strip()` nor `.rstrip()`.
- **A path fits in a code span.** `_repository_path` refuses a backtick and a control character, such as a new line. The line `Reads: ...` and the checkbox list of `tasks.md` are line based, so a path with a new line could add a task, and a backtick could end the span early.
- **The stop reason keeps the count.** The error of `chat_structured` carries the count of violations and no field path, because a path can be a key the model invented and the message reaches logs. The correction request names the path to the model. The change keeps this rule of the client.
- **`creates` marks a new path.** The issue asks for the paths that are "not marked as new", and the reply had no mark. `StageGroup.creates` lists the paths of `changes` that the step makes. A model validator refuses a path of `creates` that is not in `changes`. A path that an earlier group creates counts as known for a later group.
- **The line keeps its two sentences.** The format stays `Reads: {reads}. Changes: {changes}.` The text for an empty `reads` is `none`, a word with no stop. A created path shows ` (new)`. The implement step never parses this paragraph, so the plans written before the change still read.
- **A task has no final full stop.** A task text is a clause that the writer joins to `, and verify that ...`. The `Sentence` type removes the stops at the end of the text, so `0600.` does not render as `0600.,`.
- **The missing paths are a warning.** A path of `changes` that is no file on the default branch and in no `creates` goes to the stage comment as one line. A path in a pull request can be legitimate when the model forgot the mark, so the check never stops the item and never goes back to the model.
- **The check runs on the final groups.** `_settle` reads the groups after the split, so a split group is checked once.

## Rejected alternatives

- **A second retry loop in `_Planner.plan` for the new rules.** `chat_structured` already retries a schema violation and names it to the model. A loop beside it would be a second fix on the first.
- **A check in `check_proposal` for an empty `changes`.** The schema states the rule once and for both the proposal and the split reply (`StageSplit` holds `StageGroup` too). `check_proposal` covers the proposal only.
- **Treat a missing path as a violation.** The model plans new files, and a new file is correct. A hard stop would reject a good plan. Only the paths the model did not mark are a warning.
- **Guess new files from the path.** A rule such as "a path under `tests/` is new" is a hand-rolled heuristic. The model knows which files it creates, and the field asks it.
- **Change the line to a list.** A list per path would make a plan written before the change unreadable by the same code. The line stays one paragraph.
