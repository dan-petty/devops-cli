# Proposal: #6606

## Why

Trivy reports HIGH KSV-0014 on `tests/fixtures/image_pins/chart_render.yaml`.
The StatefulSet in the fixture lacked a pod and container security context.
Fixing the test fixture at its source resolves the finding without recurring suppressions.

## What Changes

- Add restrictive `securityContext` to the StatefulSet pod and container in `tests/fixtures/image_pins/chart_render.yaml`.
- Remove expired ignore entries for `tests/fixtures/image_pins/chart_render.yaml` from `.trivyignore.yaml`.

## Capabilities

### Modified
- `trivy-config-alerts`: The chart render test fixture meets least-privilege container security requirements.

## Impact

The `chart_render.yaml` test fixture no longer triggers KSV-0014 or KSV-0118 misconfigurations during IaC scans.

## Feasibility

Confirmed against the real system: adding the restrictive security context clears KSV-0014 and KSV-0118 during `trivy config`.
The image pin tests in `tests/k8s/test_image_pins.py` continue to pass.

## Existing Tool Considered

Trivy is the open and maintained scanner for Kubernetes IaC misconfigurations.
No custom code is built.
