## ADDED Requirements

### Requirement: The health gate leaves out the alerts of the nodes out of service
The gate before the apply and the alert wait after each host SHALL leave out a firing critical alert whose label `node`, else whose label `instance`, names the node of a host out of service. The report SHALL name each alert that they left out, once, and the audit record SHALL hold it. An alert with no such label, or for a node in service, SHALL still stop the apply.

#### Scenario: The alert of a node out of service
- **WHEN** `prometheus.url` is set, node-5 is the node of a host of the offline group, and `NodeNotReady` with `node="node-5"` fires through the apply of node-3
- **THEN** the apply ends `ok`, prints one line that it left out `NodeNotReady` of node-5 because node-5 is out of service, and the audit record holds that line

#### Scenario: The alert of a node in service
- **WHEN** `prometheus.url` is set and `NodeNotReady` with `node="node-2"` fires before the apply
- **THEN** the command exits 1, names the alert, and drains no node

#### Scenario: An alert with no node label
- **WHEN** `prometheus.url` is set, node-5 is out of service, and `ClusterMetricsMissing` with no label `node` or `instance` fires
- **THEN** the health gate names the alert as a problem

## MODIFIED Requirements

### Requirement: Each apply writes an audit record
Each apply that passes the argument checks SHALL write one audit record `infra.apply` with its result (`ok`, `refused` or `stopped`), the caller and the level, with no secret and no path of a key, and add one to `devops_cli_infra_runs_total` with the repo, the command and the result.

#### Scenario: The record of an agent apply
- **WHEN** an agent at `full` applies a plan of node-3
- **THEN** the details of the last audit record are the id, the caller `agent`, the tool `claude_code`, the level, the repo, the commit, the ref, the plan id, the playbook, the limit, the tags, the result, the reason, the hosts, the alerts that the health gate left out and the duration; node-3 has its node, disruptive classes, outcome, step, reason, two runner idents and the workloads that were down; and the record holds no name or folder of the key of `devops ssh`

#### Scenario: The record of a refusal
- **WHEN** an agent applies on a repo at `plan`
- **THEN** the last audit record has the result `refused` and the reason
