# Design

## Decisions

### Fix the test fixture at its source
`SECURITY.md` states that fixing the file in a pull request is the first choice for judging a `Trivy-config` alert.
Adding a restrictive pod `securityContext` (`runAsNonRoot: true`, `runAsUser: 10001`, `runAsGroup: 10001`, `fsGroup: 10001`, `seccompProfile.type: RuntimeDefault`) and restrictive container `securityContext` blocks (`allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `runAsUser: 10001`, `runAsGroup: 10001`, `capabilities.drop: [ALL]`, `seccompProfile.type: RuntimeDefault`) on both containers resolves `KSV-0118` and `KSV-0014` without a recurring `.trivyignore.yaml` entry.

### Keep both fixture image pins and update inventory line expectations
`src/devops_cli/research/k8s_pins.py` reads `image` fields from `tests/fixtures/research/repo/k8s/llm/valkey.yaml`, and `tests/research/test_inventory.py:93-94` asserts both the image strings (`valkey/valkey:9.1.2-alpine` and `example/untagged`) and their YAML line numbers.
Both images stay intact so the inventory test suite keeps testing an untagged image pin.
Lines 93-94 of `tests/research/test_inventory.py` update from lines `10` and `12` to lines `17` and `30` to match the shifted YAML lines.

## Rejected alternatives

- **Add a dated `.trivyignore.yaml` entry for `KSV-0118`**: The refine text of the issue assumed `example/untagged` blocked a fix to `valkey.yaml`. In reality, `trivy config tests/fixtures/research/repo/k8s/llm/valkey.yaml` shows that missing `securityContext` causes `KSV-0118` (`example/untagged` triggers `KSV-0013`). `SECURITY.md:112` requires fixing the file first.
- **Dismiss alert 1190 in GitHub code scanning**: `SECURITY.md:114` states that an agent does not dismiss an alert, and GitHub dismissals leave no repository fix.
- **Add only a pod-level `securityContext`**: Leaving container `securityContext` unset leaves `KSV-0014` (`HIGH`, `readOnlyRootFilesystem`) open on `tests/fixtures/research/repo/k8s/llm/valkey.yaml:9-12`.
