## RENAMED Requirements

- FROM: `### Requirement: The step selects one plan pull request that holds the label plan/needs-fix`
- TO: `### Requirement: The step selects one plan pull request that holds the label verdict/fix-plan`

## MODIFIED Requirements

### Requirement: The step selects one plan pull request that holds the label verdict/fix-plan
The step `fix-plan` SHALL select at most one repository item: an open item with Status Ready whose record holds `stage.pr`, without `implement.job` or claims. Its pull request SHALL be an open draft with `verdict/fix-plan`. Attempts and revisions SHALL be under bounds, with no attempt in 6 hours. Priority SHALL order items. A candidate with a branch stop SHALL log a warning and let selection continue. In mode `plan`, the step SHALL judge all candidates and log the selection and reasons.

#### Scenario: A plan pull request with the label
- **WHEN** a Staged item has an open draft plan pull request that holds `verdict/fix-plan` and no fix-plan mark
- **THEN** the step selects that pull request

#### Scenario: The bounds leave an item out
- **WHEN** the item has as many attempts on the head as `roadmap.fix_plan.head_attempts`, or an attempt less than 6 hours old, or as many revisions on the pull request as `roadmap.fix_plan.revisions`, or a claim, or a runner Job, or a Status other than Ready
- **THEN** the step selects no pull request and makes no model call

#### Scenario: Doubled settings select a plan at the old bounds
- **WHEN** `roadmap.fix_plan.head_attempts` is 4 and `roadmap.fix_plan.revisions` is 6 in the settings of the call, with no restart, and the item has 2 attempts on the head or 3 revisions on the pull request (the defaults)
- **THEN** the step selects that pull request

#### Scenario: A bound above its ceiling
- **WHEN** `roadmap.fix_plan.head_attempts` is 9, 4 times its default and one more
- **THEN** the settings load fails with an error that names `roadmap.fix_plan.head_attempts`

#### Scenario: The pull request is not an open draft with the label
- **WHEN** the recorded pull request has no `verdict/fix-plan` label or is not an open draft
- **THEN** the step selects no pull request and makes no model call

#### Scenario: A person pushed to the branch
- **WHEN** the branch of a candidate pull request holds a commit by an author other than the clone identity
- **THEN** the step leaves that candidate out with a warning and continues selection to the next candidate

#### Scenario: A branch stop selects the next candidate in the same round
- **WHEN** the first candidate has a commit by another author on its branch and a second candidate passes the rules
- **THEN** the step selects the second candidate

#### Scenario: Mode plan judges each candidate
- **WHEN** the step runs in mode plan with multiple plan pull requests
- **THEN** the step logs the mode line naming the would-be selection, and logs each left-out plan with its reason

### Requirement: The review of the head counts the open findings before the repair
In each attempt the verification pass SHALL review the plan of the head. The step SHALL give the planner the open findings of that review and the open findings of the last trusted plan comment. When the review of the head has no open finding but the comment lists an open finding, the step SHALL NOT dismiss the plan, SHALL keep `verdict/fix-plan`, and SHALL report `unchanged`.

#### Scenario: No comment lists an open finding
- **WHEN** no trusted comment of the item lists an open finding for the pull request, and the review of the head plan has one
- **THEN** the next planner request holds the head plan as `previous` and the finding of the review in `problem`

#### Scenario: A comment of an untrusted author
- **WHEN** the only comment that lists an open finding has an author with no write access, and the review of the head plan has an open finding
- **THEN** the next planner request holds the finding of the review in `problem` and no finding of that comment

#### Scenario: The comment lists fewer open findings than the review of the head
- **WHEN** the stage comment lists 1 open finding, the review of the head plan has 2 and the last review of the revision has 1
- **THEN** the step pushes the revision with the result `revised`, and its result line holds `comment=1`, `before=2` and `after=1`

#### Scenario: The review of the head finds no open finding that the comment lists
- **WHEN** the stage comment lists an open finding and the review of the head plan has none
- **THEN** the planner gets no request, the head of the branch does not change, the pull request keeps `verdict/fix-plan`, and the result is `unchanged`

