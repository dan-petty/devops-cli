# Proposal: #4793

## Why

A roadmap job posts the same comment on one item again when a later round finds the same facts. The census of 2026-11-11 counts 34 repeat refine comments on open items. On dotfiles #2 the implement checks posted 137 comments from 2026-11-01 to 2026-11-04, most of them "Stopped at docs" and "Cleared the stop at docs". No shared guard refuses a repeat. ADR 0021 also asks for a test that stops each job after each GitHub write and runs it again, and no test does this.

## What Changes

- New module `src/devops_cli/roadmap/stores/comment_repeat.py`. Before a store posts a comment that holds a job marker, it reads the comments of the issue. It refuses the comment when a comment with the same fingerprint is in the trailing run of comments that hold the same marker and is less than 7 days old. The fingerprint is the SHA-256 of the text with white space made single and each identifier of 7 or more hexadecimal digits left out, because a round names a new commit, digest or run each time.
- `GitHubRoadmapStore.comment` and `InMemoryRoadmapStore.comment` (and the comment of `close`) call the guard. `GitHubRoadmapStore` gets a `clock` argument for the window.
- Each refusal logs one line and adds 1 to `devops_cli_roadmap_comment_repeats_refused_total{row}` (6 series at most). The label is `row` and not `job`, because the collector sets `job` from the resource (#3240).
- `CONST_ROADMAP_JOB_COMMENT_MARKERS` holds the implement marker. Refine and the stage rejection read no implement comment as the reply of a person, and `retitle.py` drops its own copy of the list.
- The dry-run request plan lists the comments read before a job comment and the condition of the post.
- `RoadmapStore.comment` returns whether it posted. When the store refuses a comment of refine, refine records the time of the round in `refine.repeated_at`. The wait of the item starts at the later of that time and refine's last comment. Without this mark, a new look that a changed cited path or a closed named issue gave comes again in each round for 7 days, because the start of the wait stays before the change.
- `tests/support/write_stops.py` holds `stop_after_each_write`: it runs a job on copies of the in-memory store that stop after each write in turn, then runs the job again. The refine and stage tests use it.

## Capabilities

- `roadmap-job-comments` (new): a roadmap job posts no comment that repeats its own recent comment on the item.

## Impact

- One more `GET` of the comments of the item before each comment of a job. The jobs posted 4,262 comments in 31 days, about 140 a day.
- A refused refine comment costs one read of the issue and one `PATCH` of its job record. The replay found 13 such comments in 31 days.
- Replayed on the 7,272 comments of devops-cli since 2026-10-12, the guard refuses 128 of 4,262 job comments (115 implement, 13 refine) on 27 items, and 46 of the 137 implement comments on dotfiles #2.
- The change fits one pull request.

## Feasibility

- `GitHubRoadmapStore.comment` in `src/devops_cli/roadmap/stores/github_store.py` posts each comment with no read, and `InMemoryRoadmapStore.comment` does the same, on `main` at cbdce63f6.
- The repeat refine comments of #3066 from 2026-11-07 to 2026-11-09 differ only in the commit SHA ("Refine cannot set this item to Ready at 72c52c6f1bd1 ..."), read with `devops gh api repos/dan-petty/devops-cli/issues/3066/comments`. The clear comments of dotfiles #2 differ only in the two image digests.
- `retry_asked` in `implement.py`, `replies_after_marker` and `_stage_return` in `refine.py` read the comments after the last comment of a job. The guard keeps their answers, because it refuses a repeat only in the trailing run of the same marker: a person's reply or another job's comment ends the run.
- `InMemoryRoadmapStore.fail_write(applied=True)` already applies a write and then raises, so the harness needs no new fault mode.

## Existing Tool Considered

No GitHub feature refuses a repeat comment, and no library covers a guard on our own markers. `hashlib` gives the hash and `itertools.takewhile` the trailing run. Cost to build: about 150,000 tokens and 3 hours. The change deletes the local `_JOB_MARKERS` list of `retitle.py`.
