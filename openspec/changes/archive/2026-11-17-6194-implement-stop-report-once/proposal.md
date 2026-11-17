# Proposal: #6194

## Why

The owner rule of #6193 is that no job posts the same content two times to issues and pull requests. The implement job writes its stop report two or three times (#6194):

- On a stop, `implement_run.py` gives the stop text, which holds the table of the steps, to the comment of the run on the pull request, and `_comment` adds the table of the steps after it. The pull request shows the table two times (pull request #6157). The job then posts the same stop text on the issue.
- After each runner Job ends, `implement_submit.py` `_report` posts one more comment on the issue with the last 40 lines of the log, also when the runner posted its stop comment or its finished comment. The log tail repeats the end lines of the runner, and the digest repeats the record `implement.job_digest`.
- The review step does the reverse: on a discard it posts only "The review discarded pull request #N" on the issue, and the reason and the evidence are only in the comment on the pull request, which the jobs and refine do not read.

## What Changes

- On a stop, the job posts the stop comment on the issue first. It is the one copy of the stop report. When the pull request exists, the comment of the run on it holds the line "Stopped at <step>. The stop report is on #<issue>: <url>." and the lines that only it holds: amendments, skipped steps, scoped runs, strength and check lines, and the comments that the steps read. It holds no table. A run that finishes keeps its table on the pull request.
- `comment()` of the roadmap store gives a `PostedComment`: the page of the comment and whether the call posted it. A repeat that the guard refuses (#4793) gives the page of the earlier comment, which holds the same text. The truth value of the answer is `posted`, so refine and the marked-comment writer, which test whether the comment posted, keep their behavior.
- `_report` of the Service comments on the item only when the runner left no result, or when the Job is gone. Else it writes only the record marks.
- A discard of a rule by the review step writes the verdict, its reason and its evidence in the return comment on the issue. Then the comment of the step on the pull request becomes a link to it.
- The dry run of `devops roadmap implement` lists the writes of a stop in the new order: the comment on the item, the comment of the run on the pull request, then the Status.
- The change alters what the jobs write to GitHub, so it carries spec deltas.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job/stops`: the stop report is on the issue once, and a retry of a person clears one stop.
- `roadmap-implement-job/runner-job`: the round comments on the item only for a Job that left no result or is gone.
- `roadmap-pr-review`: a discard of a rule writes its verdict on the issue.

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/roadmap/steps/review.py`, `src/devops_cli/roadmap/steps/comment.py`, `src/devops_cli/roadmap/return_item.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/roadmap/stores/comment_repeat.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`, and the fakes `tests/support/fakes/roadmap_store.py` and `tests/support/fakes/github_repository.py`.
- Documents: `docs/roadmap/implement.md`.
- Old comments stay on GitHub. A reader of the comments reads the old and the new shapes: `retry_asked` reads only the marker, and the jobs read every comment of the issue.
- The change fits one pull request.

## Feasibility

- On `origin/main` (e6f571827), the new test of the table counted the header of the table 2 times in the comment of the run on the pull request and 1 time in the stop comment: `uv run pytest tests/roadmap/implement/test_roadmap_implement_job_table.py -k stop_after_a_push` gave `assert (2, 1, False) == (0, 1, True)`.
- On `origin/main`, the round posted "The runner Job ... ended: failed." with the log line "Failure class provider. Action left: retry." after a stop that the runner wrote, and "ended: succeeded." after the finished run (`tests/roadmap/implement/test_roadmap_implement_submit.py -k no_second_report`).
- `retry_asked` (`implement.py`) reads the comments after the last comment that holds the implement marker. The clear by retry (`stop_clear.py`) always posts its comment with that marker, and the repeat guard never refuses it: a comment of a person ends the trailing run of the guard. So the retry stays used once with no Job report after a stop.
- The issue asks that `comment()` gives the URL only. That is not enough: `refine.py` (`if comment and store.comment(...)`) and `steps/comment.py` (`create_comment`) read from the answer whether the comment posted, and a URL is also there for a refused repeat. So the answer holds both, and its truth value is `posted`.
- GitHub answers `POST /repos/{owner}/{repo}/issues/{number}/comments` with the comment, whose `html_url` is its page (REST API, "Create an issue comment").

## Existing Tool Considered

GitHub gives the page of a comment in the answer of its post, and the store already reads `html_url` of a listed comment (#6167). The change builds no tool and adds no dependency. It deletes the second table of the comment of the run, the Job report after a result, and the `extra` stop text of `_comment`. The build costs about 400k tokens and 3 hours.
