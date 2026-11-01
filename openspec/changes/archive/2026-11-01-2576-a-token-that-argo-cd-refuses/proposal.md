# Proposal

## Why

Issue #2576: Argo CD can refuse the stored API token with HTTP 401. Then `devops argo cd apps sync` ends in a Python traceback. The `httpx2.HTTPStatusError` is not a `DevOpsCLIError`, so the exit seam of `new_typer()` does not report it.

`devops argo cd apps list` and `devops argo cd apps status` do not end in a traceback. They catch the error and show it in a table row or in a status panel. But no command replaces a refused token. `get_or_mint_argocd_token` mints a token only when none is stored. So after a token expires, each Argo CD API command fails until a person deletes the keyring entry `argocd_token` by hand.

This change adds one helper that sends the request, mints a new token on HTTP 401 when the admin password is stored, and sends the request one more time. The helper raises `ArgoError` for each other failure. The three commands `list`, `sync` and `status` call it.

## What Changes

- `argocd_api_request` in `src/devops_cli/argo/credentials.py` takes the settings, the request headers and a function that sends the request with given headers. On HTTP 401 with a stored `argocd.password`, it calls `mint_argocd_token`, which stores the new token, and sends the request again once. In each other failed case it raises `ArgoError` with one message that holds the HTTP status.
- `cd_apps_sync`, `cd_apps_list` and `cd_apps_status` in `src/devops_cli/commands/argo.py` send their request through the helper. They keep their own `client.post` and `client.get` calls. They no longer call `raise_for_status`.
- The messages of the helper go in `ArgoMessages` in `src/devops_cli/lang/en/messages.py`.
- `list` and `status` keep their `except Exception` block. A failure of the helper shows as the error row of the table and as the error of the status panel, and `status` exits 1, as the spec `argo-image-pin-drift` requires today.
- The change fits one pull request. It has three task groups.

Out of scope: the other callers of the Argo CD API that read the stored token. They are `devops argo fleet sync` (and `devops argo sync --fleet`, which calls it) and `devops argo gitops sync` (`src/devops_cli/argo/fleet.py` and `src/devops_cli/argo/gitops.py`). The issue names the `devops argo cd apps` commands. These callers already catch every error and report it as a failed target or a failed result, so none ends in a traceback. They do not retry on HTTP 401. `devops argo sync <name>` without `--fleet` runs `cd_apps_sync`, so it gets the retry from group 2. See "Workflow follow-up" in `tasks.md`.

This change alters what a person observes (a command retries and prints a new message), so it carries a spec delta in the capability `argo-sync-rollouts-teardown`. That capability holds the requirements of `devops argo cd apps sync`. The capability `stack-credential-sync` is about `devops k8s sync-secrets` and does not fit.

## Capabilities

### Modified Capabilities

- `argo-sync-rollouts-teardown`: four ADDED requirements. A refused Argo CD token is replaced one time. A refusal with no stored password ends the command with one message. A refusal of the new token ends the command with one message. Another HTTP error status ends the command with its status.

## Acceptance

The acceptance criteria of #2576, from the refine block of the issue:

- Retry on 401 with a stored password: group 1 (the helper), group 2 (`sync`) and group 3 (`list` and `status`).
- Error on 401 without a password, which names `argocd.token` and the command that sets it: group 1, group 2 (one error line) and group 3 (the error row and the error of the panel).
- Error when the request after the new token gets HTTP 401 again: group 1, group 2 and group 3.
- Error on another HTTP status, with the status in the text: group 1, group 2 and group 3.
- The error is a `DevOpsCLIError`: group 1 (`ArgoError` is one, and a test asserts it).

## Impact

- Code: `src/devops_cli/argo/credentials.py`, `src/devops_cli/commands/argo.py`, `src/devops_cli/lang/en/messages.py`.
- Tests: `tests/argo/test_argo_credentials.py` (new), `tests/commands/test_argo.py`, `tests/commands/test_argo_apps_status.py`.
- Documents: none. No command, option or help text changes, so `devops docs generate` has nothing to regenerate.
- Code the change reuses: `mint_argocd_token` and `get_argocd_password` (the password reader in `src/devops_cli/config/settings.py`), `configured_level`, `ArgoError`, `_argocd` and `_argocd_client` in `src/devops_cli/commands/argo.py`.
- Tests and specs that must keep passing: `test_cd_apps_sync_payload_structure` (asserts one `client.post` call with the `json` argument), `test_argo_commands_execution`, `test_argo_cd_apps_list_and_status_render`, `test_argo_cd_apps_list_null_items`, `test_a_refused_address_in_the_argocd_token_mint_ends_the_command_with_the_cause` (all in `tests/commands/test_argo.py`), `test_status_exits_1_when_argo_cd_refuses_the_read` (`tests/commands/test_argo_apps_status.py`), the tests of `tests/http/test_k8s_credentials.py`, and the requirement "A status with an error exits 1" of `argo-image-pin-drift`.
- Code the change deletes: the three `resp.raise_for_status()` calls of `src/devops_cli/commands/argo.py`.

