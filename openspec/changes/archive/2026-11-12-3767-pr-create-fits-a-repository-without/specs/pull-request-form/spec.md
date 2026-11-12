## MODIFIED Requirements

### Requirement: devops pr create refuses a pull request that breaks the form
Before it sends the create request, `devops pr create` SHALL check `--title`, and `--body` in a repository with OpenSpec, with these rules. When there is a problem, it SHALL print every problem to stderr, exit 1, and open nothing, by `gh` or by the REST fallback. It SHALL check the scope against the labels file on the base branch and, without `--repo`, also against that of the checkout. A pull request that passes SHALL open as a draft, and the command SHALL have no option for another state.

#### Scenario: A title and a body in the form
- **WHEN** `devops pr create` is given a title and a body in the form
- **THEN** it sends the create request with `--draft`, and stderr is empty

#### Scenario: A title not in the form
- **WHEN** the title is `A plain title`
- **THEN** the exit status is 1, no create request is sent, and stderr says that the title is not in the form

#### Scenario: Every problem at once
- **WHEN** the title is `feat(zzz)!: ` followed by 61 characters and the body is empty
- **THEN** stderr names the `!`, the scope `zzz`, the limit 60, the missing `Closes` line and the missing `Change:` line

#### Scenario: A body that is not given
- **WHEN** `devops pr create` is given a title in the form and no body, in a repository with `openspec/config.yaml`
- **THEN** the exit status is 1 and no create request is sent

#### Scenario: The base branch declares fewer scopes
- **WHEN** the labels file on `--base` does not declare `scope/pr`
- **THEN** the exit status is 1, no create request is sent, and stderr names `scope/pr`

#### Scenario: A scope that only the checkout declares
- **WHEN** `--repo` is not given, the checkout declares `scope/newscope` and the base branch does not
- **THEN** a title with the scope `newscope` passes the check and the pull request opens

#### Scenario: A labels file that cannot be read
- **WHEN** the base branch has no `.github/labels.yml`
- **THEN** the exit status is 1, no create request is sent, and stderr names `.github/labels.yml`

#### Scenario: A refused pull request does not reach the fallback
- **WHEN** the title is `A plain title`
- **THEN** the REST fallback is not called

### Requirement: A dry run checks the form without a request
`devops --dry-run pr create` SHALL check the offline rules of the title and SHALL exit 1 with the problems when one fails. It SHALL check the body only when `--repo` is not given and the checkout holds `openspec/config.yaml`, because it cannot read the switch of another repository. It SHALL NOT read the labels file or `openspec/config.yaml` of GitHub, or open a roadmap store. `devops pr describe --dry-run` SHALL list the read of the issue and the read of the labels file, and SHALL read nothing.

#### Scenario: A dry run of a title not in the form
- **WHEN** `devops --dry-run pr create --title "A plain title"` runs
- **THEN** the exit status is 1, stderr says that the title is not in the form, and the command opened no roadmap store

#### Scenario: A dry run of a pull request in the form
- **WHEN** `devops --dry-run pr create` is given a title and a body in the form
- **THEN** the exit status is 0 and the output lists the requests of a real run, with the read of `.github/labels.yml`

#### Scenario: A dry run for another repository
- **WHEN** `devops --dry-run pr create --repo example/infra --head feat/19-x` is given a title in the form and a body with no `Closes` line
- **THEN** the exit status is 0, no `gh` command runs, no roadmap store opens, and the output names the branch `feat/19-x`

#### Scenario: A dry run of describe
- **WHEN** `devops pr describe 1 --summary "a summary" --dry-run` runs
- **THEN** the output lists a read of `repos/<repo>/issues/1` and a read of `.github/labels.yml`, and the command opened no roadmap store

## ADDED Requirements

### Requirement: devops pr create checks the body only in a repository with OpenSpec
`devops pr create` SHALL check `--body` only where the base branch of the target repository (the default branch without `--base`) holds `openspec/config.yaml`. A read of the file that fails for another reason than a missing file SHALL stop the command with exit 1 and the error.

#### Scenario: A repository without OpenSpec
- **WHEN** the default branch of the repository that `--repo` names has no `openspec/config.yaml`, and the body has no `Closes` line and no `Change:` line
- **THEN** the command sends the create request with `--draft` and the body as given, and stderr is empty

#### Scenario: A repository with OpenSpec
- **WHEN** the default branch of the repository that `--repo` names holds `openspec/config.yaml`, and the body has no `Closes` line and no `Change:` line
- **THEN** the exit status is 1, no create request is sent, and stderr names the missing `Closes` line and the missing `Change:` line

#### Scenario: The base branch decides
- **WHEN** the default branch holds `openspec/config.yaml`, `--base legacy` names a branch without it, and the body has no `Closes` line
- **THEN** the command sends the create request

#### Scenario: A read of the switch that fails
- **WHEN** the read of `openspec/config.yaml` fails with an error that is not a missing file
- **THEN** the error is raised, and the command does not take the repository as one without OpenSpec

### Requirement: devops pr create opens a pull request from the branch it is given
`devops pr create` SHALL take `--head` (`-H`), the branch that holds the commits of the pull request, and SHALL give it to `gh pr create` and to the REST fallback. Without `--head`, both SHALL use the branch of the checkout.

#### Scenario: A pull request in another repository
- **WHEN** `devops pr create --repo example/infra --head feat/19-x` runs in a checkout of another repository
- **THEN** the `gh pr create` command holds `--head feat/19-x` and `--repo example/infra`

#### Scenario: The REST fallback
- **WHEN** `gh pr create` fails, `--head feat/19-x` is given, and the checkout is on `main`
- **THEN** the fallback looks for an open pull request of `example:feat/19-x` and posts `head=feat/19-x`