#### Scenario: The screen does not decide the review of the head
- **WHEN** the screen of stage.verify_screen is in mode on and gives the band continue
- **THEN** the verification pass reviews the plan of the head, and its open findings are before

### Requirement: The step pushes a revision that fixes more findings of the head than it adds
When the revision of a repair is not the same plan as the plan that passed the checks, and its reviews fixed more open findings of the head than they added, the step SHALL write the change folder as one commit on the latest default branch, push it with `--force-with-lease` on the head that it read, and set the title and the body of the pull request to those of the revision. A finding of the head is fixed when the last review of the revision does not keep it open.

#### Scenario: A revision with fewer open findings
- **WHEN** the review of the head has two open findings, and the review of the revision marks one `gone` and the other `holds`
- **THEN** the branch holds one new commit whose parent is the latest default branch, the result is `revised`, and the pull request keeps `verdict/fix-plan`

#### Scenario: A revision that fixes the finding of the head and opens a finding on unchanged text
- **WHEN** the review of the head has one open finding, and the review of the revision marks it `gone` and opens one finding whose quote is in text that the revision did not change
- **THEN** the new finding is advice, the step pushes the revision, the result is `cleared`, and the pull request loses `verdict/fix-plan`

#### Scenario: A repair that gives the same plan
- **WHEN** the review of the head has one open finding, the planner answers the plan of the head, and the review of that plan marks the finding `gone`
- **THEN** the two plans are the same plan, because `render_change` gives the same files for both with one change name and one date, so the head of the branch does not change, the result is `unchanged`, the result line holds `success=false`, and the pull request keeps `verdict/fix-plan`

### Requirement: The label goes when no open finding remains
The step SHALL remove `verdict/fix-plan` for the result `cleared` (a pushed revision whose last review has no open finding), for `dismissed` (a review of the head with no open finding and no open finding listed in the last plan comment), and for `regated` only when the review of the gated plan has no open finding and no step failed. It SHALL keep the label for each other result.

#### Scenario: A revision with no open finding
- **WHEN** the review of the head has an open finding and the review of the revision has none
- **THEN** the branch holds the new commit, the result is `cleared`, and the pull request loses `verdict/fix-plan`

#### Scenario: A head plan with no open finding
- **WHEN** the checks pass the plan of the head, the review of it has no open finding, and the last plan comment lists no open finding
- **THEN** the planner gets no request, the head of the branch does not change, the pull request loses `verdict/fix-plan`, the result is `dismissed`, and the comment lists the findings as advice

### Requirement: The step pushes the plan that passed the checks
When the checks refuse the plan of the head and pass a new plan of the planner that is not the same plan as the head, and no revision is pushed, the step SHALL push that gated plan as one commit on the latest default branch with the result `regated`, also when a step after the checks fails. A failure after the checks SHALL keep its class on the result line.

#### Scenario: A gated plan with a clean review
- **WHEN** the checks refuse the plan of the head, the planner answers a plan that they pass, and the review of that plan has no open finding
- **THEN** the branch holds one new commit on the latest default branch, the result is `regated`, the pull request loses `verdict/fix-plan`, and the comment says that the checks refused the old head

#### Scenario: A gated plan with a failed repair
- **WHEN** the checks refuse the plan of the head, the planner answers a plan that they pass, its review has one open finding, and the model call of the repair fails
- **THEN** the branch holds one new commit, the result line holds `result=regated` and `class=provider`, and the pull request keeps `verdict/fix-plan`

### Requirement: A stop of the planner before the review is stopped
When a false premise, an open item whose plan on the default branch creates a path that the premise cites, or a head over the budget stops the planner before a gated plan exists, the step SHALL end the attempt with the result `stopped`, keep `verdict/fix-plan` and the Status of the item, post one fix-plan comment with the evidence, and log `stop=premise`, `stop=blocked` or `stop=over_budget`, with the class `premise_false` for a false premise.

