# Proposal

## Why

Issue #1420: the spend path of one model request loads the settings more than once. `track_request_spend` prices each request with `PricingRegistry.calculate_request_cost`, which asks `is_local` whether the call ran on local hardware. For a host that its address and its name do not decide, `_is_local_host` asked `_is_configured_cluster_host` and `_is_configured_ai_server_host`, and each of them called `load_settings`. A gateway call with no server also called it in `_is_local_gateway_configured`, and then again for the gateway URL.

## What Changes

- One call of `is_local` loads the settings at most once. A small holder, `_SettingsOnce`, loads them on first use and keeps them for the rest of the call. `is_local` makes one holder and passes it to `_is_local_server`, `_is_single_server_local`, `_is_local_host` and `_is_local_gateway_configured`.
- `_is_configured_cluster_host` and `_is_configured_ai_server_host` take the loaded `Settings`. They load nothing.
- A host that its address or its name decides (a loopback or private address, or a name that is not a public DNS name) loads nothing, as before.
- When the settings cannot load, no configured host counts as local, as before. The three broad `except Exception` blocks that did this in each helper become one, in `_SettingsOnce`, so the swallowed-failures ceiling of `pricing.py` falls from 7 to 4.
- Each request still loads the settings once, so a change to `config.yaml` takes effect at the next request. There is no process-wide cache of the configured hosts.
- No behavior that a consumer observes changes: the same hosts are local, and spend records do not change. So the change has no spec delta and sets `skip_specs: true`.
- This change fits one pull request.

## Impact

- `src/devops_cli/ai/spend/pricing.py`.
- `tests/test_ai_spend_pricing.py`, and `tests/fixtures/swallowed_failures_ceilings.json`.

## Feasibility

Measured on `origin/main` 4f7390ac with a profile hook (`sys.setprofile`) that counts calls of `load_settings`. No devops-cli name is patched, as `docs/TESTING.md` requires. Each count is for one request after the first, because the first request of a process also builds the tracer, which loads the settings twice.

| Request through `track_request_spend` | Before | After |
| :--- | ---: | ---: |
| Hosted provider (`openai`, `https://api.openai.com/v1`) | 2 | 1 |
| Gateway call that a hosted backend served | 2 | 1 |
| Gateway call with no server | 3 | 1 |
| Two hosted servers in one server field | 2 | 1 |
| Local provider (`ollama`) | 0 | 0 |

Five chat requests through `LLMClient` with the gateway faked at the HTTP edge loaded the settings 10 times before and 5 times after. Every load came from the spend path; the client loads none for a request. One `load_settings` call takes about 4.4 ms on this host (the configuration files are cached by their stamp, so the cost is the build and validation of `Settings`). The change saves about 4.4 ms for each hosted request and about 8.8 ms for a gateway call with no server.

The issue also proposed one ledger connection for each process. Measured on the same host: opening a connection with its pragmas takes 0.58 ms, and `SpendLedger.record_request` takes 14.6 ms, nearly all in the insert and its commit. A shared connection would save 0.58 ms for each request and needs a lock across the threads that record spend concurrently, so the change leaves the connection for each record as it is (see Rejected alternatives in `design.md`).

The issue's first criterion asks for a count at the settings-file read. Since the configuration files are cached by their stamp (`_config_layers`), a request reads no file, so the change counts `load_settings` calls instead, which is what still costs time.

## Existing Tool Considered

`functools.cached_property` from the standard library holds the settings for one call. No other tool applies: the change removes repeated work in our own code. The change deletes the separate `load_settings` calls and their `except Exception` blocks in `_is_configured_cluster_host`, `_is_configured_ai_server_host` and `_is_local_gateway_configured`.
