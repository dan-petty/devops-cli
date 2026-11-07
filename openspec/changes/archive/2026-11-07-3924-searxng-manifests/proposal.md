# Proposal

## Why

Issue #3924: the project has no search service of its own. Firecrawl, the only keyed provider, answers HTTP 402 (the credit is used up), and the DuckDuckGo fallback queries from the Service pod and has no second path. The owner asked on 2026-11-07 to run SearXNG on the cluster. The provider that calls it is merged and reads `search.searxng_url`. Upstream ships no Helm chart and no Kubernetes manifest (`searxng-docker` is archived; `container/docker-compose.yml` of the main repository is the upstream form), so this repository owns the manifests.

## What Changes

- `k8s/devops/searxng/`: ConfigMap `searxng-settings` (the `settings.yml`), Deployment `searxng` (image `docker.io/searxng/searxng:2026.10.23-629368e40` with the digest of its index, one replica, Pod Security `restricted`, user 977, read-only root, `emptyDir` at `/tmp` and `/var/cache/searxng`, probes on `/healthz`), Service `searxng` on 8080, NetworkPolicy `searxng-perimeter` (ingress only from `roadmap-service`; egress only DNS and public TCP 443) and NetworkPolicy `searxng-clients`. There is no Ingress.
- `k8s/devops/networkpolicy.yaml`: `devops-default-perimeter` skips the pod `searxng`.
- `k8s/devops/kustomization.yaml` and `MANIFESTS_BY_STACK["devops"]` list the new files.
- `src/devops_cli/k8s/cluster_secrets.py`: row `devops/searxng` (`SEARXNG_SECRET`, keyring-only `searxng_secret_key`, 64 hex generated, restarts `deployment/searxng`). A person runs the push command; the change creates no Secret.
- `k8s/argocd/apps/projects.yaml`: Secret `searxng` joins the orphaned-resource ignore list, as `crawl4ai` does.
- `.github/renovate.json`: a rule for the image whose pull request text tells the person to check the 14-day age of the tag and to refresh the engine names file.
- `k8s/README.md`: the table row, a section "SearXNG" (what it is, the pin and its bump steps, the license, the engines, the log, the limits) and the directory tree.
- `k8s/devops/configmap.example.yaml` already holds `search.searxng_url` (the provider item added it). The live ConfigMap has none on purpose, and this change applies nothing to the cluster.
- Tests: `tests/invariants/test_k8s_searxng.py` and its fixture `tests/fixtures/searxng/default_engine_names.txt`, `tests/commands/k8s/test_k8s_network_policies.py`, `tests/k8s/test_image_pins.py`, `tests/core/test_renovate_config.py`; and the existing tests that count the manifests, the keyring-only keys and the Secret rows.
- A manifest is observable, so the change carries a spec delta (new capability `searxng-service`).
- The change fits one pull request. The check of the network policies on the live cluster is the work of #3929.

## Capabilities

### New Capabilities

- `searxng-service`: How the SearXNG search service runs in namespace `devops`, which engines it keeps, who may call it and where it may connect.

### Modified Capabilities

None.

## Impact

- Manifests: `k8s/devops/searxng/*`, `k8s/devops/networkpolicy.yaml`, `k8s/devops/kustomization.yaml`, `k8s/argocd/apps/projects.yaml`.
- Code: `src/devops_cli/commands/k8s/stack_lifecycle.py` (`MANIFESTS_BY_STACK`), `src/devops_cli/k8s/cluster_secrets.py` (one row).
- Config: `.github/renovate.json`.
- Documents: `k8s/README.md`.
- Egress: the pod reaches public TCP 443. The issue states the egress, and the Crawl4AI egress was approved the same day. A person creates Secret `searxng` and sets `search.searxng_url` in the live ConfigMap; this change creates no Secret and applies nothing to the cluster.

## Feasibility

