## ADDED Requirements

### Requirement: Publish writes no folder of the run
The `publish` phase of implement, fix-checks, fix-conflict and stage SHALL make its new repository in the temporary folder, and SHALL write no file in the run folder or in the data folder, so it runs on a run folder that its container mounts read-only (#3700).

#### Scenario: A read-only run folder
- **WHEN** the run folder, its `state/` and `out/`, and for fix-checks the runs folder of the data folder are read-only, and `publish` runs
- **THEN** it pushes the commits of the run, as on a writable run folder

### Requirement: A prepare that leaves the item out ends the run with its reason
When the plan leaves the named item out, `prepare` SHALL print the plan and write a state that says the run ended, with the reason of the plan. `publish` SHALL print that reason and exit 0.

#### Scenario: An item that is not eligible
- **WHEN** the plan leaves item 1 out because it is not Ready, and `prepare` and then `publish` run on one run folder
- **THEN** both exit 0, the output of `prepare` holds the plan, and the output of `publish` holds the reason

### Requirement: The dry run shows each shape of the runner template under its condition
The dry run of `devops k8s run-job` SHALL read no CronJob. For the runner template, it SHALL show the create of a Job of one container `runner` with the args, under the condition that the CronJob holds one container, and the create of a Job of the init containers `prepare` and `agent` and the container `publish`, each with the args and its `--phase` and `--work`, under the condition that the CronJob holds them.

#### Scenario: Both shapes
- **WHEN** the dry run of `--template runner` runs
- **THEN** it sends no request, and shows the container `runner` and the three containers, each under its condition
