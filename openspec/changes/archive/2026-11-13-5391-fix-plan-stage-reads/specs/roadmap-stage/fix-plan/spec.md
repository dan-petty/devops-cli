## ADDED Requirements

### Requirement: The trace gate of a repair judges only the sentences that the repair adds or changes
The trace gate of a fix-plan attempt SHALL NOT judge a Feasibility sentence that the plan of the head holds word for word, because the trace gate of the run that wrote the head passed it. It SHALL judge each sentence that a reply of the planner adds or changes with the reads of the plan runs of the attempt, and SHALL refuse such a sentence that cites a file that those runs did not read.

#### Scenario: A citation that only the run of the head read
- **WHEN** the checks refuse the plan of the head, whose Feasibility section says that `src/devops_cli/sample.py` was read, and the planner answers a plan that keeps that sentence and reads no file
- **THEN** the plan passes the checks, and the result is `regated`

#### Scenario: A new citation of a file that the attempt did not read
- **WHEN** the planner answers a plan that keeps the sentences of the head and adds `` `read_file openspec/config.yaml 1 20` gives the rules of a plan. ``, and reads no file
- **THEN** the result is `failed`, and the reason says that `openspec/config.yaml` was read but the run did not read it

#### Scenario: A sentence that the repair changes
- **WHEN** the planner answers a plan that changes the line number of a citation in a sentence of the head that says `read_file` of `src/devops_cli/roadmap/decision_step.py`, and the attempt read no file
- **THEN** the trace gate refuses the changed sentence and names `src/devops_cli/roadmap/decision_step.py`
