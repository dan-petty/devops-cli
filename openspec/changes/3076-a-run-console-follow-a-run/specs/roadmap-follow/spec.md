## Purpose
How the follow command shows what a roadmap Job does: the recorded trace of the last run as the table of the pull request comment, the masked tail of a running Job's pod log, the one issue read it sends, and the secrets it masks.

## ADDED Requirements

### Requirement: The console prints the recorded trace as the comment table
The follow command SHALL print the trace of the last implement run of the item as the table of the pull request comment, with one row for each step: the step, its status, its attempts, its tokens in and out, and its last failing command.

#### Scenario: A record holds a trace of two steps
- **WHEN** A test gives a job record whose trace holds model, check and attempt events for two steps and renders the console.
- **THEN** The output holds the header of the table and one row for each of the two steps.

#### Scenario: A record holds no event
- **WHEN** A test gives a job record whose trace holds no event.
- **THEN** The output holds no table header.

### Requirement: One read of the item gives the trace and the runner Job
The command SHALL read the issue of the item once, and SHALL take the trace, the runner Job name and the runner Job state from the job record of that read. It MUST send no other GitHub request.

#### Scenario: A counting store reads the item once
- **WHEN** A test runs the command for an item whose job record holds a trace and a runner Job name, with a fake store that counts its reads and a fake cluster client.
- **THEN** The store read the item once, and the output holds the table of the trace and the live line of that Job's pod.

### Requirement: The console prints the masked tail of a running Job
While the job record names a runner Job and holds no Job state, the command SHALL print the tail of the log of that Job's pod, masked, and MUST send no GitHub request for it.

#### Scenario: A running Job
- **WHEN** A test gives a job record whose runner Job has no recorded state and a fake cluster client that returns two log lines.
- **THEN** The output holds both lines after the table, and the fake store read the item once.

#### Scenario: A finished Job reads no pod
- **WHEN** A test gives a job record whose runner Job state is recorded.
- **THEN** The command makes no Kubernetes request and prints the recorded table.

### Requirement: An item with no recorded run is named as never run
For an item whose job record holds no runner Job name and no trace, the command SHALL print one line that names the item as never run and MUST send no Kubernetes request.

#### Scenario: A record with no run fact
- **WHEN** A test runs the command for an item whose job record holds no runner Job name and no trace.
- **THEN** The output is one line that names the item as never run, and the fake cluster client counts no request.

### Requirement: Every text of the console is masked
The command MUST pass each line of the pod log and each text of the trace through the masking function of the runner log before it prints it.

#### Scenario: A secret in the pod log
- **WHEN** A test feeds a pod log line that holds a token of the masking rules.
- **THEN** The output holds the masked value and not the token.

#### Scenario: A secret in a trace text
- **WHEN** A test gives a trace whose check command holds a token of the masking rules.
- **THEN** The printed table holds the masked value and not the token.

### Requirement: The command reference states the budget and the access
The command reference SHALL state that the follow command sends one GitHub request, which reads the issue, and reads the pod log with the kubeconfig of the caller, which needs get and list on pods and get on pods/log.

#### Scenario: The docs check
- **WHEN** A test runs the docs check on the generated command reference.
- **THEN** The check passes and the entry of the command states one GitHub request and the three permissions.
