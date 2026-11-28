## MODIFIED Requirements

### Requirement: The policy keeps a Job of the Service from reaching beyond its pod
The policy SHALL refuse a Job unless `app.kubernetes.io/name` on its pod template is `devops-cli-job`, a non-stage pod sets `app.kubernetes.io/component` neither to `roadmap-stage` nor to `project-review`, the pod sets no `priorityClassName`, `nodeName` or `imagePullSecrets`, the container sets no `command`, the Job sets no `manualSelector`, and `completions` and `parallelism` are 1 or unset.

#### Scenario: A pod with the label of the Service
- **WHEN** the Job from the template changes the label `app.kubernetes.io/name` of its pod to `roadmap-service`, to the name of another pod, or removes the labels
- **THEN** the policy refuses the Job and names the rule

#### Scenario: A Job that reaches beyond the pod
- **WHEN** the Job from the template changes in one way: a `priorityClassName`, a `nodeName`, an `imagePullSecrets` entry, a container `command`, `manualSelector`, 2 for `completions`, or 2 for `parallelism`
- **THEN** the policy refuses the Job and names the rule

#### Scenario: The default values
- **WHEN** the Job from the template names `completions: 1`, `parallelism: 1` and `manualSelector: false`
- **THEN** the policy admits the Job

#### Scenario: A non-stage Job with component project-review
- **WHEN** `uv run devops ci --check --only k8s` runs the policy check for a non-stage Job whose pod template sets `app.kubernetes.io/name: devops-cli-job` and `app.kubernetes.io/component: project-review`
- **THEN** the policy refuses the Job with the pod label rule

#### Scenario: Stage and implement Jobs stay admitted
- **WHEN** `uv run devops ci --check --only k8s` runs the policy check for a stage Job with `app.kubernetes.io/component: roadmap-stage`, an implement Job with `roadmap-implement`, and an implement Job with no `app.kubernetes.io/component` label
- **THEN** the policy admits each of those Jobs
