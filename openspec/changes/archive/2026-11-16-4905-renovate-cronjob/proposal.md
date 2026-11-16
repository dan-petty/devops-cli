# Proposal: #4905

## Why
No Renovate instance runs for the 7 Service repositories. Renovate opened 0 pull requests on devops-cli from 2026-10-01 to 2026-11-16, so the pins move only after a security finding or by hand: for example, the gateway runs LiteLLM 1.103.11 while 1.109.1 is out (#4893). The owner chose a self-hosted Renovate in the cluster, with its own GitHub App, and accepted its AGPL-3.0-only license for the unmodified image (2026-11-11). #4897 added the token command that this CronJob runs.

## What Changes
- New folder `k8s/devops/renovate/` (Application `devops`, and `deploy-stack --stack devops`): CronJob `renovate` every 2 hours (UTC), ConfigMap `renovate-config` with `config.js` and `config.json`, PVC `renovate-cache` and NetworkPolicy `renovate-perimeter`.
- The pod runs init container `seed` (copies the two image folders that Renovate writes), init container `token` (the Service image runs `devops gh app-token --app renovate`, the only reader of Secret `renovate`) and container `renovate` (`ghcr.io/renovatebot/renovate:44.239.1` by digest, a lookup dry run until #4909).
- `devops-default-perimeter` skips the Renovate pod.
- The Secret table gets the row `devops/renovate` (3 keys), and the `homelab` AppProject ignores the pushed Secret as an orphan.
- ADR 0027 records the decision and the license exception. `CONTRIBUTING.md` names the exception. `docs/CLUSTER.md` gets a Renovate section, and `k8s/README.md` gets the Secret rows and a note.

## Capabilities
- `renovate-service` (new): the CronJob, its pod controls, the token path, the config, the cache, the perimeter, the Secret row and the license records.

## Impact
- Rollout: after the merge, Argo CD creates the objects. A person runs `devops k8s push-secrets --only devops/renovate`. Until then the `token` container names the settings that are not set and exits 1, so each Job stops with no request to GitHub.
- The three keys are optional (`OPTIONAL_FEATURE_SECRETS`): a push of stack `devops` on a workstation with no Renovate settings skips them with a warning and does not fail.
- The first runs are a lookup dry run: Renovate reads the repositories and writes nothing to GitHub. #4909 measures them and removes the dry run.
- Only devops-cli has a Renovate config, so the other 6 repositories get no onboarding pull request until #4913 turns onboarding on.
- The node pulls one more image (about 427 MiB compressed), and the pod uses up to 10 GiB of emptyDir space.

## Feasibility
Checked on 2026-11-16 against Renovate 44.239.1 (published 2026-11-13, the newest release at least 3 days old). Each global option exists in `lib/config/options/index.ts` at that tag, `RENOVATE_X_SQLITE_PACKAGE_CACHE` is in `docs/usage/self-hosted-experimental.md`, and `@renovatebot/osv-offline` 4.5.10 reads `OSV_OFFLINE_DATABASE_FORMAT` and `OSV_OFFLINE_MAX_AGE`. The digest of the index came from a registry read. The image config gives user 12021 (`ubuntu`, primary group 0), and its layers show `/opt/containerbase` and `/home/ubuntu` with build files, and `/var/lib/containerbase` owned by root with mode 0755. With the pinned image, a read-only root and user 12021:12021, the seed copy exited 0 and `renovate-config-validator` validated `config.js`. Trivy 0.76.2 shows no HIGH or CRITICAL finding for the new files.

## Existing Tool Considered
Renovate, self-hosted as a plain Kubernetes CronJob: the shape that its Helm chart renders. Rejected: the Renovate Helm chart (AGPL-3.0-only, widens the exception, adds a chart repository), the hosted Mend app (cannot run the project's commands), an Argo CronWorkflow in `argo-workflows` (no public HTTPS, no Secret), and `mogenius/renovate-operator` (a controller, a CRD and RBAC). Nothing is built: the change is manifests, one table row, tests and documents.
