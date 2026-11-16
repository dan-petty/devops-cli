# Design

## Decisions

- **Fix the criterion model, not the comparison.** `StageCriterion` is the input of the writer. It folds its texts with the one fold of the writer and keeps no reason for a group entry, so the proposal holds the facts that the files hold. `file_facts` and `read_back_problems` do not change their rule. `StageGroup` already folds its texts in its schema (`Text`, `Line`), so a criterion now follows the same pattern.
- **A group entry keeps no reason.** No code reads the reason of a group entry, and the line `Group <n>: <criterion>` has no place for one. A refusal would cost a model round for a value that no reader uses.
- **One fold.** `JS_SPACE` and `one_line` move to `stage_criteria.py`, which `stage_change.py` imports. The writer, `StageCriterion` and `acceptance_criteria` then fold U+FEFF as `openspec` does.
- **The reader reads the form that the writer writes.** The writer puts the documents step only at the end of a documents task, and only when `regenerates_documents(changes)` is true. The reader cuts the step in the same case. The second task of a `behavior` or `manifest` group is its work as a whole. No writer version put the documents step in that task.
- **The record of a difference.** `read_back_differences` goes into a model by its first differing field, into a list by its first differing entry, and into a text by its first differing character. A text value starts 40 characters before that character. Each value is `repr` of the value, so `''` and `None` differ in the log. The mask runs on the whole text before the index and the cut, so a cut does not leave a part of a secret that the mask does not know.
- **Where the values go.** The stage Job log has one warning line for each difference. The details of `RoadmapPlanReadBackError` hold the same records. The message and the comment at the defect limit keep only the fact names (#5214).

## Rejected alternatives

- **Write the reason of a group entry into `tasks.md`.** It changes the form of the plan files, the implement reader of the criteria and the spec of the section for a value that no step reads.
- **Drop the reason and fold the texts in `file_facts`.** It changes the comparison and leaves the proposal with facts that the files do not hold. The issue asks for no looser comparison.
- **Change the prompt to ask for `null` in a group entry.** A model can still give a string, and a prompt change needs stage eval scores.
- **Fix the comma split of a `pending-person` line here.** It needs a new line form, a change of the implement reader of the criteria (`_parse_tasks_criteria`) and a reader for the old form. The three items do not use this form. #5956 covers it.
