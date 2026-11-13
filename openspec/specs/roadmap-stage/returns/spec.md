# roadmap-stage/returns Specification

## Purpose
When the stage job returns an item to New: a rejected plan pull request, a premise that needs an open plan, a false absence, the limit of refused plans, and the ceiling on the returns of a refused reply.

## Requirements

### Requirement: The job returns an item whose premise needs an open plan
The stage job SHALL return an item to New when a cited path is missing at the staging commit and an open plan creates it. The stage job SHALL record each such open item in `refine.blocked_by` of the item. The stage job SHALL plan no change for the returned item. The stage job SHALL make no model call for the returned item.

#### Scenario: A missing path that an open plan creates
- **WHEN** the issue cites `src/devops_cli/roadmap/stage_constants.py`, the staging commit lacks it, and open item #3308 has a plan on the default branch whose `tasks.md` marks that path `(new)`
- **THEN** the stage job records #3308 in `refine.blocked_by` of the item, sets the item to New, and plans no change for it

#### Scenario: No model call for the returned item
- **WHEN** the premise probe of an item finds a dependency on an open plan
- **THEN** the stage job makes no model call for that item

### Requirement: A plan pull request closed with no merge leaves a comment on the issue
In each run the job SHALL read the pull request that `stage.pr` names for each open New or Ready item whose plan is not on the default branch. For a pull request that is closed and not merged, the job SHALL post one comment on the issue with the marker of the stage job, the marker of a rejected plan, the number of the pull request and the reason. For an open or merged pull request it SHALL post none. With `--item` it SHALL read only the pull request of the named item.

#### Scenario: The pull request is merged or open
- **WHEN** the plan pull request of an item is merged, or is open
- **THEN** the job posts no comment on the issue and writes no `stage.rejected`

#### Scenario: The pull request closed with no merge
- **WHEN** the plan pull request of a Ready item is closed and not merged
- **THEN** the job posts one comment on the issue that holds both markers, the number of the pull request and the reason

#### Scenario: The item is named
- **WHEN** a person runs the job with `--item` for one item
- **THEN** the job reads the pull request of that item and of no other item

### Requirement: The reason is the last long comment of a person
The reason SHALL be the text of the last comment on the closed pull request that has more than `EVIDENCE_MIN_CHARS` characters, that a person with write access wrote, and that the Service bot did not write. The job SHALL mask secrets in the reason and cut it to `CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS` tokens. When no comment qualifies, the comment on the issue SHALL say that no comment gives a reason, and the job SHALL still record the rejection.

#### Scenario: The last comment is one word
- **WHEN** a closed plan pull request holds a long comment of the owner and then the comment `rejected` of the owner
- **THEN** the comment on the issue holds the long comment and not the word `rejected`

#### Scenario: The newest long comment is not a reason
- **WHEN** the newest long comment on a closed plan pull request was written by the Service bot or by an account with no write access
- **THEN** the comment on the issue holds the newest long comment of a person with write access

#### Scenario: No comment gives a reason
- **WHEN** a closed plan pull request holds only the comment `rejected` of the owner
- **THEN** the comment on the issue says that no comment gives a reason, and the job still records the rejection

#### Scenario: The reason holds a secret
- **WHEN** the last long comment holds a token
- **THEN** the comment on the issue holds the masked text

### Requirement: A rejected plan returns the item to New
After the comment, the job SHALL clear every key of the stage record, write `stage.rejected` as JSON, and set a Ready item to New. An item that the same run stages again SHALL keep its Status. The job SHALL make each write for one item in the order: the delete of the branch, the comment, the Status with the record.

#### Scenario: A Ready item with a rejected plan
- **WHEN** a Ready item has a plan pull request that closed with no merge
- **THEN** the item is New, its record holds no `stage.branch`, no `stage.pr` and no `stage.ready`, and `stage.rejected` holds the number of the pull request, the hash of the text that the plan came from, the time of the close and the files that the reason names

