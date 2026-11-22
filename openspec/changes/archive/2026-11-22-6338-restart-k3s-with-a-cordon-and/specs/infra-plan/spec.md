## MODIFIED Requirements

### Requirement: The disruptive classes
A changed `ansible.builtin.reboot` SHALL be `reboot`. A changed `kubernetes.core.k8s_drain` that drains SHALL be `drain`. A changed `systemd`, `systemd_service` or `service` task that restarts, reloads or stops SHALL be `service-restart:<unit>`, `service-restart-nodrain:<unit>` when `devops_infra_restart_nodrain_units` lists the unit, and none when `devops_infra_nondisruptive_units` lists it. A service result with no arguments SHALL be disruptive, and a templated list SHALL list no unit.

#### Scenario: A unit that does not disrupt the host
- **WHEN** node-1 sets `devops_infra_nondisruptive_units: [demo]`
- **THEN** the restart of `demo` is a change of node-1 with no disruptive class

#### Scenario: A start and a cordon
- **WHEN** a changed systemd_service task has the state started, or a changed k8s_drain task has the state cordon
- **THEN** the change has no disruptive class

#### Scenario: A unit that the host lists for a no-drain restart
- **WHEN** node-3 lists the unit k3s-agent in `devops_infra_restart_nodrain_units`, and the playbook restarts that unit
- **THEN** the plan of node-3 holds the class service-restart-nodrain:k3s-agent and no other disruptive class

#### Scenario: A templated list of no-drain units
- **WHEN** the host variable `devops_infra_restart_nodrain_units` holds `{{ units }}`
- **THEN** the plan lists no unit and every restart stays disruptive
