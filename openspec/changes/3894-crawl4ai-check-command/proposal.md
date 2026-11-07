# Proposal

## Why

Crawl4AI had critical SSRF and RCE bugs in 0.8.x and 0.9.0, and six more advisories were fixed on 2026-10-15. Two points are open: whether `POST /md` and `GET /llm/{url}` run the same destination check as `/html`, `/screenshot` and `/pdf`, and whether the filter blocks cluster names such as `*.svc`. Nothing in the repository fails if a later digest bump removes one of these controls (#3894).

A live pytest test cannot cover this. The test floor fakes the network and the keyring, and it forbids a skip on the state of the host. So the check is a command, `devops k8s crawl4ai-check`, that a person runs at each digest bump. The owner chose this shape on 2026-11-07. The manual run with `CRAWL4AI_ALLOW_INTERNAL_URLS=true` and the redirect case are tracked in #4018 and #4019.

## What Changes

- Add `devops k8s crawl4ai-check` in `src/devops_cli/commands/k8s/crawl4ai_check.py`. It reads the token from the keyring, forwards a local port to Service `crawl4ai`, sends each of five routes to each of five internal targets, sends one request per route without the token, and prints one report row for each request. It exits 1 when a target is served, when a request without the token is not refused, or when the pod below reaches a blocked destination.
- Add `src/devops_cli/k8s/crawl4ai_check.py` with the route and target matrix, the rule for a refusal (`is_refusal`), and `CRAWL4AI_IMAGE`, the image the command was written for.
- Add `src/devops_cli/k8s/service_probe.py`, shared with #3929: `probe_from_pod` starts a throwaway pod with the labels of a workload, probes each destination from it with `kubectl exec`, and deletes it. The pod meets Pod Security `restricted`, and it never becomes ready, so the Service sends it no traffic. The module is not specific to Crawl4AI, so the SearXNG check of #3929 reuses it.
- Add `ServiceProbeError` to `src/devops_cli/exceptions/k8s.py`, the messages and help texts of the command, and the `--dry-run` request plan.
- Change the `k8s` row of `devops ci`: the check of `tests/gate/k8s_checks/devops_runtime.py` compares the full image of Deployment `crawl4ai` with `CRAWL4AI_IMAGE`, so a bump of the digest fails the row until a person runs the command against the new image.
- The command is a new command with a request plan, so the change carries a spec delta (`k8s-crawl4ai-check`) and `skip_specs` is false. The command is not an MCP tool: it starts a pod, so it is not read-only, and the MCP exposure table lists no `k8s` command.
- Document the command in the Crawl4AI section of `k8s/README.md` and regenerate the command documents.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `k8s-crawl4ai-check`: The route and target matrix, the refusal rule, the check without the token, the throwaway pod, the keyring token, the pinned image and the report.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/commands/k8s/crawl4ai_check.py` (new), `src/devops_cli/commands/k8s/__init__.py`, `src/devops_cli/k8s/crawl4ai_check.py` (new), `src/devops_cli/k8s/service_probe.py` (new), `src/devops_cli/exceptions/k8s.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/config/defaults.py`
- Tests: `tests/k8s/test_service_probe.py`, `tests/k8s/test_crawl4ai_check.py`, `tests/commands/k8s/test_k8s_crawl4ai_check.py`, `tests/support/kubectl_calls.py`, `tests/gate/k8s_checks/devops_runtime.py`
- Documents: `k8s/README.md`, `docs/commands/k8s.md`, `docs/CLI_REFERENCE.md`, `README.md`

## Feasibility

The premise is that a command can reach the service, send the requests, and test the NetworkPolicy from a pod. I checked each part against the repository and the tools on 2026-11-07:

- **No command exists.** `git grep -n crawl4ai-check -- src tests docs k8s README.md` finds no hit in the base commit. The manifests (#3884) are merged, and #4018 and #4019 hold the two deferred cases.
- **The pinned image.** `k8s/devops/crawl4ai/deployment.yaml:50` pins `unclecode/crawl4ai:0.9.5@sha256:0b05666882bfb67f45d559a5b827839c54127b74aedd723f8ab338a3571b5fc9`. `CRAWL4AI_IMAGE` holds the same value.
- **The refusal.** `k8s/README.md` (Crawl4AI, "The log") records a blocked request as `URL blocked (SSRF protection)` with HTTP 400. By hand on 2026-11-07: `POST /md` without the token gave 401, with the token a public page succeeded, and the name of Service `roadmap-service` gave `{"detail":"URL blocked (SSRF protection): URL blocked"}`. So a refusal body is a JSON object with the one key `detail`, and the rule accepts 400 and 403 because a second source reports 403.
- **The token.** `get_crawl4ai_api_token` in `src/devops_cli/config/settings.py` reads the credential `crawl4ai.api_token`, which the keyring stores as `crawl4ai_api_token`. `src/devops_cli/ai/page_text.py` already sends `POST /md` with `Authorization: Bearer <token>`, so the request shape is known.
- **The forward.** `kubectl port-forward` is not subject to NetworkPolicy, and Service `crawl4ai` listens on 11235 (`k8s/devops/crawl4ai/service.yaml`). `spawn_detached` and `terminate_process_group` of `src/devops_cli/core/process.py` start and stop it. `http_client(EgressLevel.LOOPBACK)` (`src/devops_cli/http/entry.py`) dials only the forward.
- **The pod.** Namespace `devops` enforces Pod Security `restricted` (`k8s/namespaces.yaml`), so a plain `kubectl run` is refused. `kubectl run` of client v1.37.1 has the flags `--image`, `--restart` and `--overrides`, which set the security context. `NetworkPolicy crawl4ai-perimeter` selects the pod by the label `app.kubernetes.io/name: crawl4ai`, and Service `crawl4ai` selects it by the same label. A pod with that label that becomes ready would join the endpoints of the Service and could take real fetches. So the pod gets a readiness probe that always fails (`exec` of `false`), and a test holds that.
- **The probe image.** The pod needs a shell and a TCP client in a small public image pinned by digest. Group 1 chooses the image and checks its client applet in its documentation. No private registry is used.
- **Not run against the cluster.** The Verify stage runs the command only against the fakes. The Publish stage runs it once through a port-forward and puts the result for each route and target role in a pull request comment.

## Existing Tool Considered

`kubectl` (Apache-2.0) covers the port-forward and the throwaway pod, and `devops_cli.http.entry` covers the requests. Neither knows the Crawl4AI route matrix, the refusal rule or the report. No open, maintained scanner tests a running Crawl4AI service, and an offline NetworkPolicy checker reads the policy document only (`tests/commands/k8s/test_k8s_network_policies.py` already does that). So the change builds one command and one shared probe module. Cost: about 400 lines, an estimated 70k tokens to write, an estimated 10k tokens for each later fix, an estimated 5k tokens a year to keep, and one day of elapsed time. The change deletes no internal code.

## Dependencies

None. The manifests (#3884) are merged.
