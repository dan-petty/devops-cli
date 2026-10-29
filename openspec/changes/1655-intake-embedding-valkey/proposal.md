# Proposal

## Why

Issue #1655: the roadmap Service and the cluster jobs run intake, and intake embeds the comparison set (the open items and the issues closed as not planned) and each checked candidate on every run. Each Service round and each cluster job is a new process, so the in-memory cache of `EmbeddingsEngine` starts empty, and a roadmap that did not change costs the same embedding requests on every round. The embedder already has a Valkey tier, but no Valkey in the cluster serves namespace `devops`: the ConfigMap names none, so `valkey.url` falls back to `valkey://localhost:6379/0`, which no pod serves.

## What Changes

- A new Valkey in namespace `llm`, `valkey-devops` (`k8s/llm/valkey-devops.yaml`), holds devops-cli's caches for the Service and the cluster jobs: the embeddings that `EmbeddingsEngine` writes and the threat-intelligence reads, the two users of `valkey.url` in a pod. It requires a password from Secret `llm/valkey-devops-auth`, keeps at most 96 MiB of data under a 128Mi limit, writes no RDB or AOF, and at the bound evicts the least recently used key. A redis-exporter sidecar serves its metrics.
- Its policy `valkey-devops-perimeter` admits namespace `devops` on TCP 6379 and namespace `monitoring` on 9121, and allows no egress. `llm-default-perimeter` leaves its pods out, and `devops-default-perimeter` lets namespace `devops` reach namespace `llm` on 6379 beside the gateway's 4000.
- The devops ConfigMap template sets `valkey.url` to `valkey://valkey-devops.llm.svc.cluster.local:6379/0` and holds no password.
- The cluster secret table gains `llm/valkey-devops-auth` (`password`) and the key `DEVOPS_CLI_VALKEY_PASSWORD` of `devops/devops-cli`, the variable of `valkey.password`. Both come from the keyring-only entry `valkey_devops_password`. The devops key adopts the live value of `llm/valkey-devops-auth` when the keyring lacks it, and either entry generates 64 hex on a first push.
- `deploy-stack --stack llm` applies the new manifest, and the Argo CD project ignores Secret `valkey-devops-auth` as an orphan, as it ignores the other pushed Secrets.
- `k8s/README.md` lists the two Secret rows, the command to ping the new Valkey, and its perimeter and memory bound.
- A manifest and a policy are observable, so the change carries a delta in `llm-valkey`: the noeviction requirement now names the cache Valkey and the run index, and new requirements cover the devops cache Valkey and intake's embeddings across runs.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `llm-valkey`: the noeviction rule names the two Valkeys that must not evict, and devops-cli's cache Valkey evicts, requires its password, admits only namespace `devops`, and keeps intake's embeddings across runs.

## Impact

- `k8s/llm/valkey-devops.yaml` (new), `k8s/llm/kustomization.yaml`, `k8s/llm/networkpolicy.yaml`, `k8s/devops/networkpolicy.yaml`, `k8s/devops/configmap.example.yaml`, `k8s/argocd/apps/projects.yaml`, `k8s/README.md`.
- `src/devops_cli/k8s/cluster_secrets.py`, `src/devops_cli/commands/k8s/stack_lifecycle.py`.
- Tests: `tests/test_k8s_valkey_stack.py`, `tests/test_roadmap_intake.py`, and the tests that pin the secret table, the policies, the deploy-stack manifests and the Helm-namespace exemptions.

## Feasibility

Checked on `origin/main` f9493fa4 (2026-10-29):

- Intake embeds through `GatewayIntakeModel._embedder`, an `EmbeddingsEngine` with the default Valkey tier, which `configured_cache_tier(load_settings())` builds from `valkey.url` and `valkey.password` (`src/devops_cli/roadmap/intake_model.py`, `src/devops_cli/ai/rag/embeddings.py`, `src/devops_cli/valkey/cache.py`). The tier keeps each vector for 7 days (`DEFAULT_VALKEY_EMBEDDING_TTL_SECONDS`).
- `valkey.password` is a managed credential whose variable is `DEVOPS_CLI_VALKEY_PASSWORD` (`src/devops_cli/config/env.py`), and the Service and the CronJob load Secret `devops-cli` with `envFrom`.
- The issue's premise about the shared Valkey changed: `k8s/llm/valkey.yaml` now requires the password of `llm/valkey-auth` (#1654), and only Open WebUI reaches it. It runs with `--maxmemory-policy noeviction`, because Open WebUI keeps its session pools and token revocations there, so it can't hold a cache that must evict.
- Measured offline with the new test, which counts the gateway's `/v1/embeddings` requests at the HTTP edge (`stub_web`): two plan runs over the same two settled items and one candidate, each with a new `EmbeddingsEngine`, send `[1, 1]` requests with no Valkey and `[1, 0]` with one Valkey shared by the runs. A run sends one batch request for all its texts while they fit one batch, so without the cache each round costs as many batch requests as the roadmap fills; with it, a round over settled items costs none.
- #1562 and #1647 are closed, so the Service can run again as the GitHub App.

## Existing Tool Considered

Valkey, the project's key-value store, with its own `requirepass` and `allkeys-lru` eviction, and the embedder's existing Valkey tier. The change adds a manifest, a policy rule, a ConfigMap key and two Secret entries, and builds no code. It deletes nothing: the client side already exists.
