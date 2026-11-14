# Design

## Context

`_execute_check_async` takes one `timeout` for every row, and `_with_test_shard` changes only the command. The Service Image Tests run the suite inside `docker run` with no outer bound.

## Goals

- A row line names its own timeout before the job limit.
- An index build has room for a measured 1,627 s run.

## Decisions

- **A field on the row.** `CheckSpec.timeout_seconds` overrides the default, so each row can hold its own bound.
- **900 s for a shard.** The job limit is 20 minutes, and the row starts after setup.
- **`timeout --kill-after=30 900`.** It stops the container and its children, and the step fails with 124.
- **3600 s for the index build.** The measured run is 1,627 s, and the build runs in a job of its own.

## Risks

- A shard on a very loaded host could reach 900 s and fail. The measured shard time is under 5 minutes.

## Tests

- A shard test row holds 900 s, and the full row holds None.
- The Service Image Tests step holds the timeout wrapper.
- `docs/TESTING.md` names the two bounds.
