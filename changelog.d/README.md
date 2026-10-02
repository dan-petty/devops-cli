# Changelog fragments

A pull request into a release branch adds its changelog entry here as `<issue>.md` instead of
editing `CHANGELOG.md`: house-style entries under `### Added`, `### Changed`, `### Deprecated`,
`### Removed`, `### Fixed` or `### Security`. The cut (`devops release prepare`) merges every
fragment into the version's section of `CHANGELOG.md` and deletes them.
