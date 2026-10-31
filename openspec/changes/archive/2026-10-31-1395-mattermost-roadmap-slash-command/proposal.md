# Proposal

## Why

Issue #1395 asks for a `/roadmap` slash command in Mattermost. Today no chat command shows the state of the in-cluster roadmap service, so operators must inspect pod logs or Prometheus metrics directly.

## What Changes

- Add `AuthorizationToken(scheme)` verifier to the webhook router.
- Add `application/x-www-form-urlencoded` body parser and synchronous responder support to the webhook router.
- Register `mattermost` provider with `WebhookExposure.CLUSTER` and `AuthorizationToken(scheme="Token")`.
- Add `mattermost.command_token` managed credential and cluster secret entry.
- Expose worker round execution status and lanes in `RepoWorker` and `ServiceManager`.
- Add `/roadmap` and `/roadmap status [repo]` command parsing and ephemeral replies.
- Increment `devops_cli_service_chat_commands_total` metric.
- Configure Mattermost `MM_SERVICESETTINGS_ALLOWEDUNTRUSTEDINTERNALCONNECTIONS` to permit connection to `roadmap-service.devops.svc.cluster.local`.
- Add network policies for Mattermost egress to roadmap-service and roadmap-service ingress from Mattermost.
- Update the Roadmap service section in `k8s/README.md`.

## Capabilities

### New Capabilities
- `mattermost-roadmap-slash-command`: Enables Mattermost to invoke the `/roadmap` slash command against the in-cluster roadmap service webhook router to show repository and lane status.

### Modified Capabilities
None.

## Impact

- Affected code: `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/server/service.py`, `src/devops_cli/config/env.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/k8s/cluster_secrets.py`, `src/devops_cli/lang/en/messages.py`.
- Manifests: `k8s/mattermost/mattermost.yaml`, `k8s/mattermost/networkpolicy.yaml`, `k8s/devops/roadmap-service/networkpolicy.yaml`.
- Documentation: `k8s/README.md`.
- Fits in one pull request.

## Feasibility

Confirmed against the real system:
- Starlette `Request.form()` parses `application/x-www-form-urlencoded` payloads from Mattermost slash command requests.
- Mattermost slash commands send an `Authorization: Token <token>` header when configured.
- The webhook router `AuthorizationToken` verifier checks authorization headers with `get_authorization_scheme_param` and `secrets.compare_digest`.
- In-cluster service address `roadmap-service.devops.svc.cluster.local:8000` is routable when allowed by `MM_SERVICESETTINGS_ALLOWEDUNTRUSTEDINTERNALCONNECTIONS` and network policies.
- Roadmap service remains at `replicas: 0` per Decision D1.

## Existing Tool Considered

Mattermost built-in slash command integrations and webhook router in `src/devops_cli/server/routes/webhooks.py`. The webhook router already handles rate limits, body size caps, exposure gating, and Prometheus metrics. Building on the existing router reuses these controls and eliminates external dependencies.
