# Proposal: #6167

## Why

Decisions and corrections often come as comments on an item, and the comments of the roadmap jobs hold context too: an alternatives check, a suggestion of the Service, the reason that an earlier attempt stopped. Refine reads the replies after its own last comment, but the stage job prefetches no comment (its model sees the last 3 comments cut to 600 characters only when it calls `read_issue`), and the implement job reads no comment but `implement: retry`. So the implement run of #3827 could not read the three comments that changed its plan, and the stage model reads at most 600 characters of the owner decision on #6058 (#6167). The owner then asked for no ignore system and no hard cap that drops context or fails a job: the jobs get all the comments, and a comment that the budget leaves out is deferred, not lost.

## What Changes

- The stage job and the implement job give their model every comment of the item that a person with write access or the Service App wrote, oldest first, each with its number, its author and its time: the comments of persons and of the roadmap jobs. The job collapses no comment. A comment of any other account never reaches a model, as for refine.
- No comment is cut. The newest comments come whole while they fit the budget of the input, each older comment gets a line of an index (number, author, time, first line), and the input counts the older comments that the index does not list.
- A new read-only tool `read_comment` reads any comment of the item whole, page by page, or lists every comment. Each stage toolset and the implement agent have it. It reads the comments that the job read, and reaches no host.
- Stage: the first plan request holds the key `comments`. The comments take the room that the body leaves under its cap, and at most `CONST_ROADMAP_STAGE_COMMENTS_MAX_TOKENS` (6,144) tokens of the context cap, so the request is no larger than before. The key of a kept plan holds the comments. The comment of a staged item names each comment that the request held whole.
- Implement: each step, a fix step too, gets the section "Comments on the item" after the documents of the change, with the time at which the plan merged and the line "Comments of persons on the item after its plan merged; a decision here overrides the plan text." The comments take at most `CONST_ROADMAP_IMPLEMENT_COMMENTS_MAX_TOKENS` (8,000) tokens and at most the room that the other inputs leave under the window, so they never take a step over it. The comment of the run on the pull request names each comment that the inputs held whole.
- The GitHub store reads the id and the page of each comment, and the dry runs of `devops roadmap stage` and `devops roadmap implement` list the new reads.
- This changes what the jobs send to a model and what they write to GitHub, so it carries spec deltas.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/context`: the first plan request holds the comments of the item, and the comment of a staged item names them.
- `roadmap-stage/toolbox`: each toolset has `read_comment`.
- `roadmap-implement-step/inputs`: the inputs of a step hold the comments of the item, and the agent has `read_comment`.
- `roadmap-implement-job/pull-request`: the comment of a run names the comments that the steps read.

## Impact

- Code: `src/devops_cli/roadmap/item_comments.py` (new), `src/devops_cli/roadmap/implement/implement_comments.py` (new), the stage planner, request, toolbox and tools, the implement step and run, the tool registry, the GitHub store, the dry-run plans, the constants and the messages.
- Prompt: `roadmap_stage_tools.md` names `read_comment`. The stage change prompt `roadmap_stage_change.md` does not change: the request says what its comments are.
- Documents: `docs/roadmap/stage.md`, `docs/roadmap/implement.md`, `docs/CLUSTER.md` and the generated references.
- The change fits one pull request.

## Feasibility

- `git grep -n "comments_on" -- src/devops_cli/roadmap/stage/` gave only `stage_rejected.py`, which reads a rejected plan; `stage_github.py:100` reads 3 comments cut to `CONST_ROADMAP_STAGE_ISSUE_COMMENT_CHARS` (600) only in `read_issue`. `git grep -n "comments_on" -- src/devops_cli/roadmap/implement/` gave only `retry_asked_on`.
- The comments of #6058, #6105 and #3827 (read with `uv run devops gh api repos/dan-petty/devops-cli/issues/<n>/comments`) count 84 to 2,018 tokens for a comment of a person, and 6,791 tokens for the longest comment of a job. Two comments on #6058 are release comments of the Service that hold no job marker.
- The squash commit of plan pull request #6164 has the author time 2026-11-17T13:49:21Z, and GitHub gives `merged_at` 2026-11-17T13:49:22Z: the commit that adds the change folder gives the time at which the plan merged, with no GitHub request.
- With code at its caps, the first stage request counts 47,863 tokens with the new tool and 47,023 tokens with 41 comments, under the limit of 48,640 tokens (the limit of the tools, 49,152, minus the headroom of 512 tokens of #6103).

## Existing Tool Considered

pydantic-ai gives the tool (`Tool`, the `tools` of `Agent`), tiktoken counts the tokens (`count_tokens`), and git gives the time of the plan. No open tool fits the comments of an item into a token budget with an index. The build costs about 150k tokens and 3 hours. The change deletes no internal code: `truncate_to_token_limit` stays for the body, and refine keeps its reads.
