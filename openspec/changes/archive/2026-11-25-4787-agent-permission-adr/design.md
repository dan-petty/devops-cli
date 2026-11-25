# Design

## Decisions

- **Use MADR 4 with `### Decision 1` through `### Decision 5` headings**: Placing each decision under a plain `### Decision N` subheading under `## Decision Outcome` gives stable `#decision-1` through `#decision-5` anchors validated by `zensical` and `devops docs check`.
- **Point to `AGENTS.md` instead of copying owner-only acts**: Naming the "Only a person" paragraph of `AGENTS.md` avoids duplicating the list of owner-only acts and keeps ADR `0038` brief.
- **Keep `k8s/agents/` as one read-only option in `k8s/README.md`**: Stating that agents apply, restart, and exercise workloads in the lab cluster reconciles `k8s/README.md` with Decision 1 without deleting the read-only ServiceAccount documentation.

## Rejected alternatives

- **Copy the "Only a person" list from `AGENTS.md`**: Two copies of the list would drift after edits and spend word budget.
- **Explicit HTML anchors or long decision titles in subheadings**: Custom HTML anchors duplicate auto-generated Markdown heading IDs, and title text changes the slug.
- **Remove the `k8s/agents/` read-only section**: Existing manifests still serve sessions that require read-only access.
