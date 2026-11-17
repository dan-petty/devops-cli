# Design

## Decisions

### One retry, same limit

The reported failure passed some seconds later, so a second attempt recovers it. Each attempt gets
the same 5 second limit, and the worst case stays at 10 seconds. A larger second limit doubles the
worst case and makes the test depend on it.

### Retry inside `_lookup_github_token`

That function sets the limit and turns the timeout into the message. A retry in
`_session_github_token` would not run for `devops gh api`, because `github_token()` passes
`retry_now=True` and skips the failure record. A retry in the process runner would retry every
subprocess.

### Only a timeout retries

An `OSError`, such as a missing gh, and a nonzero exit return at once. A repeated missing gh would
only double the fast error path.

### The attempt count is a constant

`DEFAULT_GH_AUTH_TOKEN_ATTEMPTS` in `src/devops_cli/config/defaults.py` sits beside the timeout. A
test can set it to 1, and no operational setting is added.

## Rejected alternatives

- **Raise the timeout to 30 seconds:** a broken gh blocks every GitHub call for 30 seconds.
- **A larger second limit:** it doubles the worst case.
- **Retry in `_session_github_token`:** it never runs for `devops gh api`.
- **Retry every subprocess:** it retries calls that are no token lookup.
- **Retry an `OSError`:** the issue shows a timeout, and a missing gh should fail fast.
