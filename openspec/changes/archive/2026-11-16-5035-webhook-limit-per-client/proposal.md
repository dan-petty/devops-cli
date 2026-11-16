# Proposal: #5035

## Why
Cloudflare Access refuses deliveries of the repository hook with HTTP 403: on 2026-11-16, 41 of the newest 100 deliveries (20:49Z to 21:18Z). The Access IP list holds only 6 of the 9 hook ranges of GitHub (#5017). Owner decision 2 of 2026-11-12 (Option A) replaces the list with a Bypass for Everyone on the webhook path. Before the owner makes that change, the route must keep its own controls. Today the Traefik rate limit keys on the request host, so all senders share one bucket of 60 requests a minute. After the change, any sender could use up the bucket of GitHub. Closes #5035.

## What Changes
- The Middleware `devops/roadmap-service-rate-limit` keys its bucket on `Cf-Connecting-Ip` (`sourceCriterion.requestHeaderName`), so each client has its own bucket. The rate stays 60 a minute with a burst of 60.
- A gate check holds that only the tunnel reaches the Traefik `web` entrypoint from outside the cluster: the Service of Traefik stays `ClusterIP`, and the entrypoint opens no host or node port.
- `devops roadmap onboard` row 7 accepts a hook that sends each event that the Service takes and other events too (subset, not equality).
- A test holds each event of a GitHub consumer of the Service, and each webhook event of a batch key of a due-table row, to the events that row 7 requires of the hook.
- `docs/CLUSTER.md` setup step 6 names the Bypass for Everyone on the path, step 8 lets the hook send more events, and the Webhook route section names the key of the bucket.

## Capabilities
- `roadmap-service-webhooks`: MODIFIED the Traefik limit requirement; ADDED the tunnel reach requirement and the consumer events requirement.
- `roadmap-onboard`: MODIFIED the matching hook requirement.

## Impact
- Live: after the merge, Argo CD applies the new Middleware key. GitHub's deliveries get buckets of their own. Access still answers 403 until owner step O3 changes it.
- The HMAC check (401 before the body is read), the 413 cap and the alerts `RoadmapServiceWebhooksRejected` and `RoadmapServiceWebhookDeliveriesFailed` do not change. Their tests stay.
- No new dependency.

## Feasibility
- The live Middleware (`kubectl get middleware -n devops roadmap-service-rate-limit`) has `sourceCriterion.requestHost: true`: one bucket for `hooks.<domain>`.
- Traefik v3.7.17 runs in `kube-system`. Its `rateLimit` takes `sourceCriterion.requestHeaderName`, and `GetSourceExtractor` keys on the value of that header.
- The tunnel route of `*.<domain>` sends each request to `http://traefik.kube-system.svc.cluster.local:80` with no origin request settings (`devops cloudflare tunnel routes --json`). The Service of Traefik is `ClusterIP` with no host port.
- Cloudflare sets `CF-Connecting-IP` to the client address on each request from the edge to the origin, and a transform rule cannot change it.

## Existing Tool Considered
Traefik's own `rateLimit` middleware with `sourceCriterion.requestHeaderName`. No custom code. A Cloudflare rate-limit rule was not used: no OpenTofu under `tf/` manages Cloudflare, and a dashboard rule is not in git.
