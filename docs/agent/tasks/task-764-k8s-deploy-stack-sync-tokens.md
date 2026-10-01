# Task 764: Auto-Mint and Synchronize argocd.token and grafana.token in deploy-stack

**Issue**: [#764](https://github.com/dan-petty/devops-cli/issues/764)
**Status**: Done
**Milestone**: `v0.2.24`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/k8s`, `priority/p2-medium`

---

## 1. Description & Objectives

Running `devops k8s deploy-stack` and `devops k8s sync-secrets` previously extracted initial Kubernetes admin passwords (`argocd_password` from `argocd-initial-admin-secret` and `grafana_password` from `kube-prometheus-stack-grafana`) into the OS Keyring. However, downstream CLI commands (`devops argo` and `devops grafana`) authenticate via Bearer tokens (`argocd.token` and `grafana.token`). Because token minting was omitted from the stack lifecycle, users were left with unauthenticated or 401 Unauthorized errors when querying ArgoCD or Grafana services.

Root causes identified:
1. `credentials.py`: `sync_k8s_credentials` discovered and synchronized only `argocd_password` and `grafana_password`. It did not attempt to exchange or mint API tokens with running services.
2. `argo.py`, `fleet.py`, and `gitops.py`: Only resolved `get_argocd_token(settings)`. When `argocd.token` was unconfigured, requests sent no authorization header even if `argocd.password` was present in the OS Keyring.
3. `grafana.py`: Only resolved `get_grafana_token(settings)`. When `grafana.token` was unconfigured, requests sent no authorization header even if `grafana.password` was present in the OS Keyring.

### Key Deliverables Completed:
- [x] **Stack Authentication Constants** (`src/devops_cli/config/defaults.py`):
  - Defined `DEFAULT_STACK_AUTH_TIMEOUT_SECONDS = 5.0` for bounded authentication requests during stack deployment.
- [x] **Token Minting & Discovery in Kubernetes Credentials Subsystem** (`src/devops_cli/k8s/credentials.py`):
  - Implemented `mint_argocd_token`: Authenticates against `/api/v1/session` with the admin password to mint a session JWT and securely persists it as `argocd_token` in OS Keyring.
  - Implemented `mint_grafana_token`: Authenticates via HTTP Basic Auth to find or create a `devops-cli` Service Account (`/api/serviceaccounts`) and generate a Service Account token (`/api/serviceaccounts/{id}/tokens`), with fallback to `/api/auth/keys`, persisting `grafana_token` in OS Keyring.
  - Implemented `get_or_mint_argocd_token`: Transparent on-demand resolution that falls back to password-based session token minting when `argocd.token` is missing.
  - Implemented `get_or_mint_grafana_auth`: Transparent on-demand resolution that falls back to service account token minting and HTTP Basic Auth when `grafana.token` is missing.
  - Updated `sync_k8s_credentials` to attempt token minting during credential sync when target URLs are reachable.
- [x] **Lifecycle Feedback & Command Integration** (`src/devops_cli/commands/k8s/stack_lifecycle.py`, `argo.py`, `grafana.py`, `fleet.py`, `gitops.py`):
  - Updated `_post_deploy_credentials` and `sync_secrets` to report `argocd_token` and `grafana_token` synchronization.
  - Wired `get_or_mint_argocd_token` into `_argocd`, `trigger_argocd_sync`, and `sync_fleet_app`.
  - Wired `get_or_mint_grafana_auth` into `_client_args` in `grafana.py`.
- [x] **Comprehensive Test Suite & Gated Quality Gates** (`tests/test_k8s_credentials.py`, `tests/test_grafana.py`, `tests/test_argo.py`):
  - Added unit tests for `mint_argocd_token`, `mint_grafana_token`, `get_or_mint_argocd_token`, and `get_or_mint_grafana_auth`.
  - Consolidated assertions using structural tuple equality to ensure strict $M \le 10$ cyclomatic complexity.
  - Verified 100% compliance across all Gated CI validation gates (`uv run devops ci`).
