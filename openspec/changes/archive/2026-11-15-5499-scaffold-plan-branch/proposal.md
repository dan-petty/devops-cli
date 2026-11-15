# Proposal: #5499

## Why
A Service restart stops a running stage round, and the round loses its checked plan. The branch, the worktree and the change folder live on the Service volume, and the `stage.pending` rule deletes an App-only branch after 1 hour, so a plan that passed its checks can be lost. Tracker #5482 (D1) makes scaffold a step module with its own command and result line. It runs first in the stage unit (kind `plan`) and later in the tests unit (kind `delivery`). It creates, resumes, adopts or holds the item branch so a checked plan stays on `origin` and a new round starts from it. Closes #5499.

## What Changes
- Add `src/devops_cli/roadmap/steps/scaffold.py` implementing the scaffold step with four resume results: `created`, `resumed`, `adopted`, and `held`.
- Add `create_ref` on `GitHubClient` in `src/devops_cli/github/client.py` using `POST /repos/{owner}/{repo}/git/refs`.
- Add `devops roadmap step scaffold` in `src/devops_cli/commands/roadmap_step_scaffold.py` and register it in `src/devops_cli/commands/roadmap_step.py`.
- Add `ScaffoldRecordKey` (`scaffold.branch`) to `src/devops_cli/roadmap/stores/store.py`.
- Add `RoadmapJob.SCAFFOLD` and results in `src/devops_cli/roadmap/job_result.py`.
- Update `_orphans` in `src/devops_cli/roadmap/stage/stage.py` to keep App-only branches of Ready items.
- Update `run_stage_job` and `run_stage_round` to call scaffold before planning.
- Update `docs/roadmap/stage.md` and `docs/ROADMAP_WORKFLOW.md` to state the resume rule.

## Capabilities
- Introduces `roadmap-stage/scaffold` capability: creates ref with no commit at head of `origin/main`, adopts or resumes on App-only branches, holds branches modified by others, and preserves App-only branches of Ready items during orphan cleanup.

## Impact
- Stage runs recover checked plans after service restarts or worker kills, preventing lost progress and avoiding redundant planner calls.
- Adds `devops roadmap step scaffold` CLI command.

## Feasibility
Confirmed against GitHub REST API documentation (`POST /repos/{owner}/{repo}/git/refs`), `GitHubClient` in `src/devops_cli/github/client.py:446`, and `issue_holder` in `src/devops_cli/git/worktree_add.py:550`.

## Existing Tool Considered
The GitHub git refs API creates a ref with no commit. git, `issue_holder`, `branch_form.py` and the implement checkpoint code exist. No open tool applies this resume rule. Build: 200,000 to 350,000 agent tokens and 0.5 to 1 day.

Fits in one pull request.
