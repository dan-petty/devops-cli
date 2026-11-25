# roadmap-job-grades Specification

## Purpose
The job grade of each roadmap workflow from the result line of each attempt in Loki: the grade table of the owner with one action for each grade, the ratio and its Wilson interval, and the report of `devops roadmap eval grades`.

## Requirements

### Requirement: The job grade is the floor of the ratio
The job grade of a workflow SHALL come from its attempts with `infra=false` in the window. Under 30 such attempts the grade SHALL be `too few`. With 30 or more, the grade SHALL be `100` when each attempt is a first pass, and else the highest floor that `p` reaches: `90` (0.90), `80` (0.80), `70` (0.70), `60` (0.60) or `<60`. The grade table SHALL live in one module, `roadmap/job_grade.py`.

#### Scenario: Too few attempts
- **WHEN** a workflow has 29 attempts, each a first-pass success
- **THEN** the grade is `too few`

#### Scenario: Each attempt a first pass
- **WHEN** a workflow has 30 attempts, each a first-pass success
- **THEN** the grade is `100`

#### Scenario: A line with no first-pass counts
- **WHEN** a workflow whose line has no count of fix rounds has 30 successes in 30 attempts
- **THEN** its first pass is not known and the grade is `90`

### Requirement: The report gives the point grade, the interval and the range
The report SHALL give the point grade of `p` at any count of attempts, the Wilson 95% interval of `p` from statsmodels, and the grades of the two bounds.

#### Scenario: 22 of 25 attempts
- **WHEN** a workflow has 22 successes in 25 attempts with `infra=false`
- **THEN** `p` is 0.88, the interval is [0.7004, 0.9583], the point grade is `80`, the range is `70` to `90`, and the grade is `too few`

### Requirement: An infrastructure cut counts in the share and not in the ratio
An attempt with `infra=true` SHALL count in the all-attempts ratio and in the infrastructure share, and not in `p`.

#### Scenario: An infrastructure cut
- **WHEN** a workflow has 22 successes in 25 attempts with `infra=false` and 1 attempt with `infra=true`
- **THEN** `p` is 0.88 and the infrastructure share is 0.0385

### Requirement: eval grades reads the result lines with metric instant queries
`devops roadmap eval grades` SHALL read the result lines with LogQL metric instant queries on `/loki/api/v1/query` of the Loki that `--loki-url` or `loki.url` names. `--repo` SHALL put a match of the repository in each query. `--dry-run` SHALL send no request and print each query.

#### Scenario: The dry run sends no request
- **WHEN** a person runs `devops roadmap eval grades --dry-run`
- **THEN** the command sends 0 requests and prints each LogQL query with the Loki address of `loki.url`

#### Scenario: Loki refuses a query
- **WHEN** Loki answers a query with HTTP 400 and no series-limit message
- **THEN** the report stops with `ServiceRequestError` and the status 400

### Requirement: The report gives the measures of each workflow and repository
For each workflow and repository the report SHALL give the counts, `p`, the interval and the grades, the first-pass ratio, the infrastructure share, the 3 largest failure classes, the action of the grade, the efficiency measures for a line with `tokens` and `seconds`, each version with 10 attempts or more, and the counts of 24 h and 6 h with the signals `broken` and `infra`. A job with no line SHALL get one row with no attempts.

#### Scenario: The report equals a hand count of recorded replies
- **WHEN** Loki answers each planned query with the recorded replies of `tests/fixtures/roadmap/job_grades/replies.json`
- **THEN** the row of each workflow and repository gives the counts, `p`, the interval, the grades, the top classes, the efficiency measures, the versions, the trend and the signals of the hand count

### Requirement: JSON gives one object for each workflow and repository
`devops roadmap eval grades --format json` SHALL print the report as one JSON object with the window, the repository of `--repo`, the Loki address and one object for each workflow and repository.

#### Scenario: The JSON report
- **WHEN** a person runs `devops roadmap eval grades --format json` on the recorded replies
- **THEN** the output is one JSON object whose `workflows` list has one object for each workflow and repository, with its grade

### Requirement: The docs generator writes the grade table into the job success page
`devops docs generate` SHALL write the grade table of `roadmap/job_grade.py` between the markers `<!-- JOB_GRADES_START -->` and `<!-- JOB_GRADES_END -->` of `docs/roadmap/job-success.md`, and `devops docs check` SHALL fail when the table on the page differs from the table of the code.

#### Scenario: A stale table on the page
- **WHEN** the block between the markers of the page holds another table
- **THEN** `devops docs check` names the page as out of date

### Requirement: The report reads the result lines of the Service and the Job pods, in both forms
Each query of `devops roadmap eval grades` SHALL select the containers `service`, `stage` and `fix-plan` of the namespace `devops`, SHALL count only a line that starts with `roadmap job result: ` after the parse, and SHALL parse a JSON line by its `message` field and a plain line as it is. A plain line SHALL NOT make Loki refuse a query. The base of the queries SHALL be one constant, and each query of the dashboard row `Roadmap Job Success` SHALL start with it.