#### Scenario: A person already returned the item
- **WHEN** an item that is New has a plan pull request that closed with no merge
- **THEN** the job posts the comment and writes the record, and the Status stays New

#### Scenario: A named Ready item is planned again
- **WHEN** a person runs the job with `--item` for a Ready item whose plan pull request closed with no merge, and the run stages a new plan for it
- **THEN** the item is still Ready, the record holds the new `stage.pr`, and the record holds no `stage.rejected`

### Requirement: A rejected plan loses its staged branch when only the Service wrote to it
For a rejected plan the job SHALL delete the staged branch of the record with the rule of a closed item: every commit of the branch past `origin/<default branch>` has the identity of the session as author or is a clean merge. When any other commit exists, the job SHALL keep the branch and say so in the plan. The job SHALL delete the branch only while it ends at the commit that the plan judged. A branch that is gone needs no delete.

#### Scenario: Only the Service wrote to the branch
- **WHEN** a plan pull request closed with no merge and its branch holds one commit by the session identity
- **THEN** the job deletes the branch from `origin`, and the item is no longer held by a pushed branch

#### Scenario: A person added a commit
- **WHEN** a plan pull request closed with no merge and its branch holds a commit by another author
- **THEN** the job keeps the branch, the plan lists it with its reason, and the comment and the record are still written

#### Scenario: A person pushed a commit after the plan
- **WHEN** a person pushes a commit to the branch after the plan judged it and before the job deletes it
- **THEN** the job keeps the branch, and the comment and the record are still written

#### Scenario: A named run with the branch pushed
- **WHEN** a person runs the job with `--item` for an item whose branch holds only commits of the session identity
- **THEN** the run deletes the branch, and the same run can stage the item

### Requirement: The job leaves out an item whose plan was rejected until its text or a named file changes
The job SHALL leave out an item that holds a `stage.rejected` record, and the reason SHALL name the pull request. The leave-out SHALL end when the hash of the text outside the refine section differs from the recorded hash, or when a commit on the default branch changed a file of the record after the close. The recorded hash SHALL be `stage.text_hash`. The rule SHALL apply to the rejections that the same run finds. `--item` SHALL overrule the rule.

#### Scenario: Nothing changed
- **WHEN** an item is Ready again, holds a `stage.rejected` record, its text hashes as recorded and no named file changed
- **THEN** the job leaves it out and the reason names the pull request

#### Scenario: A person edits the text
- **WHEN** a person edits the body of that item, and the pushed branch of the rejected plan was deleted
- **THEN** the job takes the item and the branch of the closed pull request holds nothing

#### Scenario: A named file changes
- **WHEN** a commit on the default branch changed a file that the reason names, after the pull request closed
- **THEN** the job takes the item

#### Scenario: A person edited the text before the job read the closed pull request
- **WHEN** a person edits the body of an item, and then closes its plan pull request, and the job reads the closed pull request in its next round
- **THEN** the job takes the item after the rejection, and does not wait for a second edit

#### Scenario: A refine round rewrites its section
- **WHEN** refine writes its section in the body and the text outside the section is the same
- **THEN** the job still leaves the item out

#### Scenario: The item is named
- **WHEN** a person runs the job with `--item` for that item
- **THEN** the job takes the item

#### Scenario: The same run finds the rejection
- **WHEN** a run finds a rejected plan whose branch a person deleted before the run
- **THEN** the run does not select the item

### Requirement: The plan request holds the reason of a rejected plan
The request of a plan call SHALL hold the key `rejected_plan` for an item whose record holds `stage.rejected`: the text of the newest comment that holds the marker of a rejected plan and that a trusted author wrote, without either marker and cut to `CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS` tokens. A request for any other item SHALL hold no such key. The prompt SHALL say that the key holds the reason of a person and that the plan must not state again the premise that the reason shows to be false.

#### Scenario: An item that was rejected and then edited
- **WHEN** the job plans an item that holds `stage.rejected` after a person edited its body
- **THEN** the request holds `rejected_plan` with the reason and with no marker

