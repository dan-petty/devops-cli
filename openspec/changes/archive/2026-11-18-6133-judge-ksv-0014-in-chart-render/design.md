# Design

## Decisions

### Add KSV-0014 dated ignore entry for chart_render.yaml
The file `tests/fixtures/image_pins/chart_render.yaml` is test input for `tests/k8s/test_image_pins.py`. Per SECURITY.md, an agent adds a time-limited ignore entry to `.trivyignore.yaml` with an expiry date of 3 days (`2026-11-21`).

### Keep test fixture unmodified
The fixture represents raw Helm template render output used by image pin extraction tests. Modifying its security context is not required when recorded as an ignored test fixture finding.

## Rejected alternatives

- **Set 90-day expiry directly**: Only the repository owner can approve an ignore longer than 14 days. An agent follows the 3-day renewal limit.
- **Dismiss alert 283 in GitHub**: An agent does not dismiss code scanning alerts.
