# Proposal

## Why

Issue #3884: the project has no service that returns the text of a web page. `web_fetch_tool` was removed in v0.2.39, and `firecrawl_search` returns titles, URLs and descriptions only. The owner asked on 2026-11-07 to run Crawl4AI on the cluster. Upstream ships no Helm chart and no Kubernetes manifest, only a Dockerfile and a compose file, so this repository owns the manifests. The owner approved the egress for the refine and alternatives jobs on 2026-11-07.

## What Changes

- `k8s/devops/crawl4ai/`: Deployment `crawl4ai` (image `unclecode/crawl4ai:0.9.5` with the digest of its index, one replica, strategy `Recreate`, Pod Security `restricted`, read-only root, an `emptyDir` for each of the six upstream tmpfs paths, 1 Gi of memory-backed `/dev/shm`, probes on `/health`, memory limit 4 Gi), Service `crawl4ai` on 11235, NetworkPolicy `crawl4ai-perimeter` (ingress only from `roadmap-service`; egress only DNS and public TCP 80 and 443) and NetworkPolicy `roadmap-service-to-crawl4ai`. There is no Ingress.
- `k8s/devops/networkpolicy.yaml`: `devops-default-perimeter` skips the pod `crawl4ai`.
- `k8s/devops/kustomization.yaml` and `MANIFESTS_BY_STACK["devops"]` list the new files.
- `.github/workflows/ci.yml`: job `third-party-image-scan` scans the pinned digest with Trivy and only reports. `docs/SDLC.md` describes it.
- `k8s/README.md`: a section "Crawl4AI" (what it is, the pin, the advisory watch, how to read the log) and the directory tree.
- Tests: `tests/invariants/test_k8s_crawl4ai.py`, `tests/commands/k8s/test_k8s_network_policies.py`, `tests/k8s/test_image_pins.py`, `tests/invariants/test_workflow_contracts.py`.
- A manifest is observable, so the change carries a spec delta (new capability `crawl4ai-service`).
- The change fits one pull request. Secret `crawl4ai` and its table row are the work of #3882, and the client is the work of #3887.

## Capabilities

### New Capabilities

- `crawl4ai-service`: How the Crawl4AI page-text service runs in namespace `devops`, who may call it and where it may connect.

### Modified Capabilities

None.

## Impact

- Manifests: `k8s/devops/crawl4ai/*`, `k8s/devops/networkpolicy.yaml`, `k8s/devops/kustomization.yaml`.
- Code: `src/devops_cli/commands/k8s/stack_lifecycle.py` (`MANIFESTS_BY_STACK`).
- Workflow: `.github/workflows/ci.yml`.
- Documents: `k8s/README.md`, `docs/SDLC.md`.
- Egress: the pod reaches public TCP 80 and 443. A person approved this for refine and alternatives on 2026-11-07. A person creates Secret `crawl4ai`; this change creates no Secret and applies nothing to the cluster.

## Feasibility

Checked on 2026-11-07 against the pinned image, with the digest `sha256:0b05666882bfb67f45d559a5b827839c54127b74aedd723f8ab338a3571b5fc9`:

- **User ID.** The config blob of the amd64 manifest (read from Docker Hub) sets `User: appuser`, a name. The layer of `groupadd -r appuser && useradd -r appuser` holds `/etc/passwd` with `appuser:x:999:999`. So the pod sets `runAsUser: 999`, because `runAsNonRoot` cannot check a name.
- **Start under the `restricted` controls.** A container of the pinned digest ran on a workstation with user 999:999, a read-only root, all capabilities dropped, `no-new-privileges`, the default seccomp profile, 4 GiB of memory, 2 CPUs, 512 processes, 1 GiB of `/dev/shm`, and a writable `tmpfs` for each of the six paths (owner root, group 999, mode 2777, which is what an `emptyDir` with `fsGroup` gives). `/health` answered 200 within 45 s, and the log held no permission error. This is a test of the pod controls on a container host, not a start on the cluster. The cluster start is the first sync after the merge.
- **IPv4.** With `GUNICORN_BIND=0.0.0.0:11235`, gunicorn listened on `http://0.0.0.0:11235` and the container address answered over IPv4.
- **Token.** A request to `/md` without the token gave HTTP 401. With the bearer token it gave HTTP 200.
- **Response shape of `/md`.** A JSON object with `url`, `filter`, `query` (null), `cache`, `markdown` (string) and `success` (boolean).
- **In-app filter.** `/md` refused `http://169.254.169.254/`, `http://localhost:11235/`, `http://127.0.0.1:11235/` and the address of the container itself with HTTP 400 `URL blocked (SSRF protection)`, and `file:///etc/passwd` with HTTP 400. The NetworkPolicy is not tested here: it needs the cluster, and issue #3894 holds that live check.
- **Memory and CPU.** One idle container used about 498 MiB and 98 processes. One page of `en.wikipedia.org` peaked at 555 MiB and 119% CPU (112 processes), two at once at 621 MiB and 177% (138), four at once at 749 MiB and 204% (166). So the first limits (request 1 Gi, limit 4 Gi, CPU 2) hold, and four pages at once saturate two CPUs.
- **Renovate.** Read the config, not run with `renovate --dry-run`: `.github/renovate.json` sets the `kubernetes` manager to `k8s/**/*.y*ml`, and the Renovate docker datasource bumps a `tag@digest` reference as one pin.
- **Image pin resolution.** `tagged_image` takes the digest of a `tag@digest` reference, and a test in `tests/k8s/test_image_pins.py` resolves such a pin.

The premise holds: the pod meets `restricted`, so the item is not returned.

## Existing Tool Considered

Crawl4AI 0.9.5 (Apache-2.0), used unmodified, with the compose file of the project as the model for the limits and the writable paths. Rejected: self-hosted Firecrawl (AGPL-3.0, a heavier stack) and Kindly Web Search MCP (no release, no SSRF check, no authentication). Building our own fetcher was done once and removed. The change deletes no internal code.
