## ADDED Requirements

### Requirement: Count a closed roadmap item
The webhook router SHALL add 1 to `devops_cli_service_roadmap_items_closed_total` with the labels `repo` and `reason` for an `issues` `closed` delivery of an issue that holds a `priority/*` label.

#### Scenario: A roadmap item closes as completed
- **WHEN** a signed `issues` `closed` delivery carries an issue with the label `priority/p1-high` and `state_reason` `completed`
- **THEN** the counter has the value 1 with the `repo` of that repository and the `reason` `completed`

### Requirement: Skip a closed candidate
The router MUST NOT count a closed issue that holds no `priority/*` label.

#### Scenario: A candidate closes
- **WHEN** a signed `issues` `closed` delivery carries an issue whose labels hold no `priority/` prefix
- **THEN** no sample of `devops_cli_service_roadmap_items_closed_total` changes

### Requirement: Prime the counter at zero
The router SHALL create `devops_cli_service_roadmap_items_closed_total` at 0 for each managed repository and each reason when it builds its routes.

#### Scenario: The router starts for two repositories
- **WHEN** the webhook router is created for the managed repositories `o/a` and `o/b`
- **THEN** the counter has a 0 sample for each of `completed`, `not_planned`, `duplicate` and `unknown` on each repository

### Requirement: Count a delivery once
The router MUST count each delivery id at most once in its process.

#### Scenario: A delivery repeats
- **WHEN** the same `issues` `closed` delivery id reaches the router twice
- **THEN** the counter with that repository and reason is 1

### Requirement: Count a close with no reason
The router SHALL use the reason `unknown` when a closed roadmap item carries no `state_reason` or a value other than `completed`, `not_planned` or `duplicate`.

#### Scenario: A roadmap item closes with a null reason
- **WHEN** a signed `issues` `closed` delivery carries an issue with the label `priority/p1-high` and `state_reason` null
- **THEN** the counter has the value 1 with the `repo` of that repository and the `reason` `unknown`

### Requirement: Count a close by the App bot
The router SHALL count a closed roadmap item whose `sender.login` is the App bot.

#### Scenario: The jobs close a roadmap item
- **WHEN** a signed `issues` `closed` delivery carries a `priority/p1-high` issue and `sender.login` equal to the App bot
- **THEN** the counter has the value 1 with the `repo` of that repository and the reason of the issue

### Requirement: Panel for closed items
The dashboard `k8s/devops/dashboards/roadmap-service-telemetry.json` SHALL chart `devops_cli_service_roadmap_items_closed_total` by `repo` and `reason` in the row "Roadmap Service".

#### Scenario: The dashboard row queries the counter
- **WHEN** the dashboard test reads the row "Roadmap Service" of `k8s/devops/dashboards/roadmap-service-telemetry.json`
- **THEN** a panel with the unit `short` queries `devops_cli_service_roadmap_items_closed_total` with `job=~"$job"`, grouped by `repo` and `reason`
