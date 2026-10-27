# Design

`pyproject.toml` pins `dnspython` exactly, so the pin changes with the lock. `uv lock` moves `idna` too, because `dnspython[idna]` depends on it.

## Rejected alternatives

- **Ignore the advisory in the audit**: Lowers a security threshold.
- **Wait for a release of `dnspython` that is not affected**: 2.9.0 is the fixed release.

## Test

The existing tests cover the code that imports `dnspython`. The full `devops ci` gates, including `audit`, check the lock.
