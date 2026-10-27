# Proposal

## Why

Issue #1968: `run_gh` reads a `gh api rate_limit` answer into the stored github.com quotas. When the check names another host with `--hostname`, that answer belongs to the other host. It does not belong to github.com. The stored github.com quotas become wrong. The limiter then paces github.com requests with wrong quota counts.

## What Changes

- `parse_gh_api_args` returns the `--hostname` option value as a new `GhApiArgs.hostname` field.
- `_prints_rate_limit_answer` returns false when the check names a host other than `github.com`.
- `_post_process_run` stores no quota from an answer when `_prints_rate_limit_answer` returns false.
- A rate-limit check that names `github.com`, or names no host, updates github.com quotas as before.
- The change alters internal quota tracking only. A consumer sees no change to a devops command, option or message. It sets `skip_specs: true` in `.openspec.yaml`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/github/request_classifier.py`, `src/devops_cli/github/rate_limiter.py`.
- Tests: `tests/test_github_rate_limiter.py`.

## Feasibility

- The premise holds. `run_gh` calls `_prints_rate_limit_answer` to decide `reads_quota`.
- `_post_process_run` calls `_extract_rate_limit_endpoint_response` when `reads_quota` is true.
- That code stores the response into the github.com limiter without a check of the named host.
- `gh api` accepts `--hostname` in `CONST_GH_API_VALUE_FLAGS`.
- `CONST_GITHUB_HOST` is `github.com` in `src/devops_cli/config/constants.py`.
- We verified offline that `parse_gh_api_args(["rate_limit", "--hostname", "ghe.example.com"]).hostname` evaluates to `ghe.example.com`.

## Existing Tool Considered

No open tool applies. The GitHub CLI already sends the request to the named host. The change inspects the flag that `gh api` accepts and compares the host with `CONST_GITHUB_HOST`. No internal code is deleted because no custom host rate limiter exists.
