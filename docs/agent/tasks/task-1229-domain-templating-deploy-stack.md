# Task: Domain Templating in deploy-stack Manifests and Roadmap-Service Ingress (#1229)

**Issue**: [#1229](https://github.com/dan-petty/devops-cli/issues/1229)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p1-high
**Scope**: scope/k8s

## Description
When `devops k8s deploy-stack --stack devops` (or `--stack all`) deployed `k8s/devops/roadmap-service/ingress.yaml`, it applied the raw manifest via `kubectl apply -f <path>` without domain substitution. The raw manifest contained the placeholder `hooks.example.com` and `pathType: Exact`. As a result, Traefik only matched `hooks.example.com` and returned HTTP 404 for incoming GitHub webhook requests hitting `hooks.<user-domain>/webhooks/github`. Additionally, `k8s/ingress/ingress-routes.yaml` lacked the `roadmap-service` ingress route.

This deliverable:
1. **Automates Domain Substitution in `deploy-stack`**: Updates `_apply_manifest_files` in `src/devops_cli/commands/k8s/stack_lifecycle.py` to automatically substitute domain placeholders in manifests using `resolve_template_domain()`, preventing future stack redeployments from reverting ingress hostnames to `example.com`.
2. **Adds `--domain / -d` to `deploy-stack`**: Adds `--domain / -d` support to `devops k8s deploy-stack`, consistent with `devops k8s apply` and `devops k8s render`.
3. **Uses Prefix Path Type**: Changes `pathType: Exact` to `pathType: Prefix` on `/webhooks/github` in `k8s/devops/roadmap-service/ingress.yaml` for robust webhook routing.
4. **Registers Ingress Route**: Adds `roadmap-service` Ingress route to `k8s/ingress/ingress-routes.yaml` for complete coverage under Cloudflare Wildcard Tunnel integration.
5. **Comprehensive Tests**: Adds unit and dry-run tests in `tests/test_k8s_devops_stack.py` and updates `tests/test_k8s_roadmap_service.py`.

## Acceptance Criteria
- [x] Ingress template domain placeholders are automatically substituted when `deploy-stack` runs.
- [x] `deploy-stack` supports `--domain / -d` option.
- [x] `roadmap-service` Ingress uses `pathType: Prefix`.
- [x] `roadmap-service` Ingress route is registered in `k8s/ingress/ingress-routes.yaml`.
- [x] All 14 CI quality gates pass via `uv run devops ci`.
- [x] End-to-end webhook delivery verified in live cluster returning HTTP 200 `{"status": "pong"}`.

## Deliverables
- [x] `src/devops_cli/commands/k8s/stack_lifecycle.py`
- [x] `k8s/devops/roadmap-service/ingress.yaml`
- [x] `k8s/ingress/ingress-routes.yaml`
- [x] `docs/CLI_REFERENCE.md` and `docs/commands/k8s.md`
- [x] `tests/test_k8s_devops_stack.py`
- [x] `tests/test_k8s_roadmap_service.py`
- [x] `changelog.d/1229.md`
- [x] Task file `docs/agent/tasks/task-1229-domain-templating-deploy-stack.md`.
