# Proposal: #4940

## Why

`devops gh api` can fail once with "GitHub is not authenticated" on a loaded host. The lookup gives
`gh auth token` 5 seconds, and the start of gh alone can take longer, so a valid login reads as not
authenticated. The command stops with no retry. Closes #4940.

## What Changes

- `_lookup_github_token` tries `gh auth token` again after a timeout, up to
  `DEFAULT_GH_AUTH_TOKEN_ATTEMPTS` attempts, with the same 5 second limit for each attempt.
- An `OSError`, a nonzero exit or a missing gh still fails at once.
- The process keeps a token that a retry finds.

## Capabilities

### Modified

- `github-app-identity`: the gh login fallback retries a timed-out token lookup.

## Impact

A slow host no longer turns a valid gh login into an authentication error. The worst case is one
more 5 second attempt. A repeated success keeps the token for the process.

## Feasibility

Confirmed against the issue and the code: `_lookup_github_token` in
`src/devops_cli/core/process.py` sets the 5 second limit and turns the timeout into the error.
`_session_github_token` keeps the token that the lookup returns, and `reset_github_token` clears it.

## Existing Tool Considered

No open tool covers this need. The alternatives check of 2026-11-15 returned `none`; no external
tool changes the limit that this function gives `gh auth token` or retries the lookup inside the
process. The retry costs about 3,000 tokens to build and 1,000 to keep.