#### Scenario: Each stop
- **WHEN** the planner stops on a false premise, an open blocker or a head over the budget
- **THEN** the result is `stopped`, the result line names the stop and holds no `before`, the label and the Status stay, and one fix-plan comment holds the evidence

### Requirement: The step ends at its time budget
The setting `roadmap.fix_plan.time_budget_seconds` SHALL start with each call of the step. The step SHALL start no plan run and no review run once the budget is spent. Such an attempt SHALL end with the result `timeout`, SHALL push nothing, SHALL keep the label `verdict/fix-plan` and SHALL keep its attempt marks.

#### Scenario: The budget ends during the review of the head
- **WHEN** the budget is 600 seconds and the review of the head ends at 600 seconds with one open finding
- **THEN** the planner gets no request, the head of the branch does not change, the pull request keeps `verdict/fix-plan`, and `fix_plan.result` is `timeout`

#### Scenario: The budget ends after a plan run
- **WHEN** the budget of 600 seconds ends while the planner writes a revision of the plan
- **THEN** no review of the revision starts, the step pushes no revision, the head of the branch does not change, and the result line holds `result=timeout`, `class=timeout` and `step=plan`

### Requirement: The decisions of the step count only blocker and major findings
The step SHALL count only a blocker or a major finding as open. A head whose review has only minor or nit findings SHALL be `dismissed` when the last plan comment lists no blocker or major finding. A pushed revision and a plan that loses the label SHALL list the other findings of its reviews as advice. A failed or a worse revision SHALL list none.

#### Scenario: A head with only a minor finding
- **WHEN** the last plan comment lists no blocker or major finding, and the review of the head has only a quoted finding with the severity `minor`
- **THEN** the planner gets no request, the head of the branch does not change, the result is `dismissed` with `before` 0, the pull request loses `verdict/fix-plan`, and the comment lists the minor finding as advice

#### Scenario: A minor finding of the comment is advice
- **WHEN** the last plan comment lists a minor finding, and the review of the head has no open finding
- **THEN** the result is `dismissed`, and the pull request loses `verdict/fix-plan`

#### Scenario: A pushed revision lists its minor finding as advice
- **WHEN** the step pushes a revision whose review holds a quoted minor finding and no blocker or major finding
- **THEN** the pull request loses `verdict/fix-plan`, and the comment lists the minor finding as advice

### Requirement: A plan comment line that the step cannot read keeps the label
The step SHALL count each line of the open findings section of the last plan comment that matches neither line form. When that count is above zero, the step SHALL end the attempt with the result `unreadable_findings` before any model call, SHALL keep `verdict/fix-plan`, and SHALL write no `dismissed`, `cleared` or `revised` result. The result line SHALL hold `unreadable` with that count, and the step SHALL log one line for each line that it could not read.

#### Scenario: Two lines that neither form matches
- **WHEN** the open findings section of the last plan comment holds two lines that match neither form
- **THEN** the result is `unreadable_findings`, the pull request keeps `verdict/fix-plan`, and the result line holds `unreadable` with the count 2

#### Scenario: An unreadable line starts no model call
- **WHEN** the open findings section of the last plan comment holds a line that matches neither form
- **THEN** the step makes no plan call and no review call, and the record counts the attempt on the head

### Requirement: An open finding of the last plan comment keeps the label
The step SHALL dismiss a plan only when the review of the head and the last plan comment list no blocker or major finding. A head with no open findings in its review, but whose last plan comment lists a blocker or a major finding, SHALL NOT be dismissed, SHALL keep `verdict/fix-plan`, and the attempt SHALL be `unchanged`.

#### Scenario: An old-form comment keeps the label
- **WHEN** the last plan comment holds a finding line of the old form, and the review of the head has no open finding
- **THEN** the result is `unchanged`, and the pull request keeps `verdict/fix-plan`

#### Scenario: A comment with no open finding is dismissed
- **WHEN** the last plan comment lists no blocker or major finding, and the review of the head has no open finding
- **THEN** the result is `dismissed`, and the pull request loses `verdict/fix-plan`
