# roadmap-stage/plan-cache Specification

## Purpose
The plan file that the stage job keeps when a plan passes the gates, and how a later run uses that file again or plans again.

## Requirements

### Requirement: A plan that passes the gates is kept as a file
The planner SHALL write the plan that passes the gates, with its `StageRequest`, to the file `roadmap/stage/<owner>/<repo>/<number>.json` under the data directory, atomically, before the model review. The file SHALL hold a key: the sha256 of the item number, the hash of its title, the hashes of its body from `body_hashes`, the model name of the task `stage`, the name of the toolset and the prompt version. The prompt version SHALL be the sha256 of the texts of the prompts that the planner reads.

#### Scenario: The key follows the input
- **WHEN** the title or the body of an item, the model name, the toolset or the text of a prompt changes
- **THEN** the key is a new value
- **WHEN** only the staged commit moves
- **THEN** the key is the same value

### Requirement: A kept plan with the same key sends the planner no request
When the file of an item holds the key of the current input, the planner SHALL send the model of the task `stage` no request for the plan. It SHALL run the gates again on the current staged commit from the kept plan and the kept request, and it SHALL run the model review again.

#### Scenario: A failed review and a rerun
- **WHEN** the model review of an item fails and the stage job plans the item again with the same input
- **THEN** the second run sends the planner no request and plans the item from the file

#### Scenario: A plan, then a confirm
- **WHEN** `devops roadmap stage --plan` and then `--confirm` plan the same item with a stub model
- **THEN** the planner gets one request in total, and the run of `--plan` made no GitHub write

#### Scenario: The commit moves
- **WHEN** the staged commit moves between two runs and the input is the same
- **THEN** the second run sends the planner no request and measures the groups on the new commit

### Requirement: An unreadable plan file stops the item with its name
A plan file that is no JSON object with a key, or that holds the current key and does not match its model, SHALL raise an error that names the file. The job SHALL NOT plan the item from a new model request in its place. A file with another key is no error: it is a miss.

#### Scenario: A corrupt file
- **WHEN** the plan file of an item holds text that is no JSON
- **THEN** the item fails with an error that names the file, and the planner gets no request

#### Scenario: A file of another key
- **WHEN** the plan file of an item holds another key and text that does not match the model
- **THEN** the job deletes the file and plans the item with a new request

### Requirement: A staged item or a changed key deletes the plan file
The stage job SHALL delete the plan file of an item when it stages the item, and when the key of the input differs from the key in the file. A write that fails SHALL leave the file.

#### Scenario: A staged item
- **WHEN** the job stages an item
- **THEN** the plan file of the item does not exist

#### Scenario: A changed input
- **WHEN** the body of an item changes and the job plans the item again
- **THEN** the old file is deleted before the planner is asked, and a new file with a new key replaces it after the plan passes

### Requirement: Each use of the plan file counts by its result
The planner SHALL add 1 to `devops_cli_roadmap_stage_plan_record_total` with the label `result`: `hit` for a plan taken from the file, `miss` for a plan that the file did not hold, and `written` for a file that the planner wrote. The counter SHALL have 3 series.

#### Scenario: A miss, a write and a hit
- **WHEN** the job plans an item twice with the same input
- **THEN** the counter has 1 point for `miss`, 1 for `written` and 1 for `hit`

### Requirement: A kept plan holds the trace facts of its run
The plan file SHALL hold the facts of the plan runs that made the plan: the names of the tools that they called, and the paths that they read and that the Feasibility section of the plan cites. A kept plan SHALL be gated with these facts, joined with the facts of each later plan run of the item, so the trace gate neither skips a kept plan nor refuses a claim that the first run supported.

#### Scenario: A revision of a kept plan
- **WHEN** the plan file of an item holds a Feasibility sentence that names `read_issue` and facts with `read_issue`, another gate refuses the kept plan, and the planner revises it with a run that calls no tool
- **THEN** the trace gate accepts the revision

#### Scenario: A claim that the facts lack
- **WHEN** the plan file holds a Feasibility sentence that names `read_issue` and facts without it
- **THEN** the trace gate refuses the kept plan

#### Scenario: The facts are bounded
- **WHEN** the plan runs read many paths and the Feasibility section cites one of them
- **THEN** the plan file holds that path and no other

#### Scenario: A new planner model
- **WHEN** the model of the task `stage` changes
- **THEN** the key is a new value and the kept plan is a miss

### Requirement: A kept plan without facts is planned again
A plan file that holds the current key and no trace facts (the format of an older job) SHALL load, and the planner SHALL count it as a miss, delete it and ask the planner model for a new plan.

#### Scenario: A file in the old format
- **WHEN** the plan file of an item holds the current key, a plan and a request, and no facts
- **THEN** the planner sends the model a request, writes a new file with facts, and counts one `miss` and one `written`

### Requirement: A refused kept plan uses no gate return
When the gates refuse a kept plan on the current staged commit, the stage job SHALL NOT count the refusal against `roadmap.stage.gate_returns`. The planner SHALL get a new first reply with the kept plan and its problem, and that reply SHALL have all the returns of `roadmap.stage.gate_returns`. The `stage gate returns` line SHALL count only the returns after that reply.

#### Scenario: Every reply stays refused
- **WHEN** the gates refuse the kept plan of item 1 and each reply of the planner
- **THEN** the planner gets 1 + `roadmap.stage.gate_returns` requests, the item fails, and the `stage gate returns` line holds `returns=` the value of `roadmap.stage.gate_returns`

#### Scenario: The new first reply passes
- **WHEN** the gates refuse the kept plan of item 1 and the next reply of the planner passes
- **THEN** the planner gets one request that holds the kept plan as `previous` and its problem, the item is ready, and the log holds no `stage gate returns` line

### Requirement: No new first reply starts after the Service stops
After the Service stops, the stage job SHALL NOT ask the planner for the new first reply of a refused kept plan. The round SHALL end with `ServiceStoppingError` and SHALL record no failure for the item.

#### Scenario: The Service stops before the new first reply
- **WHEN** the Service stops while the gates refuse the kept plan of item 1
- **THEN** the planner gets no request, the round ends with the stop, and the item has no refused-reply file
