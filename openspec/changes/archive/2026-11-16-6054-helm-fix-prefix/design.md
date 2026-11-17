# Design

## Decisions
- The rule matches the `helm` datasource and sits in the repository config, after the rule for the service image base. `HELM_RELEASES_BY_STACK` is in this repository only, so the shared preset keeps `chore(deps):`.
- The `dcgm-exporter` group sets the prefix too. Renovate builds the title of a group from its first update, so the image could give a chart update the prefix `chore(deps):`.
- No test reads the rules (owner, 2026-11-16, #6060); `renovate-config-validator` checks the form.

## Rejected alternatives
- Keep `chore(deps):` and change each title by hand: each completed chart update would fail `Semantic PR title` once more.
- Remove the version from `HELM_RELEASES_BY_STACK` and read it from the Application: a larger change of `deploy-stack`, left to #6060; the update would still change what `deploy-stack` installs.
