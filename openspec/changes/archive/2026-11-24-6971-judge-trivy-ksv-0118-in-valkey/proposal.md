# Proposal: #6971

## Why

Trivy reports `KSV-0118` at `HIGH` severity on `tests/fixtures/research/repo/k8s/llm/valkey.yaml` (alert 1190, issue #6971).
The fixture Deployment lacks pod and container `securityContext` blocks, which also triggers `KSV-0014` (`HIGH`, alert 287).
Per `SECURITY.md`, fixing the file at its source is the first choice when a manifest can set the control without breaking its workload or test role.
The change fits one pull request.

## What Changes

- Add restrictive `securityContext` blocks to the pod template and to both containers (`valkey` and `untagged`) in `tests/fixtures/research/repo/k8s/llm/valkey.yaml`.
- Keep both container images (`valkey/valkey:9.1.2-alpine` and `example/untagged`) unchanged so the inventory test fixture keeps its tagged and untagged cases.
- Update the expected line numbers for those two images in `tests/research/test_inventory.py`.
- No consumer-observable behavior changes because the change edits only a test fixture and its test file, so `skip_specs: true` stays set.

## Capabilities

None. The change modifies no `src/` code and no consumer-observable capability.

## Impact

- `trivy config` reports zero `HIGH` or `CRITICAL` findings (`KSV-0118` and `KSV-0014`) on `tests/fixtures/research/repo/k8s/llm/valkey.yaml`.
- `tests/research/test_inventory.py` continues to assert the exact parsed image pins and their updated line numbers.

## Feasibility

Confirmed against the real system with `trivy config --severity HIGH,CRITICAL tests/fixtures/research/repo/k8s/llm/valkey.yaml` (Trivy reports `KSV-0118` and `KSV-0014` before the fix) and `tests/research/test_inventory.py:93-94`.
The untagged image (`example/untagged`) causes `KSV-0013` (`MEDIUM`), not `KSV-0118` or `KSV-0014`.
Adding `securityContext` blocks clears both `HIGH` findings while preserving `example/untagged`.

## Existing Tool Considered

Trivy (`aquasecurity/trivy`) is the open, maintained scanner that reports `KSV-0118` and `KSV-0014`.
The change adds no new code and builds no replacement tool.
It edits two YAML blocks in an existing test fixture, so the build cost is zero tokens of new runtime code.
