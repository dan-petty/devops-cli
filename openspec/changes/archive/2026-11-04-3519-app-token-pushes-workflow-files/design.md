# Design

## Context

The Service and the cluster Jobs act as GitHub App `devops-cli-service` (ADR 0015). Each token asks for `CONST_GITHUB_APP_TOKEN_PERMISSIONS`, whatever the App grants. A push that changes a workflow file needs the `workflows` permission.

## Decisions

- **Every token asks for `workflows: write`.** The owner chose this on 2026-11-04. The token request stays one constant with one meaning, and `service.github_app.token_repository` still limits a Job's token to one repository.
- **The documents state the risk.** A workflow on a pushed branch can run with the secrets of the repository before a person reviews it. The branch policy of an environment keeps the secrets of that environment from such a run.

## Rejected Alternatives

- **A person makes each workflow edit, and the token stays as it is.** It keeps the narrower token, and the refusal occurs on one item in the evidence. The owner rejected it on 2026-11-04.
- **A token gets the permission only for a push whose merged plan names a workflow file.** It limits the exposure to approved plans, but it needs a second token path, tests and a plan check. The owner rejected it on 2026-11-04.
