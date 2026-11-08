# Design

## Decisions

- **Remove `pypi` from `keep_only` and keep a fixture file of engines that never answer.**: The engine returned no hit in 10 of 10 live queries and in a query that asked only for it, and `pypi.org` serves a Client Challenge page to a scraper. The fixture file holds the date and the reason of each dropped engine, and a test refuses to keep a name from it, so a later edit cannot bring the engine back without a new measure.
- **Keep `outgoing.request_timeout` at 5.0 and add no `timeout` for an engine.**: 30 live queries gave no `duckduckgo` timeout, and the 95th percentile of the slowest successful engines is 4.7 seconds. The existing test already holds the value 5.0 and an empty `engines` list.
- **Keep `duckduckgo` and `github` and accept the suspension.**: In the pinned source `duckduckgo` raises its CAPTCHA with `suspended_time=0`, so SearXNG asks again on the next query, and `github` answered 10 of 10 combined queries. SearXNG skips a suspended engine, so the search does not wait for it.
- **Name the source file and the reason of each log line in a comment of the ConfigMap file, outside the `settings.yml` text.**: The existing test reads the text of `settings.yml` for `secret_key` and `@`, so the comment sits above `apiVersion`. A test reads the file and asserts that the comment names both source files and the word "harmless".
- **Compare the README sentence with `keep_only` by the names in backticks.**: The sentence is the one list of engines in the README. A test that reads the names of that sentence fails when one list changes and the other does not.

## Rejected alternatives

- **Raise `request_timeout` or set a `timeout` on `duckduckgo`.**: 20 queries at 5.0 gave 0 timeouts, so there is no fault to remove. A higher value cannot be measured on the live service: `searx/search/__init__.py` takes `min(default_timeout, query_timeout)` and the settings set no `max_request_timeout`. A higher value also makes every search wait longer for a slow engine.
- **Remove `duckduckgo` or `github` because of the rate limits.**: The measure found 1 CAPTCHA in 30 queries for `duckduckgo` and 0 refusals for `github`. The engines are the main `general` and `it` sources, and SearXNG suspends a refusing engine by itself.
- **Add a retry loop for a suspended engine.**: The issue forbids it, and a retry asks the refusing site again and extends the suspension.
- **Mount a `limiter.toml` to hide the WARNING.**: The file would add a mount, a ConfigMap key and a test for a line that has no effect. A comment gives the reader the reason at no run-time cost.
- **Set `botdetection.trusted_proxies` or send an `X-Forwarded-For` header to hide the ERROR.**: The limiter is off and no code uses the client address. The roadmap Service would need a header only to silence one line that SearXNG logs once at start.
