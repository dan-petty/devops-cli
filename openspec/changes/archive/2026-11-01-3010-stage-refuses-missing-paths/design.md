# Design

## Decisions

- **The tree is `git ls-files -z` of the model clone, read once in a round.** `plan_stage` reads it after the selection, and only when an item is selected. The clone is at the commit that `inspect_checkout` returned, so the files are the files at the staged commit. The earlier check looked at the disk of the clone, which can hold files that the commit lacks.
- **The check is a pure function of the reply and the tree.** `path_problems(groups, tree)` returns one sentence for each missing path. `check_proposal` appends them to its other problems, so the reply goes back once and a second failure stops the item through the existing `stage_invalid` error. No new return loop and no new error class.
- **A group sees the `creates` of the groups up to itself.** The parent folders of a created path count too, so a later group can read the folder. A path in `creates` of a later group is missing, because the work that makes it has not run. The order of the groups stays another issue.
- **The files of the change folder count as existing.** The job writes them in the same commit, so `openspec/changes/<change>/tasks.md` is no missing path. The planner adds the keys of `render_change` to the tree for the check.
- **The paths come from four places.** `reads` and `changes` are paths. In the tasks (`test`, `implementation`, `documentation`) the paths are the words inside the code spans, found with the markdown-it parser of `step_files.py`. In `verify` they are the words of the command. A span or a command is split on white space, so the check cannot raise on a quote, and a word is dropped when it is not a path.
- **A word is a path in two cases.** Its last name ends in a suffix that a tracked file has, or its first folder is a top-level name of the tree. So `tests/security/test_x.py`, `uv_cmd.py` and `src/devops_cli/new_package` are paths. `status/blocked`, `example.com`, `devops_cli.config`, `--strict`, `https://example.com/a.md` and `<change>/tasks.md` are not. The two sets come from the tree, so a new suffix or a new top folder needs no change of code.
- **A location is cut off.** `tests/test_x.py::test_name` and `src/a.py:12-20` are checked as `tests/test_x.py` and `src/a.py`.
- **A glob in `reads` or `changes` passes when some tracked file matches it.** `fnmatch.fnmatchcase` of the standard library does the match. A glob in a code span is no path and is not checked.
- **A folder passes when a tracked file is below it.**
- **The problem lists the files with the same name.** It lists at most 5, sorted, from an index of base names built with the tree. The model then copies a real path. The job never picks one for it, because a guess would hide a wrong plan.
- **The check runs again after a split.** The split reply holds new groups, and the model can bring the old paths back. A failure there is a problem of the reply like the others.
- **The comment loses its note.** The paths in the plan exist or are created, so the comment has nothing to name. `missing_paths`, `StagedChange.missing` and `stage_comment_missing` go away.
- **Only code spans are checked in a task.** The implement step reads the code spans (`named_files`), so a path in plain text is not read by it. The prompt tells the model to write every path in a code span.

## Rejected alternatives

- **Keep the note in the comment.** This is what ran on 2026-10-31. A person merged 25 plans with a wrong path, and the Jobs stopped. Rejected on that evidence.
- **Stop at the first reply.** The model can fix a path when it sees the real name: `tests/security/test_scanner_tool_executor.py` for `tests/test_scanner_tool_executor.py`. One return costs one model call. The issue asks for one return.
- **Replace the path with the one file of the same name.** Two files can share a name, and a replaced path would hide a wrong plan from the model. Rejected: the model decides.
- **`git ls-tree -r <sha>`.** It lists the same files. The spec "A round reads the plans on the default branch once" counts the `ls-tree` commands of a round, and the issue names `git ls-files`.
- **`shlex.split` for `verify`.** It raises `ValueError` on an open quote, and a swallowed error is not allowed. A split on white space with a filter on each word never raises.
- **A regular expression for paths in the free text of a task.** The step reads code spans only, so a path in plain text costs nothing and is not checked. The prompt asks for code spans.
- **A tool for the model to list files.** The model has no tools in the stage call. The evaluation lists the probe of the premise as another fix, planned in its own issue.
