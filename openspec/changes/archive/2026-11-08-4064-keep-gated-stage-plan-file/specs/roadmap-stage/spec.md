## RENAMED Requirements

- FROM: `### Requirement: A stage plan writes nothing`
- TO: `### Requirement: A stage plan makes no GitHub write`

## MODIFIED Requirements

### Requirement: A stage plan makes no GitHub write
`devops roadmap stage --plan` SHALL make no write to GitHub or to the remote repository, also when the round holds a removal or a rejection. It SHALL write at most the plan file of each item that it plans.

#### Scenario: Plan only
- **WHEN** the command runs with `--plan` on a roadmap that holds a removal, a rejection and a ready item
- **THEN** the store receives no write, no branch is pushed or deleted, no GitHub write request is sent, and the plan file of the ready item exists

## ADDED Requirements

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
