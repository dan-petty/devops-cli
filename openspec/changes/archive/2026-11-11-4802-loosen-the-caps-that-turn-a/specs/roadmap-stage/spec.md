## MODIFIED Requirements

### Requirement: The change passes the OpenSpec validation
When the `openspec` binary is on `PATH`, the job SHALL run `openspec validate <change> --strict --json` on the change before it writes to git. A failed validation SHALL go back to the model with the output of the tool, `roadmap.stage.gate_returns` times at most. A failure after the last return SHALL stop the item. Without the binary, the comment on the issue SHALL say that the validation did not run.

#### Scenario: The validation fails once
- **WHEN** the first plan fails the validation and the second plan passes it
- **THEN** the job stages the second plan and the model got the output of the first failure

#### Scenario: The validation fails twice
- **WHEN** the first plan and the plan after each return fail the validation
- **THEN** the job stops the item after the last return, pushes nothing, and reports the output of the last failure

#### Scenario: No openspec binary
- **WHEN** the `openspec` binary is not on `PATH`
- **THEN** the job stages the item and its comment says that the validation did not run

### Requirement: The validation judges the change against the base specs
The job SHALL run the validation in a scratch directory that also holds the base spec of each capability the change has a delta for. Any issue in the report of OpenSpec SHALL count as a problem and SHALL go back to the model with its text, as a refused reply does, even for a valid change, such as a delta that `openspec archive` would refuse. The one exception is the INFO note that a change sets `skip_specs`.

#### Scenario: A MODIFIED requirement that the base spec lacks
- **WHEN** the plan modifies a requirement whose name is not in the base spec of an existing capability
- **THEN** the validation reports the refusal and the model gets it as the problem to correct

#### Scenario: A change that sets skip_specs
- **WHEN** OpenSpec reports only the INFO message that `skip_specs` is set
- **THEN** the validation gives no problem

#### Scenario: Another issue next to the skip_specs message
- **WHEN** OpenSpec reports the `skip_specs` message and a second INFO issue
- **THEN** the validation gives a problem that holds the second issue and not the `skip_specs` message

### Requirement: The plan names files that exist at the staged commit
The job SHALL check each path of the reply against the tracked files of the staged commit: the paths of `reads` and `changes`, the paths in the code spans of the tasks, and the paths in `verify`. A path SHALL pass when the commit holds it, or when `creates` of its group or of an earlier group lists it. A missing path SHALL go back to the model with the files of the commit of the same name. A missing path after the last return SHALL stop the item with no draft pull request.

#### Scenario: A test file that moved
- **WHEN** a group changes `tests/test_scanner_tool_executor.py` and the commit holds `tests/security/test_scanner_tool_executor.py`
- **THEN** the job asks the model again, and the problem names the missing path and lists `tests/security/test_scanner_tool_executor.py`

#### Scenario: The second reply has a missing path
- **WHEN** the second reply and each later reply still name `tests/test_scanner_tool_executor.py`
- **THEN** the job stops the item with the problem after the last return, pushes no branch and opens no draft pull request

#### Scenario: A path in a task or in a verify command
- **WHEN** a code span of a task or the `verify` command of a group names a file that the commit lacks and no group up to it creates
- **THEN** the problem names that file

#### Scenario: A created path
- **WHEN** a group changes `tests/test_new.py`, lists it in `creates`, and a later group reads it
- **THEN** the job finds no missing path
- **AND** when only a later group lists it in `creates`, the earlier group names a missing path

#### Scenario: A word that is no path
- **WHEN** a code span holds `status/blocked`, `--strict` or `uv run devops ci docs`
- **THEN** the job finds no missing path

#### Scenario: A name with no folder
- **WHEN** a code span of a task or the `verify` command holds `ruff.toml` or `grep step_files.py`
- **THEN** the job finds no missing path
- **AND** a path of `reads` or `changes` with no folder is still checked

### Requirement: A split reply is checked for the form of its commands
The job SHALL check the groups of a split reply for the form of their `verify` commands, as it checks the groups of a plan, and SHALL send a reply with a problem back to the model as a refused reply.

#### Scenario: A split group with two commands
- **WHEN** a split group has a `verify` of ``uv run devops ci test tests/x.py` and `git push origin HEAD``
- **THEN** the reply goes back to the model with the `verify` problem, and the model is asked once more

