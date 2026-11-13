## ADDED Requirements

### Requirement: The run output has no color
Every `ansible-runner` run of a playbook, the plan, the fresh check and the run of an apply, SHALL get `ANSIBLE_NOCOLOR=True` in its environment, so the event text and the plan of a host are the same in a color terminal and with no terminal. A skip result that does not read as JSON, such as a result with color codes, SHALL stay unchecked.

#### Scenario: The environment of the plan run
- **WHEN** a person plans `ansible/playbooks/03_k3s.yaml`
- **THEN** `ansible-runner` gets `ANSIBLE_NOCOLOR=True`

#### Scenario: A plan with no terminal and its apply in a color terminal
- **WHEN** a person plans node-3 with no `TERM`, and applies the plan with `TERM=xterm-256color`
- **THEN** each `ansible-runner` run gets `ANSIBLE_NOCOLOR=True`, the fresh check of node-3 equals the plan, and the apply exits 0

#### Scenario: A skip result in color
- **WHEN** the recorded run in a color terminal skips a task of node-1 and a task of node-3 by a false `when`, with the color codes around the text of each skip
- **THEN** each of the two tasks is unchecked, and the rest of the plan of each host equals the plan of the run with no terminal
