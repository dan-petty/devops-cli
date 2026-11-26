## MODIFIED Requirements

### Requirement: The Service row runs only from a clean main
With `--confirm`, row 13 SHALL add the repository to `service.repos` and, unless `--no-deploy`, push `devops/devops-cli` with `--rotate` and deploy stack `devops` when it changed `service.repos` or a webhook secret. It SHALL do so only from a clean checkout of `origin/main` of devops-cli and, for a deploy, with an environment tree whose checkout is clean at its `origin/main` and which holds an Application and the Secret table. Else the row SHALL be `refused`.

#### Scenario: A dirty checkout
- **WHEN** `git status --porcelain` lists a file and `--confirm` runs
- **THEN** row 13 is `refused` and names the file count, the config file keeps its repository list, and no `devops k8s` program starts

#### Scenario: A clean main
- **WHEN** the checkout and the infra checkout are clean at `origin/main` and `--confirm` runs on a repository outside `service.repos`
- **THEN** the config file lists the repository, and the run starts push-secrets and deploy-stack, each with `--k8s-dir` at the tree that the row checked

#### Scenario: A dirty or stale infra checkout
- **WHEN** the infra checkout has a changed file, is not at `origin/main`, or its fetch fails
- **THEN** row 13 is `refused`, names the environment tree and the reason, and no `devops k8s` program starts

#### Scenario: A tree that cannot deploy
- **WHEN** no source gives a tree, the tree holds no Application or no `cluster-secrets.toml`, or it is in no git checkout
- **THEN** row 13 is `refused` with the reason, and no `devops k8s` program starts
