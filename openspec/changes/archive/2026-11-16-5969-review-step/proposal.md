# Proposal: #5969

## Why
The bot opens about 20 pull requests a day, and they wait for a person: on 2026-11-16 at 13:30Z, 7 of 11 open bot pull requests had every check green and no job moved them, 2 failed only `Semantic PR title`, 1 plan held `plan/needs-fix` with a failed Plan Check, and 1 was blocked. The fix steps exist, but no job looks at a bot pull request as a whole and says what it needs. #5968 gave the verdict labels and the score; no job writes them. Closes #5969.

## What Changes
- New step `devops roadmap step review --pull N [--repo R] [--head SHA] [--source PATH] [--confirm]` (`roadmap/steps/review.py`, `review_facts.py`, `review_judge.py`). It reads the facts first, decides by rules, and asks the model of the new task `ai.tasks.review` (code default DeepSeek, window 256,000) only when the facts leave the verdict open.
- It writes one verdict label of #5968 and one comment, and takes the next action: mark a draft ready, leave the due fix, close and return the item, or mark the work for an update.
- New settings `roadmap.review.mode` (`plan`), `rounds` (3) and `token_budget` (16,000,000); record keys `review.pull`, `review.rounds`, `review.key`, `review.verdict`; the job `review` of the result line; `verdict_label` in `pr_verdict.py`; the comment marker of the step; the error `RoadmapPullReviewLimitError`.
- A command, its settings and its messages are observable, so the change carries a spec delta.
- The Job launcher and the watch-row trigger are not in this change (#5027 builds the launcher; the follow-up item is under Workflow follow-up of the tasks).

## Capabilities
- `roadmap-pr-review` (new): the facts and the rules, the model, the writes and the actions, the guards and the cap, and the grade of the written label.

## Impact
- Code: `src/devops_cli/roadmap/steps/review.py`, `review_facts.py`, `review_judge.py`, `src/devops_cli/commands/roadmap_step_review.py`, the settings, the defaults, the store keys, `pr_verdict.py`, `job_result.py`, the prompt `roadmap_review_pull.md`.
- Settings: `roadmap.review` goes into `k8s/devops/configmap.example.yaml` in mode `plan`. `ai.tasks.review` stays out of it: an image before this release refuses an unknown task key.
- Rollout: release, then a person sets `roadmap.review.mode: on` after a week of plan-mode result lines. The fit fits one pull request.

## Feasibility
- `pr_verdict.VERDICT_LABELS` maps each label to its verdict, and `read_bot_pulls` reads the first label event of each bot pull request (0.166.0), so a label that the step adds scores with no other change.
- `stage.text_hash` is the hash of the issue text outside the refine section when the plan was made (`stage.py`, `body_hashes`). `Item.updated_at` moves with each label and each record write, so it is no fact of an issue edit.
- GitHub GraphQL gives `reviewThreads` of a pull request and `history` of a ref with `associatedPullRequests { files }` in one request; the compare endpoint gives `merge_base_commit`, which ends the walk of the history.
- `OriginGit.push(branch, None, lease=head)` deletes a branch with `--force-with-lease` (`git_isolation.py`), as the implement job withdraws a branch.
- `job_holds` (`status_sync.py`), `mark_ready(expected_head)`, `apply_return` and `post` (`steps/comment.py`) exist and are the paths that the other steps use.

## Existing Tool Considered
- No open tool gives a verdict of these five kinds from these facts. GitHub's own review (a pull request review) has no verdict labels, no return of an item and no cap. Code review bots (CodeRabbit, PR-Agent) review a diff, not a plan and an issue, and need a hosted service or a second model path. The step reuses the project's code: the GitHub client, the check verdict, `draft_readiness`, `mark_ready`, `apply_return`, the comment writer, the structured client and the verdict labels.
- Cost to build: about 0.6M agent tokens and 1 agent-day; upkeep about 0.1M tokens a month. Run cost: one model call a review at most, on DeepSeek, at most 3 reviews a pull request.
- The change deletes no internal code.