#### Scenario: A JSON line of the Service and plain lines of two Job pods
- **WHEN** Loki holds one JSON line of the Service with `job=implement`, one plain line on stderr of a fix-plan Job pod with `job=fix_plan`, and one plain line on stderr of a stage Job pod with `job=stage`
- **THEN** the report gives 1 attempt to each of `implement`, `fix_plan` and `stage`

#### Scenario: A line in the log of a runner pod
- **WHEN** Loki also holds a plain result line in the container `runner` of a Job pod
- **THEN** the report does not count that line

#### Scenario: The dashboard reads the same lines
- **WHEN** a panel of the row `Roadmap Job Success` reads the result lines
- **THEN** its query starts with the base of the report

### Requirement: One workflow label records each verdict of a bot pull request
The package SHALL declare the workflow labels `verdict/mergeable`, `verdict/fix-plan`, `verdict/fix-implementation`, `verdict/discard-plan`, `verdict/discard-implementation` and `verdict/issue-changed`. A plan pull request SHALL read `verdict/fix-plan` and `verdict/discard-plan`, and a delivery pull request SHALL read `verdict/fix-implementation` and `verdict/discard-implementation`. Both kinds SHALL read `verdict/mergeable` and `verdict/issue-changed`.

#### Scenario: The verdict labels of each kind
- **WHEN** the verdict labels of a plan and of a delivery are read
- **THEN** the plan reads `verdict/mergeable`, `verdict/fix-plan`, `verdict/discard-plan` and `verdict/issue-changed`, the delivery reads `verdict/mergeable`, `verdict/fix-implementation`, `verdict/discard-implementation` and `verdict/issue-changed`, and each label is a workflow label

### Requirement: The first verdict label scores a bot pull request
A bot pull request whose title at its first verdict label event starts with `docs(spec): plan #` or `docs(openspec): plan #` SHALL score stage; others SHALL score implement. The search SHALL read `LABELED_EVENT` and `RENAMED_TITLE_EVENT` (`previousTitle`) with `pageInfo.hasNextPage` in one `timelineItems` call and raise `GitHubUnreadError` on overflow. Unlabeled PRs SHALL use the current title, and cross-kind first labels SHALL stay unscored.

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

### Requirement: The report gives the verdict score beside the attempt ratio
For the stage and implement rows the report SHALL give the pull requests, the open and the unscored ones, the count and the share of each verdict over the pull requests with a verdict, the attempt ratio `p`, and the verdict score `(mergeable + w × needs fix) / (mergeable + needs fix + discards)`, where `w` is `roadmap.verdict_partial_score` (default 0.5). Issue changed SHALL stay out of the score.

#### Scenario: The score of stage
- **WHEN** the plan pull requests of the window have the first verdicts mergeable, mergeable, needs fix, discard plan and issue changed, and one plan has no verdict
- **THEN** the stage row gives 6 pull requests, 1 open, the share 0.4 of mergeable, and the score 0.625

#### Scenario: A delivery that needs a fix and a delivery with the label of a plan
- **WHEN** one delivery pull request has the first verdict label `verdict/fix-implementation` and one has `verdict/fix-plan`
- **THEN** the implement row gives 2 pull requests, 1 unscored, 1 needs fix and the score 0.5

#### Scenario: The partial score setting
- **WHEN** `roadmap.verdict_partial_score` is 1 and the plan pull requests have the first verdicts mergeable and needs fix
- **THEN** the stage score is 1.0

### Requirement: Each wait that refine sets is a success
The success set of refine (`SUCCESS_RESULTS[RoadmapJob.REFINE]`) SHALL hold each value of `NextStep` that is a wait: `ready`, `person`, `split`, `blocked`, `alternatives` and `edit`. It SHALL NOT hold `retry`, `failed` or `none`. A test SHALL fail when a value of `NextStep` other than `retry`, `failed` and `none` is not in the set.

#### Scenario: A ready proposal waits on the verdict of the alternatives row
- **WHEN** the first try of refine gives a ready proposal for a public item that has no verdict of the alternatives row
- **THEN** the line holds `result=alternatives success=true first_pass=true`

#### Scenario: A try that the job failed
- **WHEN** a refine attempt sets the next step `retry`
- **THEN** the line holds `success=false first_pass=false`

#### Scenario: A new next step
- **WHEN** `NextStep` gets a new value and the success set of refine does not hold it
- **THEN** the test of the success set fails

### Requirement: The implement row scores each drafted attempt by the forge state of its delivery
The report SHALL score the `drafted` lines of `implement` that name one pull request (`pull`) once, by that pull request: with n lines, a merge or an open pull request out of draft SHALL give 1 success and n - 1 failures, a close with no merge n failures, and a draft n lines in `drafts_pending`. A line with no `pull` SHALL take the newest delivery of its item. The verdicts and the rows SHALL count only the pull requests opened in the window. With no bot a `drafted` line SHALL count as written.

