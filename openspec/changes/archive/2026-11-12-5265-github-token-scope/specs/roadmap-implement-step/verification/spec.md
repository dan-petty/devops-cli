## ADDED Requirements

### Requirement: A verification command runs git only as the negative search
The reader of a verification command (`read_verification`) SHALL refuse a command whose first word is `git`, with the reason that `git` runs only as the negative search `! git grep -n <literal> -- <paths>`, and the step SHALL start no process for it. The list of programs that a refusal names SHALL NOT hold `git`. The step, the gate of the stage job, the plan reader and the amendments SHALL read the same rule.

#### Scenario: A git call that reaches a remote
- **WHEN** a Verification line names `git ls-remote` or `git fetch` of a remote, also after the global option `-c`, and the process runner holds a token
- **THEN** the step stops with the reason that the command is refused, and starts no git process

#### Scenario: Any other git command
- **WHEN** a Verification line names `git -c core.sshCommand=<probe> fetch origin`, `git --exec-path=<probe> status`, `git -C <folder> push origin main`, `git grep -n name src/` or `git status`
- **THEN** `verification_problem` gives the reason "`git` runs only as the negative search `! git grep -n <literal> -- <paths>`"

#### Scenario: The negative search
- **WHEN** a Verification line names `! git grep -n name src/`
- **THEN** `verification_problem` gives no reason
