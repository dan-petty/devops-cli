# Proposal

## Why

Issue #2431 is part 4 of the split of #1381. The sandbox package resolves some host names two times, and it resolves other names outside `vet_addresses`, the one resolve-and-check function of `devops_cli.http.egress`.

| Caller | Check before | Check after | Level |
| :--- | :--- | :--- | :--- |
| Metrics scrape, `scrape_prometheus_metrics` | a pre-flight `validate_url_egress` in `_validate_scrape_url`, then the factory client | the factory client only; the scheme and host check stays | loopback |
| Public whitelist builder, `_resolve_public_dns` | `socket.getaddrinfo`, and its own classification of the answers | `vet_addresses` | public |
| Local whitelist builder, `_resolve_local_dns` | `socket.getaddrinfo`, and its own classification of the answers | `vet_addresses`, then the rule of the builder: each address is private or loopback, and not link-local | private, then private or loopback only |
| Public whitelist validator, `_validate_public_whitelist_item` | `is_loopback_or_private_host(host, resolve_dns=True)`, which resolves the name | `resolve_dns=False`: no lookup | no lookup |

`ai.allow_private_network` changes none of these levels.

## What Changes

- The metrics scrape loses its pre-flight address check. The factory client resolves the host one time, at the connect, at the loopback level. The scrape still refuses a URL whose scheme is not http or https, or that names no host.
- The public and local whitelist builders resolve each name with `vet_addresses`, at the port of the whitelist entry. So they also refuse a cloud metadata name before the lookup, and a scoped IPv6 answer. Each builder names its time-of-check gap in its docstring.
- The public whitelist validator makes no lookup. The policy builder makes the one lookup of each name, and refuses a name that answers a non-public address.
- A refusal of a whitelist builder is a `SandboxValidationError` that names the host. A refusal of `vet_addresses` is its cause. `devops sandbox network-policy` exits 1 and prints no policy, as before.
- `README.md` names the sandbox metrics scrape among the clients that the factory builds. The general statement that every HTTP client is checked at the connect waits for part 5 (#2437).
- A consumer sees the lookups, the levels and the refusals, so the change carries a spec delta. It creates the capability `sandbox-egress`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `sandbox-egress`: the level of the sandbox metrics scrape, its one lookup, the one lookup of each whitelist name of the NetworkPolicy, and the answers that each whitelist admits.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/sandbox/metrics.py`, `src/devops_cli/sandbox/models.py`.
- `tests/test_http_egress.py`, `tests/test_sandbox_metrics.py`, `tests/test_sandbox_networking.py`, and the tests that call the whitelist builders directly (`tests/test_sandbox_policy_properties.py`, `tests/test_validation.py`).
- `README.md`.

## Feasibility

- On `origin/main` at `daaffc62`, `rg -n 'validate_url_egress|validate_service_url|validate_configured_service_url|validate_url\(|_resolve_host_ips|resolve_dns=True|socket\.getaddrinfo' src/devops_cli/sandbox` printed the five lines of the issue: `metrics.py:16`, `metrics.py:351`, `models.py:159`, `models.py:237` and `models.py:274`.
- The new tests ran on that commit with `ScriptedResolver` and `ConnectRecorder` from `tests/web_fakes.py`. A scrape of `http://example.com:9100/metrics` made 2 lookups of `example.com`. A public whitelist policy for `example.com` and `example.org:8443` made 2 lookups of each name. The row of the metrics scrape in `test_each_caller_dials_at_its_level` found the public level, not the loopback level: the pre-flight check refused the loopback answer that the factory client admits. The public builder admitted the scoped answer `2606:4700::1%2`, which `vet_addresses` refuses. `uv run devops ci fail-to-pass --base origin/main` replayed the new and changed tests on that commit: 24 failed there and pass on the branch.
- `vet_addresses(host, port, level)` in `src/devops_cli/http/egress.py` refuses a cloud metadata name before the lookup. It refuses a cloud metadata answer, a scoped IPv6 answer and an answer that the level does not admit with `SSRFBlockedError`, which is a `ValueError`. A failed lookup raises `httpcore2.ConnectError`, which is not a `ValueError`, so the builders change it into a `SandboxValidationError`.
- `_build_whitelist_egress` has the port of each entry from `_parse_whitelist_entry`, so the builders can give `vet_addresses` its port.
- `to_k8s_network_policy` has one caller in `src`, `devops sandbox network-policy`, which catches `ValueError` and `SandboxValidationError`. `SandboxValidationError` is a `ValueError`.

## Existing Tool Considered

The change uses the resolve-and-check function of #898 (`vet_addresses` in `devops_cli.http.egress`) and the egress-checked factory client that the scrape already has. Both are built on the httpcore2 network backend API and the address predicates of pydantic-ai. The change builds no new check. It deletes these internal paths: the pre-flight `validate_url_egress` call of the scrape and its loopback shortcut, the two direct `socket.getaddrinfo` calls of the whitelist builders and their own classification of the answers, and the DNS lookup of the public whitelist validator.
