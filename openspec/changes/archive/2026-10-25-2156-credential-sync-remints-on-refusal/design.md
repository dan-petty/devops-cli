# Design

## The three outcomes of a check

A verify returns `True` for acceptance and `False` for a refusal, and raises `StackCredentialError` for a failed check. A failed check has a cause, and an acceptance or a refusal has none, so the exception carries the cause and the boolean carries the answer of the service. The sync catches only `StackCredentialError`, and puts its message in the result.

Rejected: an enum with three values and a cause field. Each caller must then test the third value and read the cause, and a caller that forgets the third value takes a failed check for a refusal, which is the defect of #2156.

## Argo CD refuses with `loggedIn: false`

`/api/v1/session/userinfo` overrides the authentication of the Argo CD API server and ignores its error (`AuthFuncOverride` in `server/session/session.go`). Thus it answers HTTP 200 for each caller. The check reads `loggedIn`: `true` is acceptance, and any other value is a refusal. HTTP 401 and 403 are refusals too, because a proxy in front of Argo CD can send them. A redirect, for example to a sign-in page, is a failed check.

Rejected: the old rule, HTTP 200 is acceptance. Upstream source shows that it accepts each refused token.

## What stops the command

The settings read and the egress check of a URL raise configuration errors (`ConfigurationError`, `InvalidURLError`, `SSRFBlockedError`). The sync does not catch them: the person must correct the configuration, and the command stops with the error. Only `StackCredentialError` becomes a `failed` entry, because it is the outcome of one credential, and the sync continues with the next credential.

Rejected: catch `DevOpsCLIError` for each credential. Then a configuration error is one line among the credential results, and the command continues with a configuration that it cannot use.

## The Grafana fallback of other commands

`devops grafana` reads Grafana with a token, or with the admin password when no token is available. `get_or_mint_grafana_auth` keeps that fallback when the mint fails, and logs a warning with the cause.

Rejected: give the mint error to `devops grafana`. The admin password works for each request that those commands make, so the error would stop commands that work today.

## The HTTP fake

The tests answer HTTP with the shared `stub_web` fixture, which gives each `httpx2.Client` a `MockTransport`. `StubWeb` answered by URL only, and it could not send a transport error. A REST collection lists on GET and creates on POST at one URL, and a timeout is a transport error. Thus `StubWeb` gets `respond(method, url, status, body)` and `fail(url, error)`.

Rejected: a new HTTP fake in `tests/support/fakes/`. #1314 owns the HTTP seam and its fake, and docs/TESTING.md gives each edge one fake. A second double now would be a second fake of the same edge.

## The order of revoke and create

The Grafana mint revokes the old tokens before it creates the new token, as before. The sync mints only after Grafana refused the stored token, so the revoke removes no token that works for this workstation. A token create that fails after the revoke leaves the account with no token, and the sync reports the cause. The change of that order is a follow-up (tasks.md, Workflow follow-up).
