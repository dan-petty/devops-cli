## ADDED Requirements

### Requirement: The stage Job names its branch and its lane clone
The Service SHALL set the annotation roadmap.devops-cli/branch to the branch of the item and the annotation roadmap.devops-cli/worktree to the clone path of the round that submits the Job, on each stage Job it creates for an item and on the pod template of that Job.

#### Scenario: A stage Job carries its branch and lane clone
- **WHEN** A test runs the stage round of item 4621 on branch feat/4621-demo in a clone under a temporary folder, with a fake Kubernetes client.
- **THEN** The metadata of the created Job and of its pod template hold roadmap.devops-cli/branch with feat/4621-demo and roadmap.devops-cli/worktree with the clone path of the round.