### Requirement: The stage job checks the form of the plan title
The stage job SHALL run `title_problems` on the title that it builds for the plan. A reply whose title has a problem SHALL go back to the model with the problems, `roadmap.stage.gate_returns` times at most, and a reply with a problem after the last return SHALL stop the item.

#### Scenario: A summary that repeats plan
- **WHEN** the first reply has the summary `plan the form of a task`
- **THEN** the job sends the problem that names the word `plan` to the model, and the second reply sets the title

#### Scenario: A summary with the issue number
- **WHEN** the reply has the summary `Stop #1 dropping a comment` for issue 1, and each returned reply is the same
- **THEN** the job sends a problem that names `#1`, and the item makes no plan

### Requirement: A failed item waits for the retry delay
The job SHALL leave an item out of the selection until the `RETRY_AFTER` wait of the class in `stage.failed_class` has passed since `stage.failed_at`, and SHALL take the other items in the same round. A missing or unknown class SHALL wait as `ci_infra`. `--item` SHALL take the item it names. A failure time that is no time SHALL hold the item for no time. No setting SHALL change the wait, and the job SHALL NOT store the time it waits until.

#### Scenario: The delay has not passed
- **WHEN** the item failed 59 minutes ago with the class `provider`
- **THEN** the job leaves the item out and takes the next item

#### Scenario: The delay has passed
- **WHEN** the item failed 1 hour ago with the class `provider`
- **THEN** the job takes the item again

#### Scenario: A refused plan waits longer
- **WHEN** the item failed 59 minutes ago with the class `plan_defect`
- **THEN** the job leaves the item out, and takes it again 1 hour after the failure

#### Scenario: A reply that breaks the schema waits six hours
- **WHEN** the item failed 1 hour ago with the class `parser`
- **THEN** the job leaves the item out, and takes it again 6 hours after the failure

#### Scenario: An item that changed does not wait
- **WHEN** the item failed with the class `head_moved`
- **THEN** the job takes the item in the next round

#### Scenario: A record with no class
- **WHEN** the job record holds `stage.failed_at` of 59 minutes ago and no `stage.failed_class`
- **THEN** the job leaves the item out, and takes it 1 hour after the failure

#### Scenario: A class that is unknown
- **WHEN** the job record holds a `stage.failed_class` that is no failure class
- **THEN** the item waits as `ci_infra` and the selection does not fail

#### Scenario: A person names the item
- **WHEN** the item failed 1 minute ago and a run names it with `--item`
- **THEN** the job takes the item

#### Scenario: A stale setting
- **WHEN** a config file still holds `roadmap.stage.retry_hours`
- **THEN** the settings load without error and the stage settings hold no such field

### Requirement: The stage check refuses an overlapping create path
The stage check SHALL refuse a plan that lists a path in `creates` that another open plan also creates. The problem SHALL name the path and the open item. The reply SHALL go back to the model as a refused reply.

#### Scenario: Two open plans create the same module
- **WHEN** open item #3308's `tasks.md` marks `src/devops_cli/roadmap/stage_constants.py` with `(new)`, and the reply of the item lists the same path in `creates`
- **THEN** the check returns a problem that names the path and #3308

### Requirement: The plan body passes the plan form before the draft opens
The stage job SHALL build the body of the draft pull request with `build_plan_body` and SHALL NOT write a body that `plan_body_problems` refuses. A refused body SHALL go back to the model with the other problems of the reply, and a refusal after the last return SHALL stop the item as a reply that fails its checks. A text with a closing keyword SHALL keep its own stop.

#### Scenario: The plan body passes
- **WHEN** the model gives a `pull_request_body` of 100 characters for issue 42
- **THEN** the draft pull request gets a body that `plan_body_problems` accepts

#### Scenario: A short body is returned once
- **WHEN** the first reply has a `pull_request_body` of 5 characters and the second reply has a text of 100 characters
- **THEN** the second request holds the problem of the short body, and the draft opens with the second body

#### Scenario: A second refusal stops the item
- **WHEN** the second reply and each later reply have a `pull_request_body` of 5 characters
- **THEN** the job stops the item, opens no draft pull request and pushes nothing

### Requirement: The module of a model that a plan extends is in changes
The stage proposal check SHALL return a problem that names the module of a model when a plan reads an attribute that the model lacks and no group lists that module in `changes`, and SHALL return no such problem when a group lists it.

