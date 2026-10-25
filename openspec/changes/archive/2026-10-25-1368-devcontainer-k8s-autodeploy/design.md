# Design

## Context

The devcontainer lifecycle previously attempted to auto-deploy Kubernetes stacks during `post-start` and `bootstrap-k8s`. This failed because subprocess isolation drops the session bus environment variables required to access the OS keyring. In addition, `post-start` starts before the session bus daemon initializes, and no cluster context was passed to `deploy-stack`.

The owner confirmed Option B: drop auto-deployment completely. Users unlock their keyring after container start and then run `devops k8s deploy-stack` manually.

## Decisions

- **Remove auto-deployment logic without shim**: In accordance with pre-1.0 policy, remove `--deploy/--no-deploy`, `_auto_deploy_k8s_stack`, and `DEVOPS_K8S_AUTO_DEPLOY`.
- **Print deploy command with context**: When `bootstrap-k8s` finishes, print `devops k8s deploy-stack --stack <stack> --context minikube`.
- **Define Minikube context constant**: Add `CONST_K8S_MINIKUBE_CONTEXT = "minikube"` to `constants.py` to prevent hardcoded string drift.
- **Pass clean arguments in background spawn**: `_spawn_background_k8s_bootstrap` passes `["--stack", stack]` without deployment flags.

## Rejected Alternatives

- **Option A: Keep auto-deploy and pass session bus environment variables**: Rejected by owner decision on issue #1368. Unattended startup cannot reliably access the keyring while the keyring remains locked by the user. Maintaining session bus pass-through and lifecycle ordering introduces fragile process coupling.
- **Keep `--deploy` as a deprecated no-op flag**: Rejected by devops-cli pre-1.0 policy. Pre-1.0 software maintains no backward compatibility or shims.
