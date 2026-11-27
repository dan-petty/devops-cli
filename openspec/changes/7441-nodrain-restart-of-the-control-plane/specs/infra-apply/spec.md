## MODIFIED Requirements

### Requirement: Stop before own node and control-plane node
An agent apply, and so the `infra-apply` step job, SHALL stop before a disruptive host on the node of its own pod, and before a control-plane host with a disruptive class other than `service-restart-nodrain:<unit>`, and report a workstation run. An agent at `full` SHALL apply a control-plane host whose disruptive classes are all `service-restart-nodrain:<unit>`, as a person does.

#### Scenario: Own node in the plan
- **WHEN** the plan has a disruptive host that is the node of the step job pod
- **THEN** the job stops before that host, uncordons no node, and posts a message that names the host and the workstation run.

#### Scenario: A drain or a reboot of the control-plane node
- **WHEN** an agent at `full` applies a plan whose control-plane host holds `service-restart:demo` or `reboot`
- **THEN** the command exits 1, the host stops at the step `drain check` with a reason that names the control-plane node, the no-drain restart and the workstation run, and no node changes

#### Scenario: A no-drain restart of the control-plane node
- **WHEN** an agent at `full` applies a plan whose control-plane host node-1 holds only `service-restart-nodrain:demo`
- **THEN** the apply ends `ok` with the steps cordon node-1, the check of node-1, the run of node-1 and uncordon node-1

#### Scenario: An agent at safe and a no-drain restart of the control-plane node
- **WHEN** an agent at `safe` applies that plan
- **THEN** the command exits 1, says that the apply needs `full`, and starts no process
