# Proposal

## Why

Issue #3273. When an implement step stops after an earlier group committed, `_push_passed` calls `_publish`. `_publish` opens the draft pull request with the body "Work on #N. The job closes the issue in the body when it finishes." That body holds no closing keyword. The stop ends the run before `_pull_request` writes the final body, so the draft stays as it is. `devops pr check-readiness` then reports the pull request as ungrounded ("it closes no issue"). The pull request cannot be judged for the real cause, which is that the work is not finished. Pull request #3172 was left in this state.

## What Changes

- The message `implement_pull_body_draft` starts with `Closes #{number}`, and its second sentence says that the job replaces the body when it finishes. The draft is grounded from its first push. Every path that calls `_publish` (the first push of a run, a stop, and any later caller) gets the same body.
- The requirement "A Planned item gets a draft pull request at its first push" no longer says that the first body holds no closing keyword. It says that the first body holds the closing keyword of the delivered issue, once.
- A stopped draft is still blocked by `check-readiness`, with the true reason: the change folder is not archived (`archives_its_change`). Nobody merges unfinished work by mistake, because only a person merges and the Status is Blocked.
- `src/devops_cli/github/merge_readiness.py` and `src/devops_cli/roadmap/grounding.py` do not change. The rule "a pull request closes one open issue of its repository" is right, and the draft now follows it.
- The closing keyword names the delivered issue only. The message holds no other issue number.
- The change fits one pull request.

## Impact

- `src/devops_cli/lang/en/messages.py` (`implement_pull_body_draft`) and the docstring of `_publish` in `src/devops_cli/roadmap/implement_run.py`.
- `openspec/specs/roadmap-implement-job/spec.md` (one MODIFIED requirement).
- `tests/roadmap/test_roadmap_implement_job.py` (one new test).
- Overlap with #3645 (a stop in the scoped checks keeps and pushes finished work): that change pushes through `_push_passed`, so it reaches `_publish` too. This change edits the body text only. It does not depend on #3645 and does not conflict with it. After #3645, more stops publish a draft, and each of them gets a grounded body.

## Feasibility

Checked on `origin/main` 555280ff, 2026-11-06.

- Cause: `_publish` in `src/devops_cli/roadmap/implement_run.py` sends `MESSAGES.roadmap.implement_pull_body_draft.format(number=...)`. That message in `src/devops_cli/lang/en/messages.py` is "Work on #{number}. The job closes the issue in the body when it finishes." `closing_keyword_in` (`src/devops_cli/roadmap/stage_change.py`) returns `None` for it, because "closes" there is followed by "the", not by an issue reference. So the draft closes no issue.
- The only writer of the final body is `_pull_request`, which runs after the archive. A stop skips it (`_push_passed` is the stop path), so the draft body is the last body.
- The failing test was written first: `test_a_stop_after_the_first_group_of_a_planned_item_leaves_a_draft_that_closes_its_issue` (the `planned_world` job fixture, git real, GitHub faked) failed because `closing_keyword_in('Work on #1. The job closes the issue in the body when it finishes.')` returned `None`.
- The refine text of the issue proposes to test the formatted body with `closing_keyword_in` and add a trailer when it holds none. The check shows that this is not needed. The message is a constant that this repository owns, so the keyword goes into the message and the test fixes it. A guard against our own constant is code for a case that cannot happen. The refine doubt that the message may already hold the keyword is false at the staging commit (see above).
- The grounding rules read the closing issue from GitHub (`read_closing_issues`), so a `Closes #N` line in the draft body is what they read. After the fix a stopped draft gets only the blocker "change not archived", which is true.

## Existing Tool Considered

No open tool or library covers the choreography of the implement job and its draft pull request. The change edits one message and one requirement, and builds no component. Cost: about 3,000 tokens to write, almost nothing to keep, and under one hour of elapsed time. The change deletes no code.
