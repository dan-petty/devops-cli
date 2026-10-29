# review-workspace Specification

## Purpose
A review and its scanners take the workspace that they read from the command that starts them, never from the working directory of the process.

## Requirements

### Requirement: A review names a Kube-linter finding by the path of the manifest in its checkout
A review SHALL name the manifest of a Kube-linter finding by its path relative to the working tree that holds the manifest, whatever the directory that the command runs in. The finding SHALL be in the payload of the manifest.

#### Scenario: A review of a manifest in another checkout
- **WHEN** a review of a checkout scans its manifest `k8s/app.yaml`, and the command runs in a directory outside that checkout
- **THEN** the Kube-linter finding of the manifest is named `k8s/app.yaml:Deployment/app`, and it is in the payload of `k8s/app.yaml`

#### Scenario: A manifest that no checkout holds
- **WHEN** Kube-linter reports a manifest that no working tree holds
- **THEN** the finding names the manifest by its file name

### Requirement: The origin lookup names the repository of the root that its caller gives
`get_repo_origin_name` SHALL take the root of its repository from its caller, and SHALL name the repository by the origin remote of that root alone. A command that has no repository option SHALL give the root of the repository that holds its working directory. The PR review and the check fallback of `devops pr checks` SHALL read the origin of the checkout that the command gives, not of the directory that the process runs in.

#### Scenario: A PR review with no repository
- **WHEN** the PR review gets no repository and a checkout whose origin is `example-org/app`, and the process runs in another checkout
- **THEN** it reads the pull request of `example-org/app`, and it reads the origin in the checkout that it got

#### Scenario: The check fallback with no repository
- **WHEN** `gh pr checks` fails, and the fallback gets no repository and a checkout whose origin is `owner/repo`
- **THEN** it reads the check runs of `owner/repo`, and it reads the origin in the checkout that it got

#### Scenario: A directory with no repository
- **WHEN** the lookup gets a directory that holds no repository, and `GITHUB_REPOSITORY` names a repository
- **THEN** it names no repository and starts no git
