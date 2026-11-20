## MODIFIED Requirements

### Requirement: Renovate pins no digest of a version input of an action
The shared preset SHALL pin the digests of github-actions and dockerfile dependencies, but not of a `uses-with` dependency of github-actions, such as the `version` input of setup-uv, because that input names a release tag and has no place for a digest.

#### Scenario: The digest pin rules are applied to each dependency type
- **WHEN** a test applies the pin rules of `.github/renovate/base.json` in order to the github-actions types `action`, `docker`, `container`, `service` and `uses-with`, and to the dockerfile types `final` and `stage`
- **THEN** only the github-actions type `uses-with` pins no digest
