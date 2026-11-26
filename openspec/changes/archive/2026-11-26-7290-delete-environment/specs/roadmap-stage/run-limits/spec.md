## MODIFIED Requirements

### Requirement: The window of the stage task is documented with its source
The page `docs/roadmap/stage.md` SHALL state the `context_window` of the task `stage` and the file that sets it, and the `max_input_tokens` of the model of that task and that the gateway config of the environment tree sets it. The stated `context_window` SHALL equal the value in `k8s/devops/configmap.example.yaml`.

#### Scenario: The page and the files agree
- **WHEN** a person reads the page and `k8s/devops/configmap.example.yaml`
- **THEN** the page states 256,000 and `k8s/devops/configmap.example.yaml`, and 1,048,576 and the gateway config of the environment repository
