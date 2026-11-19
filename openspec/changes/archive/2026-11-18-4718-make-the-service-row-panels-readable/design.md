# Design

## Decisions
- Use the standard "Signal: measure" format for all panel titles.
- Set units on every panel (for example `/h`, `s`, `short`, `currencyUSD`, and `percentunit`).
- Use `$__rate_interval` with `rate()` for rate panels and `$__range` with `increase()` for range gauges.
- Avoid using `$__range` inside time series queries.
- Keep default Grafana color schemes without custom threshold colors.
- Maintain existing declared service metrics in dashboard queries.

## Rejected alternatives
- Raw counter panels without rate calculations: Rejected because cumulative counters do not show current activity.
- Custom color palettes: Rejected because standard Grafana palettes ensure consistent visual contrast.
