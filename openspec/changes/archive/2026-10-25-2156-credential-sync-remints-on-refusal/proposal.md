# Proposal

## Why

Issue #2156: `src/devops_cli/k8s/credentials.py` changed each failure of the Argo CD and Grafana token flows into `None` or `False`. Thus its caller could not tell a refused token from a service that did not answer.

- `verify_grafana_token` returned `False` for each status other than 200 and for each exception, also for a timeout or a 502. The sync then minted a new token, and the Grafana mint first revoked each token of the `devops-cli` service account. Thus one failed read of `/api/org` revoked tokens that were valid.
- Argo CD had the same shape, and one more defect: `verify_argocd_token` took HTTP 200 from `/api/v1/session/userinfo` as acceptance. Argo CD answers that endpoint with HTTP 200 for each caller, and sets `loggedIn: false` for a token that it refuses. Thus the sync kept each refused Argo CD token.
- The mint, the account lookup, the revoke and the token create caught `Exception` and logged at debug level only. The reads of the settings and the keyring caught `Exception` too. The kubectl read changed a failed read, an output that is not JSON and an undecodable field into "not found".
- `_verify_argocd_token` and `_verify_grafana_token` were aliases with old names.
- The coverage run of CI missed 72 of 337 statements in the module: the failure branches had no test.

## What Changes

- A verify tells three outcomes apart. It returns `True` when the service accepts the token, and `False` when the service refuses it: HTTP 401 or 403, or from Argo CD HTTP 200 with `loggedIn` not `true`. It raises `StackCredentialError` with the cause when the check fails: another status, an answer that is not JSON, or a request error.
- The sync mints a new token, and the Grafana mint revokes the old tokens, only when the service refused the stored token. When the check fails, the sync keeps the stored token and reports the failure with its cause.
- The mint functions return the token, and raise `StackCredentialError` with the cause when a step fails: a refused admin session, a session with no token, a refused account create or search, an account that the search does not find, a refused token list, revoke or create, a token with no key, a request error, or a keyring that does not store the token.
- The kubectl read returns no data for a Secret that does not exist. It raises `StackCredentialError` for another kubectl error, for output that is not a JSON object, and for a field that is not base64-encoded UTF-8 text.
- `sync_k8s_credentials` returns a `CredentialSync` for each credential: `synced`, `missing`, or `failed` with its cause. It reads the settings one time. A settings or URL error is a configuration error, and it stops the command.
- `devops k8s sync-secrets` shows each failed step with its cause, and then exits with status 1. `devops k8s deploy-stack` shows the same lines after a deploy of `infra`. The help text of `sync-secrets` says this.
- `get_or_mint_argocd_token` gives a failed mint to its callers (`devops argo`). `get_or_mint_grafana_auth` keeps the admin password as the fallback of `devops grafana`, and logs a warning with the cause of the failed mint.
- No handler in the module catches `Exception`. The swallowed-failures ceiling of the module goes from 11 to 0, and its entry goes.
- `tests/test_k8s_credentials.py` tests the module through its edges: kubectl through `process_fake`, HTTP through `stub_web`, and the keyring through `mock_keyring`. No test in it patches a devops-cli name. `StubWeb` gets `respond`, an answer for one method and URL, and `fail`, a transport error for a URL.
- The command output and the requests to Argo CD and Grafana are observable behavior, so the change has a spec delta: the new capability `stack-credential-sync`.
- The change fits in one pull request.

## Capabilities

### New Capabilities

- `stack-credential-sync`: how `devops k8s sync-secrets` keeps the Argo CD admin password and the API tokens of Argo CD and Grafana in the OS keyring, and how it reports each failure.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/k8s/credentials.py`, `src/devops_cli/exceptions/k8s.py` (`StackCredentialError`), `src/devops_cli/config/constants.py`, `src/devops_cli/commands/k8s/stack_lifecycle.py`.
- `tests/test_k8s_credentials.py`, `tests/web_fakes.py`, `tests/test_k8s.py`, `tests/test_k8s_tempo.py`, `tests/fixtures/swallowed_failures_ceilings.json`.
- The generated `docs/commands/k8s.md`, `docs/CLI_REFERENCE.md` and `docs/ERRORS.md`.

## Feasibility

- The code. At origin/main 527558fa, `src/devops_cli/k8s/credentials.py` had the lines that the issue cites at b170358e, with no change: the verify functions at 389-456 with `except Exception` at 419-421 and 454-456, the sync functions at 503-554, the revoke before the create at 279-297, and the aliases at 459-460. `tests/fixtures/swallowed_failures_ceilings.json` held 11 for the module.
- Argo CD. `server/session/session.go` on the `master` branch of argoproj/argo-cd, read on 2026-10-24: `AuthFuncOverride` "authenticates the user, but ignores any error", and `GetUserInfo` returns `LoggedIn: sessionmgr.LoggedIn(ctx)` with a nil error. Thus `/api/v1/session/userinfo` answers HTTP 200 for a token that Argo CD refuses, and only `loggedIn` tells the two apart.
- Grafana. `pkg/services/authn/authnimpl/service.go` on the `main` branch of grafana/grafana builds its authentication errors with `errutil.Unauthorized`, which Grafana sends as HTTP 401.
- The settings read. On a workstation whose `config.yaml` holds a key that the settings model does not know, `load_settings()` raises. The old `_resolve_service_url` and `_resolve_existing_token` caught that error, and the sync skipped the two token steps with no message.
- No live run. The sync writes the keyring, and the Grafana mint revokes tokens, so the check of the premise used the code and the upstream source only. The tests replay each answer of the issue (200, 401, 403, 502, a timeout, a lost connection, an answer that is not JSON) through `stub_web`.

## Existing Tool Considered

- HTTP: httpx2, the client of the project, with `Response.is_success` for the status classes. The tests use httpx2's own `MockTransport` through the shared `stub_web` fixture. The HTTP seam and its fake are #1314, and the move of these clients onto the egress-checked factory is #1381.
- Base64: the standard library, `base64.b64decode(..., validate=True)`.
- Grafana: `grafana-client` (PyPI, maintained) has the service account and token calls. The change does not adopt it: it would add a dependency for four REST calls that the module already makes, and #1381 moves this client. The change builds no new client. It narrows the handlers of the six existing calls. Cost: about 200,000 tokens and 3 hours elapsed for this change. The Grafana service account endpoints have had the same shape since Grafana 9, and the Argo CD session endpoints are older, so the expected cost to keep them is low.
- Argo CD: no maintained Python client exists. The `argocd` CLI can make a token, but it is a binary that the workstation does not have.

The change deletes `_verify_argocd_token`, `_verify_grafana_token`, `_resolve_existing_token`, `_resolve_service_url`, `_safe_keyring_set`, `_post_argocd_session`, `_decode_k8s_secret_field`, `_sync_argocd_credentials` and `_sync_grafana_credentials`, the 11 broad handlers of the module, and the old tests of the module that patched `run_subprocess`, `_keyring_set`, `_resolve_existing_token`, the mint and verify functions and `httpx2.Client` methods.
