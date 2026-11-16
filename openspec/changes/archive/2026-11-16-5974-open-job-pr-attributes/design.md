# Design

## Decisions

- **The rules of CI are called, not copied.** The type rule is `hidden_type_problem` of `release_title.py`, which the `Semantic PR title` workflow runs. The form rules are `title_problems` and `plan_body_problems` of `pull_form.py`. The action inputs of the workflow (the summary pattern and the scopes) are static, and a test holds them equal to `SUMMARY_MAX_CHARS` and to the labels file. So no rule lives only in a workflow file, and the change moves none.
- **A deterministic type.** For a hidden type with runtime code, the step writes `feat` when the diff adds a runtime file, else `fix` (`release_type`). The two person decisions of 2026-11-16 agree with this rule: #5920 added a module and got `feat`, #5940 changed messages only and got `fix`. When the config hides that type too, the first shown type stands in. No model is necessary.
- **The step fixes what a rule decides, and refuses the rest.** It joins the title on one line, removes an undeclared scope and changes a hidden type. A long summary or a wrong body has no fix that keeps the meaning, so the step raises `RoadmapOpenRefusedError` with every problem and writes nothing.
- **A delivery body needs no `Change:` line at open.** The first push of the implement job opens a draft with the body `Closes #<issue>` and a note, and replaces it after the archive. `body_problems` holds the whole form at ready (`merge_readiness`). The open step holds the keyword rule and the length.
- **A missing file is no rule.** A repository with no `release-please-config.json` hides no type, and a repository with no labels file gets no scope check. Another failed read raises, so the step never writes an unchecked attribute.
- **The diff is read once.** A caller that read the diff passes its files in `OpenRequest.changed`. Else the step reads the compare endpoint only when the type is hidden.
- **The row takes only recorded delivery branches.** A candidate is the branch that `implement.branch` of an open item names, so the row never opens a branch of a person. The row leaves an item that a Job holds, a stage orphan (`stage.pending`) and a stopped item. A head that GitHub associates with a pull request, open or closed, is not opened again: a person who closed it decided.
- **Plan branches stay with stage.** The stage job records `stage.branch` after it opens the plan pull request, and it removes its orphan branches (#4051). A later change can move the orphan of stage to this row.
- **Mode.** `roadmap.open.mode` starts in `plan`, as ADR 0021 section 8 rule 5 asks for each new row. Of the code defaults of the step rows, `fix_plan` and the model tier of `fix_conflict` are `plan`.

## Rejected alternatives

- **An action of the watch row.** The watch row reads open pull requests only, and a branch with no pull request is not in its read. A list of the branches through the REST API every 3 minutes costs quota. A row with a clone reads the heads with git.
- **A model task to choose the type.** A new task key needs the image first (`AITasksConfig` is `extra="forbid"`), and the rule above decides each known case.
- **Edit `_delivery_metadata` of the implement job.** It sets the final delivery title with `update_pull`, outside the open step. The item asks to leave the two jobs to #5029 and #4719.
