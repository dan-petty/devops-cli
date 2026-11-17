## REMOVED Requirements

### Requirement: The Harbor version is pinned
**Reason**: The requirement only held a version of `pyproject.toml` equal to the one of `uv.lock`, a value test of two config files that a Renovate update fails (#6060).
**Migration**: The `lockfile` row of `devops ci` (`uv lock --check`) refuses a `uv.lock` that does not agree with `pyproject.toml`.
