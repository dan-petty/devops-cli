## MODIFIED Requirements

### Requirement: devops pr create refuses a pull request that breaks the form
Before opening a pull request, `devops pr create` SHALL check `--title`, and `--body` where OpenSpec is active, and exit 1 on any violation. Scope labels SHALL be checked against `.github/labels.yml` on the base branch, plus `--head` when `--repo` and `--head` are set, or the checkout when `--repo` is omitted. Refusals SHALL name the checked refs only when `--repo` is set. Passing pull requests SHALL open as drafts.

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
- **THEN** the exit status is 1, no create request is sent, and stderr names `scope/pr` and `--base`

#### Scenario: A label declared only on the head ref with --repo
- **WHEN** `--repo` and `--head` are both set, the base ref declares no `scope/tools` label, and the head ref declares it
- **THEN** `devops pr create` accepts the title, opens the draft, and applies `scope/tools` to the pull request

#### Scenario: A label declared only on the base ref with --head
- **WHEN** `--repo` and `--head` are both set, the base ref declares `scope/pr`, and the head ref declares no `scope/pr` label
- **THEN** `devops pr create` accepts the title and opens the draft

#### Scenario: Neither ref declares the scope label with --repo and --head
- **WHEN** `--repo` and `--head` are both set, and neither the base ref nor the head ref declares `scope/tools`
- **THEN** the exit status is 1, no create request is sent, and stderr names the base ref, `--head`, and the instruction to declare the label in the same pull request

#### Scenario: Only the base ref is read with --repo and no --head
- **WHEN** `--repo` is set without `--head`, and the base ref declares no `scope/tools` label
- **THEN** the exit status is 1, no create request is sent, and stderr names only the base ref

#### Scenario: A scope that only the checkout declares
- **WHEN** `--repo` is not given, the checkout declares `scope/newscope` and the base branch does not
- **THEN** a title with the scope `newscope` passes the check and the pull request opens

#### Scenario: The check-out mode keeps its message on refusal
- **WHEN** `--repo` is not given and `.github/labels.yml` does not declare `scope/tools`
- **THEN** the exit status is 1, no create request is sent, and stderr prints `.github/labels.yml does not declare \`scope/tools\`` with the instruction to declare the label in the same pull request

#### Scenario: A labels file that cannot be read
- **WHEN** the base branch has no `.github/labels.yml` (and `--head` also lacks it when set)
- **THEN** the exit status is 1, no create request is sent, and stderr names `.github/labels.yml`

#### Scenario: A refused pull request does not reach the fallback
- **WHEN** the title is `A plain title`
- **THEN** the REST fallback is not called
