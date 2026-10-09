# Changelog fragments

A pull request into a release branch adds its changelog entry here as `<issue>.md` instead of
editing `CHANGELOG.md`: house-style entries under `### Added`, `### Changed`, `### Deprecated`,
`### Removed`, `### Fixed` or `### Security`. The cut (the roadmap Service's
`devops roadmap close`, or `devops release prepare [--create-pr]`) merges every fragment into
the version's section of `CHANGELOG.md` and deletes them in the cut commit. A critical fix that
merges into a cut release edits that section of `CHANGELOG.md` directly in its own pull request,
with no fragment and no collate pull request
([RELEASE_CYCLE.md](../RELEASE_CYCLE.md), "A Critical Fix While the Release PR Is Open").
