# Design

## Decisions

### A dedicated Valkey for devops-cli's caches

The Service and the cluster jobs get their own Valkey, `valkey-devops`, in namespace `llm` beside the other two Valkeys, as the issue recommends.

- It evicts the least recently used key at its bound (`allkeys-lru`). Each key it holds is a cache entry that the next request rebuilds.
- Its perimeter admits only namespace `devops` on 6379, so no pod in `llm` writes the vectors that pick intake's duplicate shortlist, and no pod in `devops` reaches Open WebUI's state.
- It holds 96 MiB under a 128Mi limit, three quarters as the other Valkeys of `llm` do (#711). One embedding of `qwen3-embedding:0.6b` is about 20 KB of JSON, so it holds about 4,800, many times what a roadmap run embeds.

Rejected alternatives:

- **Admit namespace `devops` to the shared cache Valkey (`valkey`).** It runs with `--maxmemory-policy noeviction` because an evicted token revocation of Open WebUI makes a signed-out token valid again (`k8s/llm/valkey.yaml`). A cache that grows with each embedded text would fill it, and Valkey would then refuse Open WebUI's writes. One password would also let each side write the other's keys.
- **Valkey ACL users on the shared Valkey.** An ACL keeps the key spaces apart, but not the memory: the embeddings would still fill the bound that Open WebUI needs.
- **The run index (`valkey-runs`).** It keeps its data in an append-only file and evicts nothing, for runs that are the source of truth for every workstation. A cache there would fill it.
- **A Valkey in namespace `devops`.** It would need its own ingress rule in a namespace whose perimeter admits no ingress, its own Alloy scrape rule, and a third place for Valkey manifests. Namespace `llm` already holds the Valkeys, their image pins and their scrape path.

### The password reaches the pods as `valkey.password`

Secret `devops/devops-cli` gains `DEVOPS_CLI_VALKEY_PASSWORD`, the variable that `valkey.password` reads, so the pods need no new setting. Both Secrets take their value from one keyring-only entry, `valkey_devops_password`, because a workstation's own `valkey.password` belongs to the Valkey that its `valkey.url` names. The devops entry adopts the live value of `llm/valkey-devops-auth`, as `DEVOPS_CLI_AI_API_KEY` adopts the gateway key, and either entry generates the value on a first push, so `--stack devops` alone and `--stack llm` alone each work.

### Workstations

A workstation keeps its own `valkey.url`. The new Valkey has no NodePort, and the perimeter admits only namespace `devops`. A person who wants a workstation's intake to share it can reach it with `kubectl port-forward`, which no policy limits, and give its password as `valkey.password`; the change does not set that up.