Checked on 2026-11-07 against the pinned image, with the digest `sha256:aecad882e86eeb022b76351c8dce4eb48d0cbb16a5f1691f77ea32c96d317502`, on a workstation with Docker:

- **User ID.** `id searxng` in the image gives uid 977, gid 977. `/etc/searxng` and `/usr/local/searxng` belong to that user.
- **Start under the `restricted` controls.** A container of the pinned digest ran as 977:977 with a read-only root, all capabilities dropped, `no-new-privileges`, the default seccomp profile, 768 MiB then 384 MiB of memory, 1 CPU, a writable `tmpfs` at `/tmp` and at `/var/cache/searxng`, and `settings.yml` mounted read-only as one file at `/etc/searxng/settings.yml`. `/healthz` answered 200 within 15 s. The log held no permission error; the entrypoint warns that `/var/cache/searxng` is owned by root. This is a test of the pod controls on a container host, not a start on the cluster. The cluster start is the first sync after the merge.
- **Server secret.** `searx/settings_defaults.py` reads `server.secret_key` from the variable `SEARXNG_SECRET`, and `webapp.py` refuses to start with the key `ultrasecretkey`. The settings file holds no secret.
- **Engine names.** The 352 engine names of `searx/settings.yml` in the image hold all ten kept names (`docker hub` has a space). They also hold `brave`, `braveapi`, `google`, `bing`, `startpage`, `mojeek` and `qwant`, which the settings do not keep. The engines call HTTPS only (the `http://` strings in the engine code are XML namespaces), so egress on 443 is enough.
- **JSON reply.** `GET /search?q=<term>&format=json` returned the keys `answers`, `corrections`, `infoboxes`, `query`, `results`, `suggestions` and `unresponsive_engines`.
- **Categories.** With no category, only `duckduckgo` answered (10 hits) and `wikipedia` gave an infobox with no result. With `categories=it`: `github`, `stackoverflow`, `askubuntu`, `superuser`, `mdn` and `docker hub`. With `science`: `arxiv`. With `general,it,science`, all of them in one reply (63 to 90 hits). `pypi` returned no hit for any query and no error.
- **Rate limits of the engines.** After about 30 queries within minutes from one address, `duckduckgo` answered `CAPTCHA` and `github` answered `Suspended: access denied`. The other engines kept answering. The cluster address may be limited the same way; the provider chain passes the search on when SearXNG returns no hit.
- **Memory and CPU.** The idle container used 114 MiB. 20 queries one after another peaked at 117 MiB and 23% of a CPU, and 10 queries at once peaked at 122 MiB and 80% of a CPU. So the limits are a request of 192 Mi and 50m, and a limit of 384 Mi and 1 CPU.
- **Not run.** The check that a `roadmap-service` pod reaches port 8080 and a pod without the label does not (the kube-router handling of the peer shape) needs the cluster and an applied manifest. This change applies nothing, so that check is the work of #3929.
- **Renovate.** The config was read, not run with `renovate --dry-run`: the `kubernetes` manager covers `k8s/**/*.yaml`, and the docker datasource bumps a `tag@digest` reference as one pin. Whether Renovate orders the date tags of SearXNG is not checked; the rule text asks the person to check the age.
- **Image pin resolution.** A test in `tests/k8s/test_image_pins.py` resolves a pin that names `docker.io`, a date tag and a digest.

The premise holds: the pod meets `restricted`, so the item is not returned.

## Existing Tool Considered

SearXNG (AGPL-3.0), used unmodified over HTTP, with `container/docker-compose.yml` of the main repository as the model. Rejected: a community Helm chart (Artifact Hub lists about 17, none official, the best has 4 stars, several lag the app by months); the archived `searxng-docker`; the SearXNG limiter with Valkey (it needs a policy change for `valkey-devops` and refuses plain machine clients; the NetworkPolicy replaces it); a Brave engine inside SearXNG (the key would force the whole settings file into a Secret, and Brave hits could not be told apart from other hits). The change deletes no internal code.
