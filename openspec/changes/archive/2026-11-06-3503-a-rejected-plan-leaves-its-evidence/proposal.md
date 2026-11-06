# Proposal

## Why

When a person closes a plan pull request with no merge, the reason stays on the closed pull request (#3503). The issue gets no reason. Refine then sets the issue Ready again, and the stage job can plan the same false premise again. A person or an agent who reads only the issue sees a Ready item that nobody can build as written. The issues #3049, #3076, #2754 and #2740 read Ready in this state.

## What Changes

- The stage job reads the plan pull request of each open New or Ready item that holds `stage.pr` and whose plan is not on the default branch. A pull request that is closed and not merged is a rejected plan.
- For a rejected plan the job posts one comment on the issue. The comment holds the marker of the stage job, the marker of a rejected plan and the reason. The reason is the last comment on the pull request that a person with write access wrote and that is over `EVIDENCE_MIN_CHARS` characters. A shorter last comment, such as `rejected`, is no reason: the job takes the comment before it. The job masks secrets and cuts the reason to the token cap of a refine reply.
- The job returns the item to New, clears its stage record and writes the record `stage.rejected`. The record holds the pull request, the time of the close, the files that the reason names, and the hash of the text that the plan came from. An item that the same run stages again keeps its Status.
- The job records that hash as `stage.text_hash` when it stages an item. So an edit that a person made before the job read the closed pull request ends the hold.
- The job deletes the staged branch when only the session identity wrote to it, with the rule that a closed item already uses. It deletes the branch only while it ends at the commit that the plan judged. A branch with another commit stays, and the plan says so.
- The stage job leaves out an item with a `stage.rejected` record. The reason names the pull request. The hold ends when the text of the item changes (the hash outside the refine section). It ends also when a commit on the default branch changes a file that the reason names. `--item` overrules the hold, as it overrules a recorded split.
- The comment is a comment of the stage job, so refine reads it through the key `stage_return` and gives the item one new look. The request of the stage job holds the key `rejected_plan` for an item with a `stage.rejected` record. Both prompts say what the key means.
- `devops roadmap explain` shows the reason of the hold, with the pull request number, because it reads the same selection.
- New messages in `src/devops_cli/lang/en/messages.py` carry the comment, the reason of the hold and the lines of the report. The dry run lists the new reads and writes.
- The change carries spec deltas on `roadmap-stage`, `roadmap-refine` and `roadmap-explain`, because a consumer observes the comment, the hold and the requests. It also words again the requirement "The stage reply has no return path", which the return of a blocked item (#3418) made false.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A rejected plan leaves its reason on the issue and holds the item until its text changes. The requirement "The stage reply has no return path" is worded again
- `roadmap-refine`: Refine reads the reason of a rejected plan
- `roadmap-explain`: Explain names the plan pull request that holds an item

## Impact

- Code: `src/devops_cli/roadmap/stage_rejected.py` (new), `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/github/client.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/commands/roadmap.py`
- Prompts: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_refine_proposal.md`, `src/devops_cli/ai/tasks/roadmap_refine_investigation.md`
- Documents: `docs/roadmap/stage.md`, `docs/roadmap/refine.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/test_roadmap_stage_rejected.py` (new), `tests/roadmap/test_roadmap_refine.py`, `tests/roadmap/test_roadmap_explain.py`, `tests/roadmap/test_roadmap_dry_runs.py`, `tests/roadmap/test_roadmap_stage_command.py`, `tests/roadmap/test_roadmap_stage_reconcile.py`, `tests/roadmap/test_roadmap_stage_planned.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`

## Feasibility

- The premise holds on the live records. The plan pull requests of #3049 and #3076 are closed with `merged: false`. Each holds 3 comments of the owner: the first has 7,601 and 7,231 characters, the second has 4,634 and 3,512, and the last one has 8 characters (`rejected`). The issue #3049 reads `status/ready`, its record holds `stage.branch`, and `git ls-remote --heads origin 'feat/3049*'` still lists the branch. So the reason is on the pull request only, and the branch still holds the issue.
- The row `stage_ready` cannot carry the copy. `_recorded_pull` in `src/devops_cli/roadmap/stage_ready.py` returns no pull request when `stage.ready` equals `stage.pr`, and the row marks a green draft ready. The record of #3049 holds `stage.pr` and `stage.ready` with the same number, so the row marked that plan ready, and it never reads it again. The stage job reads the pull request of each staged plan, owns the clone and the branch rules, and already removes the staged branch of a closed item.
- `issue_holder` in `src/devops_cli/git/worktree_add.py` counts each pushed branch of the issue as a hold, and `add_worktree` refuses or takes over a pushed branch. So a rule that only ignores the branch would not let the stage job plan again. The job deletes the branch instead.
- `devops roadmap return` and the claim of a 401. The comment on #3049 of 2026-11-02T18:05Z says that the command fails with 401 in an agent session. The comments `returned per agent request` on the same issue at 2026-11-02T18:21Z and 2026-11-02T20:22Z show that a return went through in an agent session after it. On 2026-11-05 the parent session ran `uv run devops roadmap return <n> --comment-file <file> --confirm` five times. Each run printed `Returned item #<n> to New and posted evidence comment.` The five comments are on GitHub, written by the account of the session: #1359 at 14:47:22Z, #1335 at 14:47:33Z, #1330 at 17:03:09Z, #3062 at 17:03:22Z and #2371 at 20:22:36Z. The read and the write of `return` use one token. So the 401 does not reproduce, and its cause is not found. The change does not depend on `return`: the job copies the reason when a person only closes the pull request.
- First check of the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_rejected.py` fails on the base, after the tests are written and before the code.
- Second check: `uv run devops ci test tests/roadmap/test_roadmap_stage_rejected.py tests/roadmap/test_roadmap_stage_selection.py tests/roadmap/test_roadmap_refine.py tests/roadmap/test_roadmap_explain.py tests/roadmap/test_roadmap_dry_runs.py` passes on the branch tip.
- Third check: `uv run devops openspec check` and `uv run devops ci docs` pass.

## Existing Tool Considered

`devops roadmap return --comment` already delivers evidence to an issue, but a person or an agent must run it, and the case here is a person who only closes the pull request. `_changed_since` and `_text_paths` of `src/devops_cli/roadmap/refine.py` already decide that a file changed since a time, so the hold reuses them (they become public). The key `stage_return` and its one new look already carry a comment of the stage job to refine, so refine needs no new key. `trusted_replies` of `src/devops_cli/roadmap/trust.py` already limits the authors whose text reaches a model. No outside tool reads a closed pull request and writes its reason to an issue in this flow. The change adds about 550 lines of source, messages and prompts, and about 930 lines of tests. The text of the diff is about 20,000 tokens. The cost is an estimate: about 400,000 tokens to build, test and review it, because the reads, the runs and two reviews multiply the text. It is about 5,000 tokens a month to keep and fix it, and about 2 days elapsed. The change deletes no internal code.

## Dependencies

None.
