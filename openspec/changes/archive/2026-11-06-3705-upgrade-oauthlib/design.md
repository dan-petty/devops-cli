# Design

## Context

`uv.lock` holds `oauthlib` 4.0.0 through `kubernetes` and `requests-oauthlib`. The project does not import `oauthlib`.

## Decisions

- **Move only the lock.** A pin in `pyproject.toml` names a package that the project does not import, and `deptry` checks for that. The lock is the file that `uv audit` reads.

## Rejected alternatives

- **An ignore for the advisory.** Only the owner can lower a security threshold, and a fixed release exists.
