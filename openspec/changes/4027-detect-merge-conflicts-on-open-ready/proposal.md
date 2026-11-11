# Proposal: #4027

## Why

The roadmap Service marks a delivery pull request ready when its checks pass. A later merge into the default branch can make a conflict with that open pull request, and GitHub sends no event or alert for the new conflict. The pull request then stays blocked until a person opens its page or runs `devops pr check-readiness`. Pull request #3961 had this problem. Closes #4027.

## What Changes

- A new status-lane row, `pr_conflicts`, runs after `cloudflare_status`. It is due every 19 minutes and on a first run, calls no model and needs no clone.
- A round lists the open pull requests and reads each one that is not a draft. It takes only a delivery pull request: one into the default branch whose body closes exactly one issue, and that issue is an open Item.
- A conflict gets one comment that names the default branch and the head commit. The ledger `pr_conflicts.json` beside `schedule.json` keeps the head commit of each conflict that has its comment. The row comments again for a new head commit, or for a conflict that returns after a round with no conflict.
- A clean pull request that is only behind the default branch gets no action. The row sends no update-branch request. The issue design asked for a catch-up update, but docs/SDLC.md (Phase 1) and the owner requirement of 2026-11-11 forbid a catch-up update of an open pull request: every push starts the required checks again.
- A mergeable state that GitHub has not computed changes nothing. The next round reads it again.
- `devops pr check-readiness`, the implement watch and the row judge a conflict with one function, `merge_conflict`.
- The row sends the gauge `devops_cli_roadmap_conflicted_pulls`, by `repo`, at the end of each round.
- The Service behavior changes, so the change carries a spec delta.

## Capabilities

- `roadmap-pr-conflicts` (new): the row, its candidates, its comments, its ledger, its gauge and its failures.
- `pr-merge-readiness`: one conflict judgment for the readiness verdict and the row.
- `roadmap-implement-job`: the status lane holds `pr_conflicts` last.
- `metric-instruments`: the due table has 12 rows, so `devops_cli_roadmap_row_seconds` adds at most 36 series for one repository.

## Impact

- Code: `src/devops_cli/roadmap/pr_conflicts.py` (new), `src/devops_cli/roadmap/run.py`, `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/github/client.py` (`PullStatus` holds the merge state, the base branch and the default branch), `src/devops_cli/roadmap/implement/implement_pull.py`, `src/devops_cli/telemetry/instruments.py`, the constants, the defaults and the messages.
- GitHub requests: one listing of the open pull requests, one read of each open pull request that is not a draft, one read of the issue that a candidate closes, and one comment for each new conflict, every 19 minutes.
- Documents: k8s/README.md, CONTEXT.md, docs/TELEMETRY.md.
- No setting, manifest, ConfigMap or Secret changes. The new ledger file is written on the volume of the Service at the first round.
- The change fits one pull request.

## Feasibility

- The REST read of one pull request returns `mergeable`, `mergeable_state`, `base.ref` and `base.repo.default_branch` (https://docs.github.com/rest/pulls/pulls#get-a-pull-request). Command output of 2026-11-11 for an open pull request of this repository: `{"base":"main","default":"main","draft":false,"mergeable":null,"mergeable_state":"unknown"}`. So a read can return the unknown state while GitHub computes it, and the row must wait for the next round.
- The listing of the open pull requests holds the body and the base, but no `mergeable` field (command output: `{"default":"main","has_body":true,"has_mergeable":false}`). So the row reads each candidate on its own, as `release/merge_candidate.py` does.
- GitHub has no webhook event for a conflict that a merge into the base branch makes, so the row polls (ADR 0003).
- `GitHubClient.comment_on_pull` posts a comment on the issue of a pull request, and `closing_numbers` of `release_feed.py` reads the closing keywords of a body.

## Existing Tool Considered

- eps1lon/actions-label-merge-conflict (https://github.com/eps1lon/actions-label-merge-conflict), a maintained GitHub Action, labels a pull request with conflicts and can comment on it after a push to the base branch. It needs a workflow file in each managed repository and a `dirtyLabel` label, and a new label family collides with the label families that hold the item fields (ADR 0016). It does not filter delivery pull requests, does not use the conflict judgment of `devops pr check-readiness`, and sends no gauge to the Service's metrics. The Service already polls each managed repository with its own identity, so a row adds no workflow, label or token.
- GitHub's native mergeable state is the source of the judgment. The row adds no other tool.
- Cost to build: about 18,000 tokens to build, about 4,000 tokens a year to keep and fix, and about 2 hours of elapsed time, as the issue estimates.
- Internal code that the change deletes: the copy of the conflict states in `implement_pull.py` (`_CONFLICT_STATES`) and the inline conflict test in `merge_readiness.py`, which now call `merge_conflict`.
