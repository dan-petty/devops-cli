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

### Requirement: The dry run shows the containers of the shape of the template
The dry run of `devops k8s run-job` SHALL read the CronJob of the template from the manifests of the checkout, a local read, and SHALL show its one container, or on the phases the init containers `prepare` and `agent` and the container `publish`, each with its `--phase` and `--work`. With no manifest, it SHALL show the container that the template names.

#### Scenario: Both shapes
- **WHEN** the dry run of `--template runner` reads a template of one container, and then a template on the phases
- **THEN** it shows the container `runner` with the args, and then the three containers with their phase args
