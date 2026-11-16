## MODIFIED Requirements

### Requirement: A start from a workstation is refused when it cannot succeed
Before it creates the Job, the command SHALL refuse an Item that an agent or a person claimed, an Item whose Status is neither Ready nor Planned, a closed issue or an issue that is no Item, a repository that is not `owner/name`, and a repository that has a runner Job that has not ended. With `--confirm` it SHALL also refuse `--source`, `--filter`, `--limit`, `--no-rebase` and a missing `--item`, and name the `run-job` command.

#### Scenario: A claimed Item
- **WHEN** the Item holds `owner/human` or `owner/agent`
- **THEN** the command exits 1, names the owner, and creates no Job

#### Scenario: An Item that is not ready to implement
- **WHEN** the Item is New, In Progress, In Review or Blocked, or the issue is closed or is no Item of the roadmap
- **THEN** the command exits 1, names the Status or the cause, and creates no Job

#### Scenario: A running Job
- **WHEN** a Job of the repository carries the label `implement-repo` and has no Complete or Failed condition
- **THEN** the command exits 1, names the Job, and creates no Job

#### Scenario: An option that needs the runner
- **WHEN** the command runs with `--confirm` and `--source`, `--filter`, `--limit` or `--no-rebase`
- **THEN** the command exits 1, names the option and the `run-job` command, and sends no request

#### Scenario: A repository that is no owner and name
- **WHEN** `--repo` is `../..`, `owner/..` or has no slash
- **THEN** the command exits non-zero, reads no Item, and creates no Job

#### Scenario: A step with confirm
- **WHEN** the command runs with `--group` and `--confirm`
- **THEN** the command exits 1, and the message names `devops roadmap implement --item <n> --confirm`
