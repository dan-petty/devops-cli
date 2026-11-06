# Design

## Decisions

- **Read the groups with `parse_task_groups` and edit by line number.**: The parser already gives each group and each task with its line, and a re-parse after the rewrite gives a before-and-after comparison of the groups. A line number from the parser keeps every other line as it is. The change adds one field, `line`, to `TaskGroup`, as `GroupTask` has one.
- **Judge the rewritten plan with the same gates and call it `rewrite` only when it passes.**: The report must name a result that a person can act on. `recheck_plans` runs `read_change`, `check_gates` and `openspec validate` on the rewritten files, so `rewrite` means that the plan passes all three.
- **Take the new command from the plan.**: The command is `uv run devops ci test <files>` for the test files of the `Changes:` line, or `uv run devops ci docs` when every changed file is a document. Both forms are the forms that the stage writer uses (`stage_task_pass`, `stage_task_documents`), and both pass `read_verification`. A group with neither gets no line, so the plan stays `new-plan` and the reader says why.
- **Put the line under the first task.**: The plan reader takes the `verify` of a group from its first task. A behavior group gets the `fails on the base` form, as the stage template writes it, and any other group gets the `passes` form.
- **Change a path to a bare name only in a task text.**: A path is a sample path when it is a code span in the first line of a task, the tree lacks it, and no group lists it in `Reads:` or `Changes:` or marks it `(new)`. The paths gate does not read a bare name. The `Reads:` and `Changes:` lines and the `Verification:` lines stay as they are, because a person must decide those.
- **Write only with `--confirm`, and only to the checkout of `--source`.**: The model clone belongs to the jobs, so `--confirm` without `--source` is an error. A file that differs from the default branch stops the write before any file is written, so a local edit is never lost. The git reader strips the white space around a file, so the check ignores it and each written file ends with one line end. The command makes no commit; a person reviews the diff and opens a pull request.
- **Leave the implement job as it is.**: `_plan_reason` already leaves out a plan that fails `check_proposal`, for a staged and for a Planned item, and it gives the first problem to `explain` and to the report. The change adds the Planned test and no code.

## Rejected alternatives

- **Replace lines with a regular expression on the whole file.**: It can not keep the identity of a group or prove that only the named lines changed. `parse_task_groups` can, and the test compares the groups before and after.
- **Ask a model to rewrite the plan.**: The edit is mechanical, and a model adds cost and nondeterminism. A model also could not give the proof that only three kinds of line changed.
- **Report `rewrite` for an attempted rewrite.**: It would call a plan fixed when a gate still refuses it. The in-memory run of all three gates avoids that.
- **Use `plan/needs-fix` for a plan with no way forward.**: `stage_verify.py` line 56 assigns that label to a plan pull request. A merged plan uses the reason of #3393.
- **Guess a command for a group that names no test and no document.**: A wrong command makes the implement step fail on a plan that was only incomplete. The reader error is the better reason.
