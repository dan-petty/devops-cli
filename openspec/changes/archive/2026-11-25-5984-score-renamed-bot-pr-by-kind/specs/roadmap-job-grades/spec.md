## MODIFIED Requirements

### Requirement: The first verdict label scores a bot pull request
The verdict search SHALL select `LABELED_EVENT` and `RENAMED_TITLE_EVENT` (`previousTitle`) with `pageInfo.hasNextPage` in one `timelineItems` call and raise `GitHubUnreadError` with pull request number and timeline reason if `hasNextPage` is true. A bot pull request SHALL score by the title active at its first verdict label event (before the rename uses `previousTitle`; after uses the current title). Unlabeled PRs SHALL use the current title, and cross-kind first labels SHALL stay unscored.

#### Scenario: A plan that needs a fix and then can merge
- **WHEN** the label events of a plan pull request are `type/docs`, `verdict/fix-plan` and `verdict/mergeable`, in this order, and the step fix-plan removed `verdict/fix-plan`
- **THEN** the verdict of the plan is needs fix

#### Scenario: A delivery with the label of a plan
- **WHEN** the label events of a delivery pull request are `type/feature`, `verdict/fix-plan` and `verdict/mergeable`
- **THEN** the delivery is unscored, and the read logs that its first verdict label is a label of the other kind

#### Scenario: The old label
- **WHEN** the label events of a plan pull request are `plan/needs-fix` and `verdict/mergeable`
- **THEN** the verdict of the plan is mergeable

#### Scenario: Plan verdict before rename
- **WHEN** a bot pull request opens with a plan title, gets `verdict/mergeable`, and later renames to a delivery title
- **THEN** `read_bot_pulls` returns `PullKind.PLAN` with `Verdict.MERGEABLE` and counts it for stage

#### Scenario: Delivery verdict after rename
- **WHEN** a bot pull request opens with a plan title, renames to a delivery title, and gets `verdict/fix-implementation`
- **THEN** `read_bot_pulls` returns `PullKind.DELIVERY` with `Verdict.NEEDS_FIX` and counts it for implement

#### Scenario: More than one page of timeline events
- **WHEN** GitHub returns `timelineItems.pageInfo.hasNextPage` as true on a pull request
- **THEN** `read_bot_pulls` raises `GitHubUnreadError` naming the pull request number and timeline page limit

### Requirement: eval grades reads the bot pull requests of the window with one search
`devops roadmap eval grades` SHALL read the pull requests of the bot of `service.github_app.slug` that changed in the window, with their label and rename events, head branch, state, draft flag, and creation time, in one GraphQL search per 100 pull requests (`--repo` scopes the search). When the verdict read raises `GitHubUnreadError`, `grade_report` SHALL record `verdict_error`, keep all Loki rows, and render `verdicts not read: <reason>`.

#### Scenario: The search of the window and the repository
- **WHEN** a person runs `devops roadmap eval grades --repo example/app` at 2026-11-09T12:00:00Z with the slug `example-bot`
- **THEN** the command sends one GraphQL search for `is:pr author:app/example-bot updated:>=2026-11-02T12:00:00Z repo:example/app`

#### Scenario: No slug
- **WHEN** `service.github_app.slug` is not set
- **THEN** the command sends no request to GitHub, and its text names `service.github_app.slug`

#### Scenario: GitHub verdict read fails while Loki succeeds
- **WHEN** Loki returns grade rows and the GitHub verdict read raises `GitHubUnreadError`
- **THEN** `devops roadmap eval grades` prints `verdicts not read: <reason>` and keeps the Loki grade rows

## ADDED Requirements

### Requirement: One fix-plan label constant
Every reader and writer of `verdict/fix-plan` under `src/devops_cli/roadmap` SHALL import `FIX_PLAN_LABEL` from `workflow_labels.py` (re-exported by `stage_verify.py`), with only that single literal declaration in `workflow_labels.py`. A test SHALL verify `VERDICT_LABELS[PullKind.PLAN][FIX_PLAN_LABEL]` equals `Verdict.NEEDS_FIX`.

#### Scenario: Single source and VERDICT_LABELS match
- **WHEN** a test inspects `FIX_PLAN_LABEL` from `stage_verify.py` and scans `src/devops_cli/roadmap`
- **THEN** `VERDICT_LABELS[PullKind.PLAN][FIX_PLAN_LABEL]` is `Verdict.NEEDS_FIX` and no other module defines the literal `verdict/fix-plan`

### Requirement: Six verdict labels in docs
ADR 0021 Status History and `github_project_management.md` SHALL list all six verdict labels (`verdict/mergeable`, `verdict/fix-plan`, `verdict/discard-plan`, `verdict/issue-changed`, `verdict/fix-implementation`, and `verdict/discard-implementation`), and ADR 0021 Status History SHALL note that `plan/needs-fix` is out of date while preserving the accepted body hash.

#### Scenario: Documents match VERDICT_LABELS
- **WHEN** a test compares every label key in `VERDICT_LABELS` against ADR 0021 Status History and `github_project_management.md`
- **THEN** all six labels appear in both files and ADR 0021 Status History records that `plan/needs-fix` was replaced
