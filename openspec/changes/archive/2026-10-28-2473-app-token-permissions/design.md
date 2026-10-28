# Design

## Context

The Service and the cluster Jobs act as GitHub App `devops-cli-service` (ADR 0015). `mint_installation_token` exchanges the App's JWT for an installation token over the session's client, and `core.process` gives the token to every gh and git child. The installation grants read and write on every repository permission. Without a `permissions` body, GitHub gives each token all of them.

## Decisions

- **One constant holds the token's permissions.** `CONST_GITHUB_APP_TOKEN_PERMISSIONS` maps each permission that the roadmap jobs use to its level. The token request sends it as `permissions`. A later feature that needs more asks for a token with its own set. The App's grant stays the owner's setting.
- **gidgethub's `GitHubAPI` posts the request.** gidgethub 6.0.0's `get_installation_access_token` posts an empty body. `GitHubAPI` takes the App's ID and key, signs the JWT, and posts a JSON body, so the request still goes through gidgethub and the session's client, to GitHub's API origin only.
- **The log names the granted permissions only.** After a token is minted, one INFO record names the permissions of GitHub's reply, sorted, with no level and no token. A reply that grants more than the request asks for is no error: GitHub decides what the token carries, and the log shows it.
- **A 422 names each permission that the token asks for.** `classify_http_error` gives the status of the refusal. On HTTP 422 the reason adds each permission of the request with its level, after GitHub's text. Any other refusal keeps its reason as before.

## Rejected Alternatives

- **Read the installation's permissions after a 422 and name only the missing ones.** `GET /app/installations/{installation_id}` gives the installation's `permissions`. But the read is a second request after a refusal, it can fail too, and its failure would hide the 422 or need its own error path. GitHub's 422 also answers a request that the endpoint thinks is spam ("Validation failed, or the endpoint has been spammed"), so a 422 alone does not prove a missing permission. The six names in the error are enough for a person to compare with the App's settings page.
- **Keep `gidgethub.apps.get_installation_access_token`.** It posts `data=b""` and takes no `permissions` argument (gidgethub 6.0.0, `gidgethub/apps.py`), so it cannot scope the token.
- **Also scope the token to `service.repos` with `repositories`.** The issue asks for permissions only. The App is installed only on the managed repositories (`k8s/README.md`, "Roadmap service", step 1), so the installation already limits which repositories a token reaches.
- **Fail when the reply grants more than the request asks for.** The issue's acceptance criteria say that such a reply is no error. The token's permissions are GitHub's decision; the log shows them, so a person can see a difference.

## Risks

- A roadmap job that starts to use a permission outside the set fails at the request that needs it, with GitHub's 403. The fix is to add the permission to the constant, in a pull request that says why.
