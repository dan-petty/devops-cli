## ADDED Requirements

### Requirement: The kube-linter row lints the Applications of the tree
The check registry of `devops ci` SHALL hold a row `kube-linter` whose command is `uv run devops k8s lint`, with no TARGET, so that the row lints the build of each path source of the Argo CD Applications with the checks of `.kube-linter.yaml`. The row SHALL come before the rows of `tests/gate`.

#### Scenario: The row runs the lint of the tree
- **WHEN** the test reads the check spec of the row `kube-linter`
- **THEN** its command is `uv run devops k8s lint`, it has no other command, and it comes before the row `k8s` in the registry
