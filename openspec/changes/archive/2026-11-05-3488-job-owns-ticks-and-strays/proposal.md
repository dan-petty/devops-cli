# Proposal

## Why

Issue #3488: a step of the implement job stops when the model does not tick a task, even when every exit check of the group passes. The stop loses all the work of the group, and the next attempt spends the tokens again. #2116, #3106 and #3331 stopped this way on 2026-11-03 and 2026-11-04, with 8.49 million input tokens in the stopped groups.

A fix step also keeps the stray files that a group step removes. The #3394 fix kept `test_issue_reproduction.py` in the checkout root, because the stray listing of `git ls-files --others` omits a file that the agent staged with `git add`, and a fix step never ran that listing.

This change makes the job own the ticks and the stray files. The job ticks each task of a group whose exit checks pass. A fix step removes the stray files as a group step does, staged ones included.

## What Changes

- At the end of a group step, after every exit check passes, the job ticks each unticked task of its group in `tasks.md`, stages the file, and the commit holds the ticks. A stop before that point ticks nothing.
- A group with no verification command is ticked when its exit checks pass. The plan rule in `openspec/config.yaml` states this.
- The step no longer gives the model an extra turn for a missing tick. A failed static check or hook still gets its extra turn, and that turn no longer lists the unticked tasks.
- A fix step deletes a stray file outside `src/`, `tests/`, `docs/` and `openspec/`, as a group step does. A new file under those directories stays.
- A stray file that the agent staged with `git add` is unstaged and deleted in a group step and in a fix step.
- The prompt keeps the request to tick a task. The work-in-progress keeper (#3054) commits only the ticks that the model wrote, so the request keeps the kept work of a stopped step. The prompt drops the sentence that promises an extra turn for a missing tick.
- The spec deltas in `roadmap-implement-step` and `roadmap-implement-job` replace the requirement of the extra turn for the ticks, and name the job as the owner of the ticks.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step`: the job ticks the group at its exit, the extra turn for the ticks is removed, and the stray files of a fix step and of a staged file are removed.
- `roadmap-implement-job`: a stop site no longer passes the class `not_ticked` for a task that the step leaves unticked, because the step ticks every task of a passing group.
- `roadmap-failure-taxonomy`: the class `not_ticked` and its action go, because no step produces it.

## Impact

- Code: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_strays.py`, `src/devops_cli/roadmap/failure.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`.
- Tests: `tests/roadmap/test_roadmap_failure.py`, `tests/prometheus/test_implement_failure_labels.py`, `tests/roadmap/test_roadmap_implement_wip.py`, `tests/roadmap/test_roadmap_implement_job.py`, `tests/roadmap/test_roadmap_implement_step_hooks.py`, `tests/roadmap/test_roadmap_implement_step_own_text.py`, `tests/roadmap/test_roadmap_implement_step_ticks.py`, `tests/roadmap/test_roadmap_implement_step.py`, `tests/roadmap/test_roadmap_implement_step_repair.py`, `tests/roadmap/test_roadmap_implement_step_attempts.py`, `tests/roadmap/test_roadmap_implement_step_failure_class.py`, `tests/roadmap/test_roadmap_implement_strays.py`, `tests/roadmap/test_roadmap_implement_prompt.py`.
- Documents: `openspec/config.yaml` (the plan rule of a group with no verification command), `docs/roadmap/implement.md`, `docs/ROADMAP_WORKFLOW.md` (the row of the class `not_ticked` goes).
- The change fits one pull request. It closes #3488 and changes no other issue.

## Dependencies

#3451 (the test-form check) is absent from `origin/main`, so the criterion of a refused task waits for it. #3060 is a planned change that also modifies the requirement "A failed model call ends the step stopped". This change leaves that requirement as it is, because `openspec check` refuses two active changes that modify one requirement. Its scenario "A model call fails in the extra turn" still names the tick turn until #3060 archives, and the owner of #3060 then folds the scenario into its delta. #3490 and #3069 edit the same implement step, so a merge of them can conflict with this change.

## Feasibility

Checked on `origin/main` at 0a62030c, on 2026-11-05.

1. The unticked stop is real. `_attempt` in `src/devops_cli/roadmap/implement_step.py` stops with the reason `implement_stop_unticked` when `_unticked_failure` finds a task that is not ticked, and that check runs only after every exit check passed. The job reads only the model's ticks: `_ticked_lines` counts a tick that the model wrote.
2. The job can write the ticks. `_restore_tasks` already writes the whole `tasks.md` from its text before the run, with the ticks of the own group, so the file is in the checkout at the exit.
3. The fix step keeps its strays. `_strays` returns an empty list when `inputs.fix is not None`.
4. `git ls-files --others --exclude-standard` omits a file that is staged. A probe in a scratch repository printed `sub/` and not `stray.txt` after `git add stray.txt`. `git diff --cached --name-only --diff-filter=A` lists the staged file. `git rm --cached --force --ignore-unmatch -- <names>` unstages each name and exits 0 for a name that git does not track.
5. The work-in-progress keeper needs the model's ticks. `WipKeeper._fresh` in `src/devops_cli/roadmap/implement_wip.py` selects tasks where `now.ticked` is true. A prompt without the tick request would end every `wip:` commit.
6. The test-form check of #3451 is absent: `git grep -i "test.form"` on `origin/main` finds no check of a task. The plan-conformance scenario of #3049 is absent: `git grep -i conformance` on `origin/main` finds no scenario in `openspec/specs` or `src`.

Not verified: a real model run on a pod. The tests replay the steps with a scripted model, a real git repository and faked process edges.

## Existing Tool Considered

No open, maintained tool or library covers the tick and the stray rules: they are specific to the implement step of this repository. Git covers the staged list (`git diff --cached --name-only --diff-filter=A`) and the unstage (`git rm --cached --force --ignore-unmatch`). The change extends existing code and builds no new tool.

The internal code that the change deletes: the extra turn for the ticks (`_extra_ask` tick branch, `_unticked_fields`), the stop of an unticked task (`_unticked_failure`, `_unticked`, the class branch of `_failure_class`), the fix-step early return of `_strays`, and the messages `implement_tick_turn`, `implement_stop_unticked`, `implement_stop_tick_turn_changed` and `implement_repair_turn_ticks`.

Cost to build: about 25,000 tokens and about 1 hour for the code, the tests and the documents. Cost to keep the current rule: about 8.5 million input tokens in three stops in one day, as the issue shows.
