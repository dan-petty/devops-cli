# Changelog fragments

A pull request into a release branch adds its changelog entry here as `<issue>.md` instead of
editing `CHANGELOG.md`: house-style entries under `### Added`, `### Changed`, `### Deprecated`,
`### Removed`, `### Fixed` or `### Security`. The cut (the roadmap Service's
`devops roadmap close`, or `devops release prepare [--create-pr]`) merges every fragment into
the version's section of `CHANGELOG.md` and deletes them in the cut commit. A critical fix that
merges into a cut release edits that section of `CHANGELOG.md` directly in its own pull request,
with no fragment and no collate pull request
([RELEASE_CYCLE.md](../RELEASE_CYCLE.md), "A Critical Fix While the Release PR Is Open").

An item delivered as several pull requests gets one fragment, `<issue>.md`, from the pull request
that closes it, its last. A `Part of #<issue>` pull request adds none: parts open at once would
otherwise conflict on the one name, and an item moved out of the release part-way would still
have an entry published under it.
