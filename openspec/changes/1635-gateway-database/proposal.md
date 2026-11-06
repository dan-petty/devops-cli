# Proposal

## Why

Issue #1635: every client of the LLM gateway holds its master key, the admin key of LiteLLM. An agent session can get a gateway credential only when a person pastes the master key. LiteLLM virtual keys (expiry, request and token limits, model list, alias, own revocation) fix this, but LiteLLM keeps them only in a Postgres database that `DATABASE_URL` names, and the gateway has none. Without the database, the agent grant of #1154 cannot be built, and no cluster workload can leave the master key.

The refine round proposed to split the item in 5. The 5 parts are one change: a database for the gateway, its connection, its perimeter and its place in the stack order. None of them is useful alone, and each one edits the same two files. The change fits one pull request.

## What Changes

- A CloudNativePG `Cluster` `llm-gateway-db` in `k8s/llm/gateway-db.yaml`, with the NetworkPolicy `llm-gateway-db-perimeter`. The cluster already runs the CloudNativePG operator for the Mattermost database, and the new `Cluster` has the form of `k8s/mattermost/database.yaml`: one instance, the same pinned image, `local-path` storage, `Prune=false,Delete=false`, no superuser access.
- The `Cluster` names no `bootstrap.initdb.secret`. The operator creates the user, the database and Secret `llm-gateway-db-app` at run time. No secret goes in git, `CLUSTER_SECRETS` gets no row, and no person pushes a password.
- The gateway Deployment reads `DATABASE_URL` from the `uri` key of that Secret, sets `LITELLM_MIGRATION_DIR` on an `emptyDir`, keeps `readOnlyRootFilesystem: true`, and gets a `startupProbe`, so a pod that applies migrations is not killed.
- The gateway policy gains one egress rule to the database pods on 5432. `llm-default-perimeter` leaves the database pods out, as it leaves out the other workloads that have a policy of their own.
- `k8s/llm/kustomization.yaml` lists the file (Argo CD's `llm` Application). `_POST_HELM_BY_STACK["llm"]` lists it for deploy-stack, after the Helm releases, because the `Cluster` needs the operator's CRD. The `cloudnative-pg` release moves from stack `chat` to stack `infra`, so stack `llm` and stack `chat` share one operator and no stack installs it twice.
- The secret guard of `tests/invariants/test_k8s_manifests.py` accepts the Secret that a `Cluster` without `initdb.secret` creates.
- `k8s/README.md` describes the database, the rollout and the stack move.
- The change adds the capability `llm-gateway-database`, and modifies `k8s-helm-deploy`, because a manifest and a deploy-stack order change.
- Not in this change: `LITELLM_SALT_KEY` (see Design), a backup of the database, the agent grant command (#1154), and a virtual key for the cluster Jobs.

## Capabilities

### New Capabilities

- `llm-gateway-database`: the database of the gateway, how the gateway connects to it, its perimeter, and what the gateway does when the database is down.

### Modified Capabilities

- `k8s-helm-deploy`: stack `chat` no longer installs `cloudnative-pg`; stack `infra` does, and stack `llm` applies the database after the Helm releases.

## Impact

- Manifests: `k8s/llm/gateway-db.yaml` (new), `k8s/llm/kustomization.yaml`, `k8s/llm/networkpolicy.yaml`, `k8s/llm/gateway/deployment.yaml`, `k8s/llm/gateway/networkpolicy.yaml`, `k8s/llm/gateway/config.yaml` (comments).
- Code: `src/devops_cli/commands/k8s/stack_lifecycle.py` (the release and its repository move to `infra`; one post-Helm path).
- Tests: `tests/gate/k8s_checks/gateway_database.py` (new), `tests/invariants/test_k8s_manifests.py`.
- Documents: `k8s/README.md`.
- Rollout on the homelab: Argo CD applies the merge. The gateway has no downtime (see `k8s/README.md`, "Gateway database and virtual keys").
- Existing tests that must keep passing: `tests/commands/k8s/test_k8s_mattermost.py`, `tests/invariants/test_k8s_argocd_apps.py`, `tests/core/test_k8s_local_path_placement.py`, and the whole `k8s` row of `devops ci`.

## Feasibility

All checks ran on 2026-11-06 in a checkout at origin/main `29309f04`. The cluster was not changed.

- LiteLLM needs the database. The documents of LiteLLM (docs.litellm.ai, "Production") state that virtual keys need `DATABASE_URL`, that `prisma migrate deploy` runs at start-up, and that a read-only root file system needs `LITELLM_MIGRATION_DIR` on a writable directory. The source of `litellm-proxy-extras` at tag `v1.103.0` (`litellm_proxy_extras/utils.py`, `_get_prisma_dir`) copies the migrations into that directory when it is set.
- The pinned image runs with a read-only root. Its `Dockerfile` at tag `v1.103.0` bakes the Prisma CLI and engines under `/opt/prisma` and sets `PRISMA_OFFLINE_MODE=true`, `PRISMA_BINARY_CACHE_DIR` and `PRISMA_CLI_PATH`, so the migration needs no download and writes only to the migration directory. A live run of this image on a read-only root with a database was not made. The first rollout is that run, and the `startupProbe` and the old pod, which keeps serving, bound its risk.
- The operator creates the Secret. The CloudNativePG documents (`docs/src/applications.md`, "Secrets") state that the operator generates `[cluster name]-app`, unless `.spec.bootstrap.initdb.secret.name` names a secret, and that it holds the user name, the password, the host, the port, the database name, a `.pgpass` file and the `uri`. `docs/src/bootstrap.md` states that `initdb` uses `app` for the database and the owner when none is named. This change names `litellm` for both.
- The operator is in the cluster. `k8s/argocd/apps/cloudnative-pg.yaml` installs chart `cloudnative-pg` 0.29.1 for the Mattermost `Cluster` (`k8s/mattermost/database.yaml`). The `homelab` AppProject admits namespace `llm` and the kind `Cluster` (no resource whitelist), and Application `llm` already sets `SkipDryRunOnMissingResource=true`, so a sync before the CRD exists retries and does not fail for good.
- The connection works with the default rules. The CloudNativePG documents (`docs/src/postgresql_conf.md`, "The pg_hba section") show the default rule `host all all all scram-sha-256`, which admits a plain or a TLS client, so the URL needs no `sslmode`.
- The instance needs the API server. The documents (`docs/src/security.md`, "Calls to the API server made by the instance manager") state that the instance manager calls the API server. The issue text asked for no egress except DNS. That would stop the instance manager, so the policy has the egress form of `mattermost-db-api` in `k8s/mattermost/networkpolicy.yaml`.
- The pods carry label `cnpg.io/cluster`, which the Mattermost policies already select on. The policies of this change select on it too.
- A virtual key does not depend on a salt key. The source at tag `v1.103.0` (`litellm/proxy/common_utils/encrypt_decrypt_utils.py`) takes `LITELLM_SALT_KEY` and falls back to the master key, and uses it only to encrypt stored values. `hash_token` in `litellm/proxy/_types.py` stores a virtual key as `sha256(key)`.
- The manifests render and apply as a dry run. `kubectl kustomize k8s/llm` renders, `kubectl apply --dry-run=client -f k8s/llm/gateway-db.yaml` and `kubectl apply --dry-run=client -k k8s/llm/gateway` accept the objects, and `uv run devops ci --only k8s --check` passes 90 cases.
- No merged change or open pull request did this work: a search of the pull requests for the issue and for the words LiteLLM and Postgres finds none. The open issues about virtual keys (#3685, #3066) need this database.

## Existing Tool Considered

CloudNativePG (open, maintained, already in the cluster) runs the database and generates its Secret. LiteLLM's own virtual keys, with its Prisma migrations, store the keys. The change builds no operator, no secret generator and no migration code. It deletes the `cloudnative-pg` entries of stack `chat` in `stack_lifecycle.py`, which move to stack `infra`. The issue text proposed a hand-written StatefulSet and a `CLUSTER_SECRETS` row for a generated password. CloudNativePG covers both, so the change does not build them.