#### Scenario: Four drafted attempts
- **WHEN** the window holds `drafted` lines with no `pull` of items 7, 8, 9 and 10 and a `stopped` line of item 11, and the deliveries of 7 to 10 merged, are ready, closed with no merge, and are a draft
- **THEN** the implement row has 4 attempts, 2 successes and 1 draft pending

#### Scenario: No bot
- **WHEN** `service.github_app.slug` is not set and the window holds those lines
- **THEN** the implement row has 5 attempts and 4 successes

#### Scenario: Two Jobs on one pull request
- **WHEN** the window holds two `drafted` lines of item 7 that name one pull request, and it merged
- **THEN** the lines count 1 success and 1 failure

#### Scenario: Two pull requests of one item
- **WHEN** item 8 has a `drafted` line of a pull request that closed and one of a pull request that merged
- **THEN** the lines count 1 failure and 1 success

#### Scenario: A merged pull request, then a new draft
- **WHEN** item 9 has a `drafted` line of a pull request that merged and one of a new draft
- **THEN** the lines count 1 success and 1 draft pending

#### Scenario: A pull request opened before the window
- **WHEN** the only bot pull request of a repository was opened before the window
- **THEN** the report gives that repository no row

### Requirement: A version row counts every attempt and gives its infrastructure share
The report SHALL give each version with 10 attempts or more the count of all its attempts, infrastructure cuts included, and the share of the attempts that an infrastructure cut ended, beside the measure of the attempts with no cut.

#### Scenario: A version with an infrastructure cut
- **WHEN** the result lines of one version hold 12 attempts, and 3 of them ended with an infrastructure cut
- **THEN** the version row gives 12 all attempts, 3 infrastructure cuts and the share 0.25, beside the measure of 9 attempts

### Requirement: Counts query label set
The `COUNTS` grade query SHALL include a `keep` stage before its window range whose labels equal its `sum by` labels (`roadmap_job, repo, version, success, infra`).

#### Scenario: Seven-day counts query
- **WHEN** `plan_grade_queries(GradeWindow.D7)` builds the `COUNTS` query
- **THEN** the expression includes `| keep roadmap_job, repo, version, success, infra [7d]` before the range closing brace

### Requirement: Classes query label set
The `CLASSES` grade query SHALL include `success="false"` and `infra="false"` filters and a `keep` stage retaining its `sum by` labels plus `success` and `infra`.

#### Scenario: Seven-day classes query
- **WHEN** `plan_grade_queries(GradeWindow.D7)` builds the `CLASSES` query
- **THEN** the expression keeps `success="false"` and `infra="false"` filters and ends the log pipeline with `| keep roadmap_job, repo, failure_class, success, infra`

### Requirement: Drafted query label set
The `DRAFTED` grade query SHALL keep `roadmap_job`, `result`, and `infra` filters and include a `keep` stage whose labels equal `repo, item, pull, repair_rounds`.

#### Scenario: Seven-day drafted query
- **WHEN** `plan_grade_queries(GradeWindow.D7)` builds the `DRAFTED` query
- **THEN** the expression keeps the implement drafted and infra filters and includes `| keep repo, item, pull, repair_rounds [7d]`

### Requirement: First-passes query label set
The `FIRST_PASSES` grade query SHALL keep `success="true"` and `infra="false"` filters and include a `keep` stage whose labels equal its `sum by` labels.

#### Scenario: Seven-day first-passes query
- **WHEN** `plan_grade_queries(GradeWindow.D7)` builds the `FIRST_PASSES` query
- **THEN** the expression keeps `success="true"` and `infra="false"` filters and includes `| keep roadmap_job, repo, ...` with `_FIRST_PASS_COUNTS`

### Requirement: Efficiency query label set
Each efficiency grade query SHALL include a `keep` stage retaining `roadmap_job, repo` and its unwrapped count label before `| unwrap`.

#### Scenario: Seven-day efficiency query
- **WHEN** `plan_grade_queries(GradeWindow.D7)` builds each efficiency query
- **THEN** the pipeline includes `| keep roadmap_job, repo, <count> | unwrap <count>` before `[7d]`

### Requirement: Split on the series limit
A count grade query SHALL split its window in half down to a `1h` floor and sum the partial vectors when Loki returns HTTP 400 with `maximum number of series`.

#### Scenario: Counts query on a store over the series limit
- **WHEN** Loki answers the `[7d]` `COUNTS` query with HTTP 400 naming `maximum number of series` and answers both `[84h]` half-window queries
- **THEN** `grade_report` queries both `[84h]` halves at `end - 84h` and `end` and returns their summed counts

### Requirement: No split on another 400
The report SHALL NOT split a query when Loki returns HTTP 400 without `maximum number of series`.

#### Scenario: A query with a syntax error
- **WHEN** Loki answers HTTP 400 with `parse error`
- **THEN** `grade_report` sends one query and raises `ServiceRequestError` with status 400

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