#### Scenario: The plan omits the model module
- **WHEN** A plan reads `PullStatus.labels` and no group lists `src/devops_cli/github/client.py` in `changes`.
- **THEN** `check_proposal` returns a problem that tells the model to add `src/devops_cli/github/client.py` to a group's `changes`.

#### Scenario: The plan lists the model module
- **WHEN** A plan reads `PullStatus.labels` and a group lists `src/devops_cli/github/client.py` in `changes`.
- **THEN** `check_proposal` returns no problem for the model attribute.

#### Scenario: A second reply with the same gap stops the item
- **WHEN** The first, the second and each later reply read `PullStatus.labels` and omit `src/devops_cli/github/client.py` from `changes`.
- **THEN** The stage job records a failure of the item with `RoadmapStageError`, and the plan holds no ready change.

### Requirement: A reply of placeholders ends the item
The stage job SHALL end an item at once, with no second request, when a reply is a placeholder in `why`, `existing_tool`, each line of `feasibility` and each task of each group. The item SHALL fail with the error `RoadmapStageDegenerateError`, the job SHALL keep the reply as a refused reply, and `devops_cli_roadmap_stage_total` SHALL count the item under the result `degenerate`. A reply with one text that is no placeholder SHALL go back to the model as a refused reply.

#### Scenario: The first reply is all placeholders
- **WHEN** the first reply of item 1 holds `x` or `placeholder` in every text of the plan
- **THEN** the model gets one request, the item fails with `RoadmapStageDegenerateError`, and the result of the item is `degenerate`

#### Scenario: A reply with one real text
- **WHEN** the first reply holds `x` in `why` and in `feasibility` and a real text in `existing_tool`
- **THEN** the reply goes back to the model, as for any refused reply, and the result stays `failed` if the reply after the last return is refused

### Requirement: A refused revision of a repair round returns
A revision of a repair round that the checks refuse SHALL go back to the planner with the refused revision as `previous` and the problem as `problem`, `roadmap.stage.gate_returns` times (default 3) for each repair round, as a refused first reply does. A revision that the checks accept SHALL cause no extra planner call. A revision that is a placeholder in every text SHALL end the item with no return.

#### Scenario: The first revision is refused and the second passes
- **WHEN** the checks refuse the first revision of a repair round and accept the second
- **THEN** the planner gets a third request with `previous` set to the refused revision and `problem` set to the problem of the checks, and the job stages the second revision

#### Scenario: The returns follow the setting
- **WHEN** `roadmap.stage.gate_returns` is 2 and the checks refuse each revision of a repair round
- **THEN** the planner gets two returns for the round and no third

#### Scenario: The revision passes
- **WHEN** the checks accept the first revision of a repair round
- **THEN** the planner gets no return for the round

### Requirement: A revision that stays refused ends the item and is kept
When the checks refuse the revision of a repair round after its last return, the item SHALL fail with a text that names the review and the problem, the planner SHALL make no further request, and `<n>.refused.json` SHALL hold each refused reply of the item with its problem, the refused revisions included.

#### Scenario: Both revisions are refused
- **WHEN** the checks refuse the revision and each returned revision of a repair round
- **THEN** the item fails, the planner has made five requests, and the failure text holds the problem of the last refusal

#### Scenario: The file holds the earlier replies
- **WHEN** the checks refuse the first reply, accept the reply after the return, and refuse each revision of the repair round
- **THEN** the file `1.refused.json` holds the refused first reply and each refused revision, each with its problem

### Requirement: A failed item keeps its refused replies
When a plan fails, the stage job SHALL write the refused replies and their problems to the file `<n>.refused.json` beside the plan file of item `<n>`, under the key of the plan input. A new failed plan SHALL replace the file, and the staging of the item SHALL delete it. A reply over the byte bound SHALL be dropped with its size kept, and a problem SHALL be masked for secrets and cut to the character bound.

#### Scenario: The gates refuse a plan twice
- **WHEN** the gates refuse the first reply of item 1 and the reply after each return
- **THEN** the file `1.refused.json` holds the key and each reply, each with its problem, and no plan file exists

#### Scenario: The item is staged
- **WHEN** a later round stages item 1
- **THEN** the file `1.refused.json` is deleted