#### Scenario: A named item whose rejection the same run finds
- **WHEN** a person runs the job with `--item` for an item whose plan pull request closed with no merge and the record has no `stage.rejected` yet
- **THEN** the request holds `rejected_plan` with the reason that the run copies to the issue

#### Scenario: An item that was never rejected
- **WHEN** the job plans an item with no `stage.rejected` record
- **THEN** the request holds no `rejected_plan` key

### Requirement: A false absence returns the item
The stage job SHALL return an item to New with the probe evidence when the issue body states that a
cited class field is absent and the staging commit defines it, and SHALL make no model call for the
item.

#### Scenario: The body says a field is absent while the class defines it
- **WHEN** The body says that `PullStatus` defines no `labels` and `PullStatus` at the staging commit defines `labels`
- **THEN** The stage job returns the item to New, and its comment quotes the probe line that names the file and line of `labels`

#### Scenario: The item waits on a body edit
- **WHEN** The body states that a cited class field is absent and the staging commit defines it
- **THEN** The stage job records `refine.next_step` as `edit` for the item

### Requirement: Refused plans count on their body
When the stage job records a `plan_defect` failure, it SHALL write in the same write `stage.plan_defects`, the count of such failures on the body, and `stage.plan_defects_body`, the hash of the body without the block of the alternatives job. A body that hashes differently SHALL start the count at 1. A failure of another class SHALL keep both keys and its own `RETRY_AFTER` wait.

#### Scenario: A second refused plan on the same body
- **WHEN** the job records the second `plan_defect` failure of an item whose body did not change
- **THEN** the job record of the item holds `stage.plan_defects` 2, and the item stays Ready

#### Scenario: An edited body starts a new count
- **WHEN** an item has 2 `plan_defect` failures, a person edits its body, and the job records a `plan_defect` failure
- **THEN** the job record holds `stage.plan_defects` 1, and the item stays Ready with no comment of the job

#### Scenario: A provider failure does not count
- **WHEN** an item has 2 `plan_defect` failures and the job records a `provider` failure
- **THEN** the job record holds `stage.plan_defects` 2 and `stage.failed_class` `provider`

### Requirement: The limit of refused plans returns the item to New
The `plan_defect` failure that brings the count to `CONST_ROADMAP_STAGE_PLAN_DEFECT_LIMIT` (3) SHALL return the item to New in the same round. The job SHALL post one comment that lists in sequence, one line each and with no handle that pings, the problems of the refused replies of the last plan and then the reason of the failure, unless the checks refused the last reply. It SHALL then set New with the failure keys and clear both count keys.

#### Scenario: The third refused plan
- **WHEN** an item has 2 `plan_defect` failures on its body and a round of the Service refuses its plan again
- **THEN** the item is New, one comment of the stage job lists the problems of the refused replies, and the job record holds no `stage.plan_defects`

#### Scenario: A failure with no refused reply
- **WHEN** the failure at the limit holds no problem of a refused reply
- **THEN** the comment lists the reason of the failure

#### Scenario: A plan run that stops after a refused reply
- **WHEN** the checks refuse the first reply of the last plan and the second plan run stops
- **THEN** the comment lists the problem of the refused reply and then the reason of the stop

#### Scenario: A problem that names a handle
- **WHEN** a problem at the limit holds a handle and a line break
- **THEN** the comment shows the problem on one line with the handle in a code span

### Requirement: A staged item clears the count of refused plans
A run that stages an item SHALL clear `stage.plan_defects` and `stage.plan_defects_body` in the write of its stage record.

#### Scenario: A staged item after a refused plan
- **WHEN** a round stages an item whose job record holds a count of refused plans
- **THEN** the job record of the item holds neither count key

### Requirement: The returns of a refused reply have a hard ceiling and stop with the Service
The settings load SHALL refuse a value of `roadmap.stage.gate_returns` above `CONST_ROADMAP_STAGE_GATE_RETURNS_CEILING` (3), because each return is one more plan run. After the Service stops, the stage job SHALL start no return of a refused reply: the round SHALL end with `ServiceStoppingError` and SHALL record no failure for the item.

