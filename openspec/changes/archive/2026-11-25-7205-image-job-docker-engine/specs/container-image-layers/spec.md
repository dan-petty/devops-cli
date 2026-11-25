## ADDED Requirements

### Requirement: A pull request builds the images in the Docker Engine of the runner
The image jobs of `ci.yml` SHALL build with the Docker Engine of the runner, with no builder container, and SHALL read the registry cache that the release writes.

#### Scenario: The build reads the cache and transfers no tar file
- **WHEN** a person reads the log of the `Runner Image` job of a pull request that changes no dependency
- **THEN** the dependency stages show as `CACHED`, and the log holds no `sending tarball` line
