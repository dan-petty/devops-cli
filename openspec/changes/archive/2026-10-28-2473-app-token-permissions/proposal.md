# Proposal

## Why

Issue #2473: on 2026-10-28 the owner gave GitHub App `devops-cli-service` read and write on every repository permission, for planned repository-management work (ADR 0015, #2454). `src/devops_cli/github/app_installation.py` minted each installation token with no request body, so each token got every permission of the installation: Administration, Secrets, Variables, Environments and Workflows too, which AGENTS.md leaves to a person. A bug, a prompt injection that reaches a write, or a token that leaks could use all of them. The roadmap jobs use only Issues, Pull requests and Contents read and write, and Checks, Actions and Metadata read (`k8s/README.md`, "Roadmap service", step 1).

## What Changes

- One constant, `CONST_GITHUB_APP_TOKEN_PERMISSIONS` in `src/devops_cli/config/constants.py`, holds the token's permissions: `issues`, `pull_requests` and `contents` write, and `checks`, `actions` and `metadata` read.
- The token request sends `{"permissions": CONST_GITHUB_APP_TOKEN_PERMISSIONS}` as its body. gidgethub's `GitHubAPI` signs the App's JWT and posts the request over the session's client, as before. The process no longer calls `gidgethub.apps.get_installation_access_token`, which sends no body.
- The process logs the names of the permissions in GitHub's reply, without their levels and without the token. A reply that grants more than the request asks for is no error.
- When GitHub refuses the request with HTTP 422, the error names each permission that the token asks for, with GitHub's status and reply text. GitHub's reply does not say which permission the installation does not grant.
- ADR 0015, the "Roadmap service" text of `k8s/README.md` and the knowledge base's GitHub CLI page say that each token is scoped to these permissions, whatever the App grants.
- The change alters the request that the Service and the cluster Jobs send to GitHub, an error message and a log line, so it carries a spec delta: an ADDED requirement in `github-app-identity`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `github-app-identity`: each installation token carries only the permissions that the roadmap jobs use.

## Impact

- `src/devops_cli/github/app_installation.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/errors.py`.
- `tests/test_github_app_identity.py`.
- `docs/adr/0015-roadmap-jobs-act-as-a-github-app-on-the-personal-account.md`, `k8s/README.md`, `src/devops_cli/ai/knowledge_base/it_domains/tools/github_cli.md`.

## Feasibility

- GitHub's REST documentation, "Create an installation access token for an app" (`POST /app/installations/{installation_id}/access_tokens`, API version 2022-11-28), lists the body parameters `repositories`, `repository_ids` and `permissions`. It says: "If permissions is not specified, the installation access token will have all of the permissions" of the installation, and "The installation access token cannot be granted permissions that the app was not granted." The keys `issues`, `pull_requests`, `contents`, `checks`, `actions` and `metadata` each take `read` or `write`. The answers are 201, 401, 403, 404 and 422, and the 201 reply holds the token's `permissions`.
- The documentation names no error for a permission that the installation does not grant. Public reports show that GitHub answers HTTP 422 with "The permissions requested are not granted to this installation." and does not say which permission is missing: `actions/create-github-app-token` in ScottCooper92/binge-companions#235, and Renovate in MikaelSiidorow/systems#77. So the issue's premise that the error can name the missing permission fails as written. The error names each permission that the token asks for, and GitHub's status and text. The design records why the change does not read the installation's permissions after a refusal.
- gidgethub 6.0.0, as installed: `gidgethub/apps.py` `get_installation_access_token(gh, *, installation_id, app_id, private_key)` posts `data=b""` and takes no permissions and no body. `gidgethub.abc.GitHubAPI.__init__` takes `app_id` and `private_key` and signs an RS256 JWT whose issuer is the App ID (`_get_app_jwt`), and `GitHubAPI.post(url, *, data)` sends `data` as a JSON body. So the change posts the request through the same `gidgethub.httpx.GitHubAPI` over `session_client()` that the code already used.
- On `origin/main` 960e3573, the three new tests failed: the exchange's body was empty (`JSONDecodeError`), no log record named the permissions, and the 422 error named no permission.

## Existing Tool Considered

GitHub's documented `permissions` body parameter of the token endpoint, sent through gidgethub's `GitHubAPI.post`, which signs the App's JWT. Nothing is built. The change deletes the call to `gidgethub.apps.get_installation_access_token`, which cannot send a body.
