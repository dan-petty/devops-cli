# Design

## Decisions

- **Put the rule in `content_problems` in `src/devops_cli/roadmap/stage_change.py`, beside the placeholder and message-file rules.**: `check_proposal` calls `content_problems`, and the replay of `stage_eval_gates` calls `check_proposal`, so one rule set judges the job and the replay.
- **Compare the work text that each task states, and mirror the order of `_task_texts`: the test task, the implementation task and the documentation task of a group.**: The number of a task in `tasks.md` comes from that order, so the problem names the numbers that the file shows.
- **Normalize each work text with `" ".join(text.split()).casefold()` before the comparison.**: The model can change spacing or case without changing the work, and the check must still refuse it.
- **Keep the `Verification:` line, the `process` check and the fixed `uv run devops docs generate --sync-readme` suffix out of the comparison.**: Two tasks may share a command and stay different tasks, and a documentation task repeats a work text only when its paragraph is the same.
- **Format the group phrase from the catalog, with one entry for one group and one for two groups, and one entry for the problem itself.**: The single-group case reads as `group 2` and the two-group case as `groups 2 and 4`, and no user-facing English sits in the code.
- **Add the tests to `tests/roadmap/test_roadmap_stage_content.py`.**: That module already tests the content rules of `check_proposal`, so the new rule belongs with them.

## Rejected alternatives

- **Parse the rendered `tasks.md` and compare its task lines.**: `_task_texts` in `src/devops_cli/roadmap/stage_change.py` already renders the tasks from the group fields, so a second parse can drift from the renderer.
- **Compare the whole rendered task line, `Verification:` line and docs command included.**: The `_task_texts` code appends the fixed `REGENERATE_DOCUMENTS` command and the `verify` command to a task, so equal work would look different and a duplicate would pass.
- **Refuse two tasks that share a verification command.**: The acceptance criteria of #3456 require the check to accept group 3 task 3.1 and task 3.2 that differ in work text and share a `Verification:` command.
- **Add a fuzzy match of task text.**: A fuzzy match refuses distinct tasks, and `src/devops_cli/roadmap/stage_change.py` compares text with no such dependency today.
- **Hard-code the problem text in `stage_change.py`.**: `src/devops_cli/lang/en/messages.py` holds every `stage_problem_*` entry that `content_problems` formats, so the text belongs there.
