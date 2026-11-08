# Proposal

## Why

Nothing in the repository fails when a later SearXNG digest bump changes one of three points (#3929). First, the categories in which the kept engines answer. Second, what the service does with a query that starts with `!`: a redirect, or the choice of an engine that the ConfigMap leaves off. Third, the NetworkPolicy peers of the service: which pods reach port 8080, and where the SearXNG pod can connect.

A live pytest test cannot cover this. The test floor fakes the network and forbids a skip on the state of the host. The owner chose on 2026-11-07 a `devops k8s` command, in the shape of `devops k8s crawl4ai-check` (#3894, merged). A person runs the command at each digest bump. The same item replaces the hand-made search reply fixture with a reply of the pinned image.

## What Changes

- Add `devops k8s searxng-check` in `src/devops_cli/commands/k8s/searxng_check.py`. It forwards a local port to Service `searxng`, sends six search requests, tries three connects from throwaway pods, and prints one report row for each. It exits 1 when a request has a problem or a pod reaches a destination that the policy must block.
- Add `src/devops_cli/k8s/searxng_check.py` with the request rows, the judgment of a reply (`reply_problems`), the list of engines that must stay off, and `SEARXNG_IMAGE`, the image that the command was written for.
- Reuse `src/devops_cli/k8s/service_probe.py` (`forward_service`, `probe_from_pod`, `plan_probe_from_pod`, `service_cluster_ip`). The change adds no second copy of the forward or of the pod code.
- The six requests are `GET /search` with `format=json`, and the client follows no redirect:
  - `json-general`, `json-it` and `json-science`: a plain query in each category of `DEFAULT_SEARXNG_CATEGORIES`. The reply must hold the seven keys `answers`, `corrections`, `infoboxes`, `query`, `results`, `suggestions` and `unresponsive_engines`, `unresponsive_engines` must be a list, `results` must hold a hit, and no engine of the list that must stay off may appear in `results` or in `unresponsive_engines`.
  - `bang-off-engine`: the query `!google ...`. The status must be 200 and the reply must hold no hit of `google`.
  - `bang-external`: the query `!!g ...`. SearXNG answers an external bang with a redirect. The row records the status and the `Location` header. The command sends no request to that address. A fault or a missing answer fails the row.
  - `unused-category`: a category that no kept engine serves. The row records the status and the number of hits. The status must be 200 or 400 and not a fault.
- The three connects, each from a throwaway pod of `probe_from_pod`:
  - A pod with a neutral label, not the label of a client, tries the ClusterIP of Service `searxng` on port 8080. It must be blocked.
  - A pod with the label `app.kubernetes.io/name=searxng` tries the metadata address and the ClusterIP of Service `roadmap-service`. Both must be blocked.
- Add `DEFAULT_SEARXNG_CHECK_LOCAL_PORT` to `src/devops_cli/config/defaults.py`, and the messages and help texts of the command, and a `--dry-run` request plan.
- Change the `k8s` row of `devops ci`: the check of `tests/gate/k8s_checks/devops_runtime.py` compares the full image of Deployment `searxng` with `SEARXNG_IMAGE`, so a bump of the digest fails the row until a person runs the command against the new image.
- `tests/invariants/test_k8s_searxng.py` takes the list of engines that must stay off from `devops_cli.k8s.searxng_check`, so the list exists once.
- Replace `tests/fixtures/searxng/search_reply.json` with a reply that the pinned image gave, saved by the Publish stage, and name the image next to it. A test holds the seven keys and the image.
- The command is a new command with a request plan, so the change carries a spec delta (`k8s-searxng-check`) and `skip_specs` is false. The command is not an MCP tool: it starts pods, so it is not read-only.
- Rollout of settings: the change removes, renames or tightens no setting. It adds no setting. `DEFAULT_SEARXNG_CATEGORIES` keeps `general,it,science`. The example ConfigMap and the live ConfigMap need no change, and `tests/config/test_k8s_devops_runtime.py` already loads the example ConfigMap into Settings.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `k8s-searxng-check`: The six requests, the judgment of a reply, the engines that stay off, the redirect rule, the NetworkPolicy peers, the throwaway pods, the pinned image and the report.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/commands/k8s/searxng_check.py` (new), `src/devops_cli/commands/k8s/__init__.py`, `src/devops_cli/k8s/searxng_check.py` (new), `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/config/defaults.py`
- Tests: `tests/k8s/test_searxng_check.py` (new), `tests/commands/k8s/test_k8s_searxng_check.py` (new), `tests/support/kubectl_calls.py`, `tests/commands/k8s/test_k8s_crawl4ai_check.py`, `tests/gate/k8s_checks/devops_runtime.py`, `tests/invariants/test_k8s_searxng.py`, `tests/ai/test_web_search_searxng.py`, `tests/fixtures/searxng/search_reply.json`, `tests/fixtures/searxng/search_reply_image.txt` (new)
- Documents: `k8s/README.md`, `docs/commands/k8s.md`, `docs/CLI_REFERENCE.md`, `README.md`

## Feasibility

The premise is that a command can reach the service, send the requests, and test the NetworkPolicy peers from pods. I checked each part on 2026-11-08 against the repository and the upstream source of the pinned image. Nothing ran against the cluster in the Tests stage.

- **The shared code exists.** #4108 is merged. `src/devops_cli/k8s/service_probe.py` holds `forward_service`, `probe_from_pod`, `plan_probe_from_pod`, `service_cluster_ip`, `PodTarget` and `PodProbeRow`, and none of them knows a service name. `src/devops_cli/k8s/crawl4ai_check.py` and its command are the shape to follow.
- **No command exists.** `git grep -n searxng-check -- src tests docs k8s README.md` finds no hit in the base commit. No open or merged pull request builds it.
- **The pinned image.** `k8s/devops/searxng/deployment.yaml:37` pins `docker.io/searxng/searxng:2026.10.23-629368e40@sha256:aecad882e86eeb022b76351c8dce4eb48d0cbb16a5f1691f77ea32c96d317502`. The probes of the Deployment use `/healthz`, so the forward waits on that route. Service `searxng` listens on 8080 in namespace `devops`.
- **The format rule.** `searx/webapp.py` at commit 629368e40 calls `flask.abort(403)` when the `format` is not in `settings['search']['formats']`. So a ConfigMap without `json` shows as a 403 on the JSON requests, and the report names `search.formats`.
- **The redirect.** `searx/webapp.py` line 687 returns `redirect(result_container.redirect_url)` for every output format. `searx/query.py` sets `redirect_url` for a known external bang (`!!`). A single `!x` selects an engine or category only when it is in the loaded engines and categories. So `!google` is plain text when the ConfigMap leaves `google` off. The client of `http_client` follows redirects by default (`options.setdefault("follow_redirects", True)`), so the command passes `follow_redirects=False`.
- **The unused category.** `parse_category_form` drops a category that is not loaded and falls back to `general`. So the request gives 200 and general hits, and the row records the status and the number of hits and asserts no error text. This was read from the source and not run.
- **The categories.** The engine files at commit 629368e40 give `duckduckgo` and `wikipedia` in `general`, `github`, `stackoverflow`, `askubuntu`, `superuser`, `mdn` and `docker hub` in `it`, and `arxiv` in `science`. So `DEFAULT_SEARXNG_CATEGORIES = "general,it,science"` is right, and the live rows hold it to the pinned image.
- **By hand on 2026-11-07** (comment on #3929): the roadmap-service pod reaches `searxng:8080` and gets 200, the crawl4ai pod does not, and `/search?format=json` returns the keys `answers`, `corrections`, `infoboxes`, `query`, `results`, `suggestions` and `unresponsive_engines`. The kept engines changed in #4121: `pypi` is removed, nine remain.
- **The NetworkPolicy.** `searxng-perimeter` allows ingress on 8080 from the pod label `roadmap-service` only, and egress to CoreDNS and to public port 443 with the private, shared, link-local and metadata ranges excepted. `kubectl port-forward` is not subject to policy, so the forward reaches the pod, and the pods of `probe_from_pod` test the policy.
- **Rate limit.** `k8s/README.md` records that the upstream sites suspend an engine after about 30 queries. The command sends six queries, so a person can run it several times a day.
- **Not run.** The Tests stage made no request to the cluster and started no pod. The Publish stage runs the command once through a port-forward, puts the result for each request and target role in a pull request comment, and saves the reply fixture.

## Existing Tool Considered

`kubectl` (Apache-2.0) covers the forward and the throwaway pod, and `devops_cli.http.entry` covers the requests; both are already wrapped in `service_probe.py`. No open, maintained tool checks a running SearXNG for its reply keys, its bang handling and its NetworkPolicy peers. An offline NetworkPolicy checker reads the policy document only (`tests/commands/k8s/test_k8s_network_policies.py` already does that). So the change builds one command and one module of rows, and reuses the shared probe module. Cost: about 250 lines, an estimated 40k tokens to write, an estimated 8k tokens for each later fix, an estimated 4k tokens a year to keep, and half a day of elapsed time. The change deletes one internal copy: the list of engines that must stay off in `tests/invariants/test_k8s_searxng.py`, which moves into the module.

## Dependencies

None. #4108 is merged.
