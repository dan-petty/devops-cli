# Design

## Context

The implement step runs one task group in a checkout. Its exit checks run in a fixed order, and the step commits the group when all of them pass. Before this change, the model had to tick each task, and a missing tick gave one more turn, then a stop. The job already writes `tasks.md` back to its text before the run (`_restore_tasks`), so it can write the ticks itself.

## Decisions

### D1. The job ticks every task of the group after the last exit check

The job ticks each unticked task of its own group after the verification commands, the static checks and the hooks pass. The tick writes the group as it is in the restored `tasks.md`, and the file goes into the index before the commit.

- Chosen: tick after every exit check. A tick then records work that every check judged.
- Rejected: tick after the verification commands only. It ignores `ruff`, `mypy` and the hooks, which can still reject the work.
- Rejected: tick before the checks. It ticks work that may fail, and a stop would then keep a tick for it in the `wip:` commit path.

### D2. A group with no verification command is ticked when its exit checks pass

A group with no `Verification:` line has no command of its own. The job ticks it when the exit checks of the group pass. The exit checks still run, so the work is still judged by `ruff`, `mypy`, the hooks and the test-protection check. The plan rule in `openspec/config.yaml` states this.

- Chosen: tick on the exit checks. The work is kept, and the checks still judge it.
- Rejected: leave the group unticked and stop. It loses the work and repeats the stop of the issue.
- Rejected: refuse such a plan at the stage job. That is a staging rule outside this issue. The stage job still asks each group for a verification command, so the rule is stated for a plan that omits one.

### D3. The prompt keeps the request to tick a task

The issue asks that the prompt no longer request a tick. The work-in-progress keeper (#3054) commits a task only when the model ticked it (`WipKeeper._fresh` in `implement_wip.py`). A prompt without the request would end every `wip:` commit, and a stop would lose all the work of its group again. So the prompt keeps the request. The prompt drops the sentence that promises an extra turn for a missing tick.

- Chosen: keep the request. It is the signal of the keeper, and the job still owns the ticks of the commit.
- Rejected: remove the request and let the keeper tick. The keeper would then run the verification of every task before each model request, which costs more than the stop it avoids.

### D4. The test-form check of #3451 is a later criterion

The issue asks that a task that the test-form check of #3451 refuses stay unticked. That check is absent from `origin/main`. This change builds no predicate seam for an absent check, because a seam with no caller is speculative code. The criterion waits for #3451, and the change names it in the workflow follow-up.

- Chosen: wait for #3451. The job ticks every task of a passing group until that check exists.
- Rejected: an optional predicate with a stub test. A stub that no production code calls is a seam for a test only, which the testing rules refuse.
- Rejected: a hard dependency on #3451. It blocks this change on an item that is not merged.

### D5. The extra turn for the ticks is removed, and the step no longer stops for an unticked task

Once the job ticks every task of a passing group, no state reaches the guard of an unticked task, so the guard, its class branch and its messages go. The extra turn for the ticks goes with them. The repair turn of a failed static check or hook keeps its message, without the list of unticked tasks.

- Chosen: delete the guard and the tick turn. A guard that no input reaches is dead code.
- Rejected: keep the guard as a safety net. No test can reach it, and the test-form check of #3451 can add it back with its own test.

### D6. Strays: the staged new files join the untracked list, and a fix step has the same rule

`_strays` lists the untracked files that git does not ignore and the files that the index adds to `HEAD` (`git diff --cached --name-only --diff-filter=A`). `stray_files` decides which of them the group does not allow. A fix step uses the same test with its own group, so it removes a new file outside the four directories. The step unstages the strays with `git rm --cached --force --ignore-unmatch` and then deletes them.

- Chosen: one list for both kinds of stray, and one unstage command. It is the existing code with two inputs.
- Rejected: `git reset` then delete. It works, but it runs two commands for each file.
- Rejected: `git rm --force`. It touches the working tree and fails on a modified file.

### D8. The class `not_ticked` goes with its only producer

The step was the only producer of the class `not_ticked`. D5 removes the guard that produced it, and no other site or rule sets it. The classifier test of `roadmap-failure-taxonomy` then fails, because a class with no producer breaks the rule that each class has a source. The class and its default action go, and the taxonomy spec changes to 18 classes. The test-form check of #3451 adds a stop of its own when that check exists.

- Chosen: remove the class. It matches the rule that each class has a source.
- Rejected: keep the class for #3451. The class would wait for a check that does not exist, and the classifier test would need an exception for it.

### D7. The spec of the repair turn names no tick

The repair turn asks for a fix of the text of a failed check, and nothing else. The spec requirements `roadmap-implement-step` and `roadmap-implement-job` change to match.

## Risks

- A tick follows the exit checks of the whole group. Those checks run the verification command of every task, so a tick never follows a task whose command did not run. A group with no command is covered by D2.
- The eval property `tasks_ticked` reads the ticks in the diff of the commit. The commit still holds the ticks, so the property still holds.
