# Spec Delta

## ADDED Requirements

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
