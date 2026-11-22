# Design

## Decisions

- Pin the tag `1.0.0` and its index digest, in the form of the three files. Renovate updates both.

## Rejected alternatives

- Pin the moving tag `1` or `latest`: the digest pin already gives a fixed image, and a full version in the tag names the release in each Renovate pull request.
