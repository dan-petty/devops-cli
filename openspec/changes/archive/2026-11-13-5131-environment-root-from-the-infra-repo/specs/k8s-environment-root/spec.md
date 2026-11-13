## Purpose
The commands of devops-cli that read the environment tree of a cluster take its root from an option or from the project profile of an infra repo, never from a fixed folder of devops-cli, so the tree can live in another repository.

## ADDED Requirements

### Requirement: The environment tree comes from the option or the project profile
A command that reads the environment tree SHALL take its root from `--k8s-dir`, else from the profile fact `kubernetes.dir` of the repository that holds the current folder, else from the one entry of `infra.repos` whose checkout gives it. The source paths of the Applications SHALL be relative to the nearest folder at or above the root with `.git`, else to the parent of the root. With two such infra repos, or with no source, the command SHALL stop with a `ConfigurationError`.

#### Scenario: The option wins
- **WHEN** `--k8s-dir` names a copy of `k8s/` outside any repository
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
- **THEN** the command stops and names `--k8s-dir` and `.devops/project.toml`

### Requirement: The commands read every path of the tree under its root
A command that reads the environment tree (the `devops k8s` stack, pin, lint and Ollama commands, `devops grafana dashboards`, `devops ai gateway render` and `devops argo`) SHALL read each file of the tree that no option of its own names under the root of the tree, such as the values files, the manifests, the gateway config, the dashboards folder and the Application folders.

#### Scenario: A copy of the tree gives the same deploy
- **WHEN** `devops k8s deploy-stack --stack all --dry-run` runs once with no option and once with `--k8s-dir` at a copy of `k8s/`
- **THEN** both dry runs name the same releases, values files, manifests, kustomizations and post-Helm paths, each under its own root

#### Scenario: A copy of the tree gives the same dashboard lint
- **WHEN** `devops grafana dashboards lint --json` runs once with no option and once with `--k8s-dir` at a copy of `k8s/`
- **THEN** both give the same report and exit code

#### Scenario: The default dashboard folders
- **WHEN** `devops grafana dashboards lint` runs with no path in a checkout of devops-cli
- **THEN** it lints `monitoring/dashboards` of the tree and `dashboards` of the product base `k8s/devops` together

#### Scenario: A gateway render of another tree
- **WHEN** `devops ai gateway render --k8s-dir <copy>` runs with no file option
- **THEN** it reads and names the gateway config of the copy

#### Scenario: A lint with no target
- **WHEN** `devops k8s check-deprecated --dry-run` runs in a checkout whose profile declares `[kubernetes] dir = "cluster"`
- **THEN** the plan scans the folder `cluster` of the checkout

### Requirement: deploy-stack reads the product base apart from the tree
`devops k8s deploy-stack` and `teardown-stack` SHALL read the manifests, the post-Helm files and the ConfigMap template of the product base from `--product-dir`, else from `k8s/devops` of the repository that holds the current folder. When a selected stack has product paths and the product base is not a folder, the command SHALL exit 1 and name the folder and `--product-dir`.

#### Scenario: The product base stays in the checkout
- **WHEN** `devops k8s deploy-stack --stack all --k8s-dir <copy> --dry-run` runs in a checkout of devops-cli
- **THEN** the dry run names `k8s/devops` of the checkout as `product_dir`, and each product manifest under it

### Requirement: The names of live objects are settings
The names that devops-cli finds a live object by SHALL come from the settings `argocd.root_applications`, `gitea.applications`, `mattermost.team`, `cloudflare.access.application_name`, `cloudflare.access.allow_policy_name` and `cloudflare.access.bypass_policy_name`. Their defaults SHALL be the names of the live objects of the homelab.

#### Scenario: The defaults
- **WHEN** no source sets the six settings
- **THEN** they are `[bootstrap, cluster]`, `[gitea, gitea-manifests]`, `homelab`, `Homelab Ingress`, `Allow homelab authorized emails` and `homelab-public-ip-bypass`

#### Scenario: The root Application that gitops sync syncs
- **WHEN** `argocd.root_applications` is `[root, apps-of-apps]` and `devops argo gitops sync --dry-run` runs with no `--app-name`
- **THEN** the plan syncs `apps-of-apps`

#### Scenario: The Access names of the settings
- **WHEN** the settings name the application `Example Ingress` and the policies `Allow example emails` and `example-bypass`
- **THEN** the dry run of `devops cloudflare access sync` creates the application and the two policies with those names

#### Scenario: The Gitea Applications of the settings
- **WHEN** `gitea.applications` is `[forge]`
- **THEN** the dry run of `devops k8s doctor --stack gitea` reads the Application `forge` and no other Application
