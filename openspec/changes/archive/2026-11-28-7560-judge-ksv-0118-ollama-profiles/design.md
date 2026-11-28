# Design

## Decisions

### Set pod securityContext on the ollama-profiles DaemonSet fixture

Add a non-root pod `securityContext` (`runAsNonRoot: true`, `runAsUser: 10001`, `runAsGroup: 10001`, `fsGroup: 10001`, `seccompProfile.type: RuntimeDefault`) to `spec.template.spec` in `tests/fixtures/k8s_environment/llm/profiles/ollama-profiles.yaml`, matching the pattern established in `#6923` (`tests/fixtures/image_pins/chart_render.yaml`). `ollama_tiers` (`src/devops_cli/k8s/gpu_placement.py:54-73`) reads only `spec.template.spec.affinity.nodeAffinity`, so adding `securityContext` preserves test fixture semantics while eliminating `KSV-0118`.

## Rejected alternatives

- **Set `resources.limits.cpu` on a container**: `tests/fixtures/k8s_environment/llm/profiles/ollama-profiles.yaml:11-19` defines no `containers` list, and `trivy config` reports `KSV-0118` ("using the default security context, which allows root privileges"), not a CPU limit.
- **Add an ignore entry in `.trivyignore.yaml`**: Per `SECURITY.md:130-131`, fixing the file is the first choice, whereas `.trivyignore.yaml` expires in 3 to 14 days for findings with no fix.
- **Dismiss code-scanning alert `1258`**: `SECURITY.md:132` forbids agents from dismissing alerts; fixing the fixture closes alert `1258` cleanly on the next scan on `main`.
