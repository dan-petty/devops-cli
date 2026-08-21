1. `spec.template.spec.securityContext` configured with:
   - `runAsNonRoot: true`
   - `runAsUser: 10001` (or non-zero UID)
   - `runAsGroup: 10001`
   - `seccompProfile.type: RuntimeDefault`
2. `container.securityContext` configured with:
   - `allowPrivilegeEscalation: false`
   - `readOnlyRootFilesystem: true`
   - `capabilities.drop: ['ALL']`
3. Resource requests and limits defined (cpu, memory).
4. Liveness and readiness probes configured.
5. Temporary writable emptyDir volume mounted for `/tmp` if needed.
