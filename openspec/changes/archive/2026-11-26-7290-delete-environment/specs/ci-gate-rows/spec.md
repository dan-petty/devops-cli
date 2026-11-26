## ADDED Requirements

### Requirement: The kube-linter row lints the product base
The check registry of `devops ci` SHALL hold a row `kube-linter` whose command is `uv run devops k8s lint k8s/devops`, so that the row lints the build of the product base with the checks of `.kube-linter.yaml`. The row SHALL come before the rows of `tests/gate`.

#### Scenario: The row runs the lint of the product base
- **WHEN** a test reads the check spec of the row `kube-linter`
- **THEN** its command is `uv run devops k8s lint k8s/devops`, it has no other command, and it comes before the row `k8s` in the registry

### Requirement: The k8s row refuses a tracked environment file
The `k8s` row of `devops ci` SHALL fail when git tracks under `k8s/` a file that is not in `k8s/devops/` and is not a Markdown document, and SHALL name each such file. The check SHALL read the paths of the git index only, and no manifest.

#### Scenario: A tracked file outside the product base
- **WHEN** the rule reads a fixture git tree that tracks `k8s/llm/values.yaml`, `k8s/catalog.toml` and `k8s/devops-copy/service.yaml`
- **THEN** it names the three files

#### Scenario: The product base, a document and an untracked file
- **WHEN** the fixture tree tracks `k8s/devops/service.yaml` and `k8s/llm/README.md`, and holds an untracked file under `k8s/`
- **THEN** the rule names none of them

### Requirement: The k8s row refuses an in-cluster image registry in the product base
No object that a YAML file of `k8s/devops/` declares or that its kustomization renders SHALL run the Distribution image (Docker Hub's `registry`), be the Namespace `registry`, or be in namespace `registry`. The `k8s` row SHALL fail on such an object.

#### Scenario: The product objects
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the row passes only when no object of the product base is one of these

## REMOVED Requirements

### Requirement: The charts row renders the chart sources, and the k8s row stays local
**Reason**: The row held only checks of the Tempo chart of the environment (#7290).
**Migration**: The environment repository checks its charts.

### Requirement: The k8s row refuses a change to an environment path
**Reason**: The environment files are deleted, so no branch can change one (#7290).
**Migration**: See `The k8s row refuses a tracked environment file`.

### Requirement: The kube-linter row lints the Applications of the tree
**Reason**: This repository holds no Argo CD Application (#7290).
**Migration**: See `The kube-linter row lints the product base`.
