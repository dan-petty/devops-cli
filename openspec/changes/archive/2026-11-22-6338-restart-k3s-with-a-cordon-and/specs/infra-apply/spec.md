## MODIFIED Requirements

### Requirement: One disruptive host at a time
Each disruptive host SHALL run alone in plan order. A host whose classes are all `service-restart-nodrain:<unit>` SHALL be cordoned and SHALL NOT drain. Each other disruptive host SHALL take the drain check and the drain with no `--force`. Every disruptive host SHALL then take a fresh check that must equal its plan, the run, the Ready, GPU and node-health waits, the critical-alert wait when `prometheus.url` is set, and the uncordon only of a node that was schedulable before.

#### Scenario: Two disruptive hosts
- **WHEN** a person applies a plan of node-2 and node-1, both disruptive
- **THEN** the steps are the drain check, the drain, the check, the run and the uncordon of node-1, then the same of node-2

#### Scenario: A node that was cordoned before
- **WHEN** node-3 is cordoned before the apply
- **THEN** the apply ends `ok` and node-3 stays cordoned

#### Scenario: A no-drain restart of a host
- **WHEN** a person applies a plan whose host node-3 holds only the class service-restart-nodrain:k3s-agent
- **THEN** the steps are the cordon of node-3, the fresh check, the run, Ready, the health of the nodes and the uncordon of node-3, with no drain check and no drain

#### Scenario: The dry run of a no-drain host
- **WHEN** a person runs `devops infra apply --dry-run` on a plan whose host node-3 holds only the class service-restart-nodrain:k3s-agent
- **THEN** the listed steps hold the cordon of node-3 and no drain check and no drain
