# Proposal: #5968

## Why

Issue #5968 records that the grades of the stage and implement jobs count only the result of each attempt. They do not show what happened to the pull request after the attempt. From 2026-11-09 to 2026-11-16 the bot opened 69 plan pull requests (57 merged) and 44 delivery pull requests (33 merged), while the 7-day grades were 43/94 for stage and 6/28 for implement.

On 2026-11-16 the owner set one verdict for each plan or delivery pull request of the bot: mergeable (success), needs fix (partial success), discard plan (failure of stage), discard implementation (failure of implement) and issue changed (not scored). No record holds the verdict today, and no report reads it. The owner also gave needs fix one label for each kind, `verdict/fix-plan` and `verdict/fix-implementation`, and `verdict/fix-plan` replaces `plan/needs-fix` (#5968, comment of 2026-11-16).

## What Changes

- The package declares one workflow label for each verdict and kind (`roadmap/workflow_labels.py`): `verdict/mergeable`, `verdict/fix-plan`, `verdict/fix-implementation`, `verdict/discard-plan`, `verdict/discard-implementation` and `verdict/issue-changed`. A person or an agent vet sets a verdict label by hand.
- `verdict/fix-plan` replaces `plan/needs-fix` in each reader and writer: the stage review, the row `plan_drift`, the step and the row `fix-plan`, the row `stage_ready`, the implement selection, the settings text, the documents and the live specs. No code reads both names. Archived changes, the decision records and the recorded fixtures keep the old name. The step fix-plan finds the open findings of a plan comment by the first sentence of its heading, which names no label, so the comments on open plan pull requests still read.
- `devops roadmap eval grades` reads the bot pull requests that were opened in the window from GitHub, with one GraphQL search for each page of 100 pull requests. The search also gives the label events of each pull request. A plan pull request scores stage, and a delivery pull request scores implement. The first verdict label that a pull request got scores it. A pull request with no verdict is open. A first verdict label of the other kind, such as `verdict/fix-plan` on a delivery, leaves the pull request unscored, and the read logs why.
- For stage and implement, the report gives, beside the attempt ratio `p`, the pull requests, the open and the unscored ones, the count and the share of each verdict, and the verdict score: `(mergeable + w × needs fix) / (mergeable + needs fix + discards)`. `w` is the new setting `roadmap.verdict_partial_score` (default 0.5). Issue changed stays out of the score.
- `--dry-run` also prints the GitHub search. With no `service.github_app.slug`, the report reads no verdict and says which setting it needs.
- The command output and its JSON change, and the labels are new or renamed, so the change has spec deltas.
- Rollout: after the release with this change runs, an agent renames the GitHub label `plan/needs-fix` to `verdict/fix-plan` with one `PATCH`, so each open pull request keeps its mark, and then runs the label sync. A stage Job that started on the old image can add the old label again, so the agent checks for it one hour later.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-job-grades`: new requirements for the verdict labels, the read of the first verdict and the verdict score.
- `roadmap-stage/fix-plan`, `roadmap-stage/ready`, `roadmap-stage/verification`, `roadmap-plan-drift`, `roadmap-row-cadence`, `roadmap-implement-job/selection`, `roadmap-item-labels`: each requirement that names `plan/needs-fix` names `verdict/fix-plan`, with no other change of behavior.

## Impact

- Code: `src/devops_cli/roadmap/workflow_labels.py`, a new `src/devops_cli/roadmap/pr_verdict.py`, `src/devops_cli/roadmap/job_grade.py`, `src/devops_cli/roadmap/job_grade_report.py`, `src/devops_cli/commands/roadmap_eval_grades.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/messages.py`, and each reader and writer of `plan/needs-fix` (`git grep -n 'plan/needs-fix' -- src` finds none after the change). `PLAN_NEEDS_FIX_LABEL` of `roadmap/stage/stage_verify.py` becomes `FIX_PLAN_LABEL`.
- Tests: `tests/roadmap/test_pr_verdict.py`, `tests/commands/test_roadmap_eval_grades.py`, `tests/roadmap/test_job_grade_report.py`, and the tests of the renamed readers and writers.
- Documents: `docs/roadmap/job-success.md`, each document that named `plan/needs-fix`, the comment of `k8s/devops/configmap.example.yaml`, and the generated `docs/CONFIGURATION.md`, `docs/ENV_VARS.md` and command reference.
- GitHub: one GraphQL request (1 point) for each 100 bot pull requests of the window. On 2026-11-16 the 7-day window held 113 pull requests: 2 requests.

## Feasibility

- On 2026-11-16, a GraphQL `search` with `is:pr author:app/devops-cli-service created:>=2026-11-09T12:00:00Z` gave 113 pull requests, each with its `repository`, its `title` and its `timelineItems(itemTypes: [LABELED_EVENT])`, at a cost of 1 point for a page of 100. 38 of the first 100 got `plan/needs-fix` at some time. The step fix-plan removes that label after a repair, so only the label events keep the first verdict.
- The titles split the two kinds: a plan pull request has the title `docs(openspec): plan #<n> ...` (`roadmap/plan_check.py`); each other pull request of the bot is a delivery.

## Existing Tool Considered

GitHub's GraphQL search and the label events of the timeline hold the record, `devops gh label sync` creates the labels, and the GitHub session of devops-cli paces and counts the requests. The change builds about 480 lines of code and 520 lines of tests (about 250k tokens, 3 hours) to read and count the verdicts; no open tool scores a GitHub label per job. It deletes the label `plan/needs-fix` and the planned `verdict/needs-fix`.
