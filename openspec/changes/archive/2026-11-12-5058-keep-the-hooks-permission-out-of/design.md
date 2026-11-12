# Design

## Decisions
- **The token repository selects the set.** `service.github_app.token_repository` is set on each runner Job and never on the Service (the ConfigMap leaves it out). `_token_permissions` gives the permissions of the roadmap jobs when the setting is set, and adds `CONST_GITHUB_APP_METRICS_TOKEN_PERMISSIONS` when it is empty. The token request and the HTTP 422 error read the same function, so the error names the permissions that the process asked for.
- **One set for each process.** A process keeps one token for each gh and git child and each REST request (ADR 0015), so each process still asks for one set. Only the set differs between a runner Job and the Service.
- **A constant for the `metrics` row.** Its permissions, `repository_hooks: read` (#5017) and `administration: read` (#4757), are in a constant of their own. A later feature of the Service adds its permission to that set, and a runner Job does not get it.

## Rejected alternatives
- **A second token for the `metrics` row.** The Service would mint, keep and renew two tokens, with a second client and a second ledger key, for reads every 13 minutes. The token of the Service already reads every repository of the installation, so a second token gives the Service no smaller access. The risk is in the runner Job, and the token repository already marks it.
- **A setting that lists the permissions of each process.** A setting can give a runner Job more permissions than the roadmap jobs need, and no process needs a choice. The token repository already tells a Job from the Service.
- **Keep one shared set for every token.** A prompt injection in a step of a runner Job can then read the hook URLs, the deliveries with their payloads and response headers, and the settings of the repository, and no step needs them.
- **Remove only `repository_hooks` from the Job token.** `administration: read` is also a permission of the `metrics` row only, and it reads more: rulesets, deploy keys, self-hosted runners and pending invitations.
