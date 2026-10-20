# Task: The roadmap service stays at 0 replicas, and its development is blocked, while its machine account is suspended (#1562)

**Issue**: [#1562](https://github.com/dan-petty/devops-cli/issues/1562)
**Scope**: type/chore, scope/k8s, scope/roadmap
**Feasibility**: Checked at release/v0.2.34 (3b563b2). Argo CD's `devops` Application syncs `k8s/overlays/homelab/devops`, which takes `k8s/devops`, from `main` with `selfHeal`. With sync re-enabled, it would restore the deployment's `replicas: 1`. `devops k8s deploy-stack --stack devops` would do the same. CronJob `devops-cli` is already `suspend: true`.

## Description

GitHub suspended the machine account the roadmap Service acts as. The owner scaled `deployment/roadmap-service` to 0 and turned off the `devops` Application's sync by hand. This change keeps the Service off in git, and it stops agents from developing or exercising the Service until the account question is settled.

- **Held at 0.** `k8s/devops/roadmap-service/deployment.yaml` asks for `replicas: 0`, with a comment naming #1562, and `tests/test_k8s_roadmap_service.py` pins it. The Service, PVC, NetworkPolicy and Ingress stay, so turning the Service back on means raising the replicas and nothing else.
- **The notice.** AGENTS.md opens its roadmap-service rules with the suspension, and `k8s/README.md` opens its "Roadmap service" section with it:
  - nobody scales, restarts or re-pushes secrets for the Service;
  - only a person runs mutating `devops roadmap` commands, from their own account;
  - agents use `--plan` and `--dry-run` only, and take up no item blocked on #1562.
- **Blocked items.** These items develop the Service, or can only be checked on it. Each gets `status/blocked` and a comment pointing to #1562: #1365, #1386, #1387, #1389, #1392, #1394, #1395, #1414, #1416, #1533, #1534, #1535, #1539, #1540 and #1544. Items that fix the roadmap jobs as the CLI also runs them stay open for work. #1409 makes the job clone and the change filter fail closed when the login lookup fails, which lowers the risk of a restart.

## Acceptance Criteria

- [x] The deployment asks for 0 replicas, and `tests/test_k8s_roadmap_service.py::test_deployment_spec_and_container` pins it.
- [x] AGENTS.md and `k8s/README.md` carry the notice.
- [x] `changelog.d/1562.md` records the change.
- Pending a person: disable or remove the webhook in each repository in `service.repos`, in that repository's **Settings → Webhooks**.
- Pending a person: keep the `devops` Application's sync off until this change reaches `main`, then turn it back on. `kubectl -n devops get deployment roadmap-service` shows `0/0`.
- Reverting this change (`replicas: 1`, the notices removed, the items unblocked) is its own item, filed once the account is reinstated or the jobs act as a GitHub App.
