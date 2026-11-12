## MODIFIED Requirements

### Requirement: The command closes an issue with its reason
`devops gh issue close <number> --reason <reason>` SHALL read the issue, then close it with one `PATCH` of the issue whose body sets `state` to `closed` and `state_reason` to `completed` for `--reason completed` or to `not_planned` for `--reason not-planned`. `--repo` and `-R` SHALL name the repository, and the default SHALL be the origin of the checkout.

#### Scenario: Close as not planned
- **WHEN** the user runs `close 7 --reason not-planned -R example/repo` and #7 is an open issue
- **THEN** the command exits 0, and #7 is closed with the reason `not_planned`

#### Scenario: Close as completed
- **WHEN** the user runs `close 7 --reason completed -R example/repo` and #7 is an open issue
- **THEN** the command exits 0, and #7 is closed with the reason `completed`

### Requirement: A dry run sends no request
`devops gh issue close --dry-run` SHALL send no request and SHALL print the requests a run makes, in order: the read of the issue, the comment when `--comment-file` is given, and the `PATCH` of the close with its body.

#### Scenario: Dry run with a comment
- **WHEN** the user runs `close 7 --reason not-planned --comment-file evidence.md --dry-run`
- **THEN** the command exits 0, no request is sent, and the output lists the read of #7, the comment on #7 and the `PATCH` of #7 with `not_planned`
