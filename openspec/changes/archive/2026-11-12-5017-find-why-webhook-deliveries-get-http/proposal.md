# Proposal: #5017

## Why
GitHub records HTTP 403 with the header `Server: cloudflare` for many deliveries of the repository hook (#5017): 22 of the 60 newest on 2026-11-12 07:56-08:09Z, and 39 of the 100 newest at 10:04-10:17Z. GitHub does not send a failed delivery again. The alert `RoadmapServiceWebhooksRejected` counts only the refusals of the webhook route behind Traefik, so it cannot see a refusal at the Cloudflare edge.

## What Changes
- The cause is a Cloudflare Access policy at the edge, not a file of the repository (Feasibility). A change of an Access policy is owner decision O3, so this change does not change it. The evidence is in a comment on #5017.
- The metrics row of the Service reads the active hooks of its repository and the newest 100 deliveries of each one, and sets the gauge `devops_cli_service_webhook_delivery_failures` by `repo` and `code` to the deliveries of the last 15 minutes with no 2xx answer (`src/devops_cli/github/hook_deliveries.py`). A failed read fails the row.
- Each installation token of the App also asks for `repository_hooks: read` (ADR 0015 amended). The App has read and write on every repository permission, so the installation grants it.
- The alert `RoadmapServiceWebhookDeliveriesFailed` in the group `roadmap-service-webhooks` warns when more than 5 deliveries of one repository failed in 15 minutes, with promtool unit tests.
- The panel "Service Failed Webhook Deliveries" of the row "Roadmap Service" of the `devops-cli` dashboard charts the gauge by repository and code.
- `k8s/README.md` names the edge check: setup steps 1, 6 and 12, the Webhook route section and the Alerts table.
- The behavior of the Service and a manifest change, so the change has a spec delta.
- The change fits one pull request.

## Capabilities
- `roadmap-service-alerts`: the metrics row counts the failed deliveries of the hooks, and the alert warns on them.

## Impact
- Each metrics round of a repository sends one more request for the hooks and one for each active hook: about 10 requests an hour for a repository with one hook, within `service.github_requests_per_hour`. An unchanged page of deliveries is rare, because each delivery adds one.
- An installation that does not grant Webhooks read refuses each token with HTTP 422. The owner checks the grant of the installation before the merge.
- The token can read the configuration of each hook, its URL included but not its secret, and the deliveries of each hook.

## Feasibility
Confirmed on 2026-11-12 with read-only commands:
- `uv run devops gh api 'repos/dan-petty/devops-cli/hooks/692250036/deliveries?per_page=100'`: 39 of the 100 newest deliveries got 403, from all events, mixed with 202 answers in the same seconds.
- `uv run devops gh api repos/dan-petty/devops-cli/hooks/692250036/deliveries/<id>` for 6 of them: each answer has `Cf-Access-Domain: hooks.<domain>`, the same `Cf-Access-Aud`, and the page `Error ・ Cloudflare Access`. An accepted delivery has no `Cf-Access-*` header and carries `X-Devops-Version` from the Service.
- `devops cloudflare access status --json` and `devops cloudflare access policies <app-id>`: the application of `hooks.<domain>/webhooks/github` has the Bypass policy `gh-hooks-public-ips` with 6 GitHub ranges and no Allow policy.
- `uv run devops gh api meta --jq .hooks` gives 9 ranges: `9.234.98.160/28`, `9.234.98.176/28` and `9.234.106.48/28` are not in the policy.
- No manifest, OpenTofu file or setting holds the ranges: a person made the policy in the dashboard.
- GitHub ([About GitHub's IP addresses](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-githubs-ip-addresses)): "We make changes to our IP addresses from time to time" and "We do not recommend allowing by IP address".
- The GitHub REST API lists the deliveries of a repository hook with the permission Webhooks (read) (`repository_hooks` in the token request).

## Existing Tool Considered
The GitHub hook deliveries API (`GET /repos/{owner}/{repo}/hooks/{hook_id}/deliveries`), read through `gh api`, and the Service's Prometheus gauges with a Prometheus alert rule. No new tool. The change deletes no internal code.
