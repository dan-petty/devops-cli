# Spec Delta

## ADDED Requirements

### Requirement: The investigation reads the context window of the analysis task
The investigation of an item SHALL pass the context window of the `analysis` task to the run, so that the run offers no tool to a request when its messages and a quarter of the window reach the window. The window SHALL end the tools of a run before the counts of requests and tool calls do when the window is small. The run SHALL keep both counts as the loop guard of the job.

#### Scenario: A small window
- **WHEN** the window of the `analysis` task is 6000 tokens and the model calls a tool in every reply
- **THEN** a request offers no tool before the count of requests, and the reply of the model ends the run with its proposal

#### Scenario: A large window
- **WHEN** the window is larger than any run can fill and the model calls a tool in every reply
- **THEN** the count of requests ends the tools, and the last request offers no tool
