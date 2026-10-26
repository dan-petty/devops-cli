# Proposal

## Why

Issue #2322: cloudflared 2026.9.3 trusts eight eMudhra (emSign) intermediate certificates whose private keys are weak. A person who guesses a key can make a certificate for any host. Cloudflare fixed this in cloudflared 2026.10.2, which it builds with Go 1.27.3, and it asks every account that runs a tunnel to upgrade.

This repository pins cloudflared 2026.9.3 in two places. Deployment `cloudflared` runs the image with `--no-autoupdate`, so it never updates itself. `tools.lock` pins the binary that `devops install-tools --tool cloudflared` installs for `cloudflared access tcp`. No check stops a pin from going below the fixed release.

## What Changes

- Set the image of Deployment `cloudflared` in `k8s/cloudflared/deployment.yaml` to `cloudflare/cloudflared:2026.10.4`.
- Set `version`, each `url` and each `sha256` of the `cloudflared` entry in `src/devops_cli/tools_lock/tools.lock` to 2026.10.4.
- Add two invariant tests in `tests/test_k8s_cloudflared.py`. They fail when the image tag or the locked version goes below 2026.10.2, and when a platform `url` names another release than the locked `version`.
- The change carries a spec delta, because a manifest and the version that `devops install-tools` installs are observable. It creates the capability `cloudflared-release-pin`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

- `cloudflared-release-pin`: the cloudflared release of the tunnel Deployment and of `tools.lock` is 2026.10.2 or later.

### Modified Capabilities

None.

## Impact

- Manifest: `k8s/cloudflared/deployment.yaml`. Argo CD applies it after the merge.
- Tools lock: `src/devops_cli/tools_lock/tools.lock`.
- Tests: `tests/test_k8s_cloudflared.py`.
- Rollout: the Deployment has two replicas and the default rolling update, which allows no unavailable pod and one surge pod. A new pod must be ready before an old pod stops, so the tunnel stays connected. A connection that an old pod carries, such as a `cloudflared access tcp` session to the kube API, drops when that pod stops and reconnects.

## Feasibility

- Cloudflare's notice and its [blog post "8 eMudhra certificates are compromised"](https://blog.cloudflare.com/emudhra-certificate-compromise/) say that cloudflared before 2026.10.2 trusts the eight intermediates, and that 2026.10.2 fixes it.
- The GitHub releases of `cloudflare/cloudflared` list 2026.10.2 (2026-10-20), 2026.10.3 (2026-10-21) and 2026.10.4 (2026-10-26). The diff 2026.10.1...2026.10.4 shows Go 1.27.3 in `go.mod` and the Dockerfile and a new distroless base image. It holds no certificate code, so the rejection comes from Go 1.27.3, as the blog post says. No test here connects with a forged certificate.
- The only runtime change after 2026.10.3 is `VULN-176088` in `metrics/metrics.go`. It mounts an allowlist of debug endpoints and keeps `/metrics` and `/ready`, the paths that this Deployment's probes and Prometheus scrape use. The token reaches the container by the `TUNNEL_TOKEN` environment variable, not by an argument.
- Docker Hub holds `cloudflare/cloudflared:2026.10.4` for `amd64` and `arm64`.
- The `linux-amd64` build of 2026.10.4 runs and prints `cloudflared version 2026.10.4`.
- Each `sha256` in `tools.lock` equals the `digest` of its release asset. The `linux` values also equal the release notes. The release notes give each macOS value for the binary inside the `.tgz`: unpacking each archive and hashing `cloudflared` gives those values.
- The notice warns that the upgraded cloudflared rejects an HTTPS origin whose certificate chains to an affected intermediate. `devops cloudflare tunnel routes` shows that the tunnel has no HTTPS origin: one `tcp://` route to the kube API and `http://` routes to Traefik.

## Existing Tool Considered

The upstream cloudflared release and its official image cover the need. The change builds no code and deletes no internal code. The tests only check the pins.

Renovate is the open tool that keeps a pin current, and its `kubernetes` manager matches no file by default ([Renovate docs](https://docs.renovatebot.com/modules/manager/kubernetes/)). The follow-up in `tasks.md` covers it.