#### Scenario: A value over the ceiling
- **WHEN** `roadmap.stage.gate_returns` is 4
- **THEN** the settings load fails with an error that names `gate_returns`

#### Scenario: The Service stops during a plan
- **WHEN** the Service stops while the planner gives a reply that the checks refuse
- **THEN** the planner gets no return, the round ends with the stop, and the item has no refused-reply file

### Requirement: A refused reply that makes progress gets one extra return
When the checks refuse a reply at the last return of `roadmap.stage.gate_returns`, the stage job SHALL give the reply one more return only when no finding of the reply before it stays (the same gate and the same text, with the digits masked) and no finding of the reply has the fix class `never` in `stage_finding_classes.json`. The rule SHALL make no model call.

#### Scenario: The findings fall as in item 5136
- **WHEN** the replies have 3 findings, then 1 of them two times, then 1 new finding, and the reply of the extra return passes the checks
- **THEN** the planner gets 5 requests and the item stages

#### Scenario: A finding stays
- **WHEN** each reply has the same finding of the gate `paths`
- **THEN** the planner gets 1 + `roadmap.stage.gate_returns` requests and the item fails

#### Scenario: A finding of a code that no return fixed
- **WHEN** the last reply has a new `stage_problem_missing_test_file` finding and no finding of the reply before
- **THEN** the reply gets no extra return

### Requirement: An item gets one extra return at most
An item SHALL get at most `CONST_ROADMAP_STAGE_GATE_RETURN_EXTENSIONS` extra returns, so a reply SHALL get at most `roadmap.stage.gate_returns` + 2 planner requests. No extra return SHALL start after the Service stops.

#### Scenario: Each reply has a new finding
- **WHEN** each reply removes the finding of the reply before and has a new one
- **THEN** the planner gets `roadmap.stage.gate_returns` + 2 requests and the item fails

#### Scenario: The Service stops before the extra return
- **WHEN** the Service stops while the planner gives the reply that gets the extra return
- **THEN** the extra return does not start and the round ends with the stop

### Requirement: Each extension decision and its end are logged and counted
Each decision at the last return SHALL log one `stage gate extension:` line with its counts and its result, and in a run of a repository SHALL add 1 to `devops_cli_roadmap_stage_gate_extension_total` by `result`: `extended`, `used`, `first`, `stuck` or `never`. Each extra return SHALL log one `stage gate extension end:` line with the result `passed`, `refused` or `ended`, and in a run of a repository SHALL add 1 to `devops_cli_roadmap_stage_gate_extension_ends_total` by `result`.

#### Scenario: The extra return passes
- **WHEN** the replies fall as in item 5136 and the reply of the extra return passes the checks
- **THEN** the job logs one `stage gate extension:` line with `returns=3 in=1 gone=1 stuck=0 new=1 never=0 result=extended`, one `stage gate extension end:` line with `returns=4 result=passed`, and one count of each counter

#### Scenario: The second decision of an item
- **WHEN** each reply removes the finding of the reply before and has a new one
- **THEN** the decisions have the results `extended` and `used`, and the end line has `result=refused`

#### Scenario: The run ends before the checks judge the extra reply
- **WHEN** the Service stops while the planner gives the reply that gets the extra return
- **THEN** the end line has `result=ended`

### Requirement: The failure of a refused reply names the stop
The failure of a reply that the checks refuse after its last return SHALL name the number of the return and the stop of the extension, with the gates of the findings that stopped it.

#### Scenario: A finding stays
- **WHEN** each reply has the same finding of the gate `paths`
- **THEN** the failure text says that a finding of the gate `paths` stays from the reply before

#### Scenario: The item used its extra return
- **WHEN** each reply removes the finding of the reply before and has a new one
- **THEN** the failure text says that the item used its extra return
