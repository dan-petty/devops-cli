# Changelog fragments

A pull request into a release branch adds its changelog entry here as `<issue>.md` instead of
editing `CHANGELOG.md`: house-style entries under `### Added`, `### Changed`, `### Deprecated`,
`### Removed`, `### Fixed` or `### Security`. The cut (`devops release prepare`) merges every
fragment into the version's section of `CHANGELOG.md` and deletes them. A critical fix that
merges into a cut release adds its fragment too; once the release's fragments were collected, a
`chore/open-vX.Y.Z-collate-<issue>` pull request moves it into the version's section before the
release pull request merges, and a fragment left behind goes into the next release's section
([RELEASE_CYCLE.md](../RELEASE_CYCLE.md), "A Critical Fix While the Release PR Is Open").
