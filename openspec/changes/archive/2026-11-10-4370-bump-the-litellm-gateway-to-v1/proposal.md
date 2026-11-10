# Proposal

## Why

Issue #4370: the gateway image `ghcr.io/berriai/litellm:v1.103.0` has two critical advisories, and the gateway is reachable from outside the cluster through the tunnel.

- GHSA-7hp6-4w63-5g45 (critical, CVSS 9.9, published 2026-09-30): the proxy seals secrets and mints session tokens with one key. An internal user gets a forged admin token, becomes proxy admin and runs commands through the MCP stdio endpoint. The vulnerable range `>= 1.103.0, < 1.103.1` holds our version.
- GHSA-w4c7-34wj-hqm8 (critical, CVSS 10.0, published 2026-10-27): an unauthenticated request makes the proxy read a local file and send it to an attacker URL, which leaks `LITELLM_MASTER_KEY`. The advisory limits it to a proxy with an Enterprise licence. This repository sets no licence, so the gateway is probably not affected. The vulnerable range `< 1.103.10` names our line.

## What Changes

- Set the image tag in `k8s/llm/gateway/deployment.yaml` to `v1.103.10`, the newest patch release of the 1.103 line. It holds both fixes.
- Add a test that fails when the pinned release is below the release that holds both fixes for its line.
- Update the comment of `k8s/llm/gateway/config.yaml` and the paragraph of `k8s/README.md` about the cost map: the map of v1.103.10 lists both Claude 5.5 models.
- The configuration keys of `k8s/llm/gateway/config.yaml` stay as they are (see Feasibility).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The change moves an image tag.

## Impact

- `k8s/llm/gateway/deployment.yaml`, `k8s/llm/gateway/config.yaml`, `k8s/README.md`, `tests/ai/benchmark/test_k8s_llm_gateway.py`.
- After the merge, Argo CD syncs the Deployment. The gateway pod is replaced (the Deployment strategy is `RollingUpdate` with one replica, so the old pod serves until the new pod is ready). The pull request comment lists the checks.

## Feasibility

Read on 2026-11-10.

- Advisories: `https://api.github.com/repos/BerriAI/litellm/security-advisories` lists GHSA-7hp6-4w63-5g45 with the patched versions 1.100.4, 1.101.3, 1.102.2, 1.103.1 and 1.104.0rc2, and GHSA-w4c7-34wj-hqm8 with 1.103.10, 1.104.8, 1.105.6 and 1.106.5. The global advisory database (`/advisories/GHSA-w4c7-34wj-hqm8`) returns "Not Found", so the repository endpoint is the source.
- Releases: `/repos/BerriAI/litellm/releases` lists v1.103.1 (2026-09-30), v1.103.10 (2026-10-27 19:55 UTC) as the newest of the 1.103 line, and v1.108.4 (2026-11-09) as the latest. Tags v1.103.11 and later of the line do not exist. v1.103.10 is 14 days old.
- Image: `ghcr.io/berriai/litellm:v1.103.10` resolves to the index digest `sha256:99ad434a180d21b9c4500cb22a31c8c66e5e041a651df8819adee5c957521ea6`, read from the registry API (`/v2/berriai/litellm/manifests/v1.103.10`, header `docker-content-digest`) with an anonymous pull token. The same read for `v1.103.0` gives `sha256:bd089afdcd35b894b14a93f9743cdc8b591f82da1a38dd43a010a7b0c9de5fd7`, which equals the `imageID` of the running pod, so the method reads the real digest. The manifests of this repository pin a tag and no digest, and Renovate pins digests for GitHub Actions only, so the tag is the pin.
- Configuration: the wheels `litellm==1.103.0` and `litellm==1.103.10` were unpacked into new scratch directories and compared. Every key of `k8s/llm/gateway/config.yaml` still occurs in the source: `litellm_settings` (`callbacks`, `require_auth_for_metrics_endpoint`, `enable_end_user_cost_tracking_prometheus_only`, `drop_params`, `telemetry`, `sse_keepalive_ping_interval_seconds`), `router_settings` (`routing_strategy`, `routing_groups`, `num_retries`, `allowed_fails`, `cooldown_time`, `timeout`, `enable_pre_call_checks`, `fallbacks`) and `general_settings` (`master_key`, `cancel_on_disconnect`, `store_model_in_db`, `proxy_batch_write_at`, `pass_through_endpoints`). The type file `litellm/types/passthrough_endpoints/pass_through_endpoints.py` is identical in both wheels, so `path`, `target`, `methods`, `auth`, `forward_headers`, `include_subpath` and `headers` of the Jev route `/v1/systemone` (#4300) load as before. `litellm/types/integrations/prometheus.py` is identical, so the metric names and labels of the dashboards do not change. The headers `x-litellm-model-name` and `x-litellm-model-api-base` are still set in `common_request_processing.py`.
- Database: `litellm-proxy-extras` goes from 0.4.100 to 0.4.100.post1. It adds no migration. It changes the SQL of two applied migrations (`20260823000000_add_spend_logs_api_key_starttime_index` and `20260831120001_spend_logs_litellm_call_id_index`) to `SELECT 1;` and filters the two SpendLogs indexes out of the drift script. A start with `ENFORCE_PRISMA_MIGRATION_CHECK` on runs `prisma migrate deploy`. Not verified: whether Prisma refuses an applied migration whose checksum changed. A failed start leaves the old pod serving (see Impact).
- Behaviour changes between 1.103.0 and 1.103.10 (release notes, `compare` pages and a source diff): 1.103.1 fixes the salt-key advisory (bearer tokens are sealed with an extra authenticated prefix); 1.103.3 enforces the migration check by default (this deployment already sets it); 1.103.7 backports batch cost and pricing fixes (marked as a breaking change by the project, `fix(batches)!`); 1.103.8 removes one root certificate from the bundle and changes the image signing key; 1.103.10 keeps fewer fields in the failure log of a rejected request. The cost map of v1.103.10 lists `claude-sonnet-5-5` and `claude-haiku-5-5` with `supports_sampling_params: false`, and changes the Gemini 3.8 Flash entry (`supports_sampling_params: false`, a search quota). The groups set their prices and drop the sampling parameters themselves, so the change is not expected to alter a request.
- Later lines: v1.104.8, v1.105.6 and v1.106.5 hold the second fix too, and each adds a minor release of changes. The 1.103 line has the smallest step, so no later line is used.

## Existing Tool Considered

Renovate manages this pin, but it opens a pull request for the newest version only, and no pull request for this image is open. No tool is built. The test over the pinned release is a small guard so a pin that goes below the fixed release fails the check.
