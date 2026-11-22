# Design

## Decisions

- Pin the tag and the index digest, in the form that the three files already use. Renovate updates both.

## Rejected alternatives

- A `versioning` rule in `.github/renovate.json` for the old single number: the image publishes no more tags of that form, so the rule would match no new tag.
