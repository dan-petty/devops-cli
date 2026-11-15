# Design

## Decisions

- **Fix the manifest directly rather than adding a .trivyignore.yaml entry.**: SECURITY.md designates fixing the manifest as the first choice when judging alerts. Because GFD v0.16.2 writes its node features solely to the mounted `/etc/kubernetes/node-feature-discovery/features.d` directory, an immutable root filesystem does not break the container.
- **Retain privileged: true and the host mounts.**: Issue #5646 tracks the non-privileged transition for GFD. Until that issue lands, GFD requires device access and sysfs access.
- **Validate the manifest using an offline YAML-parse invariant test.**: Tests in `tests/invariants/` verify manifest structure quickly and deterministically without external network or daemon requirements.

## Rejected alternatives

- **Add an ignore entry to .trivyignore.yaml.**: Unnecessary because setting `readOnlyRootFilesystem: true` fixes the issue at source without breaking the workload.
- **Dismiss the alert in code scanning.**: Per SECURITY.md, only human maintainers may dismiss alerts.
- **Remove privileged: true now.**: GFD v0.16.2 fails to detect GPU devices without privileged access; that work is tracked by #5646.

## Security

Setting `readOnlyRootFilesystem: true` hardens the container by preventing modifications to the container filesystem at runtime, mitigating persistence and tamper risks if the container is compromised.
