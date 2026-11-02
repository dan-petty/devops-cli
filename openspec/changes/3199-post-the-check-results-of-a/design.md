# Design

## Decisions

- **Put the comment builder in `src/devops_cli/github/pr_evidence.py`, and keep the command in `src/devops_cli/commands/pr.py`.**: The command and the Service can import one builder, so the comment text has one owner.
- **Read the check runs with REST `GET /repos/{owner}/{repo}/commits/{ref}/check-runs` through `run_gh`.**: The response gives the check name, conclusion, details URL and head SHA, and the project already reads check runs this way through `fetch_pr_check_verdicts`.
- **Identify the command's own comment by the hidden marker line `<!-- devops-cli:pr-evidence -->` at its top.**: The marker identifies the comment after a restart, a new head commit or a new token.
- **Select the fail-to-pass run by the check-run name `Fail-to-Pass Check`.**: `.github/workflows/fail-to-pass.yml` declares that name for the job, so the name is stable.
- **Reuse the attribution footer builder of `src/devops_cli/roadmap/pull_describe.py` and add no free-text option.**: The project has one footer format, and a free-text option would let a person type a count.
- **Add the requirements to the existing `pull-request-form` capability.**: The command and its messages are observable behavior of the pull request workflow, and the capability already holds the form rules of a pull request.

## Rejected alternatives

- **Build the comment inside `src/devops_cli/commands/pr.py`.**: The Service would import a command module, and the comment text would have two callers in two packages with no shared owner.
- **Match the comment by its author login or by its text.**: Another actor can use the same token or login, and a person can write the same text, so the match is not stable.
- **Read the checks with a GraphQL status check rollup or by parsing `gh pr checks` text.**: The rollup gives less check-run detail, and the text of `gh pr checks` can change and gives no stable machine-readable fields.
- **Match the fail-to-pass run by workflow file name or by app.**: The check-run response holds no workflow file path, and the same app runs other checks, so neither match is specific.
