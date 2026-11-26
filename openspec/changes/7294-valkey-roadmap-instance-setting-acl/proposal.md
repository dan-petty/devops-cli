# Proposal: #7294

## Why

The brain index (#4676) needs a store that keeps its data and has one ACL user for each role. No `valkey-roadmap` instance exists in the cluster, and its item #4563 also moves the request budget, the GraphQL hold, the halt and the delivery ids, so the index waits for parts that it does not use. The owner split three parts out of #4563 into #7294 on 2026-11-26: the instance, the setting of its URL and its ACL users. This change builds these three parts and nothing else.

## What Changes

- The folder `k8s/devops/valkey-roadmap` builds the store `valkey-roadmap` of namespace `devops` from the shared Valkey base of dan-petty/infra at the release tag v0.24.1, with the components `valkey-persistence`, `valkey-exporter` and `valkey-acl`. The repository holds no copy of the base and no Deployment of its own. `k8s/devops/kustomization.yaml` lists the folder, and deploy-stack applies it as a kustomization.
- The store keeps an append-only file with `appendfsync everysec` on a 2Gi `local-path` claim and evicts no key (`noeviction`). The pod stays off the control-plane node.
- The policies of the base admit only the pods of namespace `devops` with the label `valkey-client: "true"` on TCP 6379, and namespace `monitoring` on the exporter port 9121. The pod gets no egress: the default perimeter of namespace `devops` no longer selects it.
- The Secret table gets the row `devops/valkey-roadmap-auth`: one generated password for each of the 3 users `brain`, `agent` and `metrics`, and the derived aclfile `users.acl`. The aclfile turns the user `default` off. `brain` reads and writes `roadmap:v1:brain-*`. `agent` only reads these keys. `metrics` holds the 9 commands of an exporter scrape and no key.
- The settings get `roadmap.state.url` and `roadmap.state.username`, and the credential `roadmap.state.password`. `roadmap_state_tier()` gives the one client tier of the process over that store, apart from the cache tier. A reader fails soft.
- `k8s/devops/configmap.example.yaml` names the URL of the store. No pod gets a user or a password, and no code calls the accessor: #4676 adds the first client.
- The change fits one pull request.
- The change alters manifests, settings and a Secret row, which a consumer observes, so it carries spec deltas.

## Capabilities

### New Capabilities

- `roadmap-state/store`: the instance `valkey-roadmap`, its settings, its network policies, its ACL users and its Secret row.
- `roadmap-state/client`: the settings that name the store and its user, and the one tier of a process that sends them and fails soft.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/k8s/cluster_secrets.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/env.py`, `src/devops_cli/valkey/cache.py`, `src/devops_cli/commands/k8s/stack_lifecycle.py`.
- Manifests: `k8s/devops/valkey-roadmap/`, `k8s/devops/kustomization.yaml`, `k8s/devops/networkpolicy.yaml`, `k8s/devops/configmap.example.yaml`.
- Gate: `tests/gate/k8s_checks/devops_runtime.py`, `tests/gate/k8s_render.py`.
- Documents: `k8s/README.md`, `docs/CLUSTER.md`, `docs/SERVICE_PATTERNS.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`.
- A build of `k8s/devops` now fetches the base from github.com. The `k8s` row of `devops ci` makes 3 such builds and takes about 17 seconds more.
- A person pushes the new Secret before the merge. The pod of the store does not start while the key `users.acl` is missing.
- The scrape of the exporter needs TCP 9121 to namespace `devops` in the egress perimeter of namespace `monitoring`, which the environment repository holds.

## Feasibility

- The base renders with remote pins. `kubectl kustomize k8s/devops/valkey-roadmap` (kubectl v1.37.3, Kustomize v5.8.1) exits 0 in about 6 seconds and gives 7 objects: 1 ConfigMap, 1 Service, 1 PersistentVolumeClaim, 1 Deployment and 3 NetworkPolicies. `kubectl kustomize k8s/devops` and `kubectl kustomize k8s/overlays/homelab/devops` exit 0 with these objects.
- The base supports a default user that is off. The README of `k8s/bases/valkey` at v0.24.1 says: "Valkey ignores `requirepass` when it reads an aclfile. Thus the file must define the user `default`: `user default on >PASSWORD ~* &* +@all` with the password of `valkey-auth`, or `user default off`." It also says: "With `user default off`, give the exporter a user of its own: patch the variables `REDIS_USER` and `REDIS_PASSWORD` of the container `exporter`."
- A throwaway pod on the workstation proved the build. It ran the command of the rendered Deployment with the image `docker.io/valkey/valkey:9.2.1-alpine` of the base, the `valkey.conf` of this change, an aclfile of the template with throwaway passwords, and the exporter `ghcr.io/oliver006/redis_exporter:v1.99.0` of the component. Valkey started with `requirepass ""` and the aclfile. A connection with no user got `NOAUTH Authentication required.`. `brain` wrote a hash at `roadmap:v1:brain-item:o/n:1` and got `NOPERM No permissions to access a key` on `roadmap:v1:window:o/n`. `agent` read the hash and got `NOPERM User agent has no permissions to run the 'hset' command` on a write.
- The count of the commands of a scrape is 9. With a `metrics` user that held no command, `ACL LOG` named each refused command, and the test added it until two scrapes gave an empty `ACL LOG`: `info`, `config|get`, `latency|latest`, `latency|histogram`, `slowlog|len`, `slowlog|get`, `commandlog|len`, `command|info` and `client|setname`. `INFO commandstats` showed no call of `dbsize`, `client|list`, `memory|usage` or `ping` by the exporter, which the aclfile of `valkey-devops` holds. With the 9 commands, the exporter gave `redis_up 1` and wrote no error line.
- Renovate updates the pins. `.github/renovate.json` extends `github>dan-petty/infra//renovate/base`, which extends `config:recommended`, so the `kustomize` manager reads each `kustomization.yaml`. The rule that turns off the dependencies of `k8s/**` leaves out `k8s/devops/**`. The fixture `tests/renovate/k8s/overlays/example/kustomization.yaml` of dan-petty/infra holds a component pin of the same form, and the CI job "Renovate presets" of that repository checks that Renovate reads it with the base preset.
- The CI row can fetch the base. The job `static` of `.github/workflows/ci.yml` runs `uv run devops ci --check --no-cache --skip test,outdated,actionlint` on a GitHub-hosted runner, with no network limit. `uv run devops ci --check --only k8s` passes on the branch with 273 cases.
- The existing tier fits. `src/devops_cli/valkey/cache.py` holds `ValkeyCacheTier`, whose `_send` gives None for a failed command, and the breaker of pybreaker. `shared_cache_tier()` shows the form of one tier for each process.

## Existing Tool Considered

- The Valkey base `k8s/bases/valkey` of dan-petty/infra and its components `valkey-acl`, `valkey-exporter` and `valkey-persistence`, pinned at a release tag that Renovate updates (ADR 0032 section 3). The change uses them through Kustomize and copies none of them.
- The official chart valkey-io/valkey-helm does not fit: the README of the base records that Argo CD here runs Kustomize with no `--enable-helm`, and that the NetworkPolicy of the chart has both types.
- Valkey ACL with an aclfile, valkey-py through the existing `ValkeyClient` and `ValkeyCacheTier`, pybreaker, and `devops k8s push-secrets` for the passwords. The change adds no dependency.
- The change deletes no internal code. It moves the state of the one cache tier of a process from three module variables into the class `_ProcessTier`, which the two tiers share.
