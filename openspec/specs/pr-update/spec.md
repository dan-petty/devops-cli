# pr-update Specification

## Purpose
Keep `devops pr update` to the one update that `docs/SDLC.md` allows, for a pull request whose required check failed and whose fix is on the base branch, so that no command makes a catch-up merge.

## Requirements

### Requirement: devops pr update merges the base only for a failed required check
`devops pr update <number>` SHALL send update-branch, locked to the head that it read, only when a check that the rules of the base branch require failed on that head and GitHub reports no conflict. For a conflict it SHALL print the local rebase steps, send no other request and exit 1. In every other case it SHALL print the reason and change nothing. The command SHALL have no `--all` option.

#### Scenario: A pull request with a conflict
- **WHEN** GitHub reports the merge state `dirty` for the pull request
- **THEN** the command prints `git fetch origin && git rebase origin/main`, reads no check, sends no update-branch request and exits 1

#### Scenario: A pull request behind main with green checks
- **WHEN** the pull request is behind `main` and every required check passed on its head
- **THEN** the command sends no update-branch request and exits 0

#### Scenario: A failed required check with no conflict
- **WHEN** a required check failed on the head and GitHub reports no conflict
- **THEN** the command sends one update-branch request whose `expected_head_sha` is that head

#### Scenario: A failed check that no rule requires
- **WHEN** only a check that the rules of the base branch do not require failed on the head
- **THEN** the command sends no update-branch request

#### Scenario: Checks that cannot be read
- **WHEN** the check runs of the head cannot be read
- **THEN** the command sends no update-branch request and exits 1

#### Scenario: No bulk update
- **WHEN** a user runs `devops pr update --all`
- **THEN** the command exits 2 with a usage error
