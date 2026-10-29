## Purpose

How `devops gh issues close` closes one issue of a repository with a reason, `completed` or `not planned`, posts an optional evidence comment before the close, refuses what it cannot close, and lists its requests in a dry run without sending any.

## ADDED Requirements

### Requirement: The command closes an issue with its reason
`devops gh issues close <number> --reason <reason>` SHALL read the issue, then close it with one `PATCH` of the issue whose body sets `state` to `closed` and `state_reason` to `completed` for `--reason completed` or to `not_planned` for `--reason not-planned`. `--repo` and `-R` SHALL name the repository, and the default SHALL be the origin of the checkout.

#### Scenario: Close as not planned
- **WHEN** the user runs `close 7 --reason not-planned -R example/repo` and #7 is an open issue
- **THEN** the command exits 0, and #7 is closed with the reason `not_planned`

#### Scenario: Close as completed
- **WHEN** the user runs `close 7 --reason completed -R example/repo` and #7 is an open issue
- **THEN** the command exits 0, and #7 is closed with the reason `completed`

### Requirement: The comment comes before the close
When `--comment-file` names a file, the command SHALL post the file's text as one comment on the issue before it closes the issue. `-` SHALL read the comment from standard input. The command SHALL refuse an empty comment before any request.

#### Scenario: The comment, then the close
- **WHEN** the user runs `close 7 --reason not-planned --comment-file evidence.md` and #7 is an open issue
- **THEN** the requests are the read of #7, then one comment with the file's text, then the `PATCH` that closes #7

#### Scenario: The close fails after the comment
- **WHEN** the comment is posted and GitHub refuses the `PATCH`
- **THEN** the command exits with a status other than 0, and the error says that the comment is on #7 and that #7 is still open

### Requirement: The command refuses what it cannot close
The command SHALL exit with a status other than 0 and send no comment and no `PATCH` when the number names no issue of the repository, names a pull request, or names an issue that is already closed. A reason other than `completed` or `not-planned` SHALL exit 2, name the allowed values and send no request.

#### Scenario: A pull request
- **WHEN** #8 is a pull request
- **THEN** `close 8 --reason completed --comment-file evidence.md` exits with a status other than 0, and no comment and no `PATCH` is sent

#### Scenario: An issue that is already closed
- **WHEN** #7 is closed
- **THEN** `close 7 --reason not-planned` exits with a status other than 0, and the error says to reopen #7 first

#### Scenario: An unknown reason
- **WHEN** the user runs `close 7 --reason wontfix`
- **THEN** the command exits 2, the output names `completed` and `not-planned`, and no request is sent

### Requirement: A dry run sends no request
`devops gh issues close --dry-run` SHALL send no request and SHALL print the requests a run makes, in order: the read of the issue, the comment when `--comment-file` is given, and the `PATCH` of the close with its body.

#### Scenario: Dry run with a comment
- **WHEN** the user runs `close 7 --reason not-planned --comment-file evidence.md --dry-run`
- **THEN** the command exits 0, no request is sent, and the output lists the read of #7, the comment on #7 and the `PATCH` of #7 with `not_planned`
