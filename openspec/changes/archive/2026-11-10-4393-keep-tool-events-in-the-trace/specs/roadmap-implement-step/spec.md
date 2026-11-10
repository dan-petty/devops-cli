## ADDED Requirements

### Requirement: The events of a trace stand in the order of the run
The step SHALL add the model event of a reply when the reply comes, so that the events stand in the order of the run: a reply, then the tool calls that it asks for. A reply that the step never receives whole, such as one that the output cap cut, SHALL get its event when its turn ends.

#### Scenario: The order of the events
- **WHEN** a step ends after a reply with one tool call, a reply with two tool calls and a last reply
- **THEN** the kinds of the events are `model`, `tool`, `model`, `tool`, `tool`, `model`, then the `attempt` event

#### Scenario: A long run
- **WHEN** a step makes 101 requests and 150 tool calls, and the events do not fit `CONST_ROADMAP_IMPLEMENT_TRACE_CHARS` characters
- **THEN** the encoded trace is not longer than the bound, it holds no `model` event, it holds the newest `tool` events in the order of the run and then the `attempt` event, and `dropped` counts the 101 model events and the older tool events

### Requirement: A shell call in a trace holds its exit status
The `tool` event of a `shell` call whose result ends with the status line of the shell SHALL hold `status`, the exit code of the command, and no text of its output. A call with no such line, and a call of another tool, SHALL hold no `status`.

#### Scenario: The exit status of a shell call
- **WHEN** the result of a `shell` call ends with the status line that holds the exit code 128
- **THEN** the `tool` event holds `status` 128 and no text of the output

#### Scenario: A shell call with no status
- **WHEN** the result of a `shell` call has no status line, or the line holds no exit code
- **THEN** the `tool` event holds no `status`
