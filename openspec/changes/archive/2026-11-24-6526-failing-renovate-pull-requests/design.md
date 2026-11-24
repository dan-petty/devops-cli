# Design

## Decisions

### Restrict incompatible runtime and package versions in Renovate
Node 26 fails runtime image tests on Debian Trixie.
Python 3.15 is unsupported by required wheel packages.
The `grafana-foundation-sdk` package published broken PyPI epoch versions.
Restricting these packages in `.github/renovate.json` prevents Renovate from opening failing pull requests.

### Shorten active OpenSpec change requirements
OpenSpec 2.1.1 enforces strict validation rules where MODIFIED requirements must have fewer than 500 characters.
Shortening requirement text in changes `3060` and `3429` satisfies OpenSpec 2.1.1 without changing normative requirements.

## Rejected alternatives

- **Upgrade base images to support Node 26**: Debian Trixie is the current stable base image standard for the repository.
- **Permit bare PyPI epoch versions**: The epoch versions break the SDK.
