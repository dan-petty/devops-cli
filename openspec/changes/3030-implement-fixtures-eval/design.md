# Design

## Decisions

- **A fixture is a folder.** `case.json` holds the facts, `issue.md` the body of the issue, `plan/` the three files that a step reads, and `results/` the recorded diffs. The loader reads all of it and checks it against the schema and against the plan, so a fixture that names a path the plan does not name fails at load, not at run.
- **The paths of the `Changes:` line are data.** The plans on `main` write that line in more than one form (`Changes: the same two files`, or a list of code spans). A parser of the line would fail on the second form. The fixture lists the paths, and the loader checks that the plan names each of them in a code span of the group.
- **Six properties, two kinds.** `tests_kept`, `diff_scope`, `no_scratch` and `tasks_ticked` come from a diff and the plan alone. `tests_pass` and `verify_passes` run commands in a tree. The first kind runs everywhere, also in CI with no git history. The second kind needs a clone and `uv run`, so it runs in a live run and with `--run-commands`.
- **The diff is the one interface of the offline properties.** A live step that is done gives `git diff <start> <commit>`. A stopped step gives `StepOutcome.diff`. A recorded result is a diff file. All three go through the same four functions.
- **`diff_scope` allows the `tasks.md` of the change.** The step ticks tasks there. Any other path outside the `Changes:` list fails the property.
- **`no_scratch` finds an added file at the root of the repository, under `.data/`, or with a scratch suffix** (`.bak`, `.orig`, `.rej`, `.tmp`). A file that the `Changes:` list names is never scratch. The patterns are constants, matched by `pathspec`.
- **`tests_kept` compares the test names on the removed lines of a diff with those on the added lines, for each Python file under `tests/`.** A deleted file loses every test that its removed lines define. A test that moves inside its file is kept. A test that moves to another file is lost, as in the step. The fixture can allow a lost test by `path::name`, for a deletion item whose dead code had tests. The check reads names and known limits are those of `implement_test_names`.
- **`tasks_ticked` applies the hunks of the `tasks.md` to the plan text.** The hunks replace the source lines with the target lines, and the check refuses a hunk whose source lines differ from the plan. Then `parse_task_groups` tells whether every task of the group is ticked.
- **The scratch clone is a local clone of the checkout at the base SHA.** `git clone --local --no-checkout`, then `git checkout`, then removal of the remote and a local identity. Nothing can push. The plan folder of the fixture is written over the folder in the clone and committed, so the step starts clean at a commit that holds the plan the fixture records. The folder is a temporary directory and goes away after the run.
- **The item comes from the fixture.** `run_step` reads `store.item(number)` once. A small protocol `ItemReader` replaces the type `RoadmapStore` on that parameter, and the fixture answers it. The run makes no GitHub request.
- **The step runs through `run_step`.** That is the path of the Job, with its prompt, tools, limits and exit checks. The eval adds no second agent.
- **`tool_calls` is a field of `StepOutcome`.** It is the count of tool calls in the replies of the turns, the sum that `_resend_after` already computes for the limit.
- **The report lists, for each fixture, the status of the step, the properties with pass, fail or skipped, the tokens in and out, the requests, the tool calls, the wall time, and the first failed property with its detail.** The JSON report holds the same fields and is written under `eval/implement/` of the data directory.
- **The group `devops roadmap eval` is its own module.** `commands/roadmap_eval.py` defines the Typer app and nothing else. Each command is a module that registers itself on that app, and `commands/roadmap.py` adds the group once and imports the modules of the commands.
- **`--check-only` exits 1 when a recorded result does not behave as recorded.** The command then proves the checker. A live run exits 0 when it ran, because a failed property is a measure, not an error of the command.
- **`--dry-run` lists the fixtures and the model requests of the steps, and makes no request.** The command is classified `request-plan`.

## Rejected alternatives

- **Read git at test time.** A replay in CI cannot assume the pinned SHA. The tests read recorded diffs, and only the live run and `--run-commands` clone.
- **`git apply --numstat --summary` for the file facts.** It gives paths and additions, but not the names on the removed lines, so it cannot tell a lost test. `unidiff` gives the lines.
- **The parser of `review/diff.py`.** It returns the added lines and the hunk ranges. It has no removed lines and no added-file flag. Adding both would grow a second parser.
- **Parse the `Changes:` line.** See the decision above. The two forms in use on `main` show that a parser would need a rule for prose.
- **Rebuild the files from the diff for `tests_kept`.** A hunk holds only a few lines of context, so the pre-image of a file is not in the diff. Full-context diffs would put whole source files in the fixtures.
- **Store the base tree in the fixture.** A tree of this repository has about 4 700 tracked files. A pinned SHA and a local clone replace it.
- **Exit 1 on any failed property in a live run.** The command measures a model. A failed property is its result. Exit 1 would hide the difference between a bad model and a broken command.
- **Add the scratch file rule to `run_step`.** That is a change to the step, which this item only measures. #3007 changed the prompt, and a later item can add a check. This command reports the property, so such a change can show its score.
