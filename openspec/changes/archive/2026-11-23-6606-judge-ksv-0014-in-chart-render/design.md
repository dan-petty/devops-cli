# Design

## Decisions

### Fix fixture at source instead of adding ignore entry
`tests/fixtures/image_pins/chart_render.yaml` is a committed repository fixture.
Adding a standard restrictive security context (`runAsNonRoot: true`, `runAsUser: 10001`, `runAsGroup: 10001`, `fsGroup: 10001`, `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, `capabilities.drop: [ALL]`, `seccompProfile.type: RuntimeDefault`) satisfies the Trivy rules permanently and removes the need for periodic ignore renewals.

### Remove expired entries from .trivyignore.yaml
With the fixture fixed at source, the suppression entries in `.trivyignore.yaml` for `chart_render.yaml` are obsolete and removed.

## Rejected alternatives

- **Renew ignore entry in .trivyignore.yaml**: Renews an unnecessary suppression for a fixture that can be fixed cleanly at source.
- **Dismiss the alert**: An agent does not dismiss alerts in code scanning; fixing the source allows the scanner to resolve the alert naturally.
