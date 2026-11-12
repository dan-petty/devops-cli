## ADDED Requirements

### Requirement: A command that makes no external request does not say that it posts

The help of each command with the dry-run class `no-external-request`, and the help of each of its parameters, SHALL hold no form of the verb "post". A test SHALL check every command that `devops` reaches, and SHALL name the command and the text for each one that says "post".

#### Scenario: A no-external-request command says post

- **WHEN** the check reads a `no-external-request` command whose help is `Post the plan comment to the pull request.`
- **THEN** it returns an error that names the command and that text

#### Scenario: A request-plan command says post

- **WHEN** the check reads a `request-plan` command whose help says `Post the comment.`
- **THEN** it returns no error for that command

#### Scenario: Every reachable command

- **WHEN** the check reads every command that `devops` reaches
- **THEN** it returns no error
