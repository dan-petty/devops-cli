Harden the following vulnerable Kubernetes Deployment manifest to comply with the Kubernetes Restricted Pod Security Standard (PSS/PSA) using a step-by-step chain-of-thought hardening procedure:

### Vulnerable Manifest:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-api
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: payment-api
  template:
    metadata:
      labels:
        app: payment-api
    spec:
      containers:
      - name: api
        image: payment-api:v1.2.0
        ports:
        - containerPort: 8080
```

### Hardening Steps:
1. **Analyze Restricted PSS Invariants**: Identify missing security controls (non-root UID, read-only rootfs, drop capabilities, seccomp profile, resource limits).
2. **Pod-Level Context**: Configure `spec.template.spec.securityContext` (`runAsNonRoot: true`, `seccompProfile: {type: RuntimeDefault}`).
3. **Container-Level Context**: Configure `securityContext` (`allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, `capabilities: {drop: ["ALL"]}`).
4. **Resource Constraints & Probes**: Add CPU/memory requests/limits and appropriate probes.
5. **Output Complete YAML**: Provide the complete, production-ready Kubernetes YAML manifest.
