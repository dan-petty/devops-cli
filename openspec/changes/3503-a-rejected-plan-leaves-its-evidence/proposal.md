# Proposal

## Why

When a person closes a plan pull request with no merge, the reason stays on the closed pull request (#3503). The issue gets no reason. Refine then sets the issue Ready again, and the stage job can plan the same false premise again. A person or an agent who reads only the issue sees a Ready item that nobody can build as written. The issues #3049, #3076, #2754 and #2740 read Ready in this state.

## What Changes

- The stage job reads the plan pull request of each open New or Ready item that holds `stage.pr` and whose plan is not on the default branch. A pull request that is closed and not merged is a rejected plan.
- For a rejected plan the job posts one comment on the issue. The comment holds the marker of the stage job, the marker of a rejected plan and the reason. The reason is the last comment on the pull request that a person with write access wrote and that is over `EVIDENCE_MIN_CHARS` characters. A shorter last comment, such as `rejected`, is no reason: the job takes the comment before it. The job masks secrets and cuts the reason to the token cap of a refine reply.
- The job returns the item to New, clears its stage record and writes the record `stage.rejected`: the pull request, the hash of the text of the item, the time of the close and the files that the reason names. The job deletes the staged branch when only the session identity wrote to it, with the rule that a closed item already uses. A branch with another commit stays, and the plan says so.
- The stage job leaves out an item with a `stage.rejected` record. The reason names the pull request. The hold ends when the text of the item changes (the hash outside the refine section) or when a commit on the default branch changes a file that the reason names. `--item` overrules the hold, as it overrules a recorded split.
- The comment is a comment of the stage job, so refine reads it through the key `stage_return` and gives the item one new look. The request of the stage job holds the key `rejected_plan` for an item with a `stage.rejected` record. Both prompts say what the key means.
- `devops roadmap explain` shows the reason of the hold, with the pull request number, because it reads the same selection.
- New messages in `src/devops_cli/lang/en/messages.py` carry the comment, the reason of the hold and the lines of the report. The dry run lists the new reads and writes.
- The change carries spec deltas on `roadmap-stage`, `roadmap-refine` and `roadmap-explain`, because a consumer observes the comment, the hold and the requests.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A rejected plan leaves its reason on the issue and holds the item until its text changes
- `roadmap-refine`: Refine reads the reason of a rejected plan
- `roadmap-explain`: Explain names the plan pull request that holds an item

## Impact

- Code: `src/devops_cli/roadmap/stage_rejected.py` (new), `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/github/client.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/commands/roadmap.py`
- Prompts: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_refine_proposal.md`, `src/devops_cli/ai/tasks/roadmap_refine_investigation.md`
- Documents: `docs/roadmap/stage.md`, `docs/roadmap/refine.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/test_roadmap_stage_rejected.py` (new), `tests/roadmap/test_roadmap_refine.py`, `tests/roadmap/test_roadmap_explain.py`, `tests/roadmap/test_roadmap_dry_runs.py`, `tests/roadmap/test_roadmap_stage_command.py`, `tests/roadmap/test_roadmap_stage_reconcile.py`, `tests/roadmap/test_roadmap_stage_planned.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`
- Test support: `src/devops_cli/roadmap/memory_store.py` (`seed_comment` takes a pull request)

## Feasibility

- The premise holds on the live records. The plan pull requests of #3049 and #3076 are closed with `merged: false`. Each holds 3 comments of the owner: the first has 7,601 and 7,231 characters, the second has 4,634 and 3,512, and the last one has 8 characters (`rejected`). The issue #3049 reads `status/ready`, its record holds `stage.branch`, and `git ls-remote --heads origin 'feat/3049*'` still lists the branch. So the reason is on the pull request only, and the branch still holds the issue.
- The row `stage_ready` cannot carry the copy. `_recorded_pull` in `src/devops_cli/roadmap/stage_ready.py` returns no pull request when `stage.ready` equals `stage.pr`, and the row marks a green draft ready. The record of #3049 holds `stage.pr` and `stage.ready` with the same number, so the row marked that plan ready, and it never reads it again. The stage job reads the pull request of each staged plan, owns the clone and the branch rules, and already removes the staged branch of a closed item.
- `issue_holder` in `src/devops_cli/git/worktree_add.py` counts each pushed branch of the issue as a hold, and `add_worktree` refuses or takes over a pushed branch. So a rule that only ignores the branch would not let the stage job plan again. The job deletes the branch instead.
- `devops roadmap return` and the claim of a 401. The comment on #3049 of 2026-11-02T18:05Z says that the command fails with 401 in an agent session. The comment `returned per agent request` on the same issue at 2026-11-02T18:21Z and 2026-11-02T20:22Z shows that a return went through in an agent session after it. The plan-only run `uv run devops roadmap return 3503 --comment "probe: Stage A check, plan only"` read the issue with no error and printed `Item #3503: fix(roadmap): a rejected plan leaves its evidence on the issue`, `Target Status: New` and `Plan only: pass --confirm to apply.` The session identity holds the scopes `gist, project, read:org, repo, workflow` (`X-Oauth-Scopes` of `GET /repos/{repo}`), and the read and the write of `return` use the same token, so a rejected token (HTTP 401) fails the read first. The write of `--confirm` was not run, because a stage of this change writes nothing on GitHub. A write probe with a no-op `PATCH` was refused by the permission system of the session, which is an approval rule and no HTTP 401. So the 401 does not reproduce, and the write stays unproven here. The change does not depend on `return`: the job copies the reason when a person only closes the pull request.
- First check of the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_rejected.py` fails on the base, after the tests are written and before the code.
- Second check: `uv run devops ci test tests/roadmap/test_roadmap_stage_rejected.py tests/roadmap/test_roadmap_stage_selection.py tests/roadmap/test_roadmap_refine.py tests/roadmap/test_roadmap_explain.py tests/roadmap/test_roadmap_dry_runs.py` passes on the branch tip.
- Third check: `uv run devops openspec check` and `uv run devops ci docs` pass.

## Existing Tool Considered

`devops roadmap return --comment` already delivers evidence to an issue, but a person or an agent must run it, and the case here is a person who only closes the pull request. `_changed_since` and `_text_paths` of `src/devops_cli/roadmap/refine.py` already decide that a file changed since a time, so the hold reuses them (they become public). The key `stage_return` and its one new look already carry a comment of the stage job to refine, so refine needs no new key. `trusted_replies` of `src/devops_cli/roadmap/trust.py` already limits the authors whose text reaches a model. No outside tool reads a closed pull request and writes its reason to an issue in this flow. The code that the change adds is about 300 lines with tests. The cost is about 25,000 tokens to build and test, about 2,000 tokens a month to keep and fix, and about 5 hours elapsed. The change deletes no internal code.

## Dependencies

None.
