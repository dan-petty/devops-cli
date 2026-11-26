## ADDED Requirements

### Requirement: A command refuses a tree that does not hold what it reads
A command that needs a path that the environment tree does not hold SHALL stop with a `ConfigurationError` that names the tree, the path, `--k8s-dir` and `infra.repos`. A command over the Argo CD Applications SHALL stop the same way when `argocd/apps` and `argocd/bootstrap` hold no Application. No command SHALL read another file in place of a missing one, or report success on such a tree.

#### Scenario: A tree with no Application
- **WHEN** `devops k8s lint`, `image-pins`, `catalog`, `check-deprecated`, `deploy-stack`, `teardown-stack` or `bootstrap`, also in a dry run, or `devops argo gitops drift` runs on a tree that holds only the folder `devops`
- **THEN** it exits non-zero and names `argocd/apps`, `--k8s-dir` and `infra.repos`

#### Scenario: A tree with no file that the command reads
- **WHEN** `devops k8s ollama prune --dry-run`, `devops ai gateway render`, `devops argo cd apps bootstrap-gitops --dry-run` or `devops grafana dashboards sync --dry-run` runs on such a tree
- **THEN** it exits non-zero and names the missing file or folder, `--k8s-dir` and `infra.repos`

#### Scenario: A tree that lacks a file of a stack
- **WHEN** `devops k8s deploy-stack` or `teardown-stack` runs, also in a dry run, on a tree with its Applications that lacks the root kustomization, or a manifest, a kustomization or a post-Helm path of a selected stack
- **THEN** it exits non-zero and names the missing path, and lists no path that is not there

#### Scenario: A checkout of devops-cli with no infra repo
- **WHEN** `devops k8s lint` runs with no `--k8s-dir` and no `infra.repos` in a checkout of devops-cli
- **THEN** it exits non-zero, because the checkout declares no `kubernetes.dir`

### Requirement: A watched path with nothing is not reported clean
`devops argo gitops drift` and `watch --once` SHALL stop with a `ConfigurationError` that names each watched path that holds no manifest and shows no change of one.

#### Scenario: A missing or empty folder
- **WHEN** the command runs with `--path` at a folder that holds a manifest and a folder that is missing or empty
- **THEN** it exits non-zero and does not report a clean tree

#### Scenario: A folder that lost its manifests
- **WHEN** `devops argo gitops drift --path <folder>` runs after each manifest of the saved baseline left the folder
- **THEN** it exits 0 and reports each one as deleted

## MODIFIED Requirements

### Requirement: The environment tree comes from the option or the project profile
A command that reads the environment tree SHALL take its root from `--k8s-dir`, else from the profile fact `kubernetes.dir` of the repository that holds the current folder, else from the one entry of `infra.repos` whose checkout gives it. The source paths of the Applications SHALL be relative to the nearest folder at or above the root with `.git`, else to the parent of the root. With two such infra repos, or with no source, the command SHALL stop with a `ConfigurationError`.

#### Scenario: The option wins
- **WHEN** `--k8s-dir` names a copy of an environment tree outside any repository
- **THEN** the root is the copy, and the source paths are relative to its parent

#### Scenario: The profile of the current repository
- **WHEN** the current folder is in a checkout whose `.devops/project.toml` declares `[kubernetes] dir = "k8s"`
- **THEN** the root is `k8s` of that checkout

#### Scenario: One infra repo gives the tree
- **WHEN** the current repository gives no `kubernetes.dir`, and one infra repo checkout detects `k8s` from its `ansible.cfg`
- **THEN** the root is `k8s` of that checkout

#### Scenario: Two infra repos give a tree
- **WHEN** two infra repo checkouts give `kubernetes.dir`
- **THEN** the command stops and names both roots and `--k8s-dir`

#### Scenario: No source gives a tree
- **WHEN** no option, no current profile and no infra repo give a tree
- **THEN** the command stops and names `--k8s-dir`, `infra.repos` and `.devops/project.toml`

### Requirement: The commands read every path of the tree under its root
A command that reads the environment tree (the `devops k8s` stack, pin, lint and Ollama commands, `devops grafana dashboards`, `devops ai gateway render` and `devops argo`) SHALL read each file of the tree that no option of its own names under the root of the tree, such as the values files, the manifests, the gateway config, the dashboards folder and the Application folders.

#### Scenario: A copy of the tree gives the same deploy
- **WHEN** `devops k8s deploy-stack --stack all --dry-run` runs once with `--k8s-dir` at a fixture environment tree and once with `--k8s-dir` at a copy of it
- **THEN** both dry runs name the same releases, values files, manifests, kustomizations and post-Helm paths, each under its own root

#### Scenario: A copy of the tree gives the same dashboard lint
- **WHEN** `devops grafana dashboards lint --json` runs once on a fixture environment tree and once on a copy of it
- **THEN** both give the same report and exit code

#### Scenario: The default dashboard folders
- **WHEN** `devops grafana dashboards lint` runs with no path and with an environment tree in a checkout of devops-cli
- **THEN** it lints `monitoring/dashboards` of the tree and `dashboards` of the product base `k8s/devops` together

#### Scenario: A gateway render of another tree
- **WHEN** `devops ai gateway render --k8s-dir <copy>` runs with no file option
- **THEN** it reads and names the gateway config of the copy

#### Scenario: A lint with no target
- **WHEN** `devops k8s check-deprecated --dry-run` runs in a checkout whose profile declares `[kubernetes] dir = "cluster"`, and that folder holds an Application
- **THEN** the plan scans the folder `cluster` of the checkout
