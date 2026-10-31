# Design

## Decisions

- **Add the affinity to the values files before removing the exemptions.**: If the exemptions are removed first, the placement test fails because the affinity is not yet in the values files. Adding the affinity first keeps the test green at every step.
- **Use the exact affinity pattern from the README Local-Path Volume Placement section.**: The README defines the pattern and the test checks for it. A different pattern would fail the test.
- **Keep the constant as an empty list rather than deleting it.**: Other code may import CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS. An empty list is a safe no-op that avoids an import error.

## Rejected alternatives

- **Remove the exemptions before adding the affinity.**: The placement test checks the affinity for every pod not in the exemption list. Removing the exemptions first makes the test fail because the affinity is not yet in the values files.
- **Use a nodeSelector instead of nodeAffinity.**: The README and the test both use the nodeAffinity form. A nodeSelector would not match the test assertion and would not be consistent with the other workloads that already use nodeAffinity.
