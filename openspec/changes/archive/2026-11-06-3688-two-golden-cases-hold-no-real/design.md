# Design

## Decisions

- **Fix the data of the case of #3372, and leave out the cases that read no commit.**: The case of #3372 has a real merge commit, so its two fields are wrong data. The cases of #3411 and #3331 describe a plan that no merge made, so no commit can hold them. Another commit would make the case read a tree that never held that plan.
- **Take the parent of the merge commit as `base_commit` of #3372.**: The set states this rule and 41 of 45 cases follow it (see Feasibility). The short hash in the old data points to a later commit, which was the head of `main` when the case was written.
- **Name the null object id `NO_COMMIT` and keep it in the data.**: The case files keep their form and the loader keeps `str`. A JSON `null` would make `base_commit` optional, and each reader (`checkout_at`, `ToolboxClient`, `plan_item`) would need a check for `None`. One property, `has_commit`, holds the rule once.
- **Apply the rule in one function, `cases_with_commit`, after `select_cases`, in both commands.**: The same call gives the cases to run, the names to report, and the count for the title and for the dry run. A rule inside `run_cases` and `evaluate_cases` would leave the dry run and the title with the wrong count.
- **Read no git in the rule.**: The spec of the dry run says it makes no request to git, and the rule must give the same list in a dry run and in a live run. A hash that names no commit in this repository is an error of the data. The test of the set holds it. A repository without the commit (a shallow clone, or another `--source`) is an error of the run, and it ends its case as `failed`.
- **A left-out case does not change the exit code.**: The case is not run, so it did not fail. The report names it, so nobody reads a smaller set as the whole set. The exit code 1 stays for a case that failed.
- **When no selected case holds a commit, raise `ConfigurationError`.**: A run of no case prints an empty score that looks like a result. The error names the cases and tells the user to pick another.
- **Keep the replay as it is.**: The replay reads the facts of the case and no git (spec), so a case with no commit replays like any case.
- **Catch `GitOperationError` in `run_case` and end the case as `failed`.**: `run_case` already ends a case for a failed model call, a refused plan and a failed tool. A checkout that git refuses is the same kind of event: one case cannot run. Without the catch, one case loses the finished cases and the spend of the run. The reason of the case is the text of the git error with credentials masked.
- **Put `left_out` on the two score objects.**: The renderers and the JSON writers already take the score. A new field with an empty default keeps their call sites, and the report of a run with no left-out case keeps its text.
- **Test the set with git.**: A test runs `git cat-file -e <hash>^{commit}` for each `base_commit` and `merge_commit` in this repository. It skips in a shallow clone, where old commits are absent. CI checks out the full history for the test jobs.

## Out of scope

- A real commit for the cases of #3411 and #3331. A plan that no merge made has no staging commit, and the choice of a nearby commit would be a guess.
- A check of the commits at the start of a live run, before the first model call. It would need git in the dry run, which the spec forbids, and `run_case` already ends the case that git cannot check out.
