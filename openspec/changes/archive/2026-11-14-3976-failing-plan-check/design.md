# Design

## Context

`_Judge._pull_reason` reads `PullStatus` for the plan pull request and checks the draft state and the `plan/needs-fix` label. It reads no check runs. The README rule says CI is the authoritative gate.

## Goals

- Spend no runner Job on a plan whose checks did not pass.
- Fail closed on an unread or pending verdict.

## Decisions

- **The gate lives in `_pull_reason`.** It runs before the Service creates a Job, and it already holds the pull request facts.
- **Fail, cancel, pending and unread leave the item out.** A pending check can settle as a failure after the Job starts. An unread check hides the verdict.
- **The head SHA names the checks.** `PullStatus.head_sha` is the commit that the plan checks ran on.
- **A reader parameter.** `plan_implement` takes `check_reader`, and the tests pass a fake summary.

## Risks

- A pull status with no head SHA skips the check. GitHub always gives a head for an open pull request, and a missing one is no stable key.

## Tests

- A failed, cancelled or pending check leaves the item out with the check name.
- An unread summary leaves the item out with the unread reason.
- A passing summary selects the item, and the reader receives the head SHA once.
