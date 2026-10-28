# GitHub is the roadmap's source of truth

Amended on 2026-10-28 by [ADR 0016](0016-labels-hold-the-roadmap-items-fields.md). Labels and milestones hold an Item's Status, Priority, Value and Effort, and no roadmap job reads or writes the project board. An Item is an issue with a `priority/*` label, and the issue body holds its job record.

Amended on 2026-10-22 by [ADR 0012](0012-releases-are-derived-by-release-please-from-trunk-and-milestones-are-planning-buckets.md). A milestone is a planning bucket, not a release. The roadmap command renders `docs/ROADMAP.md` from GitHub, and no release writes it. The change takes effect after v0.2.39, in the order of the Cutover section of ADR 0012.

The roadmap used to live in a hand-edited `docs/ROADMAP.md` that was synced out to GitHub issues, milestones and the project board. We reversed that: issues are the items, milestones are the releases, and board fields hold status and priority, while `docs/ROADMAP.md` is generated from them as a read-only view. The roadmap has to work for any GitHub repository devops-cli manages, not only one that keeps a markdown file in this repo's grammar. Automated intake and reprioritization would also turn every change into a commit and a pull request to review, adding to the review load this work is meant to reduce.

## Considered Options

- **Markdown as source, synced to GitHub** (the previous design): rejected for the reasons above, and because the sync step was fragile (a 200-issue fetch cap, skipped headings, duplicate detection by filename slug).
- **A structured file in the repo (YAML/TOML) generating both the markdown and GitHub**: rejected because it keeps the commit-per-change churn.

## Consequences

- `devops gh issues sync-roadmap` and `reconcile-roadmap` are removed rather than kept alongside the new flow, per the pre-1.0 policy.
- Task files stop carrying status, milestone and priority, because GitHub owns those.
