## Purpose
How `devops roadmap follow` shows what a roadmap Job does: the live trace of the running Job from its pod log, the recorded history of past runs from the job record of the issue body, the GitHub requests it sends, the table it prints and the secrets it masks.

## ADDED Requirements

### Requirement: The command shows a running Job and a finished Job
The `devops roadmap follow` command SHALL print the live trace of a running Job and the recorded history of finished Jobs.

#### Scenario: Running Job
- **WHEN** A person runs `devops roadmap follow` for an issue whose runner Job runs.
- **THEN** The command prints the steps, the tool calls, the check results and the attempts that the pod log holds.

#### Scenario: Finished Job
- **WHEN** A person runs `devops roadmap follow` for an issue whose runner Job has ended.
- **THEN** The command prints the rows that the job record of the issue body holds.

### Requirement: The command sends at most one GitHub request for the history
The command MUST send at most one GitHub request for the history and MUST send no GitHub request for the live trace.

#### Scenario: Live trace reads the pod
- **WHEN** A person runs `devops roadmap follow` while the Job runs.
- **THEN** The command reads the pod log and sends one GitHub request for the issue body.

### Requirement: The output has the shape of the PR comment table
The command SHALL print its rows with the header and the column order of the PR comment table.

#### Scenario: Header and columns
- **WHEN** The command prints a trace or a history.
- **THEN** The header and the column order equal those of the PR comment table.

### Requirement: The output masks secrets
The command MUST mask each value with the rules that the log lines use before it prints the value.

#### Scenario: Secret in a pod log line
- **WHEN** The pod log holds a value that the log masking rules mark as a secret.
- **THEN** The command prints the masked value and not the secret.

### Requirement: The inbox and explain output names the follow command
The `devops roadmap inbox` and `devops roadmap explain` commands SHALL print the follow command for each item that they list.

#### Scenario: Inbox and explain rows
- **WHEN** A person runs `devops roadmap inbox` or `devops roadmap explain` for an item.
- **THEN** The output holds the follow command for that item.
