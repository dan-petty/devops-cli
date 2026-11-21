# Design

## Decisions

- **Record the choice in an architecture decision record, MADR 4 form.**: The choice is difficult to reverse: it fixes where each template lives, how each consumer pins it and which repository holds private data.
- **Four homes and one placement rule.**: A template with one consumer stays with that consumer, and a template with two or more consumers, or a platform stack that any service can use, goes to infra. The rule has no list to keep current.
- **One repository tag of infra, pinned in five forms, and updated by Renovate.**: Argo CD recommends a Git tag or a commit SHA for a remote base, and Renovate extracts each form.
- **The two owner decisions of 2026-11-21 are decision text.**: The owner decided that the devops-cli release App tags infra, and that the root stacks of ADR 0026 go to dan-petty/homelab `tf/github/` because they name private repositories (#6674).
- **A dated `Fact out of date` line on ADR 0011, and no amendment key.**: ADR 0011 is superseded, and the README forbids the amendment of a superseded record.
- **The record says that the license exception of ADR 0027 grows to the upstream chart.**: The chart is AGPL-3.0, and ADR 0027 said that its exception does not cover the chart, so the owner must see the change.

## Rejected alternatives

- **Keep every template in devops-cli**: the product then holds the stacks and the rows of other services.
- **Put the shared templates in dan-petty/homelab**: homelab is private and holds the values of one environment.
- **Pin infra at `main`**: a remote base at HEAD can change with no change in the consumer.
- **A tag for each component, an OCI artifact or a git submodule**: one repository tag that Renovate updates is enough.
- **The root stacks of ADR 0026 in public infra**: they name private repositories.
- **`amended-by` on ADR 0011**: the README forbids the amendment of a superseded record.
