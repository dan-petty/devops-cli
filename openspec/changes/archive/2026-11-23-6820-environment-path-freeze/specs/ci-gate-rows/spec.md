## ADDED Requirements

### Requirement: The k8s row refuses a change to an environment path
The `k8s` row of `devops ci` SHALL refuse a branch that changes an environment path, until step 17 of `docs/HOMELAB_REPO_SWITCH.md` deletes the environment files. An environment path SHALL be a file of `k8s` outside `k8s/devops` and `k8s/overlays/homelab/devops` that is not a Markdown file. The row SHALL read the changed paths from `git diff --name-only --no-renames origin/main...HEAD`, and SHALL fail when git cannot give them.

#### Scenario: A change to an environment file
- **WHEN** the branch changes `k8s/llm/valkey.yaml` and `docs/a.md`
- **THEN** the check fails with one finding that names `k8s/llm/valkey.yaml`
- **AND** its message names dan-petty/homelab

#### Scenario: A new environment file
- **WHEN** the branch adds `k8s/new-app/deployment.yaml`
- **THEN** the check fails with one finding that names `k8s/new-app/deployment.yaml`

#### Scenario: A move out of the environment
- **WHEN** the branch moves `k8s/llm/valkey.yaml` to `k8s/devops/valkey.yaml`, so git gives both paths
- **THEN** the check fails with one finding that names `k8s/llm/valkey.yaml`

#### Scenario: The product base, a document and a file outside k8s
- **WHEN** the branch changes `k8s/devops/kustomization.yaml`, `k8s/overlays/homelab/devops/kustomization.yaml`, `k8s/README.md` and `src/devops_cli/cli.py`
- **THEN** the check passes

#### Scenario: git cannot give the changed paths
- **WHEN** `git diff` exits with status 128, because the checkout has no `origin/main`
- **THEN** the check fails, and its message names the status, the error of git and `origin/main`
