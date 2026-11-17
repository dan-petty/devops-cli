# Design

## Decisions

### Retry the closing-issue read in `_finish_created_pr`

GitHub links the issue a new pull request closes a moment after the pull request opens. The
command retries `set_delivered_status` for a bounded time, using
`DEFAULT_PR_CREATE_CLOSING_POLL_ATTEMPTS` and
`DEFAULT_PR_CREATE_CLOSING_POLL_INTERVAL_SECONDS`. It stops at the first issue whose Status it
moves.

### Warn, and exit 0, when no issue links

The pull request exists, so a missing link is no create failure. The command prints a warning
that it found no closing issue and exits 0. A read error still prints its reason and exits 1.

### Dedicated poll constants

The wait means something different from an update of a pull request head, so it gets its own
constants rather than reusing `DEFAULT_PR_UPDATE_HEAD_POLL_*`.

### `set_delivered_status` returns the linked issue

The function already returns the number of the issue whose Status it sets, and None when no
issue is linked or the Status stays. The command uses that answer to tell a completed write from
a link that has not appeared yet. A focused test pins the return value.

## Rejected alternatives

- **Parse `Closes #<n>` from the body:** the body is text, not GitHub's authoritative link, and
  it can name an issue that GitHub does not link.
- **Read without a bound:** a missing or malformed closing reference would hang the command.
- **Keep the immediate read:** GitHub can link the issue after the read, which loses the Status.
- **Exit 1 after the pull request opens:** the pull request exists, so a nonzero exit reports a
  failed create that did not happen.
