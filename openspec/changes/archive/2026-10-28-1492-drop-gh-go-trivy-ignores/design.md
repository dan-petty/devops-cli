# Design

## What is left of the item

The item has two parts: a gh build with Go 1.27.2 or later, and no ignore for the Go findings. The fix of #1800 did the first part with gh v2.102.1. This change does the second part.

## Why the tests check a floor and a list

The floor is gh v2.102.1, the first release built with Go 1.27.2 or later. A later bump only has to stay at or above it, so the test does not force every bump to edit it. The test also requires one release for the two tarballs, so a bump of one architecture alone fails.

Trivy reads an ignore that matches no finding and says nothing. That is how the three ignores stayed after #1800. The second test fails when `.trivyignore` ignores one of the three findings again.

Both tests read only committed files. They read no network and start no scanner. The second test fails on `origin/main` and passes after the change. The first test passes on both, because `origin/main` already pins v2.102.1.

## Rejected alternatives

- **Bump gh to v2.103.3, the newest release.** Rejected: v2.103.3 has the same `toolchain go1.27.3` and `golang.org/x/net v0.60.0` as v2.102.1, and Trivy finds no HIGH or CRITICAL finding in either binary. No cli/cli security advisory names v2.102.1 as vulnerable. v2.103.0 adds features, such as expiring OAuth tokens, so the bump is a dependency update and not a part of this security fix.
- **Return the item to `New`, because #1800 already moved the pin.** Rejected: the acceptance criterion for `.trivyignore` is not met on `origin/main`, and the work is small and clear.
- **Move the expiry of the ignores to a later date.** Rejected: the pinned build does not have the findings, so the ignores protect nothing. A later expiry only hides the findings if an older gh comes back.
- **A test that fails when an ignore of `.trivyignore` has expired.** Rejected: the result changes with the date and not with the tree, so the test fails on an unchanged `main`.
- **A Renovate rule for the gh tarballs of the Dockerfile.** Rejected: `.github/renovate.json` has no rule for them today, and a new rule changes how many pull requests the repository gets. That needs a decision of its own, and it does not remove the three ignores.
