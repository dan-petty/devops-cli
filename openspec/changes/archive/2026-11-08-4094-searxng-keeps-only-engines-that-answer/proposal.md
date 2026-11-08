# Proposal

## Why

A live run of SearXNG on 2026-11-07 showed engine faults and two log lines (#4094). The engine `pypi` returns no hit for any query and gives no error. The engine `duckduckgo` timed out once. `duckduckgo` and `github` can refuse one address after many queries. The pod log has an ERROR and a WARNING that look like faults. The settings in `k8s/devops/searxng/configmap.yaml` keep `pypi`, so each search with the category `it` asks an engine that cannot answer. The README of `k8s/` says that the provider "cannot rely on it", but the settings still keep it.

## What Changes

- Remove the engine `pypi` from `keep_only` in `k8s/devops/searxng/configmap.yaml`. The nine other engines stay.
- Add `tests/fixtures/searxng/engines_that_never_answer.txt` with one line for each such engine (the name, the date and the reason), and a test that no kept engine is in it.
- Add a test that the list of engines in `k8s/README.md` equals `keep_only`. It passes before the change and fails when one changes without the other.
- Add a comment to the ConfigMap file that names the source file and the reason of the ERROR "X-Forwarded-For nor X-Real-IP header is set!" and of the WARNING "missing config file: /etc/searxng/limiter.toml". Both are harmless with the limiter off. Mount no `limiter.toml`.
- Keep `outgoing.request_timeout` at 5.0 and add no `timeout` for an engine. The measure in Feasibility shows no timeout of `duckduckgo` in 30 queries.
- Keep `duckduckgo` and `github`, accept the suspension that SearXNG applies, and add no retry loop. The web search chain (`searxng`, `duckduckgo`, `firecrawl`) does not change.
- Update the engine list and the `pypi` sentence in the README of `k8s/`.
- The change carries a spec delta, because the engine list of the ConfigMap is a manifest that a consumer observes. It MODIFIES the requirement "The settings keep only engines that need no key" and ADDS the requirement for the comment on the log lines.
- No Settings key, no field of `k8s/devops/configmap.example.yaml` and no key of the live ConfigMap `devops-cli-config` is removed, renamed or tightened. Only the list `keep_only` of the ConfigMap `searxng-settings` gets shorter, and no code reads that list. So the rollout needs no test that loads the example ConfigMap into Settings.
- The change fits one pull request. It applies nothing to the cluster. The next sync of Argo CD applies the new ConfigMap, and a person restarts `deployment/searxng` to read it.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `searxng-service`: The settings keep nine engines and no engine that never answers. A comment in the ConfigMap file explains the two harmless log lines.

## Impact

- Code: none under `src/`.
- Manifests: `k8s/devops/searxng/configmap.yaml`
- Documents: `k8s/README.md`
- Tests: `tests/invariants/test_k8s_searxng.py`, `tests/fixtures/searxng/engines_that_never_answer.txt`

## Feasibility

All checks used the live service `svc/searxng` in namespace `devops` through `kubectl port-forward` with read-only queries, the pinned image `searxng/searxng:2026.10.23-629368e40`, and the source in that image. The live ConfigMap equals `k8s/devops/searxng/configmap.yaml`. Nothing was applied.

- `pypi` (confirmed). A query with `engines=pypi` returned 0 hits, no `unresponsive_engines` entry and no error. In 10 queries of `general,it,science`, `pypi` gave no hit in any query, while `duckduckgo`, `github`, `stackoverflow`, `mdn`, `docker hub` and `arxiv` answered. The engine has `timeout` 5.0 and reads the HTML of `https://pypi.org/search/`, and that site serves a "Client Challenge" page to a scraper (3,038 bytes, no `package-snippet` element), so a longer timeout does not help.
- `duckduckgo` timeout (not reproduced). 20 queries with `engines=duckduckgo` at `request_timeout` 5.0, 5 seconds apart: 19 answered with 9 or 10 hits in 0.56 to 0.87 seconds, 1 returned a CAPTCHA (the first query), 0 timed out. 10 queries of `general,it,science`: 0 unresponsive engines, 67 to 93 hits, 0.92 to 1.53 seconds. A value above 5.0 cannot be measured on the live service: the query parameter `timeout_limit` can only lower the timeout (`min(default_timeout, query_timeout)` in `searx/search/__init__.py`, and the settings set no `max_request_timeout`), and a higher `request_timeout` needs an apply. The page `/stats/errors` shows timeouts on many engines (`arxiv`, `askubuntu`, `stackoverflow`, `superuser`, `mdn`, `pypi`, `duckduckgo`), so the cause is a slow upstream and not one engine. The 95th percentile of successful requests is 2.9 seconds for `duckduckgo`, and 4.2 to 4.7 seconds for `arxiv`, `github`, `mdn` and the Stack Exchange sites. A limit below 5.0 would cut answers, and the evidence gives no reason to raise it. The timeout of 2026-11-07 was one event.
- Rate limits (decided). In the pinned source, `searx/engines/duckduckgo.py` (lines 419 and 477) raises the CAPTCHA with `suspended_time=0`, so SearXNG never suspends the engine and the next query asks again (1 CAPTCHA in 30 queries). `searx/settings_defaults.py` sets the suspension times: access denied 86400 s, CAPTCHA 86400 s, too many requests 3600 s. `github` gave 17 to 30 hits in 10 of 10 combined queries from the cluster address. Decision: keep both engines and accept the suspension. A suspended engine does not slow the search, because SearXNG skips it for the time of the suspension. The limit of about 30 queries was not tested again, because it would suspend `github` for hours.
- Log lines (harmless). The ERROR comes from `log_error_only_once` in `searx/botdetection/trusted_proxies.py`: the middleware logs it once, when a request has neither header, and the roadmap Service sends none. With `server.limiter: false` no code uses the client address. The WARNING comes from `Config.from_toml` in `searx/botdetection/config.py`: `limiter.initialize` calls `get_cfg()` even with the limiter off, and a missing file leaves the defaults of the schema.
- The chain test `uv run devops ci test tests/ai/test_web_search_searxng.py -k unresponsive` exists and passes on `main`.
- No open or merged pull request does this work. #3924, #3927, #3980 and #4033 delivered SearXNG, and #3929 is the live check, which this change does not touch.
- First check of the plan: `uv run devops ci fail-to-pass --base origin/main` shows `test_the_settings_keep_no_engine_that_never_answers`, `test_the_settings_keep_only_engines_that_need_no_key` and `test_the_configmap_says_why_the_two_log_lines_of_the_start_are_harmless` failing on the base.

## Existing Tool Considered

SearXNG covers the need with its own settings: `use_default_settings.engines.keep_only`, `outgoing.request_timeout`, the `timeout` of an engine, and the suspension of a failed engine. No other tool is needed. A different metasearch service was not considered, because #3924 put SearXNG in the stack. The change builds no code. It removes one list entry, adds one comment and two small tests. To build it costs about 40k tokens, about 2k tokens a month to keep (one fixture file with a reason for each dropped engine), and about 1.5 hours of elapsed time, most of it for the measure. The change deletes one entry of `keep_only`, one name in the README, and no internal code.
