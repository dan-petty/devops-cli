# Proposal: #6197

## Why

The owner rule of #6193: no job posts the same content twice to an issue or a pull request. Each stage and restage posted a new full stage comment, and the old one stayed: both held the same branch, pull request and groups (#3717: 10.7 KB and 23.6 KB, 40 minutes apart, both for pull request #5945). Each attempt of the step `fix-plan` posted a new comment that listed the open findings again, because `plan_comment` read only the newest comment. The record key `stage.groups` repeated the group list in the body, and no code read it (#6197).

## What Changes

- One plan-state comment on the issue for each plan pull request, with a hidden key line `<!-- devops roadmap plan state #<pull> -->`. It holds the branch, the pull request, the task groups with their tokens, the open findings and the advisory findings. The stage job writes it on each stage and restage, and the step `fix-plan` rewrites it after each attempt that comments. Both use the marked-comment upsert of `steps/comment.py` (`post`): an edit of the comment that holds the key, else a new comment.
- `RoadmapStore.edit_comment` edits a comment by its id (one `PATCH` of the comment on GitHub). `steps/comment.py` edits a comment of the store through it, in place of the code that read the private parts of the stores.
- Each stage or restage run posts a comment of the run with a hidden event line `<!-- devops roadmap plan event #<pull> -->`: the paths that moved, the run report, the overlap reads, the comments that the request held, a validation that did not run, the warnings, the replaced draft and the label notes. No group and no finding.
- Each fix-plan attempt posts a comment of the attempt with the event line: the result, the counts before and after, why a pushed gated plan keeps or loses the label, the dismissed findings, the stop evidence, and the step and the counts of a timeout. No open finding and no advice: the state comment lists both, and one sentence for each says so. A contract test builds both comments from one attempt and fails when a line of text of the comment of the attempt is in the state comment.
- `plan_comment` reads the state comment by its key. For a pull request that an older release staged, it reads the newest legacy comment that names the pull request and skips the comments of a run. The step builds the state comment of such a pull request from the legacy comments. `plan_drift.py` and `steps/review_facts.py` read through `plan_comment` as before.
- `IssueComment` gets `updated_at` from GitHub. `held_comments` orders a state comment by its last edit, so the stage and the implement models read it as a recent comment. The index label skips every hidden `<!--` line.
- `StageRecordKey.GROUPS` and its two writers go. The stage eval fixtures lose the key.
- The dry runs of `devops roadmap stage` and `devops roadmap step fix-plan` list the read, the edit or the new state comment, and the comment of the run.
- This changes what the jobs write to GitHub and what they give a model, so it carries spec deltas.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/round`: the stage job writes the plan-state comment and a comment of the run, and records no groups.
- `roadmap-stage/ready`: the state comment lists the open findings.
- `roadmap-stage/fix-plan`: the step keeps the state comment, and its comment lists no open finding.
- `roadmap-stage/context`: the state comment reads as made at its last edit, and the index label skips hidden lines.

## Impact

- Code: `src/devops_cli/roadmap/stage/plan_state.py` (new), `stage/stage.py`, `steps/fix_plan.py`, `steps/comment.py`, `item_comments.py`, `request_plan.py`, `stores/store.py`, `stores/github_store.py`, the constants and the messages, and the fake store.
- Old comments stay on GitHub as they are, and the readers accept the old and the new forms. A record of an older release keeps `stage.groups` as a key that this release does not read.
- Documents: `docs/roadmap/stage.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/CLUSTER.md` and the generated references. ADR 0021 says that the step does not edit the stage comment. An accepted record keeps its body (`tests/invariants/test_adr_records.py`), so the record stays as it is, and `docs/roadmap/stage.md` holds the current rule.
- The change fits one pull request.

## Feasibility

- `stage.py` posted the stage comment with `store.comment` in `_stage_one`, and wrote `StageRecordKey.GROUPS` in `_stage_one` and `_stop_on_budget`. `git grep -n "StageRecordKey.GROUPS\|stage.groups" -- src` gave no reader.
- `fix_plan.py` posted one comment for each attempt with `store.comment` in `_settle`, and `plan_comment` returned the newest trusted comment with a plan marker that named the pull request.
- `steps/comment.py` `post` is the upsert of the marked comments of the roadmap steps. Its store path edited a comment through the private `_roadmap` of the fake or `_write` of the GitHub store, and edited the first comment with no id in the fake.
- The GitHub REST comment payload holds `updated_at` (`GET /repos/{owner}/{repo}/issues/{number}/comments`), and `PATCH /repos/{owner}/{repo}/issues/comments/{comment_id}` edits a comment.
- `repair.py` `_unanswered` and `_filler_return` read the comments in the order of their creation: an edit keeps a comment at its place, so a state comment hides no return. A test proves it.
- With code at its caps, the first stage request counts 47,985 tokens before the change and 47,983 tokens after it, under the limit of 48,640 tokens (`tests/roadmap/stage/test_roadmap_stage_window.py`).

## Existing Tool Considered

The change reuses `steps/comment.py` `post` and `Target` for the upsert, and the GitHub REST API for the edit (`gh api -X PATCH`). No open tool keeps one state comment for each pull request of a job. The build costs about 250k tokens and 4 hours. The change deletes `_groups_recorded`, `_groups_listed`, `StageRecordKey.GROUPS`, the message `stage_comment_staged`, the list of plan markers of `fix_plan.py`, and the store path of `steps/comment.py` that read the private parts of the stores.
