# Design

## Decisions

**Dedicated subcommand under `devops k8s`.**
The command lives at `devops k8s bootstrap-roadmap-key` alongside `bootstrap-openwebui` and `bootstrap-mattermost`. It targets Kubernetes cluster bootstrapping and coordinates cluster state, gateway APIs, and workstation credentials.

**Full end-to-end default workflow with `--dry-run` and `--force`.**
By default, running `devops k8s bootstrap-roadmap-key` extracts the master key from `Secret/llm/llm-gateway-secrets`, calls `POST /key/generate` with default limits (`models=["devops-*"]`, `max_budget=50.0`, `rpm_limit=60`), saves the key to OS keyring under `roadmap_service.llm_key`, and applies Secret `devops/roadmap-service-llm-key`. If the key is already stored in keyring, it preserves the existing key unless `--force` is given.

**Reusing `secret_push` and `cluster_secrets`.**
Instead of ad-hoc kubectl commands, pushing Secret `roadmap-service-llm-key` reuses the declarative `devops_cli.k8s.secret_push` machinery, ensuring proper server-side apply, labels, and workload restart triggers.

## Rejected alternatives

- **`devops ai gateway mint-key`**: Managing cluster Secrets and bootstrap flows belongs under `devops k8s` alongside other cluster service bootstrapping commands.
- **Manual operator curl scripts**: Manual multi-step curl and keyring commands are error-prone and caused the pod failure incident in #5741.