## Feasibility

Every check below ran on `origin/main` (`e0323631`) on 2026-11-01, in a worktree of this branch.

- The traceback exists for `sync`. A scratch script (outside the repository) patched `httpx2.Client.post` and `httpx2.Client.get` to answer HTTP 401, set `DEVOPS_CLI_ARGOCD_TOKEN=stale-token`, and ran the three commands through `devops_cli.commands.argo.app`. Output: `sync exit 1 HTTPStatusError ['HTTPStatusError', 'HTTPError', 'Exception']`. The exception is not a `DevOpsCLIError`.
- `list` and `status` do not end in a traceback. The same script gave `list exit 0` with a row `Error: Client error '401 Unauthorized' for url ...`, and `status exit 1` with a panel `Error fetching status: Client error '401 Unauthorized' ...`. The cause is `except Exception as exc` at `src/devops_cli/commands/argo.py` lines 246 and 356. `git grep -n "raise_for_status" -- src/devops_cli/commands/argo.py` prints lines 243, 307 and 353. Only the call at line 307 (`cd_apps_sync`) has no handler. So the claim of the issue that each command ends in a traceback is true only for `sync`. The missing token replacement is true for all three.
- The token is never replaced. `src/devops_cli/argo/credentials.py` `resolve_argocd_server_and_token` reads `get_argocd_token(settings) or get_or_mint_argocd_token(settings)`. `get_or_mint_argocd_token` (`src/devops_cli/k8s/credentials.py` line 435) returns a stored token at once and mints only when none is stored.
- The mint exists. `mint_argocd_token(base_url, password, *, level, save_to_keyring=True, timeout=...)` (line 266 of `src/devops_cli/k8s/credentials.py`) posts to `/api/v1/session`, stores the token as `argocd_token`, and raises `StackCredentialError` when Argo CD refuses the session. `uv run python -c "..."` shows `issubclass(ArgoError, DevOpsCLIError)` and `issubclass(StackCredentialError, DevOpsCLIError)` are both `True`. So a failed mint also ends the command with one line through the exit seam.
- The command that sets the token is `devops k8s sync-secrets`. `uv run devops k8s sync-secrets --help` prints "Copy chart-generated admin credentials (Argo CD, Grafana) from the cluster into the OS keyring." `git grep -c "credentials sync" origin/main -- src README.md docs` finds no match, so the first plan was wrong to name `devops k8s credentials sync`.
- HTTP 401 and HTTP 403 differ for Argo CD. Argo CD serves its API through grpc-gateway. `HTTPStatusFromCode` in `github.com/grpc-ecosystem/grpc-gateway/runtime/errors.go` maps `codes.Unauthenticated` to 401 and `codes.PermissionDenied` to 403. So 401 means "no valid session", and 403 means "a valid session that RBAC denies". A new admin token would not be the same identity, so the helper retries on 401 only. The constant `CONST_STACK_TOKEN_REFUSED_HTTP_STATUSES` (401 and 403) serves the check of `devops k8s sync-secrets` against `/api/v1/session/userinfo`, which RBAC does not guard, so the helper does not reuse it.
- Nothing newer did this. `git log --oneline -3 -- src/devops_cli/commands/argo.py src/devops_cli/argo/credentials.py src/devops_cli/k8s/credentials.py` lists #2855 (dry-run plans), #2605 (status checks image pins) and #2568 (Helm record retirement). None of them touches the token path. `openspec/changes/` holds no other change for these three files. Change `2579` edits `src/devops_cli/models/argo.py` only. Change `2167` moves test files and names none of the files of this change. `uv run devops gh api 'search/issues?q=repo:dan-petty/devops-cli+argo+token+401+in:title,body+is:issue'` finds #2576 and the closed #2156 (the `sync-secrets` check), which does not cover these commands.
- Tests exist to extend. `tests/commands/test_argo_apps_status.py` drives `devops argo cd apps status` with the `cli` fixture, `stub_web` and `keyring_store`, and has `test_status_exits_1_when_argo_cd_refuses_the_read`. `tests/commands/test_argo.py` holds the `sync`, `list` and token-mint tests. No file in `tests/` imports `devops_cli.argo.credentials` (`git grep -n "argo.credentials" -- tests` prints nothing), so the helper gets a new file in the mirror directory, `tests/argo/test_argo_credentials.py`.

## Existing Tool Considered

The Argo CD session API (`POST /api/v1/session`) mints the token, and `mint_argocd_token` already calls it. `httpx2` (the HTTP library the project uses) offers `raise_for_status` and `Response.is_success`, which the helper uses. A retry library such as `tenacity` or an `httpx2` transport retry would repeat the same request with the same stale token, so neither covers a token swap between two requests. The helper adds about 30 lines in one function. It deletes three `raise_for_status` calls. The written cost: about 25,000 tokens to build, a few hundred tokens a year to keep it, and about one hour of elapsed time.
